import { useEffect, useState } from "react";
import { PageIntro } from "../../components/PageIntro";
import { fetchWeb, getActiveAccountId } from "./auth";

type BillingPlan = {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  price_month: number;
  currency: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
};

type BillingOverview = {
  account: {
    id: number;
    name?: string | null;
    account_no?: number | null;
    slug?: string | null;
  };
  membership: {
    role: string;
    can_view_finance: boolean;
  };
  subscription: {
    status: string;
    plan?: BillingPlan | null;
  } | null;
  effective_policy: {
    plan_code: string;
    source: string;
    limits: Record<string, number>;
    features: Record<string, boolean>;
  };
  usage: {
    period_start: string;
    period_end: string;
    requests_used: number;
    requests_limit: number;
    media_minutes_used: number;
    media_minutes_limit: number;
    users_used: number;
    users_limit: number;
    storage_used_gb: number;
    storage_limit_gb: number;
    tokens_total: number;
    cost_rub: number;
    bitrix_portals_used?: number;
    bitrix_portals_limit?: number;
  };
};

const FEATURE_LABELS: Record<string, string> = {
  allow_model_selection: "Выбор моделей",
  allow_advanced_model_tuning: "Тонкая настройка модели",
  allow_media_transcription: "Транскрибация медиа",
  allow_speaker_diarization: "Диаризация / спикеры",
  allow_client_bot: "Клиентский бот",
  allow_bitrix_integration: "Интеграция с Bitrix24",
  allow_amocrm_integration: "Интеграция с AmoCRM",
  allow_webhooks: "Вебхуки",
};

const LIMIT_LABELS: Record<string, string> = {
  requests_per_month: "Запросов в месяц",
  media_minutes_per_month: "Минут медиа в месяц",
  max_users: "Пользователей",
  max_storage_gb: "Хранилище, ГБ",
  max_bitrix_portals: "Bitrix24-порталов",
};

function formatMoneyRub(value: number | null | undefined) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString("ru-RU")} ₽/мес`;
}

function percentOf(used: number, limit: number) {
  if (!limit || limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function UsageCard({
  title,
  used,
  limit,
  suffix = "",
}: {
  title: string;
  used: number | string;
  limit: number | string;
  suffix?: string;
}) {
  const usedNum = Number(used || 0);
  const limitNum = Number(limit || 0);
  const pct = percentOf(usedNum, limitNum);

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="text-sm text-slate-500">{title}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">
        {usedNum.toLocaleString("ru-RU")}
        {suffix}
      </div>
      <div className="mt-1 text-sm text-slate-500">
        из {limitNum.toLocaleString("ru-RU")}
        {suffix}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-sky-600" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-2 text-xs text-slate-500">{pct}% лимита</div>
    </div>
  );
}

export function WebBillingPage() {
  const accountId = getActiveAccountId();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [plansRes, overviewRes] = await Promise.all([
          fetchWeb("/api/v2/web/billing/plans"),
          fetchWeb(`/api/v2/web/accounts/${accountId}/billing`),
        ]);
        const plansData = await plansRes.json().catch(() => null);
        const overviewData = await overviewRes.json().catch(() => null);
        if (cancelled) return;

        if (!plansRes.ok || !overviewRes.ok) {
          setError((overviewData && (overviewData.error || overviewData.detail)) || "Не удалось загрузить тарифы.");
          return;
        }

        setPlans(Array.isArray(plansData?.items) ? plansData.items : []);
        setOverview(overviewData as BillingOverview);
      } catch {
        if (!cancelled) setError("Не удалось загрузить тарифы.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [accountId]);

  const currentPlanCode = overview?.subscription?.plan?.code || overview?.effective_policy?.plan_code || "";

  return (
    <div className="space-y-6">
      <PageIntro
        moduleId="billing"
        fallbackTitle="Тарифы и оплата"
        fallbackDescription="Текущий тариф, лимиты и доступные функции вашего аккаунта."
      />

      {loading && <div className="rounded-2xl border border-slate-100 bg-white p-6 text-sm text-slate-500 shadow-sm">Загрузка...</div>}
      {error && <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

      {overview && !loading && (
        <>
          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-sm text-slate-500">Текущий тариф</div>
                <div className="mt-1 text-2xl font-semibold text-slate-900">
                  {overview.subscription?.plan?.name || "Default"}
                </div>
                <div className="mt-1 text-sm text-slate-500">
                  {overview.account.name || `Аккаунт ${overview.account.id}`}
                  {overview.account.account_no ? ` · №${overview.account.account_no}` : ""}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <div>
                  Статус: <span className="font-semibold">{overview.subscription?.status || "default"}</span>
                </div>
                <div>
                  Источник policy: <span className="font-semibold">{overview.effective_policy.source}</span>
                </div>
                <div className="mt-1 text-slate-500">
                  {overview.subscription?.plan ? formatMoneyRub(overview.subscription.plan.price_month) : "Индивидуальные условия"}
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <UsageCard title="Запросы" used={overview.usage.requests_used} limit={overview.usage.requests_limit} />
            <UsageCard title="Минуты медиа" used={overview.usage.media_minutes_used} limit={overview.usage.media_minutes_limit} />
            <UsageCard title="Пользователи" used={overview.usage.users_used} limit={overview.usage.users_limit} />
            <UsageCard title="Хранилище" used={overview.usage.storage_used_gb} limit={overview.usage.storage_limit_gb} suffix=" ГБ" />
            <UsageCard title="Bitrix24-порталы" used={overview.usage.bitrix_portals_used || 0} limit={overview.usage.bitrix_portals_limit || 0} />
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Что входит в ваш тариф</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {Object.entries(FEATURE_LABELS).map(([key, label]) => {
                  const enabled = !!overview.effective_policy.features?.[key];
                  return (
                    <div
                      key={key}
                      className={`rounded-xl border px-4 py-3 text-sm ${
                        enabled ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-500"
                      }`}
                    >
                      <div className="font-medium">{label}</div>
                      <div className="mt-1 text-xs">{enabled ? "Доступно" : "Недоступно на текущем тарифе"}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Лимиты</h2>
              <div className="mt-4 space-y-3">
                {Object.entries(LIMIT_LABELS).map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm">
                    <span className="text-slate-600">{label}</span>
                    <span className="font-semibold text-slate-900">
                      {Number(overview.effective_policy.limits?.[key] || 0).toLocaleString("ru-RU")}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                За текущий период: {overview.usage.tokens_total.toLocaleString("ru-RU")} токенов,{" "}
                {Number(overview.usage.cost_rub || 0).toLocaleString("ru-RU")} ₽ расходов.
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Доступные тарифы</h2>
                <p className="mt-1 text-sm text-slate-500">Сравнение планов и функций. Смена тарифа пока через администратора.</p>
              </div>
              <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-700">
                Чтобы повысить тариф, перейдите к администратору аккаунта или в поддержку.
              </div>
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              {plans.map((plan) => {
                const active = plan.code === currentPlanCode;
                return (
                  <div key={plan.id} className={`rounded-2xl border p-5 ${active ? "border-sky-300 bg-sky-50" : "border-slate-200 bg-white"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-semibold text-slate-900">{plan.name}</div>
                        <div className="mt-1 text-sm text-slate-500">{formatMoneyRub(plan.price_month)}</div>
                      </div>
                      {active && <span className="rounded-full bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white">Текущий</span>}
                    </div>
                    <div className="mt-4 space-y-2 text-sm text-slate-600">
                      {Object.entries(LIMIT_LABELS).map(([key, label]) => (
                        <div key={key} className="flex items-center justify-between">
                          <span>{label}</span>
                          <span className="font-medium text-slate-900">{Number(plan.limits?.[key] || 0).toLocaleString("ru-RU")}</span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 space-y-2 border-t border-slate-200 pt-4 text-sm">
                      {Object.entries(FEATURE_LABELS).map(([key, label]) => (
                        <div key={key} className={`flex items-center justify-between ${plan.features?.[key] ? "text-slate-700" : "text-slate-400"}`}>
                          <span>{label}</span>
                          <span>{plan.features?.[key] ? "Да" : "Нет"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
