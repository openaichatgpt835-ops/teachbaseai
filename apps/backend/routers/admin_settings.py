"""Admin: global settings (inbound-events storage)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.services.inbound_settings import (
    get_inbound_settings,
    put_inbound_settings,
    DEFAULTS,
    VALIDATION,
)

router = APIRouter(dependencies=[Depends(get_current_admin)])


class InboundEventsSettingsResponse(BaseModel):
    retention_days: int
    max_rows: int
    max_body_kb: int
    enabled: bool
    auto_prune_on_write: bool
    target_budget_mb: int
    defaults: dict


class InboundEventsSettingsUpdate(BaseModel):
    retention_days: int | None = Field(None, ge=1, le=30)
    max_rows: int | None = Field(None, ge=100, le=50000)
    max_body_kb: int | None = Field(None, ge=1, le=512)
    enabled: bool | None = None
    auto_prune_on_write: bool | None = None
    target_budget_mb: int | None = Field(None, ge=10, le=2000)


@router.get("/inbound-events", response_model=InboundEventsSettingsResponse)
def get_inbound_events_settings(db: Session = Depends(get_db)):
    """Current inbound-events storage settings + defaults."""
    current = get_inbound_settings(db)
    return InboundEventsSettingsResponse(
        retention_days=current["retention_days"],
        max_rows=current["max_rows"],
        max_body_kb=current["max_body_kb"],
        enabled=current["enabled"],
        auto_prune_on_write=current["auto_prune_on_write"],
        target_budget_mb=current["target_budget_mb"],
        defaults=dict(DEFAULTS),
    )


@router.put("/inbound-events", response_model=InboundEventsSettingsResponse)
def put_inbound_events_settings(
    payload: InboundEventsSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update inbound-events storage settings (validation applied)."""
    raw = payload.model_dump(exclude_none=True)
    if not raw:
        current = get_inbound_settings(db)
        return InboundEventsSettingsResponse(
            retention_days=current["retention_days"],
            max_rows=current["max_rows"],
            max_body_kb=current["max_body_kb"],
            enabled=current["enabled"],
            auto_prune_on_write=current["auto_prune_on_write"],
            target_budget_mb=current["target_budget_mb"],
            defaults=dict(DEFAULTS),
        )
    merged = put_inbound_settings(db, raw)
    return InboundEventsSettingsResponse(
        retention_days=merged["retention_days"],
        max_rows=merged["max_rows"],
        max_body_kb=merged["max_body_kb"],
        enabled=merged["enabled"],
        auto_prune_on_write=merged["auto_prune_on_write"],
        target_budget_mb=merged["target_budget_mb"],
        defaults=dict(DEFAULTS),
    )
