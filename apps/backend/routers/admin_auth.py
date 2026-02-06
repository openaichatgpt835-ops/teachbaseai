"""Админская авторизация."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.deps import get_db
from apps.backend.models.admin import AdminUser
from apps.backend.auth import (
    get_password_hash,
    create_access_token,
    verify_password,
    get_current_admin,
)
from apps.backend.config import get_settings

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def ensure_admin_user(db: Session) -> None:
    s = get_settings()
    existing = db.execute(select(AdminUser).where(AdminUser.email == s.admin_default_email)).scalar_one_or_none()
    if existing:
        return
    admin = AdminUser(
        email=s.admin_default_email,
        password_hash=get_password_hash(s.admin_default_password),
    )
    db.add(admin)
    db.commit()


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    ensure_admin_user(db)
    user = db.execute(select(AdminUser).where(AdminUser.email == data.email)).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь заблокирован")
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(db: Session = Depends(get_db)):
    ensure_admin_user(db)
    s = get_settings()
    user = db.execute(select(AdminUser).where(AdminUser.email == s.admin_default_email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Нет администратора")
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(access_token=token)


@router.get("/me")
def me(payload: dict = Depends(get_current_admin)):
    return {"id": payload.get("sub"), "email": payload.get("email")}
