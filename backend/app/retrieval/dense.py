from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from app.core.config import get_settings

_embeddings_singleton: OpenAIEmbeddings | None = None


def get_embeddings() -> OpenAIEmbeddings:
    global _embeddings_singleton
    if _embeddings_singleton is None:
        settings = get_settings()
        _embeddings_singleton = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
    return _embeddings_singleton


def build_dense_index(documents: list[Document]) -> FAISS:
    return FAISS.from_documents(documents, get_embeddings())


def add_to_dense_index(vectorstore: FAISS, documents: list[Document]) -> None:
    vectorstore.add_documents(documents)


def dense_search(vectorstore: FAISS, query: str, k: int) -> list[tuple[Document, float]]:
    if vectorstore is None:
        return []
    try:
        results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
    except Exception:  # noqa: BLE001 - fall back if the relevance-score fn errors for this index
        raw = vectorstore.similarity_search_with_score(query, k=k)
        results = [(doc, 1.0 / (1.0 + score)) for doc, score in raw]
    return [(doc, max(0.0, min(1.0, score))) for doc, score in results]
