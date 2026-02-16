import { useEffect, useMemo, useState } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";

type KbFile = { id: number; status: string; created_at?: string };
type KbSource = { id: number };
type TopicSummary = { topic: string; score?: number };

export function WebOverviewPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const [kbFiles, setKbFiles] = useState<KbFile[]>([]);
  const [kbSources, setKbSources] = useState<KbSource[]>([]);
  const [usersCount, setUsersCount] = useState(0);
  const [selectedUsersCount, setSelectedUsersCount] = useState(0);
  const [activeUsers, setActiveUsers] = useState(0);
  const [topicSummaries, setTopicSummaries] = useState<TopicSummary[]>([]);
  const [lastUpdated, setLastUpdated] = useState("—");

  const kbCounts = useMemo(() => {
    const counts = { ready: 0, queued: 0, error: 0 };
    for (const f of kbFiles) {
      const st = (f.status || "").toLowerCase();
      if (st === "ready") counts.ready += 1;
      else if (st === "queued" || st === "processing" || st === "uploaded") counts.queued += 1;
      else if (st === "error") counts.error += 1;
    }
    return counts;
  }, [kbFiles]);

  useEffect(() => {
    if (!portalId || !portalToken) return;
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

        if (filesRes.ok && files?.items) setKbFiles(files.items);
        if (sourcesRes.ok && sources?.items) setKbSources(sources.items);
        if (usersRes.ok && users?.items) setUsersCount(users.items.length);
        if (accessRes.ok && access?.user_ids) setSelectedUsersCount(access.user_ids.length);
        if (statsRes.ok && stats?.stats) setActiveUsers(Object.keys(stats.stats || {}).length);
        if (summaryRes.ok && summary?.items) setTopicSummaries(summary.items);
        setLastUpdated(new Date().toLocaleString("ru-RU"));
      } catch {
        // ignore
      }
    };
    load();
  }, [portalId, portalToken]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Обзор</h1>
        <p className="text-sm text-slate-500 mt-1">Ключевые метрики и фокус запросов.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900">База знаний</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Metric label="Файлов" value={kbFiles.length} />
            <Metric label="URL‑источников" value={kbSources.length} />
            <Metric label="Последнее обновление" value={lastUpdated} />
            <Metric label="Статус" value={kbCounts.error > 0 ? "Есть ошибки" : "Актуальна"} />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900">Использование</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Metric label="Активные сегодня" value={activeUsers} />
            <Metric label="Всего сотрудников" value={usersCount} />
            <Metric label="Доступ разрешён" value={selectedUsersCount} />
            <Metric label="Ошибки индексации" value={kbCounts.error} />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Фокус запросов</h2>
        {topicSummaries.length ? (
          <div className="mt-4 space-y-3">
            {topicSummaries.map((t, idx) => (
              <div key={`${t.topic}-${idx}`} className="flex items-center justify-between rounded-xl border border-slate-100 px-4 py-3">
                <div>
                  <div className="text-sm text-slate-900">{t.topic}</div>
                  {t.score ? <div className="text-xs text-slate-500">оценка: {t.score}</div> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 text-sm text-slate-500">Недостаточно данных.</div>
        )}
      </div>
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
