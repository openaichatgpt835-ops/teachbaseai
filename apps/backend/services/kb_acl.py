"""KB folders and ACL foundation helpers."""
from __future__ import annotations

KB_ACCESS_LEVELS = {"none", "read", "write", "admin"}
KB_PRINCIPAL_TYPES = {"membership", "role", "audience", "group"}
_KB_ACCESS_RANK = {"none": 0, "read": 1, "write": 2, "admin": 3}


def default_kb_access_for_role(role: str | None) -> str:
    role_norm = str(role or "").strip().lower()
    if role_norm == "owner":
        return "admin"
    if role_norm == "admin":
        return "write"
    if role_norm == "member":
        return "read"
    if role_norm == "client":
        return "none"
    return "none"


def normalize_kb_principal(principal_type: str, principal_id: str | int) -> tuple[str, str]:
    ptype = str(principal_type or "").strip().lower()
    if ptype not in KB_PRINCIPAL_TYPES:
        raise ValueError("invalid_principal_type")
    pid = str(principal_id or "").strip()
    if not pid:
        raise ValueError("invalid_principal_id")
    return ptype, pid


def kb_acl_principals_for_membership(
    membership_id: int | None,
    role: str | None,
    audience: str | None = None,
    group_ids: list[int] | None = None,
) -> set[tuple[str, str]]:
    principals: set[tuple[str, str]] = set()
    if membership_id:
        principals.add(("membership", str(int(membership_id))))
    for group_id in group_ids or []:
        if int(group_id) > 0:
            principals.add(("group", str(int(group_id))))
    role_norm = str(role or "").strip().lower()
    if role_norm:
        principals.add(("role", role_norm))
    aud_norm = str(audience or "").strip().lower()
    if aud_norm:
        principals.add(("audience", aud_norm))
    return principals


def resolve_kb_acl_access(
    acl_rows: list[tuple[str, str, str]] | list[dict[str, str]],
    principals: set[tuple[str, str]],
    inherited_access: str = "none",
    *,
    inherit_when_empty: bool = True,
) -> str:
    inherited = str(inherited_access or "none").strip().lower()
    if inherited not in _KB_ACCESS_RANK:
        inherited = "none"
    best = inherited if inherit_when_empty and not acl_rows else "none"
    for row in acl_rows:
        if isinstance(row, dict):
            principal_type = str(row.get("principal_type") or "").strip().lower()
            principal_id = str(row.get("principal_id") or "").strip()
            access_level = str(row.get("access_level") or "none").strip().lower()
        else:
            principal_type = str(row[0] or "").strip().lower()
            principal_id = str(row[1] or "").strip()
            access_level = str(row[2] or "none").strip().lower()
        if access_level not in _KB_ACCESS_RANK:
            continue
        if (principal_type, principal_id) not in principals:
            continue
        if _KB_ACCESS_RANK[access_level] > _KB_ACCESS_RANK[best]:
            best = access_level
    return best
