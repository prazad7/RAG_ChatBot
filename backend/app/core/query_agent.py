import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

QueryIntent = Literal["lookup", "aggregate"]

_SYSTEM_PROMPT = """You are the query-understanding stage of a document retrieval pipeline. You read the
user's question (and recent chat history for context) and decide how the pipeline should retrieve for it.

Classify "intent" as one of:
- "aggregate": answering requires scanning across MANY individual records or occurrences in the document and
  combining them - counting ("how many students are from Chennai"), listing all matches ("which employees
  are on the Mumbai team"), summing/averaging ("what is the total revenue across all regions"), or comparing
  across records ("which product had the most returns"). A single chunk is unlikely to contain the whole
  answer; the pipeline needs to cast a much wider net.
- "lookup": the question is answerable from one passage or fact once it's found (a definition, a single
  figure, a specific named entity's value, a yes/no).

Also produce a rewritten, information-dense search query that surfaces the concrete facts/entities/numbers
likely needed, expanding indirect or conversational phrasing into the vocabulary the source document would
actually use. And a short list (0-5) of key named entities/terms worth looking up directly in a knowledge
graph.

Respond with strict JSON: {"intent": "lookup"|"aggregate", "rewritten_query": "...", "key_entities": ["...", "..."]}
Do not include any text outside the JSON object.
"""


@dataclass
class QueryPlan:
    intent: QueryIntent
    rewritten_query: str
    key_entities: list[str] = field(default_factory=list)
    dense_candidates: int = 0
    sparse_candidates: int = 0
    top_k: int = 0
    relevance_threshold: float = 0.0


def _plan_for_intent(intent: QueryIntent, rewritten_query: str, key_entities: list[str]) -> QueryPlan:
    settings = get_settings()
    if intent == "aggregate":
        return QueryPlan(
            intent=intent,
            rewritten_query=rewritten_query,
            key_entities=key_entities,
            dense_candidates=settings.aggregate_dense_candidates,
            sparse_candidates=settings.aggregate_sparse_candidates,
            top_k=settings.aggregate_top_k,
            relevance_threshold=settings.aggregate_relevance_threshold,
        )
    return QueryPlan(
        intent="lookup",
        rewritten_query=rewritten_query,
        key_entities=key_entities,
        dense_candidates=settings.dense_candidates,
        sparse_candidates=settings.sparse_candidates,
        top_k=settings.default_top_k,
        relevance_threshold=settings.relevance_threshold,
    )


def plan_query(question: str, chat_history: list[str]) -> QueryPlan:
    """Understands the user's question and plans how the retrieval pipeline should handle it -
    in particular, detects aggregate questions (counts/lists/sums spanning many records) that need
    a much wider retrieval net and a looser relevance gate than a single-fact lookup, since any one
    matching record scores low on its own against a "how many..." style query."""
    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)

    history_snippet = "\n".join(chat_history[-6:])
    user_content = f"Recent conversation:\n{history_snippet}\n\nUser question: {question}"

    try:
        response = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_content)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.split("\n", 1)[-1] if raw.lower().startswith("json") else raw
        parsed = json.loads(raw)
        intent: QueryIntent = "aggregate" if parsed.get("intent") == "aggregate" else "lookup"
        rewritten = parsed.get("rewritten_query") or question
        entities = [str(e) for e in (parsed.get("key_entities") or [])][:5]
        return _plan_for_intent(intent, rewritten, entities)
    except Exception:  # noqa: BLE001
        logger.warning("Query planning failed, falling back to a plain lookup over the original question", exc_info=True)
        return _plan_for_intent("lookup", question, [])
