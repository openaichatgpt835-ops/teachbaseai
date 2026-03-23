import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

type HealthResponse = Record<string, unknown>;

type QueueItem = {
  queue_name: string;
  queued: number;
  started: number;
  failed: number;
  workers: number;
  overloaded: boolean;
};

type QueueResponse = {
  queues?: QueueItem[];
};

type WorkersResponse = {
  queues?: Array<{ queue_name: string; workers: Array<Record<string, unknown>> }>;
};

type ErrorSummary = {
  period: string;
  error_rate_percent: number;
  bitrix_total_requests: number;
  bitrix_error_requests: number;
  p95_latency_ms: number;
  top_codes: Array<{ key: string; count: number }>;
  top_portals: Array<{ key: string; count: number }>;
};

type ErrorItem = {
  id: string;
  created_at: string | null;
  portal_id: number | null;
  portal_domain: string;
  trace_id: string | null;
  channel: string;
  endpoint: string;
  code: string;
  message: string;
};

type TraceItem = {
  id: number;
  trace_id: string;
  portal_id: number | null;
  kind: string;
  method: string;
  path: string;
  status_code: number | null;
  latency_ms: number | null;
  created_at: string | null;
};

type InboundUsage = {
  used_mb: number;
  target_budget_mb: number;
  percent: number;
  approx_rows: number;
  oldest_at: string | null;
  newest_at: string | null;
};

type InboundItem = {
  id: number;
  created_at: string | null;
  portal_id: number | null;
  domain: string | null;
  event_name: string | null;
  trace_id: string | null;
  method: string;
  path: string;
};

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-500">{hint}</div> : null}
    </div>
  );
}

export function OperationsHomePage() {
  const healthQ = useQuery({
    queryKey: ["admin-ops-health"],
    queryFn: () => api.get("/v1/admin/system/health") as Promise<HealthResponse>,
    refetchInterval: 15000,
  });
  const queueQ = useQuery({
    queryKey: ["admin-ops-queue"],
    queryFn: () => api.get("/v1/admin/system/queue") as Promise<QueueResponse>,
    refetchInterval: 5000,
  });
  const workersQ = useQuery({
    queryKey: ["admin-ops-workers"],
    queryFn: () => api.get("/v1/admin/system/workers") as Promise<WorkersResponse>,
    refetchInterval: 10000,
  });
  const errorsSummaryQ = useQuery({
    queryKey: ["admin-ops-errors-summary"],
    queryFn: () => api.get("/v1/admin/errors/summary?period=24h") as Promise<ErrorSummary>,
    refetchInterval: 30000,
  });
  const errorsQ = useQuery({
    queryKey: ["admin-ops-errors"],
    queryFn: () => api.get("/v1/admin/errors?limit=5") as Promise<{ items: ErrorItem[]; total: number }>,
    refetchInterval: 15000,
  });
  const tracesQ = useQuery({
    queryKey: ["admin-ops-traces"],
    queryFn: () => api.get("/v1/admin/traces") as Promise<{ items: TraceItem[] }>,
    refetchInterval: 15000,
  });
  const inboundUsageQ = useQuery({
    queryKey: ["admin-ops-inbound-usage"],
    queryFn: () => api.get("/v1/admin/inbound-events/usage") as Promise<InboundUsage>,
    refetchInterval: 30000,
  });
  const inboundQ = useQuery({
    queryKey: ["admin-ops-inbound-recent"],
    queryFn: () => api.get("/v1/admin/inbound-events?limit=5") as Promise<{ items: InboundItem[]; total: number }>,
    refetchInterval: 15000,
  });

  const queues = queueQ.data?.queues ?? [];
  const failedQueues = queues.filter((q) => q.failed > 0);
  const overloadedQueues = queues.filter((q) => q.overloaded);
  const totalWorkers = (workersQ.data?.queues ?? []).reduce((acc, q) => acc + q.workers.length, 0);
  const recentTraces = (tracesQ.data?.items ?? []).slice(0, 5);
  const recentErrors = errorsQ.data?.items ?? [];
  const recentInbound = inboundQ.data?.items ?? [];
  const healthStatus = String((healthQ.data as { status?: string } | undefined)?.status ?? "unknown");

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Health" value={healthStatus} hint="Общий статус backend" />
        <StatCard
          label="Очереди"
          value={`${queues.length}`}
          hint={`${overloadedQueues.length} перегруз, ${failedQueues.length} с failed`}
        />
        <StatCard
          label="Workers"
          value={`${totalWorkers}`}
          hint="Суммарно по всем очередям"
        />
        <StatCard
          label="API errors 24h"
          value={`${errorsSummaryQ.data?.bitrix_error_requests ?? 0}`}
          hint={`rate ${errorsSummaryQ.data?.error_rate_percent ?? 0}% · p95 ${errorsSummaryQ.data?.p95_latency_ms ?? 0} ms`}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Операционный статус</h2>
              <p className="mt-1 text-sm text-slate-500">Быстрый срез по очередям, воркерам и входящим событиям.</p>
            </div>
            <Link to="/admin/system" className="text-sm font-medium text-sky-700 hover:underline">
              Открыть системную страницу
            </Link>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {queues.map((queue) => (
              <div key={queue.queue_name} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-slate-900">{queue.queue_name}</div>
                  <div className={queue.overloaded ? "text-sm font-semibold text-rose-600" : "text-sm font-semibold text-emerald-600"}>
                    {queue.overloaded ? "перегруз" : "норма"}
                  </div>
                </div>
                <div className="mt-2 text-sm text-slate-600">
                  queued: {queue.queued} · started: {queue.started} · workers: {queue.workers} · failed: {queue.failed}
                </div>
              </div>
            ))}
            {!queues.length ? <div className="text-sm text-slate-500">Нет данных по очередям.</div> : null}
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl bg-slate-50 p-4">
              <div className="text-sm font-semibold text-slate-900">Inbound storage</div>
              <div className="mt-2 text-sm text-slate-600">
                {inboundUsageQ.data ? (
                  <>
                    {inboundUsageQ.data.used_mb.toFixed(1)} MB из {inboundUsageQ.data.target_budget_mb.toFixed(1)} MB · {inboundUsageQ.data.approx_rows} rows
                  </>
                ) : (
                  "Нет данных"
                )}
              </div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <div className="text-sm font-semibold text-slate-900">Top error code</div>
              <div className="mt-2 text-sm text-slate-600">
                {errorsSummaryQ.data?.top_codes?.[0]
                  ? `${errorsSummaryQ.data.top_codes[0].key} · ${errorsSummaryQ.data.top_codes[0].count}`
                  : "Нет ошибок за период"}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Быстрые переходы</h2>
          <div className="mt-4 space-y-3 text-sm">
            <Link className="block rounded-2xl border border-slate-200 px-4 py-3 text-slate-700 hover:bg-slate-50" to="/admin/errors">
              Ошибки API
            </Link>
            <Link className="block rounded-2xl border border-slate-200 px-4 py-3 text-slate-700 hover:bg-slate-50" to="/admin/traces">
              Трейсы
            </Link>
            <Link className="block rounded-2xl border border-slate-200 px-4 py-3 text-slate-700 hover:bg-slate-50" to="/admin/inbound-events">
              Inbound Events
            </Link>
            <Link className="block rounded-2xl border border-slate-200 px-4 py-3 text-slate-700 hover:bg-slate-50" to="/admin/portals">
              Порталы и интеграции
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-1">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Последние ошибки</h2>
            <Link to="/admin/errors" className="text-sm font-medium text-sky-700 hover:underline">Все</Link>
          </div>
          <div className="mt-4 space-y-3">
            {recentErrors.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-mono text-xs text-rose-700">{item.code}</div>
                  <div className="text-xs text-slate-500">{formatDate(item.created_at)}</div>
                </div>
                <div className="mt-1 text-sm font-medium text-slate-900">{item.endpoint || item.channel}</div>
                <div className="mt-1 line-clamp-2 text-sm text-slate-600">{item.message}</div>
              </div>
            ))}
            {!recentErrors.length ? <div className="text-sm text-slate-500">Ошибок за выборку нет.</div> : null}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-1">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Последние трейсы</h2>
            <Link to="/admin/traces" className="text-sm font-medium text-sky-700 hover:underline">Все</Link>
          </div>
          <div className="mt-4 space-y-3">
            {recentTraces.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-3">
                  <Link to={`/admin/traces/${item.trace_id}`} className="font-mono text-xs text-sky-700 hover:underline">
                    {item.trace_id}
                  </Link>
                  <div className="text-xs text-slate-500">{formatDate(item.created_at)}</div>
                </div>
                <div className="mt-1 text-sm font-medium text-slate-900">{item.method} {item.path}</div>
                <div className="mt-1 text-sm text-slate-600">status {item.status_code ?? "—"} · {item.latency_ms ?? 0} ms · portal {item.portal_id ?? "—"}</div>
              </div>
            ))}
            {!recentTraces.length ? <div className="text-sm text-slate-500">Нет трейсов.</div> : null}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-1">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Последние inbound events</h2>
            <Link to="/admin/inbound-events" className="text-sm font-medium text-sky-700 hover:underline">Все</Link>
          </div>
          <div className="mt-4 space-y-3">
            {recentInbound.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-3">
                  <Link to={`/admin/inbound-events/${item.id}`} className="font-mono text-xs text-sky-700 hover:underline">
                    #{item.id}
                  </Link>
                  <div className="text-xs text-slate-500">{formatDate(item.created_at)}</div>
                </div>
                <div className="mt-1 text-sm font-medium text-slate-900">{item.method} {item.path}</div>
                <div className="mt-1 text-sm text-slate-600">{item.domain || "—"} · portal {item.portal_id ?? "—"} · {item.event_name || "event"}</div>
              </div>
            ))}
            {!recentInbound.length ? <div className="text-sm text-slate-500">Нет inbound events.</div> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
