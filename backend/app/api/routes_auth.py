from fastapi import APIRouter, HTTPException, status

from app.core.security import issue_session_token, verify_credentials
from app.core.session_manager import session_manager
from app.models.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token, session_id, expires_at = issue_session_token()
    await session_manager.create_session(session_id=session_id, tenant_id=session_id)

    return LoginResponse(session_token=token, session_id=session_id, expires_at=expires_at.isoformat())
