import { useEffect, useMemo, useState } from "react";
import { fetchPortal, fetchWeb, getWebPortalInfo } from "./auth";

type UserItem = { id: number; name: string };
type AccessItem = { user_id: string | number; telegram_username?: string | null; display_name?: string | null; kind?: string | null };

type WebUserItem = { id: string; name: string; telegram_username?: string | null };
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
        // fallback to last saved list
        const fallbackRes = await fetchWeb(`/api/v1/web/portals/${portalId}/access/users`);
        const fallback = await fallbackRes.json().catch(() => null);
        if (fallbackRes.ok && Array.isArray(fallback?.items)) {
          const items = fallback.items.filter((it: AccessItem) => (it.kind || "bitrix") === "bitrix");
          const mapped = items
            .map((it: AccessItem) => ({
              id: Number(it.user_id),
              name: it.display_name || String(it.user_id),
            }))
            .filter((u: UserItem) => Number.isFinite(u.id));
          setUsers(mapped);
          setAccessWarning(`${errText} Показан последний сохранённый список.`);
          patchCache({
            users: mapped,
            accessWarning: `${errText} Показан последний сохранённый список.`,
          });
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
    const nextWebUsers =
      items
        .filter((it) => it.kind === "web")
        .map((it) => ({
          id: String(it.user_id),
          name: it.display_name || String(it.user_id),
          telegram_username: it.telegram_username || "",
        }));
    setWebUsers(nextWebUsers);
    patchCache({
      selectedUsers: bitrixIds,
      telegramMap: tgMap,
      webUsers: nextWebUsers,
    });
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
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!portalId) return;
    patchCache({ selectedUsers, telegramMap, webUsers, users, accessWarning });
  }, [portalId, selectedUsers, telegramMap, webUsers, users, accessWarning]);

  const toggleUser = (id: number) => {
    setSelectedUsers((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const saveAccess = async () => {
    if (!portalId || !portalToken) return;
    setSaving(true);
    setSaveStatus("Сохраняю...");
    const items = selectedUsers.map((id) => ({
      user_id: id,
      telegram_username: telegramMap[id] || null,
    }));
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
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/web-users/${id}`, {
        method: "DELETE",
      });
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

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Доступ (Bitrix)</h2>
        {accessWarning && (
          <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">{accessWarning}</div>
        )}
        <input
          className="mt-4 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
          placeholder="Поиск по имени..."
          value={userSearch}
          onChange={(e) => setUserSearch(e.target.value)}
        />
        <div className="mt-4 space-y-3 max-h-[420px] overflow-auto">
          {filteredUsers.length === 0 && (
            <div className="text-sm text-slate-500">Сотрудников пока нет.</div>
          )}
          {filteredUsers.map((u) => (
            <div key={u.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={selectedUsers.includes(u.id)}
                  onChange={() => toggleUser(u.id)}
                />
                <span>{u.name}</span>
              </label>
              <input
                className="w-40 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs"
                placeholder="@telegram"
                value={telegramMap[u.id] || ""}
                onChange={(e) => setTelegramMap((prev) => ({ ...prev, [u.id]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50"
            onClick={saveAccess}
            disabled={saving}
          >
            {saving ? "Сохраняю..." : "Сохранить доступ"}
          </button>
          <div className="text-xs text-slate-500">Выбрано: {selectedUsers.length}</div>
          {saveStatus && <div className="text-xs text-slate-500">{saveStatus}</div>}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Доп. пользователи (Telegram)</h2>
        <div className="mt-4 space-y-3">
          <div>
            <label className="text-xs text-slate-600">Имя</label>
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="Например: Иван Петров"
              value={newWebUserName}
              onChange={(e) => setNewWebUserName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-slate-600">Telegram username</label>
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="@username"
              value={newWebUserTelegram}
              onChange={(e) => setNewWebUserTelegram(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3">
            <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700" onClick={addWebUser}>
              Добавить
            </button>
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
              <button
                className="rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                onClick={() => removeWebUser(u.id)}
              >
                Удалить
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
