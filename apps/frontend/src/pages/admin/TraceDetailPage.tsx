import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => api.get(`/v1/admin/traces/${traceId}`),
    enabled: !!traceId,
  });

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div className="text-red-600">Ошибка: {String(error)}</div>;
  if (!data) return null;

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
      summary?: Record<string, unknown>;
    }>;
  };

  return (
    <div>
      <div className="mb-4">
        <Link to="/admin/traces" className="text-blue-600 hover:underline">← Трейсы Bitrix</Link>
      </div>
      <h1 className="text-xl font-bold mb-4">Детали трейса: {payload.trace_id}</h1>
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
              <dd>{r.status_code ?? "—"}</dd>
              <dt className="text-gray-500">latency_ms</dt>
              <dd>{r.latency_ms ?? "—"}</dd>
              <dt className="text-gray-500">created_at</dt>
              <dd>{r.created_at ?? "—"}</dd>
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
                  <dd>{(r.summary as { target_user_id?: number }).target_user_id ?? "—"}</dd>
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
                  <dd>{(r.summary as { total?: number }).total ?? "—"}</dd>
                  <dt className="text-gray-500">ok_count</dt>
                  <dd>{(r.summary as { ok_count?: number }).ok_count ?? "—"}</dd>
                  <dt className="text-gray-500">users_failed</dt>
                  <dd>{(r.summary as { users_failed?: number }).users_failed ?? "—"}</dd>
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
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
