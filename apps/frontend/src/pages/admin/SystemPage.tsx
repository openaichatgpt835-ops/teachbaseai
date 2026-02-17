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
    refetchInterval: 5000,
  });
  const { data: workers } = useQuery({
    queryKey: ["system-workers"],
    queryFn: () => api.get("/v1/admin/system/workers"),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Система</h1>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-semibold mb-2">Здоровье сервисов</h2>
          <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(health ?? {}, null, 2)}
          </pre>
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-semibold mb-2">Очереди RQ</h2>
          <div className="space-y-2">
            {Array.isArray((queue as { queues?: unknown[] } | undefined)?.queues) ? (
              ((queue as { queues: Array<{ queue_name: string; queued: number; started: number; failed: number; workers: number; overloaded: boolean }> }).queues).map((q) => (
                <div key={q.queue_name} className="border rounded p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">{q.queue_name}</div>
                    <div className={q.overloaded ? "text-red-600 font-semibold" : "text-green-700 font-semibold"}>
                      {q.overloaded ? "перегруз" : "норма"}
                    </div>
                  </div>
                  <div className="mt-1 text-gray-700">
                    queued: {q.queued} | started: {q.started} | workers: {q.workers} | failed: {q.failed}
                  </div>
                </div>
              ))
            ) : (
              <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
                {JSON.stringify(queue ?? {}, null, 2)}
              </pre>
            )}
          </div>
        </div>
        <div className="bg-white shadow rounded-lg p-6 md:col-span-2">
          <h2 className="font-semibold mb-2">Воркеры</h2>
          <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(workers ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
