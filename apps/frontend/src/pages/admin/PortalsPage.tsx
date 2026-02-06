import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";

export function PortalsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["portals"],
    queryFn: () => api.get("/v1/admin/portals"),
  });

  if (isLoading) return <div className="text-gray-600">Загрузка порталов...</div>;
  if (error) return <div className="text-red-600">Ошибка: {String(error)}</div>;

  const items = (data?.items || []) as { id: number; domain: string; status: string }[];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Порталы</h1>
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {items.length === 0 ? (
            <li className="px-4 py-4">Порталов пока нет.</li>
          ) : (
            items.map((p) => (
              <li key={p.id}>
                <Link to={`/admin/portals/${p.id}`} className="block hover:bg-gray-50 px-4 py-4">
                  <div className="flex justify-between">
                    <span className="font-medium">{p.domain}</span>
                    <span className={`text-sm ${p.status === "active" ? "text-green-600" : "text-gray-500"}`}>
                      {p.status}
                    </span>
                  </div>
                </Link>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
