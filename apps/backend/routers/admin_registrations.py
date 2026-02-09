"""Admin: registration settings and analytics."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.activity_event import ActivityEvent
from apps.backend.models.app_setting import AppSetting
from apps.backend.models.billing import BillingUsage
from apps.backend.models.web_user import WebUser
from apps.backend.models.portal import Portal
from apps.backend.services.email import send_email

router = APIRouter(dependencies=[Depends(get_current_admin)])

SETTINGS_KEY = "mail_settings"
TEMPLATES_KEY = "mail_templates"


class MailboxSettings(BaseModel):
    smtp_host: str = ""
    smtp_port: str | int | None = "587"  # allow "25:465:587"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_secure: str = "tls"  # tls|ssl|none
    from_email: str = ""
    from_name: str = ""


class MailSettingsPayload(BaseModel):
    registration: MailboxSettings = MailboxSettings()
    onboarding: MailboxSettings = MailboxSettings()
    invoices: MailboxSettings = MailboxSettings()


class TemplateItem(BaseModel):
    subject: str = ""
    html: str = ""
    text: str = ""
    delay_days: int | None = None


class MailTemplatesPayload(BaseModel):
    registration: TemplateItem = TemplateItem()
    registration_confirmed: TemplateItem = TemplateItem()
    onboarding: list[TemplateItem] = []


def _normalize_settings(data: dict[str, Any]) -> dict[str, Any]:
    default = MailSettingsPayload().dict()
    out: dict[str, Any] = {}
    for key in default:
        box = data.get(key)
        if not isinstance(box, dict):
            out[key] = default[key]
            continue
        normalized: dict[str, Any] = {}
        for field, dv in default[key].items():
            val = box.get(field, dv)
            if val is None:
                val = dv
            if field in ("smtp_secure", "smtp_host", "smtp_user", "smtp_password", "from_email", "from_name"):
                normalized[field] = str(val)
            elif field == "smtp_port":
                normalized[field] = val
            else:
                normalized[field] = val
        out[key] = normalized
    return out


def _default_templates() -> dict[str, Any]:
    base_style = (
        "font-family: 'Segoe UI', Arial, sans-serif; background:#f6f8fc; padding:24px; color:#0f172a;"
    )
    card_style = (
        "max-width:640px;margin:0 auto;background:#ffffff;border-radius:18px;"
        "padding:28px;border:1px solid #e2e8f0;box-shadow:0 8px 30px rgba(15,23,42,.08);"
    )
    button_style = (
        "display:inline-block;background:#2563eb;color:#fff;text-decoration:none;"
        "padding:12px 18px;border-radius:10px;font-weight:600;"
    )

    def wrap(title: str, body_html: str, footer_html: str) -> str:
        return (
            f"<div style=\"{base_style}\">"
            f"<div style=\"{card_style}\">"
            f"<h1 style=\"margin:0 0 12px 0;font-size:22px;\">{title}</h1>"
            f"{body_html}"
            f"<div style=\"margin-top:22px;color:#64748b;font-size:12px;\">{footer_html}</div>"
            f"</div></div>"
        )

    registration_html = wrap(
        "Подтвердите регистрацию",
        (
            "<p style=\"margin:0 0 12px 0;\">Спасибо за регистрацию в Teachbase AI. "
            "Подтвердите email, чтобы активировать кабинет.</p>"
            f"<a style=\"{button_style}\" href=\"{{{{confirm_url}}}}\">Подтвердить email</a>"
            "<p style=\"margin:16px 0 0 0;font-size:13px;color:#475569;\">"
            "Если кнопка не работает, откройте ссылку: {{confirm_url}}</p>"
        ),
        "Если вы не регистрировались, просто игнорируйте это письмо.",
    )

    confirmed_html = wrap(
        "Регистрация подтверждена",
        (
            "<p style=\"margin:0 0 12px 0;\">Email подтвержден. Добро пожаловать в Teachbase AI.</p>"
            f"<a style=\"{button_style}\" href=\"https://necrogame.ru/login\">Войти в кабинет</a>"
        ),
        "Если у вас есть вопросы — ответьте на это письмо.",
    )

    onboarding_subjects = [
        "Онбординг 0: первый шаг",
        "Онбординг 2: загрузите знания",
        "Онбординг 5: настройте ответы",
        "Онбординг 9: подключите ботов",
        "Онбординг 15: автоматизация лидов",
        "Онбординг 28: закрепим результат",
    ]
    onboarding_bodies = [
        "Начните с базы знаний: загрузите файлы и ссылки, чтобы бот отвечал фактами.",
        "Добавьте источники: PDF, DOCX, таблицы и URL — бот сможет искать в них.",
        "Настройте сценарий: вопросы, уточнения и финальный ответ для клиентов.",
        "Подключите Telegram-бота или Bitrix24 для работы сотрудников.",
        "Настройте отправку лидов в Bitrix24 и webhook-интеграции.",
        "Проверьте аналитику и улучшайте конверсию.",
    ]
    delays = [0, 2, 5, 9, 15, 28]
    onboarding: list[dict[str, Any]] = []
    for idx, delay in enumerate(delays):
        body_html = (
            f"<p style=\"margin:0 0 12px 0;\">{onboarding_bodies[idx]}</p>"
            f"<a style=\"{button_style}\" href=\"https://necrogame.ru/app\">Открыть кабинет</a>"
        )
        onboarding.append(
            {
                "subject": onboarding_subjects[idx],
                "html": wrap(onboarding_subjects[idx], body_html, "Письмо из серии онбординга Teachbase AI."),
                "text": (
                    f"{onboarding_subjects[idx]}\n"
                    f"{onboarding_bodies[idx]}\n"
                    "Открыть кабинет: https://necrogame.ru/app"
                ),
                "delay_days": delay,
            }
        )

    return {
        "registration": {
            "subject": "Подтвердите регистрацию в Teachbase AI",
            "html": registration_html,
            "text": (
                "Подтвердите регистрацию в Teachbase AI.\n"
                "Ссылка подтверждения: {{confirm_url}}\n"
                "Если вы не регистрировались, просто игнорируйте это письмо."
            ),
        },
        "registration_confirmed": {
            "subject": "Регистрация подтверждена",
            "html": confirmed_html,
            "text": "Регистрация подтверждена. Войти: https://necrogame.ru/login",
        },
        "onboarding": onboarding,
    }


def _get_settings(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, SETTINGS_KEY)
    if not row:
        return MailSettingsPayload().dict()
    data = row.value_json or {}
    return _normalize_settings(data)


def _get_templates(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, TEMPLATES_KEY)
    if not row:
        return _default_templates()
    data = row.value_json or {}
    default = _default_templates()
    if "onboarding" not in data or not isinstance(data.get("onboarding"), list):
        data["onboarding"] = default["onboarding"]
    for key in ("registration", "registration_confirmed"):
        if key not in data or not isinstance(data.get(key), dict):
            data[key] = default[key]
        else:
            for field, dv in default[key].items():
                if not data[key].get(field):
                    data[key][field] = dv
    if not data["onboarding"]:
        data["onboarding"] = default["onboarding"]
    else:
        for idx, item in enumerate(data["onboarding"]):
            if not isinstance(item, dict):
                data["onboarding"][idx] = default["onboarding"][min(idx, len(default["onboarding"]) - 1)]
                continue
            defaults = default["onboarding"][min(idx, len(default["onboarding"]) - 1)]
            for field, dv in defaults.items():
                if not item.get(field):
                    item[field] = dv
    return data


def _resolve_port(raw: str | int | None, secure: str) -> int:
    if isinstance(raw, int):
        return raw
    text = str(raw or "").strip()
    parts = [p for p in text.replace(",", ":").split(":") if p.strip().isdigit()]
    ports = []
    for p in parts:
        try:
            ports.append(int(p))
        except Exception:
            pass
    if secure == "ssl" and 465 in ports:
        return 465
    if secure == "tls" and 587 in ports:
        return 587
    if 25 in ports:
        return 25
    if ports:
        return ports[0]
    return 465 if secure == "ssl" else (587 if secure == "tls" else 25)


@router.get("/registrations/settings")
def get_mail_settings(db: Session = Depends(get_db)):
    return _get_settings(db)


@router.put("/registrations/settings")
def set_mail_settings(body: dict[str, Any], db: Session = Depends(get_db)):
    row = db.get(AppSetting, SETTINGS_KEY)
    data = _normalize_settings(body or {})
    if not row:
        row = AppSetting(key=SETTINGS_KEY, value_json=data)
        db.add(row)
    else:
        row.value_json = data
    db.commit()
    return {"status": "ok"}


@router.get("/registrations/templates")
def get_mail_templates(db: Session = Depends(get_db)):
    return _get_templates(db)


@router.put("/registrations/templates")
def set_mail_templates(body: dict[str, Any], db: Session = Depends(get_db)):
    row = db.get(AppSetting, TEMPLATES_KEY)
    data = body or {}
    if not row:
        row = AppSetting(key=TEMPLATES_KEY, value_json=data)
        db.add(row)
    else:
        row.value_json = data
    db.commit()
    return {"status": "ok"}


@router.get("/registrations/stats")
def get_registration_stats(db: Session = Depends(get_db)):
    total = int(db.execute(select(func.count(WebUser.id))).scalar() or 0)
    confirmed = int(
        db.execute(select(func.count(WebUser.id)).where(WebUser.email_verified_at.isnot(None))).scalar() or 0
    )
    web_hits = int(db.execute(select(func.count(ActivityEvent.id)).where(ActivityEvent.kind == "web")).scalar() or 0)
    iframe_hits = int(db.execute(select(func.count(ActivityEvent.id)).where(ActivityEvent.kind == "iframe")).scalar() or 0)
    ai_requests = int(db.execute(select(func.count(BillingUsage.id))).scalar() or 0)

    # ret3: activity on any 3 days within 8 days after registration (days 1-8)
    ret3 = 0
    users = db.execute(select(WebUser.id, WebUser.created_at)).all()
    for uid, created_at in users:
        if not created_at:
            continue
        start = (created_at.date() + timedelta(days=1))
        end = (created_at.date() + timedelta(days=8))
        rows = db.execute(
            select(ActivityEvent.created_at).where(
                ActivityEvent.web_user_id == uid,
                ActivityEvent.created_at >= datetime.combine(start, datetime.min.time()),
                ActivityEvent.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
            )
        ).scalars().all()
        days = {r.date() for r in rows if r}
        if len(days) >= 3:
            ret3 += 1

    return {
        "registrations_total": total,
        "registrations_confirmed": confirmed,
        "web_hits": web_hits,
        "iframe_hits": iframe_hits,
        "ai_requests": ai_requests,
        "ret3": ret3,
    }


class TestEmailBody(BaseModel):
    to: str
    mailbox: str = "registration"  # registration|onboarding|invoices
    template: str = "registration"  # registration|registration_confirmed|onboarding
    onboarding_index: int = 0


@router.post("/registrations/test-email")
def send_test_email(body: TestEmailBody, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    templates = _get_templates(db)
    mailbox_key = body.mailbox if body.mailbox in settings else "registration"
    tpl_key = body.template
    tpl: dict[str, Any] = {}
    if tpl_key == "onboarding":
        onboarding = templates.get("onboarding") or []
        idx = max(0, min(body.onboarding_index, len(onboarding) - 1))
        tpl = onboarding[idx] if onboarding else {}
    else:
        tpl = templates.get(tpl_key) or {}
    subject = tpl.get("subject") or "Teachbase AI"
    html = tpl.get("html") or ""
    text = tpl.get("text") or ""
    html = html.replace("{{confirm_url}}", "https://necrogame.ru/confirm?token=demo")
    text = text.replace("{{confirm_url}}", "https://necrogame.ru/confirm?token=demo")
    mb = settings.get(mailbox_key) or {}
    port = _resolve_port(mb.get("smtp_port"), str(mb.get("smtp_secure") or "tls"))
    ok, err = send_email(
        host=mb.get("smtp_host") or "",
        port=port,
        username=mb.get("smtp_user") or "",
        password=mb.get("smtp_password") or "",
        secure=str(mb.get("smtp_secure") or "tls"),
        from_email=mb.get("from_email") or "",
        from_name=mb.get("from_name") or "",
        to_email=body.to,
        subject=subject,
        html=html,
        text=text,
    )
    if not ok:
        return {"status": "error", "error": err}
    return {"status": "ok"}


@router.get("/registrations/stats/portals")
def get_stats_by_portal(metric: str, db: Session = Depends(get_db)):
    allowed = {
        "registrations_total",
        "registrations_confirmed",
        "web_hits",
        "iframe_hits",
        "ai_requests",
        "ret3",
    }
    if metric not in allowed:
        return {"status": "error", "error": "unknown_metric"}

    portal_map = {pid: domain for pid, domain in db.execute(select(Portal.id, Portal.domain)).all()}

    rows: list[tuple[int | None, int]] = []
    if metric == "registrations_total":
        rows = db.execute(
            select(WebUser.portal_id, func.count(WebUser.id)).group_by(WebUser.portal_id)
        ).all()
    elif metric == "registrations_confirmed":
        rows = db.execute(
            select(WebUser.portal_id, func.count(WebUser.id))
            .where(WebUser.email_verified_at.isnot(None))
            .group_by(WebUser.portal_id)
        ).all()
    elif metric == "web_hits":
        rows = db.execute(
            select(ActivityEvent.portal_id, func.count(ActivityEvent.id))
            .where(ActivityEvent.kind == "web")
            .group_by(ActivityEvent.portal_id)
        ).all()
    elif metric == "iframe_hits":
        rows = db.execute(
            select(ActivityEvent.portal_id, func.count(ActivityEvent.id))
            .where(ActivityEvent.kind == "iframe")
            .group_by(ActivityEvent.portal_id)
        ).all()
    elif metric == "ai_requests":
        rows = db.execute(
            select(BillingUsage.portal_id, func.count(BillingUsage.id))
            .group_by(BillingUsage.portal_id)
        ).all()
    elif metric == "ret3":
        ret3_by_portal: dict[int | None, int] = {}
        users = db.execute(select(WebUser.id, WebUser.portal_id, WebUser.created_at)).all()
        for uid, portal_id, created_at in users:
            if not created_at:
                continue
            start = (created_at.date() + timedelta(days=1))
            end = (created_at.date() + timedelta(days=8))
            events = db.execute(
                select(ActivityEvent.created_at).where(
                    ActivityEvent.web_user_id == uid,
                    ActivityEvent.created_at >= datetime.combine(start, datetime.min.time()),
                    ActivityEvent.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
                )
            ).scalars().all()
            days = {r.date() for r in events if r}
            if len(days) >= 3:
                ret3_by_portal[portal_id] = ret3_by_portal.get(portal_id, 0) + 1
        rows = list(ret3_by_portal.items())

    out = []
    for portal_id, count in rows:
        out.append(
            {
                "portal_id": portal_id,
                "domain": portal_map.get(portal_id) or "web-portal",
                "count": int(count),
            }
        )
    out.sort(key=lambda r: r["count"], reverse=True)
    return {"status": "ok", "items": out}


@router.get("/registrations/stats/timeseries")
def get_timeseries(metric: str, period: str = "month", portal_id: int | None = None, db: Session = Depends(get_db)):
    allowed = {
        "registrations_total",
        "registrations_confirmed",
        "web_hits",
        "iframe_hits",
        "ai_requests",
        "ret3",
    }
    if metric not in allowed:
        return {"status": "error", "error": "unknown_metric"}

    days = 7 if period == "week" else (30 if period == "month" else 365)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    def fill_series(rows: list[tuple[date, int]]) -> list[dict[str, Any]]:
        by_day = {r[0]: int(r[1]) for r in rows}
        out = []
        d = start_date
        while d <= end_date:
            out.append({"date": d.isoformat(), "count": by_day.get(d, 0)})
            d += timedelta(days=1)
        return out

    rows: list[tuple[date, int]] = []
    if metric == "registrations_total":
        q = select(func.date(WebUser.created_at), func.count(WebUser.id)).where(
            WebUser.created_at >= start_dt, WebUser.created_at < end_dt
        )
        if portal_id is not None:
            q = q.where(WebUser.portal_id == portal_id)
        rows = db.execute(q.group_by(func.date(WebUser.created_at))).all()
    elif metric == "registrations_confirmed":
        q = select(func.date(WebUser.email_verified_at), func.count(WebUser.id)).where(
            WebUser.email_verified_at.isnot(None),
            WebUser.email_verified_at >= start_dt,
            WebUser.email_verified_at < end_dt,
        )
        if portal_id is not None:
            q = q.where(WebUser.portal_id == portal_id)
        rows = db.execute(q.group_by(func.date(WebUser.email_verified_at))).all()
    elif metric in ("web_hits", "iframe_hits"):
        q = select(func.date(ActivityEvent.created_at), func.count(ActivityEvent.id)).where(
            ActivityEvent.kind == ("web" if metric == "web_hits" else "iframe"),
            ActivityEvent.created_at >= start_dt,
            ActivityEvent.created_at < end_dt,
        )
        if portal_id is not None:
            q = q.where(ActivityEvent.portal_id == portal_id)
        rows = db.execute(q.group_by(func.date(ActivityEvent.created_at))).all()
    elif metric == "ai_requests":
        q = select(func.date(BillingUsage.created_at), func.count(BillingUsage.id)).where(
            BillingUsage.created_at >= start_dt,
            BillingUsage.created_at < end_dt,
        )
        if portal_id is not None:
            q = q.where(BillingUsage.portal_id == portal_id)
        rows = db.execute(q.group_by(func.date(BillingUsage.created_at))).all()
    elif metric == "ret3":
        ret3_by_day: dict[date, int] = {}
        q = select(WebUser.id, WebUser.portal_id, WebUser.created_at).where(
            WebUser.created_at >= start_dt, WebUser.created_at < end_dt
        )
        if portal_id is not None:
            q = q.where(WebUser.portal_id == portal_id)
        users = db.execute(q).all()
        for uid, p_id, created_at in users:
            if not created_at:
                continue
            start = (created_at.date() + timedelta(days=1))
            end = (created_at.date() + timedelta(days=8))
            rows_ev = db.execute(
                select(ActivityEvent.created_at).where(
                    ActivityEvent.web_user_id == uid,
                    ActivityEvent.created_at >= datetime.combine(start, datetime.min.time()),
                    ActivityEvent.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
                )
            ).scalars().all()
            days_set = {r.date() for r in rows_ev if r}
            if len(days_set) >= 3:
                ret3_by_day[created_at.date()] = ret3_by_day.get(created_at.date(), 0) + 1
        rows = list(ret3_by_day.items())

    return {"status": "ok", "items": fill_series(rows)}
