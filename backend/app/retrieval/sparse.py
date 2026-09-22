import re

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class SparseIndex:
    """BM25-based sparse retriever, built fresh per session over that session's chunks only."""

    def __init__(self, documents: list[Document]):
        self.documents = documents
        self._corpus_tokens = [_tokenize(doc.page_content) for doc in documents]
        self._bm25 = BM25Okapi(self._corpus_tokens) if documents else None

    def search(self, query: str, k: int) -> list[tuple[Document, float]]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        max_score = max(scores) if len(scores) else 0.0
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in ranked_indices:
            if scores[idx] <= 0:
                continue
            normalized = scores[idx] / max_score if max_score > 0 else 0.0
            results.append((self.documents[idx], normalized))
        return results


def build_sparse_index(documents: list[Document]) -> SparseIndex:
    return SparseIndex(documents)
