"""Админская аутентификация JWT."""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer

from apps.backend.config import get_settings

security = HTTPBearer(auto_error=False)

# bcrypt limit; pass as bytes to avoid passlib's internal 72-byte test crash
_MAX_PW_BYTES = 72


def _to_bytes(s: str) -> bytes:
    b = s.encode("utf-8")
    return b[: _MAX_PW_BYTES] if len(b) > _MAX_PW_BYTES else b


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode() if isinstance(hashed, str) else hashed)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    s = get_settings()
    to_encode = data.copy()
    exp = expires_delta or timedelta(minutes=s.jwt_expire_minutes)
    to_encode.update({"exp": datetime.utcnow() + exp})
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError:
        return None


def create_portal_token(portal_id: int, expires_minutes: int = 10) -> str:
    """Короткоживущий JWT для iframe (portal_id в sub, type=portal)."""
    s = get_settings()
    to_encode = {"sub": str(portal_id), "type": "portal"}
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)


async def get_portal_from_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int | None:
    """Возвращает portal_id из Bearer (admin или portal JWT). Для portal JWT sub=portal_id."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    if payload.get("type") == "portal" and "sub" in payload:
        try:
            return int(payload["sub"])
        except (TypeError, ValueError):
            return None
    # Admin JWT: нет type=portal, но может вызывать с заголовком X-Portal-Id
    return None


async def require_portal_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int:
    """Требует portal JWT или admin JWT. Возвращает portal_id (из JWT или path)."""
    portal_id_path = request.path_params.get("portal_id") or request.query_params.get("portal_id")
    try:
        portal_id_path = int(portal_id_path) if portal_id_path is not None else None
    except (TypeError, ValueError):
        portal_id_path = None
    if not credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    if payload.get("type") == "portal":
        try:
            pid = int(payload["sub"])
            if portal_id_path is not None and pid != portal_id_path:
                raise HTTPException(status_code=403, detail="Доступ к другому порталу запрещён")
            return pid
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Недействительный portal токен")
    # Admin JWT: разрешаем, portal_id из path/query
    if portal_id_path is not None:
        return portal_id_path
    raise HTTPException(status_code=400, detail="Укажите portal_id")


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return payload

# Portal token with user_id claim for iframe admin checks.
def create_portal_token_with_user(portal_id: int, user_id: int | None, expires_minutes: int = 10) -> str:
    s = get_settings()
    to_encode = {"sub": str(portal_id), "type": "portal"}
    if user_id is not None:
        to_encode["uid"] = int(user_id)
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)
