import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

export function TraceDetailPage() {
  const [copiedKey, setCopiedKey] = useState<string>("");
  const { traceId } = useParams<{ traceId: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => api.get(`/v1/admin/traces/${traceId}`),
    enabled: !!traceId,
  });
  const timelineQ = useQuery({
    queryKey: ["trace-timeline", traceId],
    queryFn: () => api.get(`/v1/admin/traces/${traceId}/timeline`) as Promise<{
      trace_id: string;
      items: Array<{
        source: string;
        id: number;
        created_at: string | null;
        portal_id: number | null;
        kind: string | null;
        status: string | number | null;
        summary: string | null;
      }>;
    }>,
    enabled: !!traceId,
  });

  if (isLoading) return <div>...</div>;
  if (error) return <div className="text-red-600">: {String(error)}</div>;
  if (!data) return null;

  const copyJson = async (key: string, value: unknown) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(""), 1200);
    } catch {
      setCopiedKey("");
    }
  };

  const payload = data as {
    trace_id: string;
    items: Array<{
      id: number;
      trace_id: string;
      portal_id: number | null;
      direction: string;
      kind: string;
      method: string;
      path: string;
      status_code: number | null;
      latency_ms: number | null;
      created_at: string | null;
      bitrix_error_code?: string;
      bitrix_error_desc?: string;
      event_message_add_url?: string;
      content_type_sent?: string;
      sent_keys?: string[];
      top_level_name_enabled?: boolean;
      api_prefix_used?: string;
      event_urls_sent?: string[];
      request_json?: unknown;
      response_json?: unknown;
      headers_min?: Record<string, unknown>;
      summary?: Record<string, unknown>;
    }>;
  };

  return (
    <div>
      <div className="mb-4">
        <Link to="/admin/traces" className="text-blue-600 hover:underline">  Bitrix</Link>
      </div>
      <h1 className="text-xl font-bold mb-4"> : {payload.trace_id}</h1>
      {timelineQ.data?.items?.length ? (
        <div className="mb-6 bg-white shadow rounded-lg p-4 border">
          <h2 className="text-sm font-semibold mb-2">Timeline</h2>
          <div className="space-y-2">
            {timelineQ.data.items.map((t) => (
              <div key={`${t.source}-${t.id}`} className="text-sm text-gray-700 border rounded px-3 py-2">
                <span className="font-mono text-xs text-gray-500 mr-2">{t.created_at?.slice(0, 19) ?? ""}</span>
                <span className="font-medium mr-2">{t.source}</span>
                <span className="mr-2">{t.kind ?? ""}</span>
                <span className="text-gray-500 mr-2">status: {String(t.status ?? "")}</span>
                <span className="text-gray-500">{t.summary ?? ""}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="space-y-6">
        {payload.items.map((r) => (
          <div key={r.id} className="bg-white shadow rounded-lg p-4 border">
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">dir</dt>
              <dd>{r.direction}</dd>
              <dt className="text-gray-500">kind</dt>
              <dd>{r.kind}</dd>
              <dt className="text-gray-500">method</dt>
              <dd>{r.method}</dd>
              <dt className="text-gray-500">path</dt>
              <dd className="font-mono">{r.path}</dd>
              <dt className="text-gray-500">status_code</dt>
              <dd>{r.status_code ?? ""}</dd>
              <dt className="text-gray-500">latency_ms</dt>
              <dd>{r.latency_ms ?? ""}</dd>
              <dt className="text-gray-500">created_at</dt>
              <dd>{r.created_at ?? ""}</dd>
              {r.bitrix_error_code != null && (
                <>
                  <dt className="text-gray-500">bitrix_error_code</dt>
                  <dd className="text-red-600">{r.bitrix_error_code}</dd>
                </>
              )}
              {r.bitrix_error_desc != null && (
                <>
                  <dt className="text-gray-500">bitrix_error_desc</dt>
                  <dd className="text-gray-700">{r.bitrix_error_desc}</dd>
                </>
              )}
              {r.event_message_add_url != null && (
                <>
                  <dt className="text-gray-500">event_message_add_url</dt>
                  <dd className="font-mono text-xs break-all">{r.event_message_add_url}</dd>
                </>
              )}
              {r.content_type_sent != null && (
                <>
                  <dt className="text-gray-500">content_type_sent</dt>
                  <dd>{r.content_type_sent}</dd>
                </>
              )}
              {r.api_prefix_used != null && (
                <>
                  <dt className="text-gray-500">api_prefix_used</dt>
                  <dd>{r.api_prefix_used}</dd>
                </>
              )}
              {r.sent_keys != null && r.sent_keys.length > 0 && (
                <>
                  <dt className="text-gray-500">sent_keys</dt>
                  <dd className="font-mono text-xs">{r.sent_keys.join(", ")}</dd>
                </>
              )}
              {r.event_urls_sent != null && r.event_urls_sent.length > 0 && (
                <>
                  <dt className="text-gray-500">event_urls_sent</dt>
                  <dd className="font-mono text-xs break-all">{r.event_urls_sent.join(", ")}</dd>
                </>
              )}
              {(r.kind === "imbot_chat_add" || r.kind === "imbot_message_add") && r.summary && (
                <>
                  <dt className="text-gray-500">target_user_id</dt>
                  <dd>{(r.summary as { target_user_id?: number }).target_user_id ?? ""}</dd>
                  {(r.summary as { dialog_id?: string }).dialog_id != null && (
                    <>
                      <dt className="text-gray-500">dialog_id</dt>
                      <dd className="font-mono text-xs">{(r.summary as { dialog_id?: string }).dialog_id}</dd>
                    </>
                  )}
                  {(r.summary as { chat_id?: number }).chat_id != null && (
                    <>
                      <dt className="text-gray-500">chat_id</dt>
                      <dd>{(r.summary as { chat_id?: number }).chat_id}</dd>
                    </>
                  )}
                </>
              )}
              {r.kind === "prepare_chats" && r.summary && (
                <>
                  <dt className="text-gray-500">total</dt>
                  <dd>{(r.summary as { total?: number }).total ?? ""}</dd>
                  <dt className="text-gray-500">ok_count</dt>
                  <dd>{(r.summary as { ok_count?: number }).ok_count ?? ""}</dd>
                  <dt className="text-gray-500">users_failed</dt>
                  <dd>{(r.summary as { users_failed?: number }).users_failed ?? ""}</dd>
                  {(r.summary as { failed?: Array<{ user_id?: number; code?: string }> }).failed?.length ? (
                    <>
                      <dt className="text-gray-500">failed</dt>
                      <dd className="font-mono text-xs">
                        {(r.summary as { failed: Array<{ user_id?: number; code?: string }> }).failed
                          .map((f) => `${f.user_id ?? "?"}: ${f.code ?? "?"}`)
                          .join("; ")}
                      </dd>
                    </>
                  ) : null}
                </>
              )}
              {r.headers_min != null && (
                <>
                  <dt className="text-gray-500">headers_min</dt>
                  <dd>
                    <div className="mb-1">
                      <button
                        type="button"
                        onClick={() => copyJson(`headers-${r.id}`, r.headers_min)}
                        className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
                      >
                        {copiedKey === `headers-${r.id}` ? "Скопировано" : "Скопировать JSON"}
                      </button>
                    </div>
                    <pre className="text-xs bg-gray-50 border rounded p-2 overflow-x-auto">
                      {JSON.stringify(r.headers_min, null, 2)}
                    </pre>
                  </dd>
                </>
              )}
              {r.request_json != null && (
                <>
                  <dt className="text-gray-500">request_json</dt>
                  <dd>
                    <div className="mb-1">
                      <button
                        type="button"
                        onClick={() => copyJson(`request-${r.id}`, r.request_json)}
                        className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
                      >
                        {copiedKey === `request-${r.id}` ? "Скопировано" : "Скопировать JSON"}
                      </button>
                    </div>
                    <pre className="text-xs bg-gray-50 border rounded p-2 overflow-x-auto">
                      {JSON.stringify(r.request_json, null, 2)}
                    </pre>
                  </dd>
                </>
              )}
              {r.response_json != null && (
                <>
                  <dt className="text-gray-500">response_json</dt>
                  <dd>
                    <div className="mb-1">
                      <button
                        type="button"
                        onClick={() => copyJson(`response-${r.id}`, r.response_json)}
                        className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
                      >
                        {copiedKey === `response-${r.id}` ? "Скопировано" : "Скопировать JSON"}
                      </button>
                    </div>
                    <pre className="text-xs bg-gray-50 border rounded p-2 overflow-x-auto">
                      {JSON.stringify(r.response_json, null, 2)}
                    </pre>
                  </dd>
                </>
              )}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
