import { useEffect, useMemo, useState } from "react";
import { HelpTriggerButton } from "../../components/ui/HelpTriggerButton";
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
  allow_speaker_diarization: "Разделение спикеров",
  allow_client_bot: "Клиентский бот",
  allow_bitrix_integration: "Интеграция с Bitrix24",
  allow_amocrm_integration: "Интеграция с AmoCRM",
  allow_webhooks: "Вебхуки",
};

const LIMIT_LABELS: Record<string, string> = {
  requests_per_month: "Запросы в месяц",
  media_minutes_per_month: "Минуты медиа",
  max_users: "Пользователи",
  max_storage_gb: "Хранилище, ГБ",
  max_bitrix_portals: "Bitrix24-порталы",
};

function formatMoney(value: number | null | undefined, currency = "RUB") {
  if (value == null) return "—";
  return `${Number(value).toLocaleString("ru-RU")} ${currency}`;
}

function percentOf(used: number, limit: number) {
  if (!limit || limit <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((used / limit) * 100)));
}

function usageItem(label: string, used: number, limit: number, suffix = "") {
  const pct = percentOf(used, limit);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">
        {used.toLocaleString("ru-RU")}
        {suffix}
      </div>
      <div className="mt-1 text-sm text-slate-500">
        из {limit.toLocaleString("ru-RU")}
        {suffix}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-sky-500" style={{ width: `${pct}%` }} />
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
  const [helpOpen, setHelpOpen] = useState(false);

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
  const currentPlan = overview?.subscription?.plan || null;

  const visiblePlans = useMemo(() => plans.filter((plan) => plan.is_active), [plans]);

  return (
    <div className="space-y-6 pb-8">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">Тарифы и оплата</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Текущий тариф и лимиты</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Текущий план, использование и доступные улучшения для вашего аккаунта.
            </p>
          </div>
          <HelpTriggerButton onClick={() => setHelpOpen(true)} />
        </div>
      </section>

      {loading ? <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">Загрузка тарифов...</div> : null}
      {error ? <div className="rounded-3xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div> : null}

      {overview && !loading ? (
        <>
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div>
                <div className="text-sm text-slate-500">Текущий тариф</div>
                <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{currentPlan?.name || "Индивидуальные условия"}</div>
                <div className="mt-2 text-sm text-slate-500">
                  {overview.account.name || `Аккаунт ${overview.account.id}`}
                  {overview.account.account_no ? ` · №${overview.account.account_no}` : ""}
                </div>
              </div>
              <div className="min-w-[260px] rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">Стоимость</div>
                <div className="mt-2 text-2xl font-semibold text-slate-950">{currentPlan ? formatMoney(currentPlan.price_month, currentPlan.currency) : "Индивидуально"}</div>
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  <div>Статус: <span className="font-medium text-slate-900">{overview.subscription?.status || "default"}</span></div>
                  <div>Роль: <span className="font-medium text-slate-900">{overview.membership.role}</span></div>
                </div>
              </div>
            </div>
            {overview.effective_policy.source !== "plan" ? (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Для аккаунта действуют индивидуальные условия. Итоговые лимиты и функции могут отличаться от базового тарифа.
              </div>
            ) : null}
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {usageItem("Запросы", overview.usage.requests_used, overview.usage.requests_limit)}
            {usageItem("Минуты медиа", overview.usage.media_minutes_used, overview.usage.media_minutes_limit)}
            {usageItem("Пользователи", overview.usage.users_used, overview.usage.users_limit)}
            {usageItem("Хранилище", overview.usage.storage_used_gb, overview.usage.storage_limit_gb, " ГБ")}
            {usageItem("Bitrix24-порталы", overview.usage.bitrix_portals_used || 0, overview.usage.bitrix_portals_limit || 0)}
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">Что входит</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {Object.entries(FEATURE_LABELS).map(([key, label]) => {
                  const enabled = !!overview.effective_policy.features?.[key];
                  return (
                    <div
                      key={key}
                      className={[
                        "rounded-2xl border px-4 py-3 text-sm",
                        enabled ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-500",
                      ].join(" ")}
                    >
                      <div className="font-medium">{label}</div>
                      <div className="mt-1 text-xs">{enabled ? "Доступно" : "Недоступно на текущих условиях"}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">Лимиты</h2>
              <div className="mt-4 space-y-3">
                {Object.entries(LIMIT_LABELS).map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3 text-sm">
                    <span className="text-slate-600">{label}</span>
                    <span className="font-semibold text-slate-900">{Number(overview.effective_policy.limits?.[key] || 0).toLocaleString("ru-RU")}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                За период: {overview.usage.tokens_total.toLocaleString("ru-RU")} токенов · {Number(overview.usage.cost_rub || 0).toLocaleString("ru-RU")} ₽ расходов.
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Доступные тарифы</h2>
                <p className="mt-1 text-sm text-slate-500">Сравнение текущего плана и возможных улучшений.</p>
              </div>
              <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-700">
                Смена тарифа пока проводится через администратора или поддержку.
              </div>
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              {visiblePlans.map((plan) => {
                const active = plan.code === currentPlanCode;
                return (
                  <div key={plan.id} className={["rounded-3xl border p-5", active ? "border-sky-300 bg-sky-50" : "border-slate-200 bg-white"].join(" ")}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-semibold text-slate-900">{plan.name}</div>
                        <div className="mt-1 text-sm text-slate-500">{formatMoney(plan.price_month, plan.currency)} / месяц</div>
                      </div>
                      {active ? <span className="rounded-full bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white">Текущий</span> : null}
                    </div>
                    <div className="mt-4 space-y-2 text-sm text-slate-600">
                      {Object.entries(LIMIT_LABELS).map(([key, label]) => (
                        <div key={key} className="flex items-center justify-between gap-3">
                          <span>{label}</span>
                          <span className="font-medium text-slate-900">{Number(plan.limits?.[key] || 0).toLocaleString("ru-RU")}</span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 border-t border-slate-200 pt-4">
                      <div className="space-y-2 text-sm">
                        {Object.entries(FEATURE_LABELS).slice(0, 4).map(([key, label]) => (
                          <div key={key} className="flex items-center justify-between gap-3">
                            <span className={plan.features?.[key] ? "text-slate-700" : "text-slate-400"}>{label}</span>
                            <span className={plan.features?.[key] ? "text-slate-900" : "text-slate-400"}>{plan.features?.[key] ? "Да" : "Нет"}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      ) : null}

      {helpOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/25 px-4">
          <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Как это работает</h2>
                <p className="mt-1 text-sm text-slate-500">Тариф определяет базовые лимиты и функции, а индивидуальные условия могут их менять.</p>
              </div>
              <button type="button" className="rounded-xl px-3 py-2 text-sm text-slate-600 hover:bg-slate-100" onClick={() => setHelpOpen(false)}>
                Закрыть
              </button>
            </div>
            <div className="mt-5 space-y-4 text-sm text-slate-600">
              <div>
                <div className="font-medium text-slate-900">Текущий тариф</div>
                <div className="mt-1">Показывает базовую цену и набор возможностей, закреплённых за вашим аккаунтом.</div>
              </div>
              <div>
                <div className="font-medium text-slate-900">Лимиты</div>
                <div className="mt-1">Использование считается в рамках текущего расчётного периода.</div>
              </div>
              <div>
                <div className="font-medium text-slate-900">Индивидуальные условия</div>
                <div className="mt-1">Если для аккаунта действуют исключения, итоговые лимиты и функции могут отличаться от базового тарифа.</div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
