"""Зависимости FastAPI."""
from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from apps.backend.database import get_session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()
