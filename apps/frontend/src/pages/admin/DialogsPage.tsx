import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";

export function DialogsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dialogs"],
    queryFn: () => api.get("/v1/admin/dialogs"),
  });

  if (isLoading) return <div className="text-gray-600">Загрузка диалогов...</div>;
  if (error) return <div className="text-red-600">Ошибка: {String(error)}</div>;

  const items = (data?.items || []) as { id: number; portal_id: number; provider_dialog_id: string }[];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Диалоги</h1>
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {items.length === 0 ? (
            <li className="px-4 py-4">Диалогов пока нет. Используйте симулятор.</li>
          ) : (
            items.map((d) => (
              <li key={d.id}>
                <Link to={`/admin/dialogs/${d.id}`} className="block hover:bg-gray-50 px-4 py-4">
                  <span className="font-medium">Диалог #{d.id}</span>
                  <span className="text-gray-500 ml-2">portal={d.portal_id} | {d.provider_dialog_id}</span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
