from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.chat_pipeline import record_turn, run_chat_pipeline
from app.core.security import get_current_session_id
from app.core.session_manager import session_manager
from app.eval.deepeval_metrics import compute_eval_scores, get_eval_scores
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigUpdateRequest,
    EvalScores,
    GraphContext,
    GuardrailInfo,
    SourceAttribution,
)
from app.utils.timing import elapsed_timer

router = APIRouter(prefix="/api", tags=["chat"])


@router.patch("/config")
async def update_config(payload: ConfigUpdateRequest, session_id: str = Depends(get_current_session_id)) -> dict:
    session = session_manager.get_session(session_id)
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(session.config, key, value)
    return {"config": session.config.__dict__}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    session_id: str = Depends(get_current_session_id),
) -> ChatResponse:
    session = session_manager.get_session(session_id)

    async with session.lock:
        record_turn(session, role="user", content=payload.message, result=None, elapsed=0.0)

        with elapsed_timer() as timer:
            result = await run_chat_pipeline(session, payload.message)

        record_turn(session, role="assistant", content=result.answer, result=result, elapsed=timer["seconds"])

    if result.context_chunks:
        background_tasks.add_task(
            compute_eval_scores, result.turn_id, payload.message, result.answer, result.context_chunks
        )

    return ChatResponse(
        turn_id=result.turn_id,
        answer=result.answer,
        sources=[SourceAttribution(**s) for s in result.sources],
        graph_context=GraphContext(**result.graph_context),
        elapsed_seconds=timer["seconds"],
        guardrail=GuardrailInfo(**result.guardrail),
    )


@router.get("/chat/{turn_id}/eval", response_model=EvalScores)
async def get_turn_eval(turn_id: str, session_id: str = Depends(get_current_session_id)) -> EvalScores:
    session_manager.get_session(session_id)  # validates the session exists / token is valid
    scores = get_eval_scores(turn_id)
    if scores is None:
        return EvalScores(turn_id=turn_id, status="pending")
    return EvalScores(
        turn_id=turn_id,
        answer_relevancy=scores.get("answer_relevancy"),
        faithfulness=scores.get("faithfulness"),
        status=scores.get("status", "unknown"),
    )
