import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export function SystemPage() {
  const { data: health } = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.get("/v1/admin/system/health"),
  });
  const { data: queue } = useQuery({
    queryKey: ["system-queue"],
    queryFn: () => api.get("/v1/admin/system/queue"),
  });
  const { data: workers } = useQuery({
    queryKey: ["system-workers"],
    queryFn: () => api.get("/v1/admin/system/workers"),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6"></h1>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-semibold mb-2"></h2>
          <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(health ?? {}, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-semibold mb-2"></h2>
          <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(queue ?? {}, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6 md:col-span-2">
          <h2 className="font-semibold mb-2">Workers</h2>
          <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(workers ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
