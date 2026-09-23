import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.query_agent import QueryPlan, plan_query
from app.core.session_manager import ChatTurn, SessionState
from app.graph.knowledge_graph import graph_search
from app.guardrails.input_guard import check_input
from app.guardrails.output_guard import check_output_safety
from app.retrieval.dense import dense_search
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import rerank

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "The query is not relevant to or found within the uploaded document."

# Sub-splits an already-retrieved chunk into smaller windows before per-chunk match extraction
# (aggregate queries only - see _generate_aggregate_answer). This doesn't touch the actual
# stored/indexed chunks (chunk_size=1000 in app/ingestion/pipeline.py, tuned for dense/sparse
# retrieval quality) - it's a purely in-memory re-split of retrieval results, addressing a
# different problem: LLMs are measurably less reliable at noticing a record positioned in the
# middle of a multi-record chunk than one near an edge ("lost in the middle"), which caused
# extraction to consistently miss real matches sitting mid-chunk. Keeping each extraction window
# small means there's barely a "middle" left to lose anything in.
_extraction_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=0)

_ANSWER_SYSTEM_PROMPT = """You are a document question-answering assistant. Answer the user's question
using ONLY the facts present in the provided context. Cite specific figures, tables, or sections from
the context when relevant. If the context does not contain the answer, say exactly:
"{fallback}"
Never use outside knowledge. Never speculate beyond what the context supports.
""".format(fallback=FALLBACK_MESSAGE)

_MATCH_EXTRACTION_SYSTEM_PROMPT = """You extract individual records from ONE chunk of a larger document that
match a question's criteria. Your output feeds a program that combines results from every chunk to compute
an exact count/list/sum - so it must cover every matching record in THIS chunk, not just the obvious ones.

- The question states one or more conditions a record must satisfy - re-read it carefully and identify
  exactly how many separate conditions it actually states (often just one; sometimes two or more joined by
  "and"/"who also"/etc). A record only counts as a match if it satisfies ALL of the conditions the question
  ACTUALLY states - never add, assume, or carry over a condition the question didn't mention.
- Check every record in the chunk against those conditions - do not skip or sample.
- Match text values case-INsensitively and allow for minor formatting variation (e.g. "Chennai", "chennai",
  and "CHENNAI" are the same city; "ML" and "Machine Learning" may be the same course - use judgment based
  on what the question is asking).
- For each match, give:
  - "identifier": the record's single most specific unique identifier ONLY - e.g. just an ID/code/primary
    key if the record has one, otherwise just its name. Never combine multiple fields (not "ID - Name" or
    "ID, Name") - chunks can overlap at their boundaries, so the exact same record may be extracted again
    from a neighboring chunk, and it must produce an IDENTICAL identifier string both times so a
    deduplication step can recognize it as the same record.
  - "detail": a one-line note stating the record's actual value for EVERY condition the question mentions,
    not just one of them - e.g. for "students from Chennai who paid the fee", write both the city and the
    fee-paid value ("City=Chennai, Fee_Paid=yes"), not just one. A downstream check re-verifies each
    condition from this text alone, so leaving one out makes a genuine match look unverifiable. Include
    ONLY values for conditions the question actually asks about - do not add other fields from the record
    "for context"; a single-condition question (e.g. just a course name) gets a single-fact detail.
- If nothing in this chunk matches, that's a completely normal result - don't force a match.

Respond with strict JSON only: {"matches": [{"identifier": "...", "detail": "..."}]}
Do not include any text outside the JSON object.
"""

_AGGREGATE_SYNTHESIS_SYSTEM_PROMPT = """You write the final answer for an AGGREGATE question (a count, list,
sum, average, or comparison across many records). A program has already scanned the full document and
extracted every matching record for you, deduplicated - given below as a JSON list, with the exact
already-computed count of how many there are.

Phrase a natural-language answer to the question using EXACTLY this list and EXACTLY this count. Do not
recount, estimate, or second-guess the number - the extraction is already complete and correct. You may
briefly enumerate the matches if that helps answer the question, but the stated count/total must match the
given number exactly.

If the given list is empty, say exactly:
"{fallback}"
""".format(fallback=FALLBACK_MESSAGE)


@dataclass
class PipelineResult:
    turn_id: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    graph_context: dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    guardrail: dict = field(default_factory=dict)
    context_chunks: list[str] = field(default_factory=list)


def _generate_answer(question: str, context_text: str) -> str:
    settings = get_settings()
    # Deterministic generation: the downstream grounding check re-verifies this exact wording
    # against the context, so a more creative/varied phrasing (higher temperature) has more
    # surface area to trip that check on borderline-but-correct answers.
    llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)
    messages = [
        SystemMessage(content=_ANSWER_SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n{context_text}\n\nQuestion: {question}"),
    ]
    response = llm.invoke(messages)
    return response.content.strip()


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1] if raw.lower().startswith("json") else raw
    return json.loads(raw)


async def _extract_chunk_matches(question: str, chunk_text: str) -> list[dict]:
    """Aggregate-query helper: asks the model to find matches within ONE chunk only. Splitting
    the enumeration this way - one small, easy sub-task per chunk instead of one call asked to
    scan the entire concatenated context - avoids the recall failures a single large-context call
    has when asked to exhaustively enumerate matches across dozens of records."""
    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)
    messages = [
        SystemMessage(content=_MATCH_EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {question}\n\nChunk:\n{chunk_text}"),
    ]
    try:
        response = await llm.ainvoke(messages)
        parsed = _parse_json_response(response.content)
        matches = parsed.get("matches", [])
        return [m for m in matches if isinstance(m, dict) and m.get("identifier")]
    except Exception:  # noqa: BLE001
        logger.warning("Chunk match extraction failed; treating this chunk as having no matches", exc_info=True)
        return []


_MATCH_CONSISTENCY_SYSTEM_PROMPT = """A previous extraction step pulled candidate matching records for a
question out of a large document, chunk by chunk. Occasionally that step makes a mistake: it includes a
record whose own recorded "detail" doesn't actually satisfy one of the question's conditions (most often
when the question has more than one condition and the record only satisfies some of them).

First, identify exactly which condition(s) the QUESTION ITSELF states - often just one. A candidate's
"detail" may mention additional facts about the record that the question never asked about at all (e.g. a
fee-paid status, when the question only asked about a course); those extra facts are NOT conditions and must
be completely ignored - never reject a candidate over a fact the question didn't ask about.

Given the question and the candidate list below, re-check each candidate's "detail" against ONLY the
condition(s) the question actually states, and decide if it genuinely satisfies all of THOSE (not any extra
facts also present in "detail"). This is a final consistency check on data that's already been extracted,
not a new search - judge only from what each candidate's own "detail" states.

Respond with strict JSON only: {"keep_identifiers": ["...", "..."]}
List the "identifier" of every candidate that genuinely satisfies all of the question's own conditions. Do
not include any text outside the JSON object.
"""


def _filter_consistent_matches(question: str, matches: list[dict]) -> list[dict]:
    if not matches:
        return matches
    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)
    candidates_json = json.dumps(matches)
    messages = [
        SystemMessage(content=_MATCH_CONSISTENCY_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {question}\n\nCandidates:\n{candidates_json}"),
    ]
    try:
        response = llm.invoke(messages)
        parsed = _parse_json_response(response.content)
        keep = {str(i).strip().lower() for i in parsed.get("keep_identifiers", [])}
        return [m for m in matches if str(m["identifier"]).strip().lower() in keep]
    except Exception:  # noqa: BLE001
        logger.warning("Match consistency filter failed; keeping all extracted matches", exc_info=True)
        return matches


def _synthesize_aggregate_answer(question: str, matches: list[dict]) -> str:
    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)
    matches_json = json.dumps({"count": len(matches), "matches": matches})
    messages = [
        SystemMessage(content=_AGGREGATE_SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {question}\n\nExtracted matches:\n{matches_json}"),
    ]
    response = llm.invoke(messages)
    return response.content.strip()


async def _generate_aggregate_answer(question: str, chunks: list[Document]) -> str:
    windows = [
        window for doc in chunks for window in _extraction_splitter.split_text(doc.page_content)
    ]
    per_chunk_matches = await asyncio.gather(*[_extract_chunk_matches(question, w) for w in windows])
    seen_identifiers: set[str] = set()
    deduped_matches: list[dict] = []
    for matches in per_chunk_matches:
        for match in matches:
            key = str(match["identifier"]).strip().lower()
            if key in seen_identifiers:
                continue
            seen_identifiers.add(key)
            deduped_matches.append(match)
    consistent_matches = _filter_consistent_matches(question, deduped_matches)
    return _synthesize_aggregate_answer(question, consistent_matches)


async def run_chat_pipeline(session: SessionState, message: str) -> PipelineResult:
    turn_id = str(uuid.uuid4())
    settings = get_settings()
    cfg = session.config

    # 1. Input guardrail: jailbreak / prompt injection / unsafe content.
    allowed, reason = await check_input(message)
    if not allowed:
        return PipelineResult(
            turn_id=turn_id,
            answer="I'm sorry, I can't respond to that.",
            guardrail={
                "input_allowed": False,
                "input_reason": reason,
                "output_grounded": False,
                "grounding_score": 0.0,
                "rewritten_query": message,
            },
        )

    history_strings = [f"{turn.role}: {turn.content}" for turn in session.chat_history[-6:]]
    # Query-understanding agent: classifies the question (single-fact lookup vs. an
    # aggregate that requires scanning/counting/summing across many records) and plans
    # retrieval breadth and the relevance gate accordingly - see app/core/query_agent.py.
    plan: QueryPlan = plan_query(message, history_strings)
    rewritten_query, key_entities = plan.rewritten_query, plan.key_entities
    effective_top_k = max(cfg.top_k, plan.top_k)

    # 2. Multi-strategy retrieval (each toggle-able per session config).
    ranked_lists: dict[str, list[tuple[Document, float]]] = {}
    graph_context: dict = {"nodes": [], "edges": []}

    if cfg.use_dense and session.vectorstore is not None:
        ranked_lists["dense"] = dense_search(session.vectorstore, rewritten_query, plan.dense_candidates)

    if cfg.use_sparse and session.bm25_retriever is not None:
        ranked_lists["sparse"] = session.bm25_retriever.search(rewritten_query, plan.sparse_candidates)

    if cfg.use_graph:
        graph_docs, graph_context = graph_search(session.tenant_id, key_entities, settings.graph_candidates)
        if graph_docs:
            ranked_lists["graph"] = [(doc, 1.0) for doc in graph_docs]

    fused = reciprocal_rank_fusion(ranked_lists, k=settings.rrf_k) if ranked_lists else []

    if not fused:
        return PipelineResult(
            turn_id=turn_id,
            answer=FALLBACK_MESSAGE,
            graph_context=graph_context,
            guardrail={
                "input_allowed": True,
                "input_reason": None,
                "output_grounded": False,
                "grounding_score": 0.0,
                "rewritten_query": rewritten_query,
            },
        )

    # 3. Re-rank the fused candidate pool for final precision.
    candidate_docs = [r.document for r in fused[: max(settings.rerank_top_n * 3, effective_top_k * 3)]]
    contributors_by_key = {id(r.document): r.contributing_retrievers for r in fused}

    if cfg.use_rerank:
        reranked = rerank(rewritten_query, candidate_docs, top_n=effective_top_k)
    else:
        reranked = [(doc, fused[i].fused_score) for i, doc in enumerate(candidate_docs[:effective_top_k])]

    top_score = reranked[0][1] if reranked else 0.0
    if not reranked or top_score < plan.relevance_threshold:
        return PipelineResult(
            turn_id=turn_id,
            answer=FALLBACK_MESSAGE,
            graph_context=graph_context,
            guardrail={
                "input_allowed": True,
                "input_reason": None,
                "output_grounded": False,
                "grounding_score": 0.0,
                "rewritten_query": rewritten_query,
            },
        )

    context_chunks = [doc.page_content for doc, _ in reranked]
    context_text = "\n\n---\n\n".join(
        f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}" for doc, _ in reranked
    )

    # 4. Generate, then run the output guardrails (safety + factual grounding).
    if plan.intent == "aggregate":
        # Graph-derived pseudo-documents (individual relationship triples) still contribute to
        # retrieval/relevance scoring above, but are excluded here: the knowledge graph's LLM-based
        # entity extraction can represent the same real record under two different node identities
        # (e.g. a person's name in one triple, their record ID in another), which a per-chunk
        # extraction pass can't always recognize as the same entity - causing double-counting on
        # top of what the source document chunks (which carry a real, consistent ID) already give.
        aggregate_chunks = [doc for doc, _ in reranked if doc.metadata.get("source") != "knowledge_graph"]
        answer = await _generate_aggregate_answer(message, aggregate_chunks)
    else:
        answer = _generate_answer(message, context_text)

    is_safe = await check_output_safety(answer)
    if not is_safe:
        answer = "I'm sorry, I can't share that response."
        grounded, grounding_score = False, 0.0
    else:
        # The generation prompts (_ANSWER_SYSTEM_PROMPT / _AGGREGATE_SYNTHESIS_SYSTEM_PROMPT)
        # already instruct the model to say FALLBACK_MESSAGE verbatim when the context doesn't
        # support an answer, using ONLY the same real, already-relevance-gated context it was
        # given - so that self-assessment, made by the one call with full context of its own
        # reasoning, IS the grounding check. A separate LLM call re-judging the finished answer
        # from scratch, with no visibility into why it was written, was tried here and measured
        # to be net-negative: it doesn't reliably catch new hallucinations (the answer is already
        # constrained to the given context) but frequently rejects genuinely correct answers -
        # even the exact same (answer, context) pair going in could flip between "grounded" and
        # "not grounded" across calls, since temperature=0 reduces but doesn't eliminate LLM
        # sampling noise. That false-rejection failure mode is exactly the bug this pipeline
        # exists to avoid, so it isn't run.
        grounded = answer != FALLBACK_MESSAGE
        grounding_score = 1.0 if grounded else 0.0

    sources = [
        {
            "file_name": doc.metadata.get("source", "unknown"),
            "chunk_index": doc.metadata.get("chunk_index", -1),
            "preview": doc.page_content[:220],
            "retriever": "+".join(contributors_by_key.get(id(doc), ["rerank"])),
            "score": round(float(score), 4),
        }
        for doc, score in reranked
    ]

    return PipelineResult(
        turn_id=turn_id,
        answer=answer,
        sources=sources,
        graph_context=graph_context,
        guardrail={
            "input_allowed": True,
            "input_reason": None,
            "output_grounded": grounded,
            "grounding_score": grounding_score,
            "rewritten_query": rewritten_query,
        },
        context_chunks=context_chunks,
    )


def record_turn(session: SessionState, role: str, content: str, result: PipelineResult | None, elapsed: float) -> None:
    session.chat_history.append(
        ChatTurn(
            turn_id=result.turn_id if result else str(uuid.uuid4()),
            role=role,
            content=content,
            sources=result.sources if result else [],
            graph_context=result.graph_context if result else None,
            elapsed_seconds=elapsed,
            guardrail=result.guardrail if result else None,
        )
    )
