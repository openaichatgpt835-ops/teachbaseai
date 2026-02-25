import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

type AuditItem = {
  web_user_id: number;
  email: string;
  portal_id: number | null;
  portal_domain: string | null;
  install_type: string | null;
  account_id: number | null;
  account_no: number | null;
  membership_id: number | null;
  role: string | null;
  membership_status: string | null;
  kb_access: string | null;
  can_invite_users: boolean | null;
  can_manage_settings: boolean | null;
  can_view_finance: boolean | null;
  healthy_owner_default: boolean;
};

type AuditResponse = {
  items: AuditItem[];
  summary: { total: number; ok: number; broken: number };
};

export function RbacOwnersAuditPage() {
  const [email, setEmail] = useState("");
  const [submittedEmail, setSubmittedEmail] = useState("");

  const queryString = useMemo(() => {
    const qs = new URLSearchParams();
    if (submittedEmail.trim()) qs.set("email", submittedEmail.trim());
    return qs.toString();
  }, [submittedEmail]);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["rbac-owner-audit", queryString],
    queryFn: () =>
      api.get(`/v1/admin/portals/rbac/owners/audit${queryString ? `?${queryString}` : ""}`) as Promise<AuditResponse>,
  });

  const items = data?.items || [];
  const summary = data?.summary || { total: 0, ok: 0, broken: 0 };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">RBAC аудит владельцев</h1>
        <p className="text-sm text-gray-600">Контроль owner-ролей и дефолтных прав для web-пользователей.</p>
      </div>

      <div className="rounded-md bg-white p-4 shadow">
        <div className="flex items-center gap-2">
          <input
            className="w-[360px] rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="Фильтр по email (часть строки)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            onClick={() => setSubmittedEmail(email)}
          >
            Применить
          </button>
          <button
            className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => refetch()}
          >
            Обновить
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-md bg-white p-3 shadow">
          <div className="text-xs text-gray-500">Всего</div>
          <div className="text-xl font-semibold">{summary.total}</div>
        </div>
        <div className="rounded-md bg-white p-3 shadow">
          <div className="text-xs text-gray-500">OK</div>
          <div className="text-xl font-semibold text-green-700">{summary.ok}</div>
        </div>
        <div className="rounded-md bg-white p-3 shadow">
          <div className="text-xs text-gray-500">Проблемы</div>
          <div className="text-xl font-semibold text-rose-700">{summary.broken}</div>
        </div>
      </div>

      {isLoading || isFetching ? <div className="text-gray-600">Загрузка...</div> : null}
      {error ? <div className="text-red-600">Ошибка: {String(error)}</div> : null}

      <div className="overflow-auto rounded-md bg-white shadow">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">Email</th>
              <th className="px-3 py-2 text-left">Portal</th>
              <th className="px-3 py-2 text-left">Account</th>
              <th className="px-3 py-2 text-left">Role</th>
              <th className="px-3 py-2 text-left">KB</th>
              <th className="px-3 py-2 text-left">Invite</th>
              <th className="px-3 py-2 text-left">Settings</th>
              <th className="px-3 py-2 text-left">Finance</th>
              <th className="px-3 py-2 text-left">Health</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-gray-500" colSpan={9}>Данных нет.</td>
              </tr>
            ) : (
              items.map((r) => (
                <tr key={`${r.web_user_id}-${r.portal_id}`} className="border-t border-gray-100">
                  <td className="px-3 py-2">{r.email}</td>
                  <td className="px-3 py-2">{r.portal_domain || r.portal_id || "—"}</td>
                  <td className="px-3 py-2">{r.account_no || r.account_id || "—"}</td>
                  <td className="px-3 py-2">{r.role || "—"}</td>
                  <td className="px-3 py-2">{r.kb_access || "—"}</td>
                  <td className="px-3 py-2">{r.can_invite_users === null ? "—" : r.can_invite_users ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{r.can_manage_settings === null ? "—" : r.can_manage_settings ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">{r.can_view_finance === null ? "—" : r.can_view_finance ? "Да" : "Нет"}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-1 text-xs ${r.healthy_owner_default ? "bg-green-100 text-green-700" : "bg-rose-100 text-rose-700"}`}>
                      {r.healthy_owner_default ? "OK" : "BROKEN"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

