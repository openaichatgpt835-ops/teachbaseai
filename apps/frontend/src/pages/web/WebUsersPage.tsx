import { useEffect, useState } from "react";
import { PageIntro } from "../../components/PageIntro";
import { fetchPortal, fetchWeb, getActiveAccountId, getWebPortalInfo } from "./auth";

type WebUserItem = { id: string; name: string; telegram_username?: string | null };
type AccountGroupItem = {
  id: number;
  name: string;
  kind: "staff" | "client";
  membership_ids: number[];
  members?: { membership_id: number; user_id: number; role: string; status: string }[];
};
type LinkedIdentity = {
  id: number;
  external_id?: string | null;
  display_value?: string | null;
  integration_id?: number | null;
};
type V2UserItem = {
  membership_id: number;
  user_id: number;
  display_name?: string | null;
  role: "owner" | "admin" | "member" | "client";
  status: "active" | "invited" | "blocked" | "deleted";
  permissions: {
    kb_access: "none" | "read" | "write";
    can_invite_users: boolean;
    can_manage_settings: boolean;
    can_view_finance: boolean;
  };
  web?: { login?: string | null; email?: string | null } | null;
  bitrix?: LinkedIdentity[];
  telegram?: LinkedIdentity[];
  amo?: LinkedIdentity[];
  access_center?: {
    portal_id?: number | null;
    bitrix_linked?: boolean;
    bitrix_allowlist?: boolean;
    bitrix_user_ids?: string[];
    telegram_username?: string | null;
  } | null;
  groups?: { id: number; name: string; kind?: "staff" | "client" }[];
};
type V2InviteItem = { id: number; email?: string | null; role: string; status: string; expires_at?: string | null; accept_url?: string | null };
type MeContext = {
  account?: { id?: number | null } | null;
  membership?: {
    role?: "owner" | "admin" | "member" | "client";
    kb_access?: "none" | "read" | "write";
    can_invite_users?: boolean;
    can_manage_settings?: boolean;
    can_view_finance?: boolean;
  } | null;
};

type UsersCacheState = {
  selectedUsers: number[];
  telegramMap: Record<number, string>;
  webUsers: WebUserItem[];
};

const usersCache = new Map<number, UsersCacheState>();

export function WebUsersPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const cached = portalId ? usersCache.get(portalId) : null;

  const [selectedUsers, setSelectedUsers] = useState<number[]>(cached?.selectedUsers || []);
  const [telegramMap, setTelegramMap] = useState<Record<number, string>>(cached?.telegramMap || {});
  const [saveStatus, setSaveStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingBitrixKey, setSavingBitrixKey] = useState<string>("");

  const [webUsers, setWebUsers] = useState<WebUserItem[]>(cached?.webUsers || []);
  const [newWebUserName, setNewWebUserName] = useState("");
  const [newWebUserTelegram, setNewWebUserTelegram] = useState("");
  const [webUserMessage, setWebUserMessage] = useState("");

  const [accountId, setAccountId] = useState<number>(0);
  const [meCtx, setMeCtx] = useState<MeContext | null>(null);
  const [v2Users, setV2Users] = useState<V2UserItem[]>([]);
  const [v2UsersLoading, setV2UsersLoading] = useState(false);
  const [v2Msg, setV2Msg] = useState("");
  const [invites, setInvites] = useState<V2InviteItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member" | "client">("member");
  const [inviteMsg, setInviteMsg] = useState("");

  const [manualName, setManualName] = useState("");
  const [manualLogin, setManualLogin] = useState("");
  const [manualEmail, setManualEmail] = useState("");
  const [manualPass, setManualPass] = useState("");
  const [manualRole, setManualRole] = useState<"member" | "admin" | "client">("member");
  const [accountTelegramMap, setAccountTelegramMap] = useState<Record<number, string>>({});
  const [savingTelegramMembershipId, setSavingTelegramMembershipId] = useState<number>(0);
  const [accountGroups, setAccountGroups] = useState<AccountGroupItem[]>([]);
  const [groupName, setGroupName] = useState("");
  const [groupKind, setGroupKind] = useState<"staff" | "client">("staff");
  const [groupMembershipIds, setGroupMembershipIds] = useState<number[]>([]);
  const [groupMsg, setGroupMsg] = useState("");
  const [editingGroupId, setEditingGroupId] = useState<number>(0);

  const patchCache = (patch: Partial<UsersCacheState>) => {
    if (!portalId) return;
    const prev = usersCache.get(portalId) || {
      selectedUsers: [],
      telegramMap: {},
      webUsers: [],
    };
    usersCache.set(portalId, { ...prev, ...patch });
  };

  const loadAccountContext = async () => {
    const storedAccountId = getActiveAccountId();
    if (storedAccountId) {
      setAccountId(storedAccountId);
    }
    const meRes = await fetchWeb("/api/v2/web/auth/me");
    const me = await meRes.json().catch(() => null);
    if (!meRes.ok) return;
    setMeCtx((me || null) as MeContext | null);
    const aid = Number(me?.account?.id || storedAccountId || 0);
    if (!Number.isFinite(aid) || aid <= 0) return;
    setAccountId(aid);
  };

  const loadV2Users = async (aid?: number) => {
    const current = aid || accountId;
    if (!current) return;
    setV2UsersLoading(true);
    setV2Msg("");
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${current}/access-center`);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setV2Msg(data?.detail || data?.message || "Не удалось загрузить пользователей аккаунта.");
        return;
      }
      const nextItems = Array.isArray(data?.items) ? data.items : [];
      setV2Users(nextItems);
      setAccountGroups(
        Array.isArray(data?.groups)
          ? data.groups.map((group: any) => ({
              id: Number(group?.id || 0),
              name: String(group?.name || ""),
              kind: String(group?.kind || "staff") === "client" ? "client" : "staff",
              membership_ids: Array.isArray(group?.membership_ids)
                ? group.membership_ids.map((value: any) => Number(value)).filter((value: number) => Number.isFinite(value))
                : [],
              members: Array.isArray(group?.members) ? group.members : [],
            }))
          : [],
      );
      const nextSelected = nextItems.flatMap((it: V2UserItem) =>
        it.access_center?.bitrix_allowlist
          ? (it.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value))
          : [],
      );
      const nextTelegramMap: Record<number, string> = {};
      nextItems.forEach((it: V2UserItem) => {
        const username = it.access_center?.telegram_username || "";
        if (!username) return;
        (it.access_center?.bitrix_user_ids || []).forEach((value) => {
          const numeric = Number(value);
          if (Number.isFinite(numeric)) {
            nextTelegramMap[numeric] = `@${username}`;
          }
        });
      });
      const nextAccountTelegramMap: Record<number, string> = {};
      nextItems.forEach((it: V2UserItem) => {
        const username = Array.isArray(it.telegram) && it.telegram.length > 0
          ? String(it.telegram[0]?.external_id || it.telegram[0]?.display_value || "").replace(/^@/, "")
          : "";
        if (username) nextAccountTelegramMap[it.membership_id] = username;
      });
      setSelectedUsers(nextSelected);
      setTelegramMap(nextTelegramMap);
      setAccountTelegramMap(nextAccountTelegramMap);
      if (Array.isArray(data?.legacy_web_users)) {
        const nextWebUsers = data.legacy_web_users.map((it: any) => ({
          id: String(it.user_id ?? it.id),
          name: it.display_name || String(it.user_id ?? it.id),
          telegram_username: it.telegram_username || "",
        }));
        setWebUsers(nextWebUsers);
        patchCache({ selectedUsers: nextSelected, telegramMap: nextTelegramMap, webUsers: nextWebUsers });
      } else {
        patchCache({ selectedUsers: nextSelected, telegramMap: nextTelegramMap });
      }
    } finally {
      setV2UsersLoading(false);
    }
  };

  const loadInvites = async (aid?: number) => {
    const current = aid || accountId;
    if (!current) return;
    const res = await fetchWeb(`/api/v2/web/accounts/${current}/invites`);
    const data = await res.json().catch(() => null);
    if (!res.ok) return;
    setInvites(Array.isArray(data?.items) ? data.items : []);
  };

  useEffect(() => {
    if (portalId) {
      const s = usersCache.get(portalId);
      if (s) {
        setSelectedUsers(s.selectedUsers || []);
        setTelegramMap(s.telegramMap || {});
        setWebUsers(s.webUsers || []);
      }
    }
    loadAccountContext();
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!accountId) return;
    loadV2Users(accountId);
    loadInvites(accountId);
  }, [accountId]);

  useEffect(() => {
    if (!portalId) return;
    patchCache({ selectedUsers, telegramMap, webUsers });
  }, [portalId, selectedUsers, telegramMap, webUsers]);

  const saveAccess = async (focusKey?: string) => {
    if (!portalId || !portalToken) return;
    setSaving(true);
    setSavingBitrixKey(focusKey || "");
    setSaveStatus("Сохраняю...");
    const items = selectedUsers.map((id) => ({ user_id: id, telegram_username: telegramMap[id] || null }));
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/users`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setSaveStatus(data?.detail || data?.error || "Ошибка");
      } else {
        setSaveStatus("Сохранено");
        await loadV2Users(accountId);
      }
    } catch {
      setSaveStatus("Ошибка");
    } finally {
      setSaving(false);
      setSavingBitrixKey("");
    }
  };

  const addWebUser = async () => {
    if (!portalId || !portalToken) return;
    setWebUserMessage("");
    const name = newWebUserName.trim();
    if (!name) {
      setWebUserMessage("Укажите имя.");
      return;
    }
    const payload = { name, telegram_username: newWebUserTelegram.trim() || null };
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/web-users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setWebUserMessage(data?.detail || data?.error || "Ошибка добавления.");
        return;
      }
      setNewWebUserName("");
      setNewWebUserTelegram("");
      setWebUserMessage("Добавлено");
      await loadV2Users(accountId);
    } catch {
      setWebUserMessage("Ошибка добавления.");
    }
  };

  const removeWebUser = async (id: string) => {
    if (!portalId || !portalToken) return;
    setWebUserMessage("");
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/web-users/${id}`, { method: "DELETE" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setWebUserMessage(data?.detail || data?.error || "Ошибка удаления.");
        return;
      }
      await loadV2Users(accountId);
      setWebUserMessage("Удалено");
    } catch {
      setWebUserMessage("Ошибка удаления.");
    }
  };

  const patchMembership = async (membershipId: number, patch: Record<string, unknown>) => {
    if (!accountId) return;
    if (!canManageSettings) {
      setV2Msg("Недостаточно прав для изменения ролей и прав.");
      return;
    }
    setV2Msg("");
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/memberships/${membershipId}/permissions`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setV2Msg(data?.detail || data?.message || "Ошибка сохранения прав.");
      return;
    }
    await loadV2Users(accountId);
  };

  const createInvite = async () => {
    if (!accountId) return;
    if (!canInviteUsers) {
      setInviteMsg("Недостаточно прав для приглашений.");
      return;
    }
    setInviteMsg("");
    const email = inviteEmail.trim();
    if (!email) {
      setInviteMsg("Укажите email.");
      return;
    }
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/invites/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role: inviteRole, expires_days: 7 }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setInviteMsg(data?.detail || data?.message || "Ошибка отправки приглашения.");
      return;
    }
    setInviteEmail("");
    setInviteMsg("Приглашение отправлено.");
    await loadInvites(accountId);
  };

  const revokeInvite = async (id: number) => {
    if (!accountId) return;
    if (!canInviteUsers) {
      setInviteMsg("Недостаточно прав для приглашений.");
      return;
    }
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/invites/${id}/revoke`, { method: "POST" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setInviteMsg(data?.detail || data?.message || "Ошибка отзыва приглашения.");
      return;
    }
    await loadInvites(accountId);
  };

  const copyInviteLink = async (url: string | null | undefined) => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setInviteMsg("Ссылка приглашения скопирована.");
    } catch {
      setInviteMsg("Не удалось скопировать ссылку.");
    }
  };

  const createManualUser = async () => {
    if (!accountId) return;
    if (!canInviteUsers) {
      setV2Msg("Недостаточно прав для создания пользователей.");
      return;
    }
    setV2Msg("");
    const login = manualLogin.trim();
    const password = manualPass.trim();
    if (!login || !password) {
      setV2Msg("Для ручного создания нужны login и пароль.");
      return;
    }
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/users/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        display_name: manualName.trim() || null,
        login,
        email: manualEmail.trim() || null,
        password,
        role: manualRole,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setV2Msg(data?.detail || data?.message || "Ошибка создания пользователя.");
      return;
    }
    setManualName("");
    setManualLogin("");
    setManualEmail("");
    setManualPass("");
    setManualRole("member");
    await loadV2Users(accountId);
  };

  const saveMembershipTelegram = async (membershipId: number) => {
    if (!accountId) return;
    if (!canInviteUsers) {
      setV2Msg("Недостаточно прав для привязки Telegram.");
      return;
    }
    setSavingTelegramMembershipId(membershipId);
    setV2Msg("");
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/memberships/${membershipId}/telegram`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_username: (accountTelegramMap[membershipId] || "").trim() || null }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setV2Msg(data?.detail || data?.message || "Ошибка сохранения Telegram.");
        return;
      }
      await loadV2Users(accountId);
    } finally {
      setSavingTelegramMembershipId(0);
    }
  };

  const resetGroupEditor = () => {
    setEditingGroupId(0);
    setGroupName("");
    setGroupKind("staff");
    setGroupMembershipIds([]);
  };

  const toggleGroupMembership = (membershipId: number, checked: boolean) => {
    setGroupMembershipIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(membershipId);
      else next.delete(membershipId);
      return Array.from(next).sort((a, b) => a - b);
    });
  };

  const startEditGroup = (group: AccountGroupItem) => {
    setEditingGroupId(group.id);
    setGroupName(group.name);
    setGroupKind(group.kind || "staff");
    setGroupMembershipIds([...(group.membership_ids || [])].sort((a, b) => a - b));
    setGroupMsg("");
  };

  const saveGroup = async () => {
    if (!accountId || !canManageSettings) {
      setGroupMsg("Недостаточно прав для управления группами.");
      return;
    }
    const name = groupName.trim();
    if (!name) {
      setGroupMsg("Укажите название группы.");
      return;
    }
    setGroupMsg("");
    const method = editingGroupId ? "PATCH" : "POST";
    const path = editingGroupId
      ? `/api/v2/web/accounts/${accountId}/user-groups/${editingGroupId}`
      : `/api/v2/web/accounts/${accountId}/user-groups`;
    const res = await fetchWeb(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, kind: groupKind, membership_ids: groupMembershipIds }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setGroupMsg(data?.detail || data?.message || "Ошибка сохранения группы.");
      return;
    }
    resetGroupEditor();
    setGroupMsg(editingGroupId ? "Группа обновлена." : "Группа создана.");
    await loadV2Users(accountId);
  };

  const deleteGroup = async (groupId: number) => {
    if (!accountId || !canManageSettings) {
      setGroupMsg("Недостаточно прав для управления группами.");
      return;
    }
    setGroupMsg("");
    const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/user-groups/${groupId}`, {
      method: "DELETE",
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setGroupMsg(data?.detail || data?.message || "Ошибка удаления группы.");
      return;
    }
    if (editingGroupId === groupId) resetGroupEditor();
    setGroupMsg("Группа удалена.");
    await loadV2Users(accountId);
  };

  const canInviteUsers = !!meCtx?.membership?.can_invite_users;
  const canManageSettings = !!meCtx?.membership?.can_manage_settings;
  const activeUsers = v2Users.filter((u) => u.status === "active");
  const clientUsersCount = activeUsers.filter((u) => u.role === "client").length;
  const staffUsersCount = activeUsers.filter((u) => u.role !== "client").length;
  const invitedUsersCount = v2Users.filter((u) => u.status === "invited").length;
  const bitrixLinkedCount = v2Users.filter((u) => !!u.access_center?.bitrix_linked).length;
  const clientTelegramLinkedCount = activeUsers.filter(
    (u) => u.role === "client" && !!String(accountTelegramMap[u.membership_id] || "").trim(),
  ).length;
  const clientGroups = accountGroups.filter((group) => group.kind === "client");
  const clientGroupCount = clientGroups.length;
  const clientGroupedMembershipCount = new Set(clientGroups.flatMap((group) => group.membership_ids || [])).size;
  const selectableGroupUsers = v2Users.filter((u) => (groupKind === "client" ? u.role === "client" : u.role !== "client"));

  const roleLabel = (role: string) => {
    if (role === "owner") return "Владелец";
    if (role === "admin") return "Администратор";
    if (role === "client") return "Клиент";
    return "Сотрудник";
  };
  const kbAccessLabel = (mode: string) => {
    if (mode === "write") return "Полный";
    if (mode === "read") return "Чтение";
    return "Нет";
  };
  const statusLabel = (status: string) => {
    if (status === "active") return "Активен";
    if (status === "invited") return "Приглашен";
    if (status === "blocked") return "Заблокирован";
    if (status === "deleted") return "Удален";
    return status;
  };
  const renderIdentityTag = (kind: "web" | "bitrix" | "telegram" | "amo", label: string) => {
    const tone =
      kind === "web"
        ? "border-sky-200 bg-sky-50 text-sky-700"
        : kind === "bitrix"
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : kind === "telegram"
            ? "border-cyan-200 bg-cyan-50 text-cyan-700"
            : "border-violet-200 bg-violet-50 text-violet-700";
    return <span className={`rounded-full border px-2 py-0.5 text-[11px] ${tone}`}>{label}</span>;
  };
  const renderIdentityValue = (items: LinkedIdentity[] | undefined, fallbackPrefix: string) => {
    if (!Array.isArray(items) || items.length === 0) return "—";
    return items
      .map((it) => it.display_value || it.external_id || `${fallbackPrefix}:${it.id}`)
      .filter(Boolean)
      .join(", ");
  };
  const renderBitrixAccess = (u: V2UserItem) => {
    const access = u.access_center;
    if (!access?.bitrix_linked) return "Bitrix не привязан";
    if (access.bitrix_allowlist) {
      return `Bitrix в доступе${access.telegram_username ? ` · @${access.telegram_username}` : ""}`;
    }
    return "Bitrix привязан, но не в allowlist";
  };
  const toggleBitrixAllow = (u: V2UserItem, checked: boolean) => {
    const ids = (u.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value));
    if (ids.length === 0) return;
    setSelectedUsers((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => {
        if (checked) next.add(id);
        else next.delete(id);
      });
      return Array.from(next);
    });
  };
  const setBitrixTelegram = (u: V2UserItem, value: string) => {
    const ids = (u.access_center?.bitrix_user_ids || []).map((entry) => Number(entry)).filter((entry) => Number.isFinite(entry));
    if (ids.length === 0) return;
    setTelegramMap((prev) => {
      const next = { ...prev };
      ids.forEach((id) => {
        next[id] = value;
      });
      return next;
    });
  };
  const resolveBitrixTelegram = (u: V2UserItem) => {
    const ids = (u.access_center?.bitrix_user_ids || []).map((value) => Number(value)).filter((value) => Number.isFinite(value));
    for (const id of ids) {
      const current = telegramMap[id];
      if (current) return current;
    }
    return "";
  };

  return (
    <div className="space-y-6">
      <PageIntro
        moduleId="users"
        fallbackTitle="Пользователи и доступы"
        fallbackDescription="Роли, права и доступы для участников аккаунта."
      />

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900">Доп. пользователи (Telegram)</h2>
          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs text-slate-600">Имя</label>
              <input className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" placeholder="Например: Иван Петров" value={newWebUserName} onChange={(e) => setNewWebUserName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-slate-600">Telegram username</label>
              <input className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" placeholder="@username" value={newWebUserTelegram} onChange={(e) => setNewWebUserTelegram(e.target.value)} />
            </div>
            <div className="flex items-center gap-3">
              <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700" onClick={addWebUser}>Добавить</button>
              {webUserMessage && <div className="text-xs text-slate-500">{webUserMessage}</div>}
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {webUsers.length === 0 && <div className="text-sm text-slate-500">Пока нет дополнительных пользователей.</div>}
            {webUsers.map((u) => (
              <div key={u.id} className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2">
                <div>
                  <div className="text-sm text-slate-900">{u.name}</div>
                  {u.telegram_username && <div className="text-xs text-slate-500">@{u.telegram_username}</div>}
                </div>
                <button className="rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50" onClick={() => removeWebUser(u.id)}>Удалить</button>
              </div>
            ))}
          </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Группы доступа</h2>
            <p className="mt-1 text-xs text-slate-500">
              Группы нужны для настройки доступа к папкам и файлам базы знаний по отделам и командам.
            </p>
          </div>
          {editingGroupId > 0 && (
            <button
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={resetGroupEditor}
            >
              Отменить редактирование
            </button>
          )}
        </div>
        {!canManageSettings && (
          <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Недостаточно прав для управления группами.
          </div>
        )}

        <div className="mt-4 grid gap-6 xl:grid-cols-[minmax(0,360px)_1fr]">
          <div className="space-y-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
            <div>
              <label className="text-xs text-slate-600">Название группы</label>
              <input
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                placeholder="Например: Отдел продаж"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                disabled={!canManageSettings}
              />
            </div>
            <div>
              <label className="text-xs text-slate-600">Тип группы</label>
              <select
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                value={groupKind}
                onChange={(e) => {
                  const nextKind = e.target.value as "staff" | "client";
                  setGroupKind(nextKind);
                  setGroupMembershipIds((prev) =>
                    prev.filter((membershipId) => {
                      const user = v2Users.find((item) => item.membership_id === membershipId);
                      return nextKind === "client" ? user?.role === "client" : user?.role !== "client";
                    }),
                  );
                }}
                disabled={!canManageSettings}
              >
                <option value="staff">Отдел / группа сотрудников</option>
                <option value="client">Группа клиентов</option>
              </select>
            </div>
            <div>
              <div className="text-xs text-slate-600">Участники группы</div>
              <div className="mt-2 max-h-64 space-y-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3">
                {selectableGroupUsers.length === 0 && <div className="text-xs text-slate-500">Нет подходящих участников для этого типа группы.</div>}
                {selectableGroupUsers.map((u) => (
                  <label key={u.membership_id} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1 hover:bg-slate-50">
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-slate-800">{u.display_name || u.web?.email || "Без имени"}</span>
                      <span className="text-[11px] text-slate-500">{roleLabel(u.role)}</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={groupMembershipIds.includes(u.membership_id)}
                      disabled={!canManageSettings}
                      onChange={(e) => toggleGroupMembership(u.membership_id, e.target.checked)}
                    />
                  </label>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50"
                onClick={saveGroup}
                disabled={!canManageSettings}
              >
                {editingGroupId ? "Сохранить группу" : "Создать группу"}
              </button>
              {groupMsg && <div className="text-xs text-slate-500">{groupMsg}</div>}
            </div>
          </div>

          <div className="space-y-3">
            {accountGroups.length === 0 && (
              <div className="rounded-xl border border-slate-100 px-4 py-3 text-sm text-slate-500">
                Групп пока нет.
              </div>
            )}
            {accountGroups.map((group) => (
              <div key={group.id} className="rounded-2xl border border-slate-100 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{group.name}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {group.kind === "client" ? "Группа клиентов" : "Группа сотрудников"} · Участников: {group.membership_ids.length}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      onClick={() => startEditGroup(group)}
                      disabled={!canManageSettings}
                    >
                      Изменить
                    </button>
                    <button
                      className="rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                      onClick={() => deleteGroup(group.id)}
                      disabled={!canManageSettings}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {group.membership_ids.length === 0 && <span className="text-xs text-slate-500">Нет участников.</span>}
                  {group.membership_ids.map((membershipId) => {
                    const user = v2Users.find((item) => item.membership_id === membershipId);
                    const label = user?.display_name || user?.web?.email || `Участник ${membershipId}`;
                    return (
                      <span key={membershipId} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
                        {label}
                      </span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Пользователи аккаунта (RBAC v2)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Роли и права для web-аккаунта: база знаний, настройки, приглашения, финансы. Роль
          <span className="mx-1 font-medium text-slate-700">Клиент</span>
          нужна для клиентского бота и доступа только к разрешенным материалам.
        </p>
        {!canManageSettings && !canInviteUsers && (
          <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Недостаточно прав для управления пользователями.
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">Сотрудники</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">{staffUsersCount}</div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">Клиенты</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">{clientUsersCount}</div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">Приглашены</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">{invitedUsersCount}</div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">Привязаны к Bitrix</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">{bitrixLinkedCount}</div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-900">Готовность клиентского бота</div>
              <p className="mt-1 text-xs text-slate-600">
                Чтобы клиентский бот отвечал только по разрешенным материалам, клиенту нужен аккаунт, Telegram username,
                клиентская группа и доступ к папкам или файлам в базе знаний.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a href="/app/settings/integrations" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50">
                Интеграции
              </a>
              <a href="/app/kb" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50">
                База знаний
              </a>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">Клиенты</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">{clientUsersCount}</div>
              <div className="mt-1 text-xs text-slate-500">
                {clientUsersCount > 0 ? "Аккаунты клиентов созданы." : "Создайте хотя бы одного клиента."}
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">Telegram username</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">{clientTelegramLinkedCount}</div>
              <div className="mt-1 text-xs text-slate-500">
                {clientTelegramLinkedCount > 0
                  ? "Клиенты связаны с Telegram."
                  : "Назначьте @telegram для клиентов в таблице ниже."}
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">Клиентские группы</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">{clientGroupCount}</div>
              <div className="mt-1 text-xs text-slate-500">
                {clientGroupCount > 0 ? "Группы можно использовать в правилах KB." : "Создайте группу клиентов для сегментации материалов."}
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">Клиентов в группах</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">{clientGroupedMembershipCount}</div>
              <div className="mt-1 text-xs text-slate-500">
                {clientGroupedMembershipCount > 0
                  ? "Можно открывать материалы клиентским группам."
                  : "Добавьте клиентов в одну или несколько групп."}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Имя" value={manualName} onChange={(e) => setManualName(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Логин" value={manualLogin} onChange={(e) => setManualLogin(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Email (опционально)" value={manualEmail} onChange={(e) => setManualEmail(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Пароль" type="password" value={manualPass} onChange={(e) => setManualPass(e.target.value)} disabled={!canInviteUsers} />
        </div>
        <div className="mt-3 max-w-xs">
          <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm disabled:opacity-60" value={manualRole} onChange={(e) => setManualRole(e.target.value as "member" | "admin" | "client")} disabled={!canInviteUsers}>
            <option value="member">Сотрудник</option>
            <option value="admin">Администратор</option>
            <option value="client">Клиент</option>
          </select>
        </div>
        {manualRole === "client" && (
          <div className="mt-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-700">
            Клиент не получает доступ к базе знаний по умолчанию. Доступ открывается через правила папок и файлов в разделе
            <span className="mx-1 font-medium">База знаний</span>
            и используется клиентским ботом.
          </div>
        )}
        <div className="mt-3">
          <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50" onClick={createManualUser} disabled={!canInviteUsers}>Создать пользователя</button>
        </div>
        <div className="mt-4 flex items-center gap-3 text-xs text-slate-500">
          <div>Выбрано Bitrix ID: {selectedUsers.length}</div>
          {saveStatus && <div>{saveStatus}</div>}
        </div>

        <div className="mt-4 overflow-auto rounded-xl border border-slate-100">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Пользователь</th>
                <th className="px-3 py-2 text-left">Роль</th>
                <th className="px-3 py-2 text-left">База знаний</th>
                <th className="px-3 py-2 text-left">Права</th>
                <th className="px-3 py-2 text-left">Bitrix</th>
                <th className="px-3 py-2 text-left">Статус</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {!v2UsersLoading && v2Users.length === 0 && (
                <tr><td className="px-3 py-3 text-slate-500" colSpan={7}>Нет данных.</td></tr>
              )}
              {v2Users.map((u) => (
                <tr key={u.membership_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <div className="text-slate-800">{u.display_name || "Без имени"}</div>
                    <div className="text-xs text-slate-500">{u.web?.email || u.web?.login || "—"}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {u.web && renderIdentityTag("web", "Web")}
                      {Array.isArray(u.bitrix) && u.bitrix.length > 0 && renderIdentityTag("bitrix", `Bitrix: ${u.bitrix.length}`)}
                      {Array.isArray(u.telegram) && u.telegram.length > 0 && renderIdentityTag("telegram", `Telegram: ${u.telegram.length}`)}
                      {Array.isArray(u.amo) && u.amo.length > 0 && renderIdentityTag("amo", `Amo: ${u.amo.length}`)}
                    </div>
                    <div className="mt-2 space-y-1 text-[11px] text-slate-500">
                      {u.web && (
                        <div>
                          <span className="font-medium text-slate-600">Web:</span> {u.web.email || u.web.login || "—"}
                        </div>
                      )}
                      {Array.isArray(u.bitrix) && u.bitrix.length > 0 && (
                        <div>
                          <span className="font-medium text-slate-600">Bitrix:</span> {renderIdentityValue(u.bitrix, "bitrix")}
                        </div>
                      )}
                      {Array.isArray(u.telegram) && u.telegram.length > 0 && (
                        <div>
                          <span className="font-medium text-slate-600">Telegram:</span> {renderIdentityValue(u.telegram, "telegram")}
                        </div>
                      )}
                      {Array.isArray(u.amo) && u.amo.length > 0 && (
                        <div>
                          <span className="font-medium text-slate-600">Amo:</span> {renderIdentityValue(u.amo, "amo")}
                        </div>
                      )}
                      {Array.isArray(u.groups) && u.groups.length > 0 && (
                      <div>
                        <span className="font-medium text-slate-600">Группы:</span>{" "}
                          {u.groups.map((group) => `${group.name}${group.kind === "client" ? " (клиенты)" : ""}`).join(", ")}
                      </div>
                      )}
                      <div>
                        <span className="font-medium text-slate-600">Доступ:</span> {renderBitrixAccess(u)}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <select className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs" value={u.role} disabled={u.role === "owner" || !canManageSettings} onChange={(e) => patchMembership(u.membership_id, { role: e.target.value })}>
                      <option value="owner">Владелец</option>
                      <option value="admin">Администратор</option>
                      <option value="member">Сотрудник</option>
                      <option value="client">Клиент</option>
                    </select>
                    <div className="mt-1 text-[11px] text-slate-500">{roleLabel(u.role)}</div>
                  </td>
                  <td className="px-3 py-2">
                    <select className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs" value={u.permissions.kb_access} disabled={u.role === "owner" || !canManageSettings} onChange={(e) => patchMembership(u.membership_id, { kb_access: e.target.value })}>
                      <option value="none">Нет доступа</option>
                      <option value="read">Чтение</option>
                      <option value="write">Полный доступ</option>
                    </select>
                    <div className="mt-1 text-[11px] text-slate-500">{kbAccessLabel(u.permissions.kb_access)}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                      <label className="inline-flex items-center gap-1"><input type="checkbox" checked={!!u.permissions.can_invite_users} disabled={u.role === "owner" || !canManageSettings} onChange={(e) => patchMembership(u.membership_id, { can_invite_users: e.target.checked })} /> Приглашения</label>
                      <label className="inline-flex items-center gap-1"><input type="checkbox" checked={!!u.permissions.can_manage_settings} disabled={u.role === "owner" || !canManageSettings} onChange={(e) => patchMembership(u.membership_id, { can_manage_settings: e.target.checked })} /> Настройки</label>
                      <label className="inline-flex items-center gap-1"><input type="checkbox" checked={!!u.permissions.can_view_finance} disabled={u.role === "owner" || !canManageSettings} onChange={(e) => patchMembership(u.membership_id, { can_view_finance: e.target.checked })} /> Финансы</label>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {u.access_center?.bitrix_linked ? (
                      <div className="space-y-2 text-xs text-slate-600">
                        <label className="inline-flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={!!u.access_center?.bitrix_allowlist}
                            disabled={!canManageSettings}
                            onChange={(e) => toggleBitrixAllow(u, e.target.checked)}
                          />
                          <span>{renderBitrixAccess(u)}</span>
                        </label>
                        <input
                          className="w-40 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs disabled:opacity-60"
                          placeholder="@telegram"
                          value={resolveBitrixTelegram(u)}
                          disabled={!canManageSettings}
                          onChange={(e) => setBitrixTelegram(u, e.target.value)}
                        />
                        <button
                          className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                          disabled={!canManageSettings || saving}
                          onClick={() => saveAccess(`bitrix:${u.membership_id}`)}
                        >
                          {saving && savingBitrixKey === `bitrix:${u.membership_id}` ? "Сохраняю..." : "Сохранить"}
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-500">Bitrix не привязан</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{statusLabel(u.status)}</td>
                  <td className="px-3 py-2">
                    <div className="space-y-2">
                      {u.role === "client" && (
                        <div className="space-y-1">
                          <input
                            className="w-40 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs disabled:opacity-60"
                            placeholder="@telegram"
                            value={accountTelegramMap[u.membership_id] || ""}
                            disabled={!canInviteUsers}
                            onChange={(e) => setAccountTelegramMap((prev) => ({ ...prev, [u.membership_id]: e.target.value.replace(/^@+/, "") }))}
                          />
                          <button
                            className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                            disabled={!canInviteUsers || savingTelegramMembershipId === u.membership_id}
                            onClick={() => saveMembershipTelegram(u.membership_id)}
                          >
                            {savingTelegramMembershipId === u.membership_id ? "Сохраняю..." : "Telegram"}
                          </button>
                        </div>
                      )}
                      {u.role !== "owner" && canManageSettings && (
                        <button className="rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50" onClick={async () => {
                          const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/users/${u.user_id}`, { method: "DELETE" });
                          const data = await res.json().catch(() => null);
                          if (!res.ok) {
                            setV2Msg(data?.detail || data?.message || "Ошибка удаления пользователя.");
                            return;
                          }
                          await loadV2Users(accountId);
                        }}>Удалить</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {v2Msg && <div className="mt-3 text-xs text-rose-600">{v2Msg}</div>}
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Приглашения</h2>
        {!canInviteUsers && (
          <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            У вас нет права отправлять приглашения.
          </div>
        )}
        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm lg:col-span-2 disabled:opacity-60" placeholder="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} disabled={!canInviteUsers} />
          <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm disabled:opacity-60" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as "admin" | "member" | "client")} disabled={!canInviteUsers}>
            <option value="member">Сотрудник</option>
            <option value="admin">Администратор</option>
            <option value="client">Клиент</option>
          </select>
          <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50" onClick={createInvite} disabled={!canInviteUsers}>Отправить</button>
        </div>
        {inviteRole === "client" && (
          <div className="mt-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-700">
            Приглашенный клиент будет видеть только те материалы, для которых в базе знаний открыт клиентский доступ.
          </div>
        )}
        {inviteMsg && <div className="mt-2 text-xs text-slate-500">{inviteMsg}</div>}

        <div className="mt-4 space-y-2">
          {invites.length === 0 && <div className="text-sm text-slate-500">Приглашений пока нет.</div>}
          {invites.map((inv) => (
            <div key={inv.id} className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2">
              <div>
                <div className="text-sm text-slate-800">{inv.email || "—"}</div>
                <div className="text-xs text-slate-500">role: {inv.role} · status: {inv.status}</div>
              </div>
              <div className="flex items-center gap-2">
                {inv.status === "pending" && (
                  <button
                    className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    onClick={() => copyInviteLink(inv.accept_url)}
                  >
                    Копировать ссылку
                  </button>
                )}
                {inv.status === "pending" && (
                  <button
                    className="rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                    onClick={() => revokeInvite(inv.id)}
                  >
                    Отозвать
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
