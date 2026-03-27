import { useEffect, useState } from "react";
import { coreModuleEmptyState, coreModuleLoadingLabel } from "../../../../shared/ui/modules";
import { coreSectionCopy } from "../../../../shared/ui/sections";
import { EmptyStateBlock } from "../../components/EmptyStateBlock";
import { PageIntro } from "../../components/PageIntro";
import { SectionCard } from "../../components/SectionCard";
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
  const sourcesEmpty = coreModuleEmptyState(
    "sources",
    "Источников пока нет",
    "Добавьте URL-источники, чтобы база знаний обновлялась из внешних материалов.",
  );
  const sourcesLoadingLabel = coreModuleLoadingLabel("sources", "Загрузка...");
  const sectionCopy = coreSectionCopy("sources");

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
      <PageIntro
        moduleId="sources"
        fallbackTitle="Источники данных"
        fallbackDescription="Добавляйте URL-источники и внешние материалы для аккаунта."
      />

      <SectionCard title={sectionCopy.sourceListTitle}>
        <div className="mt-4">
          <label className="text-xs text-slate-600">{sectionCopy.sourceInputLabel}</label>
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
              {sectionCopy.addUrlAction}
            </button>
          </div>
          {message && <div className="mt-2 text-xs text-slate-500">{message}</div>}
        </div>
      </SectionCard>

      <SectionCard
        title={sectionCopy.sourceListTitle}
        actions={<div className="text-xs text-slate-500">{loading ? sourcesLoadingLabel : sectionCopy.countLabel(sources.length)}</div>}
      >
        {sources.length === 0 ? (
          <EmptyStateBlock className="mt-4" title={sourcesEmpty.title} description={sourcesEmpty.description} />
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
      </SectionCard>
    </div>
  );
}
