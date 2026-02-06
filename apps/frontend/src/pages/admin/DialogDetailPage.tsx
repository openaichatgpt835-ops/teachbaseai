import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export function DialogDetailPage() {
  const { id } = useParams();
  const { data: dialog, isLoading: ld } = useQuery({
    queryKey: ["dialog", id],
    queryFn: () => api.get(`/v1/admin/dialogs/${id}`),
    enabled: !!id,
  });
  const { data: messages, isLoading: lm } = useQuery({
    queryKey: ["dialog-messages", id],
    queryFn: () => api.get(`/v1/admin/dialogs/${id}/messages`),
    enabled: !!id,
  });

  if (ld || lm) return <div>Загрузка...</div>;
  if (!dialog) return null;

  const d = dialog as { id: number; portal_id: number; provider_dialog_id: string };
  const items = (messages?.items || []) as { id: number; direction: string; body: string }[];

  return (
    <div>
      <div className="mb-4">
        <Link to="/admin/dialogs" className="text-blue-600 hover:underline">← Диалоги</Link>
      </div>
      <h1 className="text-2xl font-bold mb-6">Диалог #{d.id}</h1>
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <p className="text-gray-600">Portal: {d.portal_id} | Provider: {d.provider_dialog_id}</p>
      </div>
      <h2 className="text-lg font-semibold mb-4">Сообщения</h2>
      <div className="space-y-2">
        {items.map((m) => (
          <div
            key={m.id}
            className={`p-4 rounded-lg ${m.direction === "rx" ? "bg-blue-50" : "bg-green-50"}`}
          >
            <span className="text-xs text-gray-500">{m.direction}</span>
            <p className="mt-1">{m.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
