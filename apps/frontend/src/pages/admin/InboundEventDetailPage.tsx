import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export function InboundEventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["inbound-event", id],
    queryFn: () =>
      api.get(`/v1/admin/inbound-events/${id}`) as Promise<{
        id: number;
        created_at: string | null;
        trace_id: string | null;
        portal_id: number | null;
        domain: string | null;
        member_id: string | null;
        dialog_id: string | null;
        user_id: string | null;
        event_name: string | null;
        remote_ip: string | null;
        method: string;
        path: string;
        query: string | null;
        content_type: string | null;
        headers_json: Record<string, unknown> | null;
        body_preview: string | null;
        body_truncated: boolean;
        body_sha256: string | null;
        parsed_redacted_json: Record<string, unknown> | null;
        hints_json: Record<string, unknown> | null;
        status_hint: string | null;
      }>,
    enabled: !!id,
  });

  if (!id || isLoading || !data) {
    return <div>{isLoading ? "Загрузка..." : "Не найден"}</div>;
  }

  return (
    <div>
      <Link to="/admin/inbound-events" className="text-blue-600 hover:underline mb-2 inline-block">
        ← Inbound events
      </Link>
      <h1 className="text-xl font-bold mb-4">Inbound event #{data.id}</h1>
      <dl className="grid grid-cols-1 gap-2 mb-4">
        <dt className="font-medium text-gray-600">created_at</dt>
        <dd className="font-mono text-sm">{data.created_at ?? "—"}</dd>
        <dt className="font-medium text-gray-600">trace_id</dt>
        <dd className="font-mono text-sm">{data.trace_id ?? "—"}</dd>
        <dt className="font-medium text-gray-600">portal_id / domain</dt>
        <dd className="font-mono text-sm">{data.portal_id ?? "—"} / {data.domain ?? "—"}</dd>
        <dt className="font-medium text-gray-600">member_id</dt>
        <dd className="font-mono text-sm">{data.member_id ?? "—"}</dd>
        <dt className="font-medium text-gray-600">dialog_id</dt>
        <dd className="font-mono text-sm">{data.dialog_id ?? "—"}</dd>
        <dt className="font-medium text-gray-600">user_id</dt>
        <dd className="font-mono text-sm">{data.user_id ?? "—"}</dd>
        <dt className="font-medium text-gray-600">event_name</dt>
        <dd className="font-mono text-sm">{data.event_name ?? "—"}</dd>
        <dt className="font-medium text-gray-600">remote_ip</dt>
        <dd className="font-mono text-sm">{data.remote_ip ?? "—"}</dd>
        <dt className="font-medium text-gray-600">method / path</dt>
        <dd className="font-mono text-sm">{data.method} {data.path}</dd>
        <dt className="font-medium text-gray-600">body_sha256</dt>
        <dd className="font-mono text-sm break-all">{data.body_sha256 ?? "—"}</dd>
        <dt className="font-medium text-gray-600">body_truncated</dt>
        <dd>{data.body_truncated ? "yes" : "no"}</dd>
      </dl>
      {data.hints_json && Object.keys(data.hints_json).length > 0 && (
        <div className="mb-4">
          <h2 className="text-sm font-bold text-gray-700 mb-1">hints_json</h2>
          <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-32">
            {JSON.stringify(data.hints_json, null, 2)}
          </pre>
        </div>
      )}
      {data.headers_json && Object.keys(data.headers_json).length > 0 && (
        <div className="mb-4">
          <h2 className="text-sm font-bold text-gray-700 mb-1">headers_json</h2>
          <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-32">
            {JSON.stringify(data.headers_json, null, 2)}
          </pre>
        </div>
      )}
      {data.parsed_redacted_json && (
        <div className="mb-4">
          <h2 className="text-sm font-bold text-gray-700 mb-1">parsed_redacted_json</h2>
          <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-64">
            {JSON.stringify(data.parsed_redacted_json, null, 2)}
          </pre>
        </div>
      )}
      {data.body_preview != null && (
        <div className="mb-4">
          <h2 className="text-sm font-bold text-gray-700 mb-1">body_preview</h2>
          <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-64 whitespace-pre-wrap break-all">
            {data.body_preview.length > 8000 ? data.body_preview.slice(0, 8000) + "\n…" : data.body_preview}
          </pre>
        </div>
      )}
    </div>
  );
}
