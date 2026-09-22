import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from langchain_core.documents import Document


@dataclass
class ChatTurn:
    turn_id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    graph_context: dict[str, Any] | None = None
    elapsed_seconds: float | None = None
    guardrail: dict[str, Any] | None = None
    eval_scores: dict[str, Any] | None = None


@dataclass
class SessionConfig:
    use_dense: bool = True
    use_sparse: bool = True
    use_graph: bool = True
    use_rerank: bool = True
    top_k: int = 6


@dataclass
class SessionState:
    session_id: str
    tenant_id: str
    created_at: float = field(default_factory=time.time)
    documents: list[Document] = field(default_factory=list)
    vectorstore: Any = None
    bm25_retriever: Any = None
    uploaded_files: list[str] = field(default_factory=list)
    chat_history: list[ChatTurn] = field(default_factory=list)
    config: SessionConfig = field(default_factory=SessionConfig)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Strictly isolates per-user state so parallel sessions never share memory or vector data."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._registry_lock = asyncio.Lock()

    async def create_session(self, session_id: str, tenant_id: str) -> SessionState:
        async with self._registry_lock:
            state = SessionState(session_id=session_id, tenant_id=tenant_id)
            self._sessions[session_id] = state
            return state

    def get_session(self, session_id: str) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or expired")
        return state

    async def delete_session(self, session_id: str) -> None:
        async with self._registry_lock:
            self._sessions.pop(session_id, None)

    def active_session_count(self) -> int:
        return len(self._sessions)


session_manager = SessionManager()
