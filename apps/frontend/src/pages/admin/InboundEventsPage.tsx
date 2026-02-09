import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useState } from "react";

type Settings = {
  retention_days: number;
  max_rows: number;
  max_body_kb: number;
  enabled: boolean;
  auto_prune_on_write: boolean;
  target_budget_mb: number;
  defaults: Record<string, unknown>;
};

type Usage = {
  used_mb: number;
  target_budget_mb: number;
  percent: number;
  approx_rows: number;
  oldest_at: string | null;
  newest_at: string | null;
};

export function InboundEventsPage() {
  const queryClient = useQueryClient();
  const [portalId, setPortalId] = useState<string>("");
  const [domain, setDomain] = useState("");
  const [traceId, setTraceId] = useState("");
  const [limit] = useState(200);

  const params = new URLSearchParams();
  if (portalId) params.set("portal_id", portalId);
  if (domain) params.set("domain", domain);
  if (traceId) params.set("trace_id", traceId);
  params.set("limit", String(limit));

  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ["inbound-settings"],
    queryFn: () => api.get("/v1/admin/settings/inbound-events") as Promise<Settings>,
  });

  const { data: usageData, isLoading: usageLoading, refetch: refetchUsage } = useQuery({
    queryKey: ["inbound-usage"],
    queryFn: () => api.get("/v1/admin/inbound-events/usage") as Promise<Usage>,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["inbound-events", portalId, domain, traceId, limit],
    queryFn: () =>
      api.get(`/v1/admin/inbound-events?${params}`) as Promise<{
        items: Array<{
          id: number;
          created_at: string | null;
          portal_id: number | null;
          domain: string | null;
          member_id: string | null;
          dialog_id: string | null;
          user_id: string | null;
          event_name: string | null;
          trace_id: string | null;
          user_agent: string | null;
          content_type: string | null;
          body_truncated: boolean;
          hints_json: Record<string, unknown> | null;
          method: string;
          path: string;
        }>;
        total: number;
      }>,
  });

  const pruneMutation = useMutation({
    mutationFn: (body: { mode: string; older_than_days?: number }) =>
      api.post("/v1/admin/inbound-events/prune", body) as Promise<{
        deleted_rows: number;
        remaining_rows: number;
        used_mb_after: number;
      }>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbound-usage"] });
      queryClient.invalidateQueries({ queryKey: ["inbound-events"] });
    },
  });

  const saveSettingsMutation = useMutation({
    mutationFn: (payload: Partial<Settings>) =>
      api.put("/v1/admin/settings/inbound-events", payload) as Promise<Settings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbound-settings"] });
      setEditForm(null);
    },
  });

  const settings = settingsData;
  const usage = usageData;
  const items = data?.items ?? [];
  const disabled = !settings?.enabled;
  const overBudget = usage && usage.target_budget_mb > 0 && usage.used_mb > usage.target_budget_mb;

  const [editForm, setEditForm] = useState<Partial<Settings> | null>(null);
  const form = editForm ?? settings ?? ({} as Settings);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Inbound events (POST /v1/bitrix/events)</h1>

      {disabled && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded">
            (enabled=false).      .
        </div>
      )}
      {overBudget && (
        <div className="bg-orange-50 border border-orange-200 text-orange-800 px-4 py-2 rounded">
           {usage?.used_mb} MB,    {usage?.target_budget_mb} MB.   -.
        </div>
      )}

      {/* Storage settings */}
      <section className="bg-white shadow rounded p-4">
        <h2 className="text-lg font-semibold mb-3">Storage settings</h2>
        {settingsLoading && <p className="text-gray-500">...</p>}
        {!settingsLoading && settings && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.enabled ?? false}
                onChange={(e) => setEditForm((f) => ({ ...f, enabled: e.target.checked }))}
              />
              enabled
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.auto_prune_on_write ?? false}
                onChange={(e) => setEditForm((f) => ({ ...f, auto_prune_on_write: e.target.checked }))}
              />
              auto_prune_on_write
            </label>
            <label className="flex items-center gap-2">
              retention_days
              <input
                type="number"
                min={1}
                max={30}
                className="border rounded px-2 py-1 w-20"
                value={form.retention_days ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, retention_days: parseInt(e.target.value, 10) || undefined }))}
              />
            </label>
            <label className="flex items-center gap-2">
              max_rows
              <input
                type="number"
                min={100}
                max={50000}
                className="border rounded px-2 py-1 w-24"
                value={form.max_rows ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, max_rows: parseInt(e.target.value, 10) || undefined }))}
              />
            </label>
            <label className="flex items-center gap-2">
              max_body_kb
              <input
                type="number"
                min={1}
                max={512}
                className="border rounded px-2 py-1 w-20"
                value={form.max_body_kb ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, max_body_kb: parseInt(e.target.value, 10) || undefined }))}
              />
            </label>
            <label className="flex items-center gap-2">
              target_budget_mb
              <input
                type="number"
                min={10}
                max={2000}
                className="border rounded px-2 py-1 w-24"
                value={form.target_budget_mb ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, target_budget_mb: parseInt(e.target.value, 10) || undefined }))}
              />
            </label>
            <div className="sm:col-span-2">
              <button
                type="button"
                className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                disabled={saveSettingsMutation.isPending || !editForm || Object.keys(editForm).length === 0}
                onClick={() => editForm && saveSettingsMutation.mutate(editForm)}
              >
                {saveSettingsMutation.isPending ? "" : ""}
              </button>
              {editForm && Object.keys(editForm).length > 0 && (
                <button
                  type="button"
                  className="ml-2 text-gray-600 text-sm"
                  onClick={() => setEditForm(null)}
                >
                  
                </button>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Storage usage */}
      <section className="bg-white shadow rounded p-4">
        <h2 className="text-lg font-semibold mb-3">Storage usage</h2>
        {usageLoading && <p className="text-gray-500">...</p>}
        {!usageLoading && usage && (
          <>
            <div className="flex items-center gap-4 mb-2">
              <div className="flex-1 bg-gray-200 rounded-full h-4 max-w-xs">
                <div
                  className={`h-4 rounded-full ${overBudget ? "bg-orange-500" : "bg-blue-500"}`}
                  style={{ width: `${Math.min(100, usage.percent)}%` }}
                />
              </div>
              <span className="text-sm">
                {usage.used_mb} MB / {usage.target_budget_mb} MB ({usage.percent}%)
              </span>
            </div>
            <p className="text-sm text-gray-600">
              approx_rows: {usage.approx_rows}  oldest: {usage.oldest_at?.slice(0, 19) ?? ""}  newest: {usage.newest_at?.slice(0, 19) ?? ""}
            </p>
            <button
              type="button"
              className="mt-2 text-blue-600 text-sm hover:underline"
              onClick={() => refetchUsage()}
            >
              
            </button>
          </>
        )}
      </section>

      {/* Prune */}
      <section className="bg-white shadow rounded p-4">
        <h2 className="text-lg font-semibold mb-3"></h2>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            className="bg-gray-600 text-white px-3 py-1 rounded text-sm hover:bg-gray-700 disabled:opacity-50"
            disabled={pruneMutation.isPending}
            onClick={() => pruneMutation.mutate({ mode: "auto" })}
          >
            {pruneMutation.isPending ? "" : " - "}
          </button>
          <button
            type="button"
            className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700 disabled:opacity-50"
            disabled={pruneMutation.isPending}
            onClick={() => {
              if (window.confirm("   inbound events?")) {
                pruneMutation.mutate({ mode: "all" });
              }
            }}
          >
             
          </button>
        </div>
        {pruneMutation.data && (
          <p className="mt-2 text-sm text-gray-600">
            : {pruneMutation.data.deleted_rows}, : {pruneMutation.data.remaining_rows}, used_mb_after: {pruneMutation.data.used_mb_after}
          </p>
        )}
      </section>

      {/* Table */}
      <section className="bg-white shadow rounded overflow-hidden">
        <h2 className="text-lg font-semibold p-4 pb-2"> inbound </h2>
        <div className="mb-4 px-4 flex flex-wrap gap-2 items-center">
          <input
            type="text"
            placeholder="portal_id"
            className="border rounded px-2 py-1 text-sm w-24"
            value={portalId}
            onChange={(e) => setPortalId(e.target.value)}
          />
          <input
            type="text"
            placeholder="domain"
            className="border rounded px-2 py-1 text-sm w-48"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
          <input
            type="text"
            placeholder="trace_id"
            className="border rounded px-2 py-1 text-sm w-40"
            value={traceId}
            onChange={(e) => setTraceId(e.target.value)}
          />
        </div>
        {isLoading && <p className="px-4 text-gray-500">...</p>}
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">created_at</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">portal</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">domain</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">member_id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">dialog_id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">user_id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">event</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">trace_id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">trunc</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{r.id}</td>
                <td className="px-4 py-2 text-sm text-gray-500">{r.created_at?.slice(0, 19) ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.portal_id ?? ""}</td>
                <td className="px-4 py-2 text-sm truncate max-w-[140px]">{r.domain ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.member_id ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.dialog_id ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.user_id ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.event_name ?? (r.hints_json?.event_name ? String(r.hints_json.event_name) : "")}</td>
                <td className="px-4 py-2 text-sm font-mono">{r.trace_id ?? ""}</td>
                <td className="px-4 py-2 text-sm">{r.body_truncated ? "yes" : ""}</td>
                <td className="px-4 py-2 text-sm">
                  <Link to={`/admin/inbound-events/${r.id}`} className="text-blue-600 hover:underline">
                    
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-4 py-2 text-sm text-gray-500">: {items.length}</p>
      </section>
    </div>
  );
}
