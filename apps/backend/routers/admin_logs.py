"""Админские endpoints логов."""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from apps.backend.auth import get_current_admin

router = APIRouter()

LOG_DIR = Path("/var/log/teachbaseai")  # для prod; dev может быть пусто


@router.get("/backend", response_class=PlainTextResponse)
def logs_backend(
    tail: int = Query(200, ge=1, le=2000),
    _: dict = Depends(get_current_admin),
):
    path = LOG_DIR / "backend.log"
    if not path.exists():
        return f"Лог не найден: {path}\nВ dev-режиме логи выводятся в stdout."
    lines = path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    return "\n".join(lines[-tail:])


@router.get("/worker", response_class=PlainTextResponse)
def logs_worker(
    tail: int = Query(200, ge=1, le=2000),
    _: dict = Depends(get_current_admin),
):
    path = LOG_DIR / "worker.log"
    if not path.exists():
        return f"Лог не найден: {path}\nВ dev-режиме логи выводятся в stdout."
    lines = path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    return "\n".join(lines[-tail:])


@router.get("/nginx", response_class=PlainTextResponse)
def logs_nginx(
    tail: int = Query(200, ge=1, le=2000),
    _: dict = Depends(get_current_admin),
):
    path = LOG_DIR / "nginx.log"
    if not path.exists():
        return f"Лог nginx не найден: {path}"
    lines = path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    return "\n".join(lines[-tail:])
