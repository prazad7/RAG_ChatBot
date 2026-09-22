from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "ragchatbot123"
    neo4j_database: str = "neo4j"
    graph_search_enabled: bool = True

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str = ""
    langchain_project: str = "rag-chatbot"

    # DeepEval
    deepeval_enabled: bool = True
    confident_api_key: str = ""

    # Auth
    app_auth_username: str = "admin"
    app_auth_password: str = "password@123"

    # Sessions / JWT
    jwt_secret_key: str = "change-me-to-a-random-secret-in-production"
    jwt_expire_minutes: int = 120

    # CORS
    backend_cors_origins: str = "http://localhost:5173"

    # OCR
    tesseract_cmd: str = ""

    # Retrieval defaults
    default_top_k: int = 6
    rrf_k: int = 60
    dense_candidates: int = 15
    sparse_candidates: int = 15
    graph_candidates: int = 10
    rerank_top_n: int = 6
    relevance_threshold: float = 0.15

    # Retrieval overrides for aggregate-intent queries (counts/lists/sums spanning many
    # chunks) - see app/core/query_agent.py. Wider candidate pool and a much lower
    # relevance gate, since any one matching record scores low against a "how many..."
    # phrasing even though it's exactly the data the answer needs.
    aggregate_dense_candidates: int = 40
    aggregate_sparse_candidates: int = 40
    aggregate_top_k: int = 25
    aggregate_relevance_threshold: float = 0.02

    # Storage
    data_dir: Path = BACKEND_DIR / "data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    return settings
