import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, getAuthToken } from "../../api/client";

type ErrorItem = {
  id: string;
  created_at: string | null;
  portal_id: number | null;
  portal_domain: string;
  trace_id: string | null;
  channel: string;
  endpoint: string;
  method: string;
  code: string;
  message: string;
  status_code: number | null;
  kind: string;
};

export function ErrorsPage() {
  const [params, setParams] = useSearchParams();
  const qTrace = params.get("trace_id") ?? "";
  const qPortal = params.get("portal") ?? params.get("portal_id") ?? "";
  const qChannel = params.get("channel") ?? "";
  const qCode = params.get("code") ?? "";
  const period = params.get("period") ?? "24h";

  const queryString = new URLSearchParams();
  queryString.set("limit", "200");
  if (qTrace.trim()) queryString.set("trace_id", qTrace.trim());
  if (qPortal.trim()) queryString.set("portal", qPortal.trim());
  if (qChannel.trim()) queryString.set("channel", qChannel.trim());
  if (qCode.trim()) queryString.set("code", qCode.trim());

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-errors", qTrace, qPortal, qChannel, qCode],
    queryFn: () => api.get(`/v1/admin/errors?${queryString.toString()}`) as Promise<{ items: ErrorItem[]; total: number }>,
  });
  const summaryQ = useQuery({
    queryKey: ["admin-errors-summary", period],
    queryFn: () =>
      api.get(`/v1/admin/errors/summary?period=${encodeURIComponent(period)}`) as Promise<{
        period: string;
        error_rate_percent: number;
        bitrix_total_requests: number;
        bitrix_error_requests: number;
        p95_latency_ms: number;
        top_codes: Array<{ key: string; count: number }>;
        top_portals: Array<{ key: string; count: number }>;
      }>,
  });

  const items = data?.items ?? [];
  const API_BASE = (import.meta.env.VITE_API_BASE || "/api") as string;
  const exportParams = new URLSearchParams(queryString);
  exportParams.delete("limit");
  exportParams.set("limit", "2000");

  const download = async (kind: "csv" | "json") => {
    const token = getAuthToken();
    const url = `${API_BASE}/v1/admin/errors/export.${kind}?${exportParams.toString()}`;
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = kind === "csv" ? "api_errors.csv" : "api_errors.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  };
  const onChange = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value.trim()) next.set(name, value.trim());
    else next.delete(name);
    setParams(next);
  };
  const setPeriod = (value: "1h" | "24h" | "7d") => onChange("period", value);

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Ошибки API</h1>
      <div className="mb-4 flex gap-2">
        <button className={`px-3 py-1.5 text-sm rounded border ${period === "1h" ? "bg-blue-600 text-white border-blue-600" : "bg-white border-gray-300"}`} onClick={() => setPeriod("1h")}>1ч</button>
        <button className={`px-3 py-1.5 text-sm rounded border ${period === "24h" ? "bg-blue-600 text-white border-blue-600" : "bg-white border-gray-300"}`} onClick={() => setPeriod("24h")}>24ч</button>
        <button className={`px-3 py-1.5 text-sm rounded border ${period === "7d" ? "bg-blue-600 text-white border-blue-600" : "bg-white border-gray-300"}`} onClick={() => setPeriod("7d")}>7д</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-white shadow rounded p-3">
          <div className="text-xs text-gray-500">Error rate</div>
          <div className="text-xl font-semibold">{summaryQ.data?.error_rate_percent ?? 0}%</div>
        </div>
        <div className="bg-white shadow rounded p-3">
          <div className="text-xs text-gray-500">Ошибки / всего</div>
          <div className="text-xl font-semibold">{summaryQ.data?.bitrix_error_requests ?? 0} / {summaryQ.data?.bitrix_total_requests ?? 0}</div>
        </div>
        <div className="bg-white shadow rounded p-3">
          <div className="text-xs text-gray-500">p95 latency</div>
          <div className="text-xl font-semibold">{summaryQ.data?.p95_latency_ms ?? 0} ms</div>
        </div>
        <div className="bg-white shadow rounded p-3">
          <div className="text-xs text-gray-500">Top code</div>
          <div className="text-sm font-medium">{summaryQ.data?.top_codes?.[0]?.key ?? "—"}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <div className="bg-white shadow rounded p-3">
          <div className="text-sm font-semibold mb-2">Top codes</div>
          <div className="space-y-1 text-sm">
            {(summaryQ.data?.top_codes ?? []).map((x) => (
              <div key={x.key} className="flex justify-between"><span className="font-mono">{x.key}</span><span>{x.count}</span></div>
            ))}
          </div>
        </div>
        <div className="bg-white shadow rounded p-3">
          <div className="text-sm font-semibold mb-2">Top portals</div>
          <div className="space-y-1 text-sm">
            {(summaryQ.data?.top_portals ?? []).map((x) => (
              <div key={x.key} className="flex justify-between"><span className="font-mono">{x.key}</span><span>{x.count}</span></div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white shadow rounded p-4 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <input
          value={qPortal}
          onChange={(e) => onChange("portal", e.target.value)}
          placeholder="portal_id или домен"
          className="border rounded px-3 py-2 text-sm"
        />
        <input
          value={qTrace}
          onChange={(e) => onChange("trace_id", e.target.value)}
          placeholder="trace_id"
          className="border rounded px-3 py-2 text-sm"
        />
        <select
          value={qChannel}
          onChange={(e) => onChange("channel", e.target.value)}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">канал: все</option>
          <option value="bitrix_http">bitrix_http</option>
          <option value="inbound">inbound</option>
          <option value="outbox">outbox</option>
        </select>
        <input
          value={qCode}
          onChange={(e) => onChange("code", e.target.value)}
          placeholder="code содержит..."
          className="border rounded px-3 py-2 text-sm"
        />
      </div>

      {isLoading && <div className="text-gray-500">Загрузка...</div>}
      {error && <div className="text-red-600">Ошибка загрузки: {String(error)}</div>}

      <div className="text-sm text-gray-600 mb-2">Всего найдено: {data?.total ?? 0}</div>
      <div className="mb-3 flex gap-2">
        <button
          className="px-3 py-1.5 text-sm rounded border border-gray-300 bg-white hover:bg-gray-50"
          onClick={() => download("csv")}
        >
          Экспорт CSV
        </button>
        <button
          className="px-3 py-1.5 text-sm rounded border border-gray-300 bg-white hover:bg-gray-50"
          onClick={() => download("json")}
        >
          Экспорт JSON
        </button>
      </div>

      <div className="bg-white shadow rounded overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Время</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Канал</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Портал</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Код</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Endpoint</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">trace_id</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Сообщение</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-3 py-2 text-sm text-gray-600">{r.created_at?.slice(0, 19) ?? ""}</td>
                <td className="px-3 py-2 text-sm">{r.channel}</td>
                <td className="px-3 py-2 text-sm">{r.portal_id ?? ""} {r.portal_domain ? `(${r.portal_domain})` : ""}</td>
                <td className="px-3 py-2 text-sm font-mono">{r.code}</td>
                <td className="px-3 py-2 text-sm">
                  <span className="font-mono text-xs">{r.method}</span> {r.endpoint}
                </td>
                <td className="px-3 py-2 text-sm font-mono">
                  {r.trace_id ? <Link className="text-blue-600 hover:underline" to={`/admin/traces/${r.trace_id}`}>{r.trace_id}</Link> : ""}
                </td>
                <td className="px-3 py-2 text-sm text-gray-700 max-w-[360px] truncate" title={r.message || ""}>
                  {r.message || ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
