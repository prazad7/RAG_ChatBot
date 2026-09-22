import logging

import torch
from langchain_core.documents import Document
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_tokenizer = None
_model = None


def _load_model() -> None:
    global _tokenizer, _model
    if _model is not None:
        return
    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
    _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
    _model.eval()


def rerank(query: str, documents: list[Document], top_n: int) -> list[tuple[Document, float]]:
    """Cross-encoder re-ranking: scores each (query, document) pair jointly for much
    higher precision than the bi-encoder / BM25 rankings that produced the candidate set."""
    if not documents:
        return []
    try:
        _load_model()
    except Exception:  # noqa: BLE001
        logger.warning("Cross-encoder reranker unavailable, falling back to input order", exc_info=True)
        return [(doc, 1.0 - i / max(len(documents), 1)) for i, doc in enumerate(documents[:top_n])]

    pairs = [(query, doc.page_content[:2000]) for doc in documents]
    with torch.no_grad():
        inputs = _tokenizer.batch_encode_plus(
            pairs, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        logits = _model(**inputs).logits.view(-1)
        scores = torch.sigmoid(logits).tolist()

    scored = list(zip(documents, scores))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_n]
