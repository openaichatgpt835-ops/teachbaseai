import { useEffect, useState } from "react";
import { PageIntro } from "../../components/PageIntro";
import { fetchPortal, fetchWeb, getActiveAccountId, getWebPortalInfo } from "./auth";

type WebUserItem = { id: string; name: string; telegram_username?: string | null };
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
  role: "owner" | "admin" | "member";
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
};
type V2InviteItem = { id: number; email?: string | null; role: string; status: string; expires_at?: string | null; accept_url?: string | null };
type MeContext = {
  account?: { id?: number | null } | null;
  membership?: {
    role?: "owner" | "admin" | "member";
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
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [inviteMsg, setInviteMsg] = useState("");

  const [manualName, setManualName] = useState("");
  const [manualLogin, setManualLogin] = useState("");
  const [manualEmail, setManualEmail] = useState("");
  const [manualPass, setManualPass] = useState("");

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
      setSelectedUsers(nextSelected);
      setTelegramMap(nextTelegramMap);
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
        role: "member",
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
    await loadV2Users(accountId);
  };

  const canInviteUsers = !!meCtx?.membership?.can_invite_users;
  const canManageSettings = !!meCtx?.membership?.can_manage_settings;

  const roleLabel = (role: string) => {
    if (role === "owner") return "Владелец";
    if (role === "admin") return "Администратор";
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
        <h2 className="text-sm font-semibold text-slate-900">Пользователи аккаунта (RBAC v2)</h2>
        <p className="mt-1 text-xs text-slate-500">Роли и права для web-аккаунта: база знаний, настройки, приглашения, финансы.</p>
        {!canManageSettings && !canInviteUsers && (
          <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Недостаточно прав для управления пользователями.
          </div>
        )}

        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Имя" value={manualName} onChange={(e) => setManualName(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Логин" value={manualLogin} onChange={(e) => setManualLogin(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Email (опционально)" value={manualEmail} onChange={(e) => setManualEmail(e.target.value)} disabled={!canInviteUsers} />
          <input className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-60" placeholder="Пароль" type="password" value={manualPass} onChange={(e) => setManualPass(e.target.value)} disabled={!canInviteUsers} />
        </div>
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
          <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm disabled:opacity-60" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as "admin" | "member")} disabled={!canInviteUsers}>
            <option value="member">Сотрудник</option>
            <option value="admin">Администратор</option>
          </select>
          <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50" onClick={createInvite} disabled={!canInviteUsers}>Отправить</button>
        </div>
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
