import { useEffect, useMemo, useState } from "react";
import { fetchPortal, fetchWeb, getWebPortalInfo } from "./auth";

type UserItem = { id: number; name: string };
type AccessItem = { user_id: string | number; telegram_username?: string | null; display_name?: string | null; kind?: string | null };
type WebUserItem = { id: string; name: string; telegram_username?: string | null };
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
  users: UserItem[];
  selectedUsers: number[];
  telegramMap: Record<number, string>;
  webUsers: WebUserItem[];
  accessWarning: string;
};

const usersCache = new Map<number, UsersCacheState>();

export function WebUsersPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const cached = portalId ? usersCache.get(portalId) : null;

  const [users, setUsers] = useState<UserItem[]>(cached?.users || []);
  const [userSearch, setUserSearch] = useState("");
  const [selectedUsers, setSelectedUsers] = useState<number[]>(cached?.selectedUsers || []);
  const [telegramMap, setTelegramMap] = useState<Record<number, string>>(cached?.telegramMap || {});
  const [accessWarning, setAccessWarning] = useState(cached?.accessWarning || "");
  const [saveStatus, setSaveStatus] = useState("");
  const [saving, setSaving] = useState(false);

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
      users: [],
      selectedUsers: [],
      telegramMap: {},
      webUsers: [],
      accessWarning: "",
    };
    usersCache.set(portalId, { ...prev, ...patch });
  };

  const filteredUsers = useMemo(() => {
    const q = userSearch.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => u.name.toLowerCase().includes(q));
  }, [users, userSearch]);

  const loadUsers = async () => {
    if (!portalId || !portalToken) return;
    try {
      const res = await fetchPortal(`/api/v1/bitrix/users?portal_id=${portalId}`);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const errCode = data?.error || "";
        const errMap: Record<string, string> = {
          missing_client_credentials: "Bitrix API недоступен: не задан client_id/client_secret (Админка → Portal → OAuth).",
          missing_refresh_token: "Bitrix API недоступен: нет refresh_token. Откройте приложение в Bitrix24 или переустановите.",
          bitrix_auth_invalid: "Bitrix API недоступен: токен протух. Откройте приложение в Bitrix24, чтобы обновить токен.",
        };
        const errText = errMap[errCode] || data?.detail || data?.error || "Bitrix API недоступен.";
        const fallbackRes = await fetchWeb(`/api/v1/web/portals/${portalId}/access/users`);
        const fallback = await fallbackRes.json().catch(() => null);
        if (fallbackRes.ok && Array.isArray(fallback?.items)) {
          const items = fallback.items.filter((it: AccessItem) => (it.kind || "bitrix") === "bitrix");
          const mapped = items
            .map((it: AccessItem) => ({ id: Number(it.user_id), name: it.display_name || String(it.user_id) }))
            .filter((u: UserItem) => Number.isFinite(u.id));
          setUsers(mapped);
          setAccessWarning(`${errText} Показан последний сохранённый список.`);
          patchCache({ users: mapped, accessWarning: `${errText} Показан последний сохранённый список.` });
          return;
        }
        setAccessWarning(errText || "Не удалось загрузить пользователей.");
        patchCache({ accessWarning: errText || "Не удалось загрузить пользователей." });
        return;
      }
      const list = (data?.users || []).map((u: any) => ({
        id: Number(u.id),
        name: `${u.name || ""} ${u.last_name || ""}`.trim() || u.email || `ID ${u.id}`,
      }));
      setUsers(list);
      setAccessWarning("");
      patchCache({ users: list, accessWarning: "" });
    } catch {
      setAccessWarning("Не удалось загрузить пользователей.");
      patchCache({ accessWarning: "Не удалось загрузить пользователей." });
    }
  };

  const loadAllowlist = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/users`);
    const data = await res.json().catch(() => null);
    if (!res.ok) return;
    const items: AccessItem[] = Array.isArray(data?.items) ? data.items : [];
    const bitrixIds = items
      .filter((it) => (it.kind || "bitrix") === "bitrix")
      .map((it) => Number(it.user_id))
      .filter((n) => Number.isFinite(n));
    setSelectedUsers(bitrixIds);
    const tgMap: Record<number, string> = {};
    items.forEach((it) => {
      if ((it.kind || "bitrix") !== "bitrix") return;
      const id = Number(it.user_id);
      if (!Number.isFinite(id)) return;
      const raw = it.telegram_username || "";
      tgMap[id] = raw ? `@${raw}` : "";
    });
    setTelegramMap(tgMap);
    const nextWebUsers = items
      .filter((it) => it.kind === "web")
      .map((it) => ({ id: String(it.user_id), name: it.display_name || String(it.user_id), telegram_username: it.telegram_username || "" }));
    setWebUsers(nextWebUsers);
    patchCache({ selectedUsers: bitrixIds, telegramMap: tgMap, webUsers: nextWebUsers });
  };

  const loadAccountContext = async () => {
    const meRes = await fetchWeb("/api/v2/web/auth/me");
    const me = await meRes.json().catch(() => null);
    if (!meRes.ok || !me?.account?.id) return;
    setMeCtx(me as MeContext);
    const aid = Number(me.account.id);
    if (!Number.isFinite(aid) || aid <= 0) return;
    setAccountId(aid);
  };

  const loadV2Users = async (aid?: number) => {
    const current = aid || accountId;
    if (!current) return;
    setV2UsersLoading(true);
    setV2Msg("");
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${current}/users`);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setV2Msg(data?.detail || data?.message || "Не удалось загрузить пользователей аккаунта.");
        return;
      }
      setV2Users(Array.isArray(data?.items) ? data.items : []);
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
        setUsers(s.users || []);
        setSelectedUsers(s.selectedUsers || []);
        setTelegramMap(s.telegramMap || {});
        setWebUsers(s.webUsers || []);
        setAccessWarning(s.accessWarning || "");
      }
    }
    loadUsers();
    loadAllowlist();
    loadAccountContext();
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!accountId) return;
    loadV2Users(accountId);
    loadInvites(accountId);
  }, [accountId]);

  useEffect(() => {
    if (!portalId) return;
    patchCache({ selectedUsers, telegramMap, webUsers, users, accessWarning });
  }, [portalId, selectedUsers, telegramMap, webUsers, users, accessWarning]);

  const toggleUser = (id: number) => {
    setSelectedUsers((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const saveAccess = async () => {
    if (!portalId || !portalToken) return;
    setSaving(true);
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
      }
    } catch {
      setSaveStatus("Ошибка");
    } finally {
      setSaving(false);
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
      await loadAllowlist();
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
      await loadAllowlist();
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

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900">Доступ (Bitrix)</h2>
          {accessWarning && <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">{accessWarning}</div>}
          <input className="mt-4 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" placeholder="Поиск по имени..." value={userSearch} onChange={(e) => setUserSearch(e.target.value)} />
          <div className="mt-4 max-h-[420px] space-y-3 overflow-auto">
            {filteredUsers.length === 0 && <div className="text-sm text-slate-500">Сотрудников пока нет.</div>}
            {filteredUsers.map((u) => (
              <div key={u.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2">
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={selectedUsers.includes(u.id)} onChange={() => toggleUser(u.id)} />
                  <span>{u.name}</span>
                </label>
                <input className="w-40 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs" placeholder="@telegram" value={telegramMap[u.id] || ""} onChange={(e) => setTelegramMap((prev) => ({ ...prev, [u.id]: e.target.value }))} />
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50" onClick={saveAccess} disabled={saving}>{saving ? "Сохраняю..." : "Сохранить доступ"}</button>
            <div className="text-xs text-slate-500">Выбрано: {selectedUsers.length}</div>
            {saveStatus && <div className="text-xs text-slate-500">{saveStatus}</div>}
          </div>
        </div>

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

        <div className="mt-4 overflow-auto rounded-xl border border-slate-100">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Пользователь</th>
                <th className="px-3 py-2 text-left">Роль</th>
                <th className="px-3 py-2 text-left">База знаний</th>
                <th className="px-3 py-2 text-left">Права</th>
                <th className="px-3 py-2 text-left">Статус</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {!v2UsersLoading && v2Users.length === 0 && (
                <tr><td className="px-3 py-3 text-slate-500" colSpan={6}>Нет данных.</td></tr>
              )}
              {v2Users.map((u) => (
                <tr key={u.membership_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <div className="text-slate-800">{u.display_name || "Без имени"}</div>
                    <div className="text-xs text-slate-500">{u.web?.email || u.web?.login || "—"}</div>
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
