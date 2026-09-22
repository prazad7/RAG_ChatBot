import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def verify_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    return username == settings.app_auth_username and password == settings.app_auth_password


def issue_session_token() -> tuple[str, str, datetime]:
    """Create a brand-new, isolated session and sign a JWT for it. The session_id doubles
    as the tenant_id: each login is its own fully isolated tenant (vectorstore, BM25 index,
    chat memory, and graph-namespace are all scoped to this one value)."""
    settings = get_settings()
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "session_id": session_id,
        "tenant_id": session_id,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return token, session_id, expires_at


def decode_session_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token") from exc


async def get_current_session_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token")
    payload = decode_session_token(credentials.credentials)
    return payload["session_id"]
