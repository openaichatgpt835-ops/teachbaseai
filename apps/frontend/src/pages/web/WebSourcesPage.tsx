import { useEffect, useState } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";

type KbSource = {
  id: number;
  url: string;
  status?: string;
  created_at?: string;
};

const sourcesCache = new Map<number, KbSource[]>();

export function WebSourcesPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const [sources, setSources] = useState<KbSource[]>(() => (portalId ? sourcesCache.get(portalId) || [] : []));
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const loadSources = async () => {
    if (!portalId || !portalToken) return;
    setLoading(true);
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/sources`);
      const data = await res.json().catch(() => null);
      if (res.ok && data?.items) {
        setSources(data.items);
        sourcesCache.set(portalId, data.items);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (portalId) {
      const cached = sourcesCache.get(portalId);
      if (cached) setSources(cached);
    }
    loadSources();
  }, [portalId, portalToken]);

  const addUrl = async () => {
    if (!portalId || !portalToken || !url.trim()) return;
    setMessage("Добавление...");
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/sources/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setMessage(data?.error || data?.detail || "Ошибка");
        return;
      }
      setMessage("Добавлено.");
      setUrl("");
      await loadSources();
    } catch {
      setMessage("Ошибка");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Источники данных</h1>
        <p className="text-sm text-slate-500 mt-1">Добавляйте URL‑источники (YouTube / VK / Rutube).</p>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">URL‑источники</h2>
        <div className="mt-4">
          <label className="text-xs text-slate-600">Ссылка</label>
          <div className="mt-2 flex gap-3">
            <input
              type="url"
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="https://..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button
              className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
              onClick={addUrl}
            >
              Добавить URL
            </button>
          </div>
          {message && <div className="mt-2 text-xs text-slate-500">{message}</div>}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Источники</h2>
          <div className="text-xs text-slate-500">{loading ? "Загрузка..." : `Всего: ${sources.length}`}</div>
        </div>
        {sources.length === 0 ? (
          <div className="mt-4 text-sm text-slate-500">Источников пока нет.</div>
        ) : (
          <div className="mt-4 space-y-3">
            {sources.map((s) => (
              <div key={s.id} className="rounded-xl border border-slate-100 px-4 py-3">
                <div className="text-sm text-slate-900">{s.url}</div>
                <div className="text-xs text-slate-500 mt-1">
                  {s.status || "—"} {s.created_at ? `· ${s.created_at}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
