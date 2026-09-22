from fastapi import APIRouter, Depends

from app.core.security import get_current_session_id
from app.core.session_manager import session_manager

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("/me")
async def get_session_info(session_id: str = Depends(get_current_session_id)) -> dict:
    session = session_manager.get_session(session_id)
    return {
        "session_id": session.session_id,
        "uploaded_files": session.uploaded_files,
        "config": session.config.__dict__,
        "chat_history": [
            {
                "turn_id": t.turn_id,
                "role": t.role,
                "content": t.content,
                "sources": t.sources,
                "graph_context": t.graph_context,
                "elapsed_seconds": t.elapsed_seconds,
                "guardrail": t.guardrail,
            }
            for t in session.chat_history
        ],
    }


@router.delete("/me")
async def end_session(session_id: str = Depends(get_current_session_id)) -> dict:
    await session_manager.delete_session(session_id)
    return {"status": "session ended"}
