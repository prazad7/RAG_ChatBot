import logging

import truststore

# Use the OS-native certificate store instead of certifi's bundle, so TLS verification
# matches whatever CAs the machine already trusts (e.g. a corporate/AV TLS-inspection root).
truststore.inject_into_ssl()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_auth, routes_chat, routes_session, routes_upload
from app.core.config import get_settings
from app.core.session_manager import session_manager
from app.eval.deepeval_metrics import ensure_deepeval_env
from app.eval.langsmith_setup import configure_langsmith
from app.graph.knowledge_graph import is_graph_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hybrid RAG Chatbot", version="1.0.0")

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_upload.router)
app.include_router(routes_chat.router)
app.include_router(routes_session.router)


@app.on_event("startup")
async def on_startup() -> None:
    configure_langsmith()
    ensure_deepeval_env()
    graph_ok = is_graph_available()
    logger.info("Graph search available: %s", graph_ok)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "active_sessions": session_manager.active_session_count(),
        "graph_search_available": is_graph_available(),
    }
