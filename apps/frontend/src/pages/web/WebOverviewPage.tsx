import { useEffect, useMemo, useState } from "react";
import { coreModuleEmptyState } from "../../../../shared/ui/modules";
import { coreSectionCopy } from "../../../../shared/ui/sections";
import { EmptyStateBlock } from "../../components/EmptyStateBlock";
import { PageIntro } from "../../components/PageIntro";
import { SectionCard } from "../../components/SectionCard";
import { fetchPortal, getActiveAccountId, getWebPortalInfo } from "./auth";

type KbFile = { id: number; status: string; created_at?: string };
type KbSource = { id: number };
type TopicSummary = { topic: string; score?: number };
type OverviewState = {
  kbFiles: KbFile[];
  kbSources: KbSource[];
  usersCount: number;
  selectedUsersCount: number;
  activeUsers: number;
  topicSummaries: TopicSummary[];
  lastUpdated: string;
};

const OVERVIEW_DEFAULT: OverviewState = {
  kbFiles: [],
  kbSources: [],
  usersCount: 0,
  selectedUsersCount: 0,
  activeUsers: 0,
  topicSummaries: [],
  lastUpdated: "—",
};

const overviewCache = new Map<number, OverviewState>();

export function WebOverviewPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const activeAccountId = getActiveAccountId();
  const cacheKey = activeAccountId || portalId;
  const [overview, setOverview] = useState<OverviewState>(() => {
    if (!cacheKey) return OVERVIEW_DEFAULT;
    return overviewCache.get(cacheKey) || OVERVIEW_DEFAULT;
  });

  const kbCounts = useMemo(() => {
    const counts = { ready: 0, queued: 0, error: 0 };
    for (const f of overview.kbFiles) {
      const st = (f.status || "").toLowerCase();
      if (st === "ready") counts.ready += 1;
      else if (st === "queued" || st === "processing" || st === "uploaded") counts.queued += 1;
      else if (st === "error") counts.error += 1;
    }
    return counts;
  }, [overview.kbFiles]);

  const sortedTopicSummaries = useMemo(() => {
    return [...overview.topicSummaries].sort((a, b) => Number(b.score ?? -1) - Number(a.score ?? -1));
  }, [overview.topicSummaries]);
  const overviewEmpty = coreModuleEmptyState(
    "overview",
    "Обзор пока пуст",
    "Подключите источники и задайте первый вопрос, чтобы наполнить рабочий обзор.",
  );
  const sectionCopy = coreSectionCopy("overview");

  useEffect(() => {
    if (!portalId || !portalToken) return;
    const cached = cacheKey ? overviewCache.get(cacheKey) : null;
    if (cached) setOverview(cached);

    const load = async () => {
      try {
        const [filesRes, sourcesRes, usersRes, accessRes, statsRes, summaryRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/sources`),
          fetchPortal(`/api/v1/bitrix/users?portal_id=${portalId}`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/access/users`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/users/stats?hours=24`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/dialogs/summary`),
        ]);
        const files = await filesRes.json().catch(() => null);
        const sources = await sourcesRes.json().catch(() => null);
        const users = await usersRes.json().catch(() => null);
        const access = await accessRes.json().catch(() => null);
        const stats = await statsRes.json().catch(() => null);
        const summary = await summaryRes.json().catch(() => null);

        setOverview((prev) => {
          const accessItems = Array.isArray(access?.items) ? access.items : [];
          const bitrixFromUsers = usersRes.ok && Array.isArray(users?.items) ? users.items.length : null;
          const bitrixFromAccess = new Set(
            accessItems
              .filter((it: any) => (it?.kind || "bitrix") === "bitrix")
              .map((it: any) => String(it?.user_id || ""))
              .filter(Boolean)
          ).size;
          const nonBitrixCount = new Set(
            accessItems
              .filter((it: any) => (it?.kind || "bitrix") !== "bitrix")
              .map((it: any) => `${String(it?.kind || "other")}:${String(it?.user_id || "")}`)
              .filter((v: string) => !v.endsWith(":"))
          ).size;
          const totalUsers = (bitrixFromUsers ?? bitrixFromAccess) + nonBitrixCount;

          const next: OverviewState = {
            kbFiles: filesRes.ok && files?.items ? files.items : prev.kbFiles,
            kbSources: sourcesRes.ok && sources?.items ? sources.items : prev.kbSources,
            usersCount: Number.isFinite(totalUsers) ? totalUsers : prev.usersCount,
            selectedUsersCount: accessRes.ok && accessItems.length ? accessItems.length : prev.selectedUsersCount,
            activeUsers: statsRes.ok && stats?.stats ? Object.keys(stats.stats || {}).length : prev.activeUsers,
            topicSummaries: summaryRes.ok && summary?.items ? summary.items : prev.topicSummaries,
            lastUpdated: new Date().toLocaleString("ru-RU"),
          };
          if (cacheKey) overviewCache.set(cacheKey, next);
          return next;
        });
      } catch {
        // keep previous snapshot
      }
    };

    load();
  }, [portalId, portalToken, cacheKey]);

  return (
    <div className="space-y-6">
      <PageIntro
        moduleId="overview"
        fallbackTitle="Обзор"
        fallbackDescription="Ключевые метрики и фокус запросов."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={sectionCopy.overviewKnowledgeTitle}>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Metric label={sectionCopy.overviewMetricLabel("files")} value={overview.kbFiles.length} />
            <Metric label={sectionCopy.overviewMetricLabel("url_sources")} value={overview.kbSources.length} />
            <Metric label={sectionCopy.overviewMetricLabel("last_updated")} value={overview.lastUpdated} />
            <Metric label={sectionCopy.overviewMetricLabel("status")} value={kbCounts.error > 0 ? "Есть ошибки" : "Актуальна"} />
          </div>
        </SectionCard>

        <SectionCard title={sectionCopy.overviewUsageTitle}>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Metric label={sectionCopy.overviewMetricLabel("active_today")} value={overview.activeUsers} />
            <Metric label={sectionCopy.overviewMetricLabel("users_total")} value={overview.usersCount} />
            <Metric label={sectionCopy.overviewMetricLabel("access_granted")} value={overview.selectedUsersCount} />
            <Metric label={sectionCopy.overviewMetricLabel("index_errors")} value={kbCounts.error} />
          </div>
        </SectionCard>
      </div>

      <SectionCard title={sectionCopy.overviewFocusTitle}>
        {sortedTopicSummaries.length ? (
          <div className="mt-4 space-y-3">
            {sortedTopicSummaries.map((t, idx) => (
              <div key={`${t.topic}-${idx}`} className="flex items-center justify-between rounded-xl border border-slate-100 px-4 py-3">
                <div>
                  <div className="text-sm text-slate-900">{t.topic}</div>
                  {t.score ? <div className="text-xs text-slate-500">оценка: {t.score}</div> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyStateBlock className="mt-4" title={overviewEmpty.title} description={overviewEmpty.description} />
        )}
      </SectionCard>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900 mt-1">{value}</div>
    </div>
  );
}
