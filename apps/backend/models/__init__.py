"""Модели SQLAlchemy."""
from apps.backend.models.portal import Portal, PortalToken, PortalUsersAccess
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.dialog_rag_cache import DialogRagCache
from apps.backend.models.dialog_state import DialogState
from apps.backend.models.event import Event
from apps.backend.models.outbox import Outbox
from apps.backend.models.billing import BillingPlan, PortalBilling, UsageCounter, PortalUsageLimit, BillingUsage
from apps.backend.models.admin import AdminUser
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.app_setting import AppSetting
from apps.backend.models.kb import KBFile, KBChunk, KBEmbedding, KBSource, KBJob
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.models.portal_telegram_setting import PortalTelegramSetting
from apps.backend.models.portal_bot_flow import PortalBotFlow
from apps.backend.models.topic_summary import PortalTopicSummary
from apps.backend.models.web_user import WebUser, WebSession
from apps.backend.models.activity_event import ActivityEvent
from apps.backend.models.portal_link_request import PortalLinkRequest

__all__ = [
    "Portal",
    "PortalToken",
    "PortalUsersAccess",
    "Dialog",
    "Message",
    "DialogRagCache",
    "DialogState",
    "Event",
    "Outbox",
    "BillingPlan",
    "PortalBilling",
    "UsageCounter",
    "PortalUsageLimit",
    "BillingUsage",
    "AdminUser",
    "BitrixHttpLog",
    "BitrixInboundEvent",
    "AppSetting",
    "PortalKBSetting",
    "PortalTelegramSetting",
    "PortalBotFlow",
    "KBFile",
    "KBChunk",
    "KBEmbedding",
    "KBSource",
    "KBJob",
    "PortalTopicSummary",
    "WebUser",
    "WebSession",
    "ActivityEvent",
    "PortalLinkRequest",
]
