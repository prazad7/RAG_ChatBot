import hashlib
from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass
class FusedResult:
    document: Document
    fused_score: float
    contributing_retrievers: list[str]


def _doc_key(doc: Document) -> str:
    source = doc.metadata.get("source", "")
    chunk_index = doc.metadata.get("chunk_index")
    if chunk_index is not None:
        return f"{source}::{chunk_index}"
    return hashlib.sha1(doc.page_content.encode("utf-8")).hexdigest()


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[tuple[Document, float]]],
    k: int = 60,
) -> list[FusedResult]:
    """Combines ranked lists from dense / sparse / graph retrievers via Reciprocal Rank Fusion.

    RRF score for a document = sum over each retriever it appears in of 1 / (k + rank),
    where `rank` is its 1-indexed position in that retriever's ranked list. This favors
    documents that multiple retrieval strategies agree on, without needing to normalize
    each retriever's raw similarity scale against the others.
    """
    scores: dict[str, float] = {}
    documents: dict[str, Document] = {}
    contributors: dict[str, set[str]] = {}

    for retriever_name, ranked in ranked_lists.items():
        for rank, (doc, _raw_score) in enumerate(ranked, start=1):
            key = _doc_key(doc)
            documents[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            contributors.setdefault(key, set()).add(retriever_name)

    fused = [
        FusedResult(document=documents[key], fused_score=score, contributing_retrievers=sorted(contributors[key]))
        for key, score in scores.items()
    ]
    fused.sort(key=lambda r: r.fused_score, reverse=True)
    return fused
