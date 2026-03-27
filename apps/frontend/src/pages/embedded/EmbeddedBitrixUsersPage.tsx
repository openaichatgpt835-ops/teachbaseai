import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { EmbeddedBitrixContext } from "./EmbeddedBitrixGate";
import { fetchPortal } from "../web/auth";

type BitrixPortalUser = {
  id: number | string;
  name?: string;
  last_name?: string;
  email?: string;
  active?: boolean;
};

type AccessItem = {
  user_id: string;
  telegram_username?: string | null;
  display_name?: string | null;
  kind?: string | null;
};

const LABELS = {
  title: "Пользователи Bitrix24",
  subtitle: "Управление доступом сотрудников текущего Bitrix-портала. Доступно только администратору портала.",
  adminOnly: "Управление пользователями Bitrix24 доступно только администратору текущего портала.",
  refresh: "Обновить",
  save: "Сохранить доступ",
  saving: "Сохраняю...",
  search: "Поиск по имени или email",
  access: "Доступ",
  telegram: "Telegram username",
  employee: "Сотрудник",
  empty: "Сотрудники Bitrix24 не найдены.",
  selected: "Разрешён доступ",
  users: "пользователей",
  loadUsersError: "Не удалось загрузить сотрудников Bitrix24.",
  loadAccessError: "Не удалось загрузить текущий доступ Bitrix24.",
  saveError: "Не удалось сохранить доступ Bitrix24.",
  saveOk: "Доступ сохранён.",
  noEmail: "—",
  enabled: "Разрешён",
  disabled: "Отключён",
} as const;

function userDisplayName(user: BitrixPortalUser) {
  return [user.name, user.last_name].filter(Boolean).join(" ") || `ID ${user.id}`;
}

export function EmbeddedBitrixUsersPage() {
  const ctx = useOutletContext<EmbeddedBitrixContext>();
  const [users, setUsers] = useState<BitrixPortalUser[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<number[]>([]);
  const [telegramMap, setTelegramMap] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");

  const load = async () => {
    if (!ctx?.portalId) return;
    setLoading(true);
    setMessage("");
    try {
      const [usersRes, accessRes] = await Promise.all([
        fetchPortal(`/api/v1/bitrix/users?portal_id=${ctx.portalId}&start=0&limit=200`),
        fetchPortal(`/api/v1/bitrix/portals/${ctx.portalId}/access/users`),
      ]);
      const usersData = await usersRes.json().catch(() => null);
      const accessData = await accessRes.json().catch(() => null);

      if (!usersRes.ok) {
        setMessage(usersData?.detail || usersData?.error || LABELS.loadUsersError);
        return;
      }
      if (!accessRes.ok) {
        setMessage(accessData?.detail || accessData?.error || LABELS.loadAccessError);
        return;
      }

      const nextUsers = Array.isArray(usersData?.users) ? usersData.users : [];
      const accessItems = Array.isArray(accessData?.items) ? (accessData.items as AccessItem[]) : [];
      const nextSelected = accessItems
        .filter((item) => (item.kind || "bitrix") === "bitrix")
        .map((item) => Number(item.user_id))
        .filter((item) => Number.isFinite(item));

      const nextTelegramMap: Record<number, string> = {};
      accessItems.forEach((item) => {
        const id = Number(item.user_id);
        if (!Number.isFinite(id) || !item.telegram_username) return;
        nextTelegramMap[id] = item.telegram_username.startsWith("@") ? item.telegram_username : `@${item.telegram_username}`;
      });

      setUsers(nextUsers);
      setSelectedUsers(nextSelected);
      setTelegramMap(nextTelegramMap);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [ctx?.portalId]);

  const filteredUsers = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return users;
    return users.filter((user) => {
      const hay = `${user.name || ""} ${user.last_name || ""} ${user.email || ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [users, query]);

  const toggleAccess = (userId: number, checked: boolean) => {
    setSelectedUsers((prev) => {
      const next = new Set(prev);
      if (checked) next.add(userId);
      else next.delete(userId);
      return Array.from(next);
    });
    if (!checked) {
      setTelegramMap((prev) => {
        const next = { ...prev };
        delete next[userId];
        return next;
      });
    }
  };

  const save = async () => {
    if (!ctx?.portalId || !ctx?.isPortalAdmin) return;
    setSaving(true);
    setMessage("");
    try {
      const items = selectedUsers.map((id) => ({
        user_id: id,
        telegram_username: telegramMap[id] || null,
      }));
      const res = await fetchPortal(`/api/v1/bitrix/portals/${ctx.portalId}/access/users`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setMessage(data?.detail || data?.error || LABELS.saveError);
        return;
      }
      setMessage(LABELS.saveOk);
      await load();
    } finally {
      setSaving(false);
    }
  };

  if (!ctx?.isPortalAdmin) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{LABELS.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{LABELS.subtitle}</p>
        </div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {LABELS.adminOnly}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{LABELS.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{LABELS.subtitle}</p>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            {LABELS.selected}: <span className="font-semibold text-slate-900">{selectedUsers.length}</span> {LABELS.users}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => void load()}
              disabled={loading || saving}
            >
              {LABELS.refresh}
            </button>
            <button
              type="button"
              className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50"
              onClick={() => void save()}
              disabled={loading || saving}
            >
              {saving ? LABELS.saving : LABELS.save}
            </button>
          </div>
        </div>

        <div className="mt-4">
          <input
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            placeholder={LABELS.search}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {message && <div className="mt-3 text-sm text-slate-600">{message}</div>}

        <div className="mt-4 overflow-auto rounded-xl border border-slate-100">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">{LABELS.employee}</th>
                <th className="px-3 py-2 text-left">{LABELS.access}</th>
                <th className="px-3 py-2 text-left">{LABELS.telegram}</th>
              </tr>
            </thead>
            <tbody>
              {!loading && filteredUsers.length === 0 && (
                <tr>
                  <td className="px-3 py-3 text-slate-500" colSpan={3}>
                    {LABELS.empty}
                  </td>
                </tr>
              )}
              {filteredUsers.map((user) => {
                const userId = Number(user.id);
                const checked = selectedUsers.includes(userId);
                return (
                  <tr key={String(user.id)} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-900">{userDisplayName(user)}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {user.email || LABELS.noEmail} · ID {user.id}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => toggleAccess(userId, e.target.checked)}
                        />
                        <span>{checked ? LABELS.enabled : LABELS.disabled}</span>
                      </label>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        className="w-44 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs disabled:opacity-50"
                        placeholder="@username"
                        value={telegramMap[userId] || ""}
                        disabled={!checked}
                        onChange={(e) =>
                          setTelegramMap((prev) => ({
                            ...prev,
                            [userId]: e.target.value,
                          }))
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
