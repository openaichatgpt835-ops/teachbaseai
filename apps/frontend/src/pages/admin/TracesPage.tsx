import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export function TracesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["traces"],
    queryFn: () => api.get("/v1/admin/traces") as Promise<{ items: unknown[] }>,
  });

  const items = (data?.items ?? []) as Array<{
    id: number;
    trace_id: string;
    portal_id: number | null;
    direction: string;
    kind: string;
    method: string;
    path: string;
    summary: string | null;
    status_code: number | null;
    latency_ms: number | null;
    created_at: string | null;
  }>;

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Трейсы Bitrix</h1>
      {isLoading && <p>Загрузка...</p>}
      <div className="bg-white shadow rounded overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">trace_id</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">portal</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">dir</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">kind</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">method</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">path</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">ms</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {items.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-mono">
                  <Link to={`/admin/traces/${r.trace_id}`} className="text-blue-600 hover:underline">
                    {r.trace_id}
                  </Link>
                </td>
                <td className="px-4 py-2 text-sm">{r.portal_id ?? "—"}</td>
                <td className="px-4 py-2 text-sm">{r.direction}</td>
                <td className="px-4 py-2 text-sm">{r.kind}</td>
                <td className="px-4 py-2 text-sm">{r.method}</td>
                <td className="px-4 py-2 text-sm truncate max-w-[200px]">{r.path}</td>
                <td className="px-4 py-2 text-sm">{r.status_code ?? "—"}</td>
                <td className="px-4 py-2 text-sm">{r.latency_ms ?? "—"}</td>
                <td className="px-4 py-2 text-sm text-gray-500">{r.created_at?.slice(0, 19) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
