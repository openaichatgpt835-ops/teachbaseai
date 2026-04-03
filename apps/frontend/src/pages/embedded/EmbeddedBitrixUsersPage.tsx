import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { fetchPortal } from "../web/auth";
import type { EmbeddedBitrixContext } from "./EmbeddedBitrixGate";

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
  title: "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438 Bitrix24",
  subtitle:
    "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043e\u043c \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u043e\u0432 \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e Bitrix-\u043f\u043e\u0440\u0442\u0430\u043b\u0430. \u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u043f\u043e\u0440\u0442\u0430\u043b\u0430.",
  adminOnly:
    "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\u043c\u0438 Bitrix24 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e \u043f\u043e\u0440\u0442\u0430\u043b\u0430.",
  refresh: "\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c",
  save: "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f",
  saving: "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u044e...",
  search: "\u041f\u043e\u0438\u0441\u043a \u043f\u043e \u0438\u043c\u0435\u043d\u0438 \u0438\u043b\u0438 email",
  access: "\u0414\u043e\u0441\u0442\u0443\u043f",
  telegram: "Telegram username",
  employee: "\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a",
  empty: "\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0438 Bitrix24 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b.",
  selected: "\u0420\u0430\u0437\u0440\u0435\u0448\u0451\u043d \u0434\u043e\u0441\u0442\u0443\u043f",
  total: "\u0412\u0441\u0435\u0433\u043e \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u043e\u0432",
  users: "\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439",
  note:
    "\u0414\u043e\u0441\u0442\u0443\u043f \u0440\u0430\u0437\u0440\u0435\u0448\u0430\u0435\u0442 \u043f\u043e\u0438\u0441\u043a \u0438 \u043e\u0442\u0432\u0435\u0442\u044b \u043f\u043e \u0431\u0430\u0437\u0435 \u0437\u043d\u0430\u043d\u0438\u0439 \u0438\u0437 \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e Bitrix24-\u043f\u043e\u0440\u0442\u0430\u043b\u0430.",
  loadUsersError: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u043e\u0432 Bitrix24.",
  loadAccessError: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u0434\u043e\u0441\u0442\u0443\u043f Bitrix24.",
  saveError: "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f Bitrix24.",
  saveOk: "\u0414\u043e\u0441\u0442\u0443\u043f \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d.",
  loading: "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u043e\u0432...",
  noEmail: "\u2014",
  enabled: "\u0420\u0430\u0437\u0440\u0435\u0448\u0451\u043d",
  disabled: "\u041e\u0442\u043a\u043b\u044e\u0447\u0451\u043d",
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
  const [messageTone, setMessageTone] = useState<"info" | "error" | "success">("info");
  const [query, setQuery] = useState("");

  const load = async () => {
    if (!ctx?.portalId) return;
    setLoading(true);
    setMessage("");
    setMessageTone("info");
    try {
      const [usersRes, accessRes] = await Promise.all([
        fetchPortal(`/api/v1/bitrix/users?portal_id=${ctx.portalId}&start=0&limit=200`),
        fetchPortal(`/api/v1/bitrix/portals/${ctx.portalId}/access/users`),
      ]);
      const usersData = await usersRes.json().catch(() => null);
      const accessData = await accessRes.json().catch(() => null);

      if (!usersRes.ok) {
        setMessageTone("error");
        setMessage(usersData?.detail || usersData?.error || LABELS.loadUsersError);
        return;
      }
      if (!accessRes.ok) {
        setMessageTone("error");
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
    setMessageTone("info");
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
        setMessageTone("error");
        setMessage(data?.detail || data?.error || LABELS.saveError);
        return;
      }
      setMessageTone("success");
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
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {LABELS.note}
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

      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {LABELS.note}
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600">
            <div>
              {LABELS.selected}: <span className="font-semibold text-slate-900">{selectedUsers.length}</span> {LABELS.users}
            </div>
            <div>
              {LABELS.total}: <span className="font-semibold text-slate-900">{users.length}</span>
            </div>
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

        {message && (
          <div
            className={`mt-3 rounded-xl px-3 py-2 text-sm ${
              messageTone === "error"
                ? "border border-rose-200 bg-rose-50 text-rose-700"
                : messageTone === "success"
                  ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border border-slate-200 bg-slate-50 text-slate-600"
            }`}
          >
            {message}
          </div>
        )}

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
              {loading && (
                <tr>
                  <td className="px-3 py-3 text-slate-500" colSpan={3}>
                    {LABELS.loading}
                  </td>
                </tr>
              )}
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
