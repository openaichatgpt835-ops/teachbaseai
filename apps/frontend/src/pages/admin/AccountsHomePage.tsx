import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

type PortalItem = {
  id: number;
  domain: string;
  status: string;
};

type DialogItem = {
  id: number;
  portal_id: number;
  provider_dialog_id: string;
};

type AuditItem = {
  web_user_id: number;
  email: string;
  portal_id: number | null;
  portal_domain: string | null;
  account_id: number | null;
  account_no: number | null;
  healthy_owner_default: boolean;
  role: string | null;
};

type AuditResponse = {
  items: AuditItem[];
  summary: { total: number; ok: number; broken: number };
};

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-500">{hint}</div> : null}
    </div>
  );
}

export function AccountsHomePage() {
  const portalsQ = useQuery({
    queryKey: ["admin-accounts-portals"],
    queryFn: () => api.get("/v1/admin/portals") as Promise<{ items: PortalItem[] }>,
    refetchInterval: 30000,
  });
  const dialogsQ = useQuery({
    queryKey: ["admin-accounts-dialogs"],
    queryFn: () => api.get("/v1/admin/dialogs") as Promise<{ items: DialogItem[] }>,
    refetchInterval: 30000,
  });
  const auditQ = useQuery({
    queryKey: ["admin-accounts-rbac-audit"],
    queryFn: () => api.get("/v1/admin/portals/rbac/owners/audit") as Promise<AuditResponse>,
    refetchInterval: 30000,
  });

  const portals = portalsQ.data?.items ?? [];
  const dialogs = dialogsQ.data?.items ?? [];
  const audit = auditQ.data;
  const activePortals = portals.filter((p) => p.status === "active");
  const brokenOwners = (audit?.items ?? []).filter((item) => !item.healthy_owner_default).slice(0, 6);
  const recentPortals = portals.slice(0, 6);
  const recentDialogs = dialogs.slice(0, 6);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Порталы" value={String(portals.length)} hint={`${activePortals.length} active`} />
        <StatCard label="Диалоги" value={String(dialogs.length)} hint="Все каналы и provider_dialog_id" />
        <StatCard label="Owner audit" value={String(audit?.summary.broken ?? 0)} hint={`${audit?.summary.ok ?? 0} ok / ${audit?.summary.total ?? 0} total`} />
        <StatCard label="Account coverage" value={String(new Set((audit?.items ?? []).map((x) => x.account_id).filter(Boolean)).size)} hint="Аккаунты в owner-аудите" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Порталы и интеграции</h2>
              <p className="mt-1 text-sm text-slate-500">Последние порталы и их текущий статус.</p>
            </div>
            <Link to="/admin/portals" className="text-sm font-medium text-sky-700 hover:underline">Все порталы</Link>
          </div>
          <div className="mt-4 space-y-3">
            {recentPortals.map((portal) => (
              <Link key={portal.id} to={`/admin/portals/${portal.id}`} className="block rounded-2xl border border-slate-200 p-4 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-slate-900">{portal.domain}</div>
                  <div className={portal.status === "active" ? "text-sm font-semibold text-emerald-600" : "text-sm font-semibold text-slate-500"}>{portal.status}</div>
                </div>
                <div className="mt-1 text-sm text-slate-500">portal #{portal.id}</div>
              </Link>
            ))}
            {!recentPortals.length ? <div className="text-sm text-slate-500">Порталов пока нет.</div> : null}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">RBAC и владельцы</h2>
              <p className="mt-1 text-sm text-slate-500">Проблемные owner-связки, которые требуют внимания.</p>
            </div>
            <Link to="/admin/rbac-owners" className="text-sm font-medium text-sky-700 hover:underline">Открыть аудит</Link>
          </div>
          <div className="mt-4 space-y-3">
            {brokenOwners.map((row) => (
              <div key={`${row.web_user_id}-${row.portal_id}`} className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                <div className="font-medium text-slate-900">{row.email}</div>
                <div className="mt-1 text-sm text-slate-600">{row.portal_domain || `portal ${row.portal_id ?? "—"}`} · account {row.account_no || row.account_id || "—"}</div>
                <div className="mt-1 text-sm text-rose-700">role: {row.role || "—"}</div>
              </div>
            ))}
            {!brokenOwners.length ? <div className="text-sm text-slate-500">Критичных owner-проблем не найдено.</div> : null}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Последние диалоги</h2>
            <p className="mt-1 text-sm text-slate-500">Быстрый переход к свежим chat/dialog объектам.</p>
          </div>
          <Link to="/admin/dialogs" className="text-sm font-medium text-sky-700 hover:underline">Все диалоги</Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {recentDialogs.map((dialog) => (
            <Link key={dialog.id} to={`/admin/dialogs/${dialog.id}`} className="rounded-2xl border border-slate-200 p-4 hover:bg-slate-50">
              <div className="font-medium text-slate-900">Диалог #{dialog.id}</div>
              <div className="mt-1 text-sm text-slate-600">portal {dialog.portal_id}</div>
              <div className="mt-1 truncate text-sm text-slate-500">{dialog.provider_dialog_id}</div>
            </Link>
          ))}
          {!recentDialogs.length ? <div className="text-sm text-slate-500">Диалогов пока нет.</div> : null}
        </div>
      </section>
    </div>
  );
}
