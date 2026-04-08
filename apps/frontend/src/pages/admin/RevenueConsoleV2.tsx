import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { HelpTriggerButton } from "../../components/ui/HelpTriggerButton";
import { ToastNotice } from "../../components/ui/ToastNotice";

type RevenueTab = "plans" | "cohorts" | "accounts" | "payments";

type Plan = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  price_month: number;
  currency: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
  default_version?: PlanVersion | null;
  versions_count?: number;
};

type PlanVersion = {
  id: number;
  plan_id: number;
  version_code: string;
  name: string;
  price_month: number;
  currency: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
  is_default_for_new_accounts: boolean;
};

type RevenueAccount = {
  id: number;
  account_no: number | null;
  name: string;
  slug: string | null;
  status: string;
  owner_email: string | null;
  plan: Plan | null;
  plan_version: PlanVersion | null;
  subscription_status: string | null;
  cohorts: Array<{ id: number; code: string; name: string; source: string }>;
  final_price_month: number | null;
  currency: string | null;
  adjustments_count: number;
  runtime_source: string;
};

type AdjustmentItem = {
  id: number;
  kind: string;
  target_key: string | null;
  value_json: Record<string, unknown>;
  valid_from: string | null;
  valid_to: string | null;
  reason: string | null;
};

type RevenueAccountDetail = {
  account: { id: number; account_no: number | null; name: string; slug: string | null; status: string };
  subscription: {
    id: number;
    status: string;
    billing_cycle: string;
    trial_until: string | null;
    started_at: string | null;
    ended_at: string | null;
    plan: Plan | null;
    plan_version: PlanVersion | null;
  } | null;
  runtime_policy: {
    limits: Record<string, number>;
    features: Record<string, boolean>;
    explain: Array<Record<string, unknown>>;
  };
  commercial_policy: {
    base_price_month: number | null;
    final_price_month: number | null;
    currency: string | null;
    discounts: Array<Record<string, unknown>>;
    explain: Array<Record<string, unknown>>;
    plan: Plan | null;
    plan_version: PlanVersion | null;
    subscription_status: string | null;
  };
  cohorts: Array<{
    id: number;
    code: string;
    name: string;
    source: string;
    policies: Array<{ id: number; discount_type: string; discount_value: number; plan_version_id: number }>;
  }>;
  adjustments: AdjustmentItem[];
};

type Cohort = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  rule_json: Record<string, unknown>;
  is_active: boolean;
  accounts_count: number;
  policies: Array<{
    id: number;
    cohort_id: number;
    plan_version_id: number;
    discount_type: string;
    discount_value: number;
    feature_adjustments_json: Record<string, boolean>;
    limit_adjustments_json: Record<string, number>;
  }>;
};

type CohortAccountItem = {
  id: number;
  account_no: number | null;
  name: string;
  slug: string | null;
  status: string;
  source: string;
};

type FormState = {
  code: string;
  name: string;
  price_month: string;
  currency: string;
  is_active: boolean;
};

type VersionFormState = {
  version_code: string;
  name: string;
  price_month: string;
  currency: string;
  is_active: boolean;
  is_default_for_new_accounts: boolean;
  limits_json: string;
  features_json: string;
};

type SubscriptionFormState = {
  plan_id: string;
  plan_version_id: string;
  status: string;
  billing_cycle: string;
};

type AdjustmentFormState = {
  kind: string;
  target_key: string;
  value: string;
  reason: string;
};

type CohortFormState = {
  code: string;
  name: string;
  description: string;
  is_active: boolean;
  rule_json: string;
  plan_version_id: string;
  discount_type: string;
  discount_value: string;
  limit_adjustments_json: string;
  feature_adjustments_json: string;
};

const PLAN_EMPTY: FormState = { code: "", name: "", price_month: "", currency: "RUB", is_active: true };
const VERSION_EMPTY: VersionFormState = {
  version_code: "",
  name: "",
  price_month: "",
  currency: "RUB",
  is_active: true,
  is_default_for_new_accounts: false,
  limits_json: "{}",
  features_json: "{}",
};
const SUBSCRIPTION_EMPTY: SubscriptionFormState = {
  plan_id: "",
  plan_version_id: "",
  status: "active",
  billing_cycle: "monthly",
};
const ADJUSTMENT_EMPTY: AdjustmentFormState = {
  kind: "discount_percent",
  target_key: "",
  value: "",
  reason: "",
};
const COHORT_EMPTY: CohortFormState = {
  code: "",
  name: "",
  description: "",
  is_active: true,
  rule_json: "{}",
  plan_version_id: "",
  discount_type: "none",
  discount_value: "",
  limit_adjustments_json: "{}",
  feature_adjustments_json: "{}",
};

function parseJson(value: string, label: string) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    throw new Error(`Некорректный JSON: ${label}`);
  }
}

function formatMoney(value: number | null | undefined, currency = "RUB") {
  if (value == null) return "—";
  return `${value.toLocaleString("ru-RU")} ${currency}`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

function metricCard(label: string, value: string, hint?: string) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-500">{hint}</div> : null}
    </div>
  );
}

function parseJsonSafe(value: string) {
  try {
    return JSON.parse(value || "{}") as Record<string, unknown>;
  } catch {
    return {};
  }
}

function adjustmentKindLabel(kind: string) {
  const labels: Record<string, string> = {
    discount_percent: "Скидка %",
    discount_fixed: "Скидка фикс",
    custom_price: "Спеццена",
    feature_grant: "Выдать фичу",
    feature_revoke: "Отключить фичу",
    limit_bonus: "Увеличить лимит",
  };
  return labels[kind] || kind;
}

export function RevenueConsoleV2() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<RevenueTab>("plans");
  const [helpOpen, setHelpOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone?: "info" | "error" } | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<number | "new">("new");
  const [selectedVersionId, setSelectedVersionId] = useState<number | "new">("new");
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [selectedCohortId, setSelectedCohortId] = useState<number | "new">("new");
  const [planForm, setPlanForm] = useState<FormState>(PLAN_EMPTY);
  const [versionForm, setVersionForm] = useState<VersionFormState>(VERSION_EMPTY);
  const [subscriptionForm, setSubscriptionForm] = useState<SubscriptionFormState>(SUBSCRIPTION_EMPTY);
  const [adjustmentForm, setAdjustmentForm] = useState<AdjustmentFormState>(ADJUSTMENT_EMPTY);
  const [cohortForm, setCohortForm] = useState<CohortFormState>(COHORT_EMPTY);

  const plansQ = useQuery({
    queryKey: ["admin-revenue-v2-plans"],
    queryFn: () => api.get("/v1/admin/revenue/plans") as Promise<{ items: Plan[] }>,
    refetchInterval: 30000,
  });
  const accountsQ = useQuery({
    queryKey: ["admin-revenue-v2-accounts"],
    queryFn: () => api.get("/v1/admin/revenue/accounts?limit=300") as Promise<{ items: RevenueAccount[] }>,
    refetchInterval: 30000,
  });
  const cohortsQ = useQuery({
    queryKey: ["admin-revenue-v2-cohorts"],
    queryFn: () => api.get("/v1/admin/revenue/cohorts") as Promise<{ items: Cohort[] }>,
    refetchInterval: 30000,
  });

  const plans = plansQ.data?.items ?? [];
  const accounts = accountsQ.data?.items ?? [];
  const cohorts = cohortsQ.data?.items ?? [];
  const selectedPlan = selectedPlanId === "new" ? null : plans.find((item) => item.id === selectedPlanId) ?? null;
  const selectedCohort = selectedCohortId === "new" ? null : cohorts.find((item) => item.id === selectedCohortId) ?? null;

  const versionsQ = useQuery({
    queryKey: ["admin-revenue-v2-plan-versions", selectedPlan?.id ?? null],
    queryFn: () => api.get(`/v1/admin/revenue/plans/${selectedPlan?.id}/versions`) as Promise<{ items: PlanVersion[] }>,
    enabled: !!selectedPlan?.id,
  });
  const versions = versionsQ.data?.items ?? [];
  const selectedVersion = selectedVersionId === "new" ? null : versions.find((item) => item.id === selectedVersionId) ?? null;
  const selectedAccount = selectedAccountId == null ? null : accounts.find((item) => item.id === selectedAccountId) ?? null;

  const accountDetailQ = useQuery({
    queryKey: ["admin-revenue-v2-account-detail", selectedAccount?.id ?? null],
    queryFn: () => api.get(`/v1/admin/revenue/accounts/${selectedAccount?.id}`) as Promise<RevenueAccountDetail>,
    enabled: !!selectedAccount?.id,
  });

  const cohortAccountsQ = useQuery({
    queryKey: ["admin-revenue-v2-cohort-accounts", selectedCohort?.id ?? null],
    queryFn: () =>
      api.get(`/v1/admin/revenue/cohorts/${selectedCohort?.id}/accounts?limit=100`) as Promise<{ items: CohortAccountItem[] }>,
    enabled: !!selectedCohort?.id,
  });

  const versionOptionsQ = useQuery({
    queryKey: ["admin-revenue-v2-plan-versions-for-subscription", subscriptionForm.plan_id],
    queryFn: () => api.get(`/v1/admin/revenue/plans/${subscriptionForm.plan_id}/versions`) as Promise<{ items: PlanVersion[] }>,
    enabled: !!subscriptionForm.plan_id,
  });
  const subscriptionVersions = versionOptionsQ.data?.items ?? [];
  const cohortAccounts = cohortAccountsQ.data?.items ?? [];
  const allVersionOptions = useMemo(() => {
    const map = new Map<number, PlanVersion>();
    plans.forEach((plan) => {
      if (plan.default_version) map.set(plan.default_version.id, plan.default_version);
    });
    versions.forEach((version) => map.set(version.id, version));
    subscriptionVersions.forEach((version) => map.set(version.id, version));
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [plans, versions, subscriptionVersions]);

  const metrics = useMemo(() => {
    const activePlans = plans.filter((item) => item.is_active).length;
    const activeAccounts = accounts.filter((item) => item.subscription_status === "active").length;
    const special = accounts.filter((item) => item.adjustments_count > 0).length;
    const mrr = accounts.reduce((sum, item) => sum + Number(item.final_price_month || 0), 0);
    return { activePlans, activeAccounts, special, mrr };
  }, [plans, accounts]);

  useEffect(() => {
    if (selectedPlanId === "new" && plans.length && activeTab === "plans") setSelectedPlanId(plans[0].id);
  }, [selectedPlanId, plans, activeTab]);

  useEffect(() => {
    if (selectedAccountId == null && accounts.length && activeTab === "accounts") setSelectedAccountId(accounts[0].id);
  }, [selectedAccountId, accounts, activeTab]);

  useEffect(() => {
    if (selectedCohortId === "new" && cohorts.length && activeTab === "cohorts") setSelectedCohortId(cohorts[0].id);
  }, [selectedCohortId, cohorts, activeTab]);

  useEffect(() => {
    if (selectedVersionId === "new" && versions.length && selectedPlan && activeTab === "plans") setSelectedVersionId(versions[0].id);
  }, [selectedVersionId, versions, selectedPlan, activeTab]);

  useEffect(() => {
    if (!selectedPlan) {
      setPlanForm(PLAN_EMPTY);
      setVersionForm(VERSION_EMPTY);
      return;
    }
    setPlanForm({
      code: selectedPlan.code,
      name: selectedPlan.name,
      price_month: String(selectedPlan.price_month ?? ""),
      currency: selectedPlan.currency ?? "RUB",
      is_active: selectedPlan.is_active,
    });
  }, [selectedPlan?.id]);

  useEffect(() => {
    if (!selectedVersion) {
      setVersionForm(VERSION_EMPTY);
      return;
    }
    setVersionForm({
      version_code: selectedVersion.version_code,
      name: selectedVersion.name,
      price_month: String(selectedVersion.price_month ?? ""),
      currency: selectedVersion.currency ?? "RUB",
      is_active: selectedVersion.is_active,
      is_default_for_new_accounts: selectedVersion.is_default_for_new_accounts,
      limits_json: JSON.stringify(selectedVersion.limits ?? {}, null, 2),
      features_json: JSON.stringify(selectedVersion.features ?? {}, null, 2),
    });
  }, [selectedVersion?.id]);

  useEffect(() => {
    const sub = accountDetailQ.data?.subscription;
    setSubscriptionForm({
      plan_id: sub?.plan?.id ? String(sub.plan.id) : "",
      plan_version_id: sub?.plan_version?.id ? String(sub.plan_version.id) : "",
      status: sub?.status || "active",
      billing_cycle: sub?.billing_cycle || "monthly",
    });
  }, [accountDetailQ.data?.subscription?.id, selectedAccount?.id]);

  useEffect(() => {
    if (!selectedCohort) {
      setCohortForm(COHORT_EMPTY);
      return;
    }
    const policy = selectedCohort.policies[0];
    setCohortForm({
      code: selectedCohort.code,
      name: selectedCohort.name,
      description: selectedCohort.description || "",
      is_active: selectedCohort.is_active,
      rule_json: JSON.stringify(selectedCohort.rule_json || {}, null, 2),
      plan_version_id: policy?.plan_version_id ? String(policy.plan_version_id) : "",
      discount_type: policy?.discount_type || "none",
      discount_value: policy?.discount_value != null ? String(policy.discount_value) : "",
      limit_adjustments_json: JSON.stringify(policy?.limit_adjustments_json || {}, null, 2),
      feature_adjustments_json: JSON.stringify(policy?.feature_adjustments_json || {}, null, 2),
    });
  }, [selectedCohort?.id]);

  function updateCohortRuleField(key: "account_created_before" | "account_created_after" | "channel" | "manual_tag", value: string) {
    const next = { ...parseJsonSafe(cohortForm.rule_json) };
    if (value.trim()) next[key] = value.trim();
    else delete next[key];
    setCohortForm({ ...cohortForm, rule_json: JSON.stringify(next, null, 2) });
  }

  async function refreshAll() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-plans"] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-accounts"] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-cohorts"] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-cohort-accounts", selectedCohort?.id ?? null] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-plan-versions", selectedPlan?.id ?? null] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-account-detail", selectedAccount?.id ?? null] }),
      qc.invalidateQueries({ queryKey: ["admin-revenue-v2-plan-versions-for-subscription", subscriptionForm.plan_id] }),
    ]);
  }

  const savePlan = useMutation({
    mutationFn: async () => {
      const payload = {
        code: planForm.code.trim(),
        name: planForm.name.trim(),
        price_month: Number(planForm.price_month || 0),
        currency: planForm.currency.trim() || "RUB",
        is_active: planForm.is_active,
        limits: {},
        features: {},
      };
      return selectedPlan ? api.put(`/v1/admin/revenue/plans/${selectedPlan.id}`, payload) : api.post("/v1/admin/revenue/plans", payload);
    },
    onSuccess: async () => {
      setToast({ message: selectedPlan ? "Тариф обновлён." : "Тариф создан." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const saveVersion = useMutation({
    mutationFn: async () => {
      if (!selectedPlan?.id) throw new Error("Сначала выбери тариф.");
      const payload = {
        version_code: versionForm.version_code.trim(),
        name: versionForm.name.trim(),
        price_month: Number(versionForm.price_month || 0),
        currency: versionForm.currency.trim() || "RUB",
        is_active: versionForm.is_active,
        is_default_for_new_accounts: versionForm.is_default_for_new_accounts,
        limits: parseJson(versionForm.limits_json, "лимиты версии"),
        features: parseJson(versionForm.features_json, "фичи версии"),
      };
      return selectedVersion
        ? api.put(`/v1/admin/revenue/plan-versions/${selectedVersion.id}`, payload)
        : api.post(`/v1/admin/revenue/plans/${selectedPlan.id}/versions`, payload);
    },
    onSuccess: async () => {
      setToast({ message: selectedVersion ? "Версия тарифа обновлена." : "Версия тарифа создана." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const setVersionDefault = useMutation({
    mutationFn: async () => {
      if (!selectedVersion?.id) throw new Error("Выбери версию тарифа.");
      return api.post(`/v1/admin/revenue/plan-versions/${selectedVersion.id}/set-default`);
    },
    onSuccess: async () => {
      setToast({ message: "Версия назначена для новых клиентов." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const toggleVersion = useMutation({
    mutationFn: async () => {
      if (!selectedVersion?.id) throw new Error("Выбери версию тарифа.");
      return api.post(`/v1/admin/revenue/plan-versions/${selectedVersion.id}/${selectedVersion.is_active ? "deactivate" : "activate"}`);
    },
    onSuccess: async () => {
      setToast({ message: "Статус версии обновлён." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const saveSubscription = useMutation({
    mutationFn: async () => {
      if (!selectedAccount?.id) throw new Error("Выбери аккаунт.");
      return api.put(`/v1/admin/revenue/accounts/${selectedAccount.id}/subscription`, {
        plan_id: Number(subscriptionForm.plan_id),
        plan_version_id: subscriptionForm.plan_version_id ? Number(subscriptionForm.plan_version_id) : null,
        status: subscriptionForm.status,
        billing_cycle: subscriptionForm.billing_cycle,
      });
    },
    onSuccess: async () => {
      setToast({ message: "Коммерческие условия аккаунта обновлены." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const createAdjustment = useMutation({
    mutationFn: async () => {
      if (!selectedAccount?.id) throw new Error("Выбери аккаунт.");
      const payload: Record<string, unknown> = { kind: adjustmentForm.kind, reason: adjustmentForm.reason || null };
      if (adjustmentForm.target_key.trim()) payload.target_key = adjustmentForm.target_key.trim();
      payload.value = adjustmentForm.kind === "limit_bonus" ? { delta: Number(adjustmentForm.value || 0) } : { value: Number(adjustmentForm.value || 0) };
      return api.post(`/v1/admin/revenue/accounts/${selectedAccount.id}/adjustments`, payload);
    },
    onSuccess: async () => {
      setAdjustmentForm(ADJUSTMENT_EMPTY);
      setToast({ message: "Корректировка добавлена." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const deleteAdjustment = useMutation({
    mutationFn: async (adjustmentId: number) => {
      if (!selectedAccount?.id) throw new Error("Выбери аккаунт.");
      return api.delete(`/v1/admin/revenue/accounts/${selectedAccount.id}/adjustments/${adjustmentId}`);
    },
    onSuccess: async () => {
      setToast({ message: "Корректировка удалена." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const saveCohort = useMutation({
    mutationFn: async () => {
      const payload = {
        code: cohortForm.code.trim(),
        name: cohortForm.name.trim(),
        description: cohortForm.description.trim() || null,
        is_active: cohortForm.is_active,
        rule: parseJson(cohortForm.rule_json, "правило когорты"),
      };
      return selectedCohort
        ? api.put(`/v1/admin/revenue/cohorts/${selectedCohort.id}`, payload)
        : api.post("/v1/admin/revenue/cohorts", payload);
    },
    onSuccess: async () => {
      setToast({ message: selectedCohort ? "Когорта обновлена." : "Когорта создана." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  const saveCohortPolicy = useMutation({
    mutationFn: async () => {
      if (!selectedCohort?.id) throw new Error("Сначала выбери когорту.");
      return api.put(`/v1/admin/revenue/cohorts/${selectedCohort.id}/policy`, {
        plan_version_id: Number(cohortForm.plan_version_id),
        discount_type: cohortForm.discount_type,
        discount_value: Number(cohortForm.discount_value || 0),
        limits: parseJson(cohortForm.limit_adjustments_json, "лимиты когорты"),
        features: parseJson(cohortForm.feature_adjustments_json, "фичи когорты"),
        is_active: cohortForm.is_active,
      });
    },
    onSuccess: async () => {
      setToast({ message: "Политика когорты обновлена." });
      await refreshAll();
    },
    onError: (error: Error) => setToast({ message: error.message, tone: "error" }),
  });

  return (
    <div className="space-y-6">
      <div className="pointer-events-none fixed right-6 top-6 z-50">
        {toast ? <ToastNotice message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">Revenue Console</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Тарифы и коммерческие условия</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">Планы, версии тарифов, когорты и индивидуальные условия по аккаунтам.</p>
          </div>
          <HelpTriggerButton onClick={() => setHelpOpen(true)} />
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {metricCard("Активные тарифы", String(metrics.activePlans), `${plans.length} всего`)}
          {metricCard("Активные аккаунты", String(metrics.activeAccounts), `${accounts.length} в списке`)}
          {metricCard("Исключения", String(metrics.special), "Аккаунты с корректировками")}
          {metricCard("MRR", formatMoney(metrics.mrr), "По рассчитанной цене аккаунтов")}
        </div>
        <div className="mt-5 flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2">
          {[["plans", "Тарифы"], ["cohorts", "Когорты"], ["accounts", "Аккаунты"], ["payments", "Платежи"]].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id as RevenueTab)}
              className={[
                "rounded-xl px-4 py-2 text-sm font-medium transition",
                activeTab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {activeTab === "plans" ? (
        <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Тарифы</h2>
                <p className="mt-1 text-sm text-slate-500">План и набор его версий.</p>
              </div>
              <Button size="sm" onClick={() => { setSelectedPlanId("new"); setSelectedVersionId("new"); setPlanForm(PLAN_EMPTY); setVersionForm(VERSION_EMPTY); }}>Новый тариф</Button>
            </div>
            <div className="mt-4 space-y-2">
              {plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => { setSelectedPlanId(plan.id); setSelectedVersionId("new"); }}
                  className={[
                    "w-full rounded-2xl border p-4 text-left transition",
                    selectedPlan?.id === plan.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-slate-900">{plan.name}</div>
                    <div className={plan.is_active ? "text-xs font-medium text-emerald-700" : "text-xs text-slate-500"}>{plan.is_active ? "Активен" : "Архив"}</div>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">{plan.code}</div>
                  <div className="mt-2 text-sm text-slate-700">{formatMoney(plan.default_version?.price_month ?? plan.price_month, plan.default_version?.currency ?? plan.currency)}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{selectedPlan ? "Параметры тарифа" : "Новый тариф"}</h2>
                  <p className="mt-1 text-sm text-slate-500">Базовая карточка тарифа и статус.</p>
                </div>
                <Button variant="primary" onClick={() => savePlan.mutate()} disabled={savePlan.isPending}>{savePlan.isPending ? "Сохраняю..." : selectedPlan ? "Сохранить тариф" : "Создать тариф"}</Button>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Код</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={planForm.code} disabled={!!selectedPlan} onChange={(e) => setPlanForm({ ...planForm, code: e.target.value })} /></label>
                <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Название</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} /></label>
                <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Цена по умолчанию</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={planForm.price_month} onChange={(e) => setPlanForm({ ...planForm, price_month: e.target.value })} /></label>
                <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Валюта</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={planForm.currency} onChange={(e) => setPlanForm({ ...planForm, currency: e.target.value })} /></label>
              </div>
            </div>

            {selectedPlan ? (
              <div className="grid gap-6 2xl:grid-cols-[320px_minmax(0,1fr)]">
                <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-slate-900">Версии</h3>
                      <p className="mt-1 text-sm text-slate-500">Цены и наборы условий.</p>
                    </div>
                    <Button size="sm" onClick={() => { setSelectedVersionId("new"); setVersionForm(VERSION_EMPTY); }}>Новая версия</Button>
                  </div>
                  <div className="mt-4 space-y-2">
                    {versions.map((version) => (
                      <button
                        key={version.id}
                        type="button"
                        onClick={() => setSelectedVersionId(version.id)}
                        className={[
                          "w-full rounded-2xl border p-4 text-left transition",
                          selectedVersion?.id === version.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50",
                        ].join(" ")}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="font-medium text-slate-900">{version.name}</div>
                          {version.is_default_for_new_accounts ? <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-700">Для новых</span> : null}
                        </div>
                        <div className="mt-1 text-sm text-slate-500">{version.version_code}</div>
                        <div className="mt-2 text-sm text-slate-700">{formatMoney(version.price_month, version.currency)}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-slate-900">{selectedVersion ? "Редактирование версии" : "Новая версия"}</h3>
                      <p className="mt-1 text-sm text-slate-500">Лимиты и функции версии тарифа.</p>
                    </div>
                    <div className="flex gap-2">
                      {selectedVersion ? (
                        <>
                          <Button size="sm" variant="secondary" onClick={() => setVersionDefault.mutate()}>Сделать базовой</Button>
                          <Button size="sm" variant="secondary" onClick={() => toggleVersion.mutate()}>{selectedVersion.is_active ? "Архивировать" : "Активировать"}</Button>
                        </>
                      ) : null}
                      <Button variant="primary" size="sm" onClick={() => saveVersion.mutate()} disabled={saveVersion.isPending}>{saveVersion.isPending ? "Сохраняю..." : selectedVersion ? "Сохранить версию" : "Создать версию"}</Button>
                    </div>
                  </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Код версии</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={versionForm.version_code} disabled={!!selectedVersion} onChange={(e) => setVersionForm({ ...versionForm, version_code: e.target.value })} /></label>
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Название версии</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={versionForm.name} onChange={(e) => setVersionForm({ ...versionForm, name: e.target.value })} /></label>
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Цена в месяц</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={versionForm.price_month} onChange={(e) => setVersionForm({ ...versionForm, price_month: e.target.value })} /></label>
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Валюта</div><input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={versionForm.currency} onChange={(e) => setVersionForm({ ...versionForm, currency: e.target.value })} /></label>
                  </div>
                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Лимиты</div><textarea className="h-72 w-full rounded-2xl border border-slate-200 px-3 py-3 font-mono text-xs" value={versionForm.limits_json} onChange={(e) => setVersionForm({ ...versionForm, limits_json: e.target.value })} /></label>
                    <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Функции</div><textarea className="h-72 w-full rounded-2xl border border-slate-200 px-3 py-3 font-mono text-xs" value={versionForm.features_json} onChange={(e) => setVersionForm({ ...versionForm, features_json: e.target.value })} /></label>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {activeTab === "accounts" ? (
        <section className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <div><h2 className="text-lg font-semibold text-slate-900">Аккаунты</h2><p className="mt-1 text-sm text-slate-500">Тариф, версия и индивидуальные условия.</p></div>
            <div className="mt-4 space-y-2">
              {accounts.map((account) => (
                <button
                  key={account.id}
                  type="button"
                  onClick={() => setSelectedAccountId(account.id)}
                  className={[
                    "w-full rounded-2xl border p-4 text-left transition",
                    selectedAccount?.id === account.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-2"><div className="font-medium text-slate-900">{account.name}</div><div className="text-xs text-slate-500">{account.subscription_status || "без подписки"}</div></div>
                  <div className="mt-1 text-sm text-slate-500">№{account.account_no ?? account.id} · {account.owner_email || "email не задан"}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                    <span className="rounded-full bg-slate-100 px-2 py-1">{account.plan_version?.name || account.plan?.name || "—"}</span>
                    {account.adjustments_count ? <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">Корректировок: {account.adjustments_count}</span> : null}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            {selectedAccount && accountDetailQ.data ? (
              <>
                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold text-slate-900">{selectedAccount.name}</h2>
                      <p className="mt-1 text-sm text-slate-500">№{selectedAccount.account_no ?? selectedAccount.id} · {selectedAccount.owner_email || "email не задан"}</p>
                    </div>
                    <div className="text-right"><div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">Итоговая цена</div><div className="mt-2 text-2xl font-semibold text-slate-950">{formatMoney(accountDetailQ.data.commercial_policy.final_price_month, accountDetailQ.data.commercial_policy.currency || "RUB")}</div></div>
                  </div>
                  <div className="mt-5 grid gap-4 md:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 p-4"><div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">План</div><div className="mt-2 text-base font-semibold text-slate-900">{accountDetailQ.data.commercial_policy.plan?.name || "Не назначен"}</div><div className="mt-1 text-sm text-slate-500">{accountDetailQ.data.commercial_policy.plan_version?.name || "Без версии"}</div></div>
                    <div className="rounded-2xl border border-slate-200 p-4"><div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">Когорта</div><div className="mt-2 text-base font-semibold text-slate-900">{accountDetailQ.data.cohorts[0]?.name || "Нет"}</div><div className="mt-1 text-sm text-slate-500">{accountDetailQ.data.cohorts[0]?.source === "manual" ? "Ручное назначение" : "Автоматическое правило"}</div></div>
                    <div className="rounded-2xl border border-slate-200 p-4"><div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">Подписка</div><div className="mt-2 text-base font-semibold text-slate-900">{accountDetailQ.data.subscription?.status || "Нет"}</div><div className="mt-1 text-sm text-slate-500">{accountDetailQ.data.subscription?.billing_cycle === "annual" ? "Годовая" : "Месячная"}</div></div>
                  </div>
                </div>

                <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_360px]">
                  <div className="space-y-6">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex items-center justify-between gap-4">
                        <div><h3 className="text-base font-semibold text-slate-900">Коммерческие условия</h3><p className="mt-1 text-sm text-slate-500">План, версия и период оплаты.</p></div>
                        <Button variant="primary" size="sm" onClick={() => saveSubscription.mutate()}>Сохранить</Button>
                      </div>
                      <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <label className="space-y-2"><div className="text-sm font-medium text-slate-700">План</div><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={subscriptionForm.plan_id} onChange={(e) => { const nextPlanId = e.target.value; const nextPlan = plans.find((item) => String(item.id) === nextPlanId); setSubscriptionForm({ ...subscriptionForm, plan_id: nextPlanId, plan_version_id: nextPlan?.default_version?.id ? String(nextPlan.default_version.id) : "" }); }}><option value="">Выбери тариф</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}</select></label>
                        <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Версия</div><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={subscriptionForm.plan_version_id} onChange={(e) => setSubscriptionForm({ ...subscriptionForm, plan_version_id: e.target.value })}><option value="">Выбери версию</option>{subscriptionVersions.map((version) => <option key={version.id} value={version.id}>{version.name}</option>)}</select></label>
                        <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Статус</div><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={subscriptionForm.status} onChange={(e) => setSubscriptionForm({ ...subscriptionForm, status: e.target.value })}><option value="trial">trial</option><option value="active">active</option><option value="paused">paused</option><option value="canceled">canceled</option></select></label>
                        <label className="space-y-2"><div className="text-sm font-medium text-slate-700">Период оплаты</div><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={subscriptionForm.billing_cycle} onChange={(e) => setSubscriptionForm({ ...subscriptionForm, billing_cycle: e.target.value })}><option value="monthly">Ежемесячно</option><option value="annual">Годовой</option></select></label>
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <h3 className="text-base font-semibold text-slate-900">Фичи и лимиты</h3>
                      <div className="mt-4 grid gap-4 xl:grid-cols-2">
                        <div className="rounded-2xl border border-slate-200 p-4"><div className="text-sm font-medium text-slate-700">Лимиты</div><div className="mt-3 space-y-2 text-sm text-slate-600">{Object.entries(accountDetailQ.data.runtime_policy.limits || {}).map(([key, value]) => <div key={key} className="flex items-center justify-between gap-3"><span>{key}</span><span className="font-medium text-slate-900">{String(value)}</span></div>)}</div></div>
                        <div className="rounded-2xl border border-slate-200 p-4"><div className="text-sm font-medium text-slate-700">Функции</div><div className="mt-3 space-y-2 text-sm text-slate-600">{Object.entries(accountDetailQ.data.runtime_policy.features || {}).map(([key, value]) => <div key={key} className="flex items-center justify-between gap-3"><span>{key}</span><span className={value ? "font-medium text-emerald-700" : "font-medium text-slate-400"}>{value ? "Вкл." : "Выкл."}</span></div>)}</div></div>
                      </div>
                      <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Источники правил: {accountDetailQ.data.runtime_policy.explain.map((entry, index) => <span key={index} className="mr-2 inline-flex rounded-full bg-white px-2 py-1 text-xs text-slate-700">{String(entry.layer || "слой")}</span>)}</div>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <h3 className="text-base font-semibold text-slate-900">Почему такая цена</h3>
                      <div className="mt-4 space-y-3 text-sm text-slate-600">
                        <div className="flex items-center justify-between gap-3"><span>Базовая цена</span><span className="font-medium text-slate-900">{formatMoney(accountDetailQ.data.commercial_policy.base_price_month, accountDetailQ.data.commercial_policy.currency || "RUB")}</span></div>
                        {accountDetailQ.data.commercial_policy.discounts.map((item, index) => <div key={index} className="flex items-center justify-between gap-3"><span>{String(item.label || item.kind || "Корректировка")}</span><span className="font-medium text-slate-900">{item.value ? String(item.value) : String(item.final_price_month || "—")}</span></div>)}
                        <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-3"><span>Итог</span><span className="text-base font-semibold text-slate-950">{formatMoney(accountDetailQ.data.commercial_policy.final_price_month, accountDetailQ.data.commercial_policy.currency || "RUB")}</span></div>
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex items-center justify-between gap-4"><div><h3 className="text-base font-semibold text-slate-900">Корректировки</h3><p className="mt-1 text-sm text-slate-500">Скидки, спеццены, фичи и лимиты.</p></div><Button size="sm" variant="primary" onClick={() => createAdjustment.mutate()}>Добавить</Button></div>
                      <div className="mt-4 grid gap-3">
                        <select className="w-full rounded-xl border border-slate-200 px-3 py-2.5" value={adjustmentForm.kind} onChange={(e) => setAdjustmentForm({ ...adjustmentForm, kind: e.target.value })}><option value="discount_percent">Скидка %</option><option value="discount_fixed">Скидка фикс</option><option value="custom_price">Спеццена</option><option value="feature_grant">Выдать фичу</option><option value="feature_revoke">Отключить фичу</option><option value="limit_bonus">Увеличить лимит</option></select>
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" placeholder="Ключ фичи или лимита" value={adjustmentForm.target_key} onChange={(e) => setAdjustmentForm({ ...adjustmentForm, target_key: e.target.value })} />
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" placeholder="Значение" value={adjustmentForm.value} onChange={(e) => setAdjustmentForm({ ...adjustmentForm, value: e.target.value })} />
                        <input className="w-full rounded-xl border border-slate-200 px-3 py-2.5" placeholder="Причина" value={adjustmentForm.reason} onChange={(e) => setAdjustmentForm({ ...adjustmentForm, reason: e.target.value })} />
                      </div>
                      <div className="mt-4 space-y-2">{accountDetailQ.data.adjustments.map((item) => <div key={item.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><div className="font-medium text-slate-900">{adjustmentKindLabel(item.kind)}</div><div className="flex items-center gap-3"><div className="text-xs text-slate-500">{formatDateTime(item.valid_to)}</div><button type="button" className="text-xs font-medium text-rose-600 hover:text-rose-700" onClick={() => deleteAdjustment.mutate(item.id)}>Удалить</button></div></div><div className="mt-1 text-sm text-slate-600">{item.target_key || "—"} · {JSON.stringify(item.value_json || {})}</div>{item.reason ? <div className="mt-1 text-sm text-slate-500">{item.reason}</div> : null}</div>)}</div>
                    </div>
                  </div>
                </div>
              </>
            ) : <div className="rounded-3xl border border-slate-200 bg-white p-8 text-sm text-slate-500 shadow-sm">Выбери аккаунт слева.</div>}
          </div>
        </section>
      ) : null}

      {activeTab === "cohorts" ? (
        <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Когорты</h2>
                <p className="mt-1 text-sm text-slate-500">Grandfathering и групповые условия.</p>
              </div>
              <Button
                size="sm"
                onClick={() => {
                  setSelectedCohortId("new");
                  setCohortForm(COHORT_EMPTY);
                }}
              >
                Новая когорта
              </Button>
            </div>
            <div className="mt-4 space-y-2">
              {cohorts.map((cohort) => (
                <button
                  key={cohort.id}
                  type="button"
                  onClick={() => setSelectedCohortId(cohort.id)}
                  className={[
                    "w-full rounded-2xl border p-4 text-left transition",
                    selectedCohort?.id === cohort.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-slate-900">{cohort.name}</div>
                    <div className={cohort.is_active ? "text-xs text-emerald-700" : "text-xs text-slate-500"}>
                      {cohort.is_active ? "Активна" : "Архив"}
                    </div>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">{cohort.code}</div>
                  <div className="mt-2 text-sm text-slate-600">
                    Аккаунтов: {cohort.accounts_count} · Политик: {cohort.policies.length}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-slate-900">{selectedCohort ? "Параметры когорты" : "Новая когорта"}</h3>
                  <p className="mt-1 text-sm text-slate-500">Правило отбора и базовая информация.</p>
                </div>
                <Button variant="primary" size="sm" onClick={() => saveCohort.mutate()}>
                  {selectedCohort ? "Сохранить когорту" : "Создать когорту"}
                </Button>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Код</div>
                  <input
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={cohortForm.code}
                    disabled={!!selectedCohort}
                    onChange={(e) => setCohortForm({ ...cohortForm, code: e.target.value })}
                  />
                </label>
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Название</div>
                  <input
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={cohortForm.name}
                    onChange={(e) => setCohortForm({ ...cohortForm, name: e.target.value })}
                  />
                </label>
              </div>
              <label className="mt-4 block space-y-2">
                <div className="text-sm font-medium text-slate-700">Описание</div>
                <input
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                  value={cohortForm.description}
                  onChange={(e) => setCohortForm({ ...cohortForm, description: e.target.value })}
                />
              </label>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Созданы до даты</div>
                  <input
                    type="date"
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={String(parseJsonSafe(cohortForm.rule_json).account_created_before || "").slice(0, 10)}
                    onChange={(e) => updateCohortRuleField("account_created_before", e.target.value)}
                  />
                </label>
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Созданы после даты</div>
                  <input
                    type="date"
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={String(parseJsonSafe(cohortForm.rule_json).account_created_after || "").slice(0, 10)}
                    onChange={(e) => updateCohortRuleField("account_created_after", e.target.value)}
                  />
                </label>
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Канал</div>
                  <select
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={String(parseJsonSafe(cohortForm.rule_json).channel || "")}
                    onChange={(e) => updateCohortRuleField("channel", e.target.value)}
                  >
                    <option value="">Любой</option>
                    <option value="bitrix">Bitrix</option>
                    <option value="telegram">Telegram</option>
                    <option value="amo">AmoCRM</option>
                  </select>
                </label>
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Ручной тег</div>
                  <input
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                    value={String(parseJsonSafe(cohortForm.rule_json).manual_tag || "")}
                    onChange={(e) => updateCohortRuleField("manual_tag", e.target.value)}
                  />
                </label>
              </div>
              <label className="mt-4 block space-y-2">
                <div className="text-sm font-medium text-slate-700">Правило JSON</div>
                <textarea
                  className="h-40 w-full rounded-2xl border border-slate-200 px-3 py-3 font-mono text-xs"
                  value={cohortForm.rule_json}
                  onChange={(e) => setCohortForm({ ...cohortForm, rule_json: e.target.value })}
                />
              </label>
            </div>

            {selectedCohort ? (
              <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h3 className="text-base font-semibold text-slate-900">Коммерческая политика</h3>
                      <p className="mt-1 text-sm text-slate-500">Какая версия тарифа и какая скидка применяются.</p>
                    </div>
                    <Button variant="primary" size="sm" onClick={() => saveCohortPolicy.mutate()}>
                      Сохранить политику
                    </Button>
                  </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <div className="text-sm font-medium text-slate-700">Версия тарифа</div>
                      <select
                        className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                        value={cohortForm.plan_version_id}
                        onChange={(e) => setCohortForm({ ...cohortForm, plan_version_id: e.target.value })}
                      >
                        <option value="">Выбери версию</option>
                        {allVersionOptions.map((version) => {
                          const ownerPlan = plans.find((plan) => plan.id === version.plan_id);
                          return (
                            <option key={version.id} value={version.id}>
                              {(ownerPlan?.name || "Тариф")} · {version.name}
                            </option>
                          );
                        })}
                      </select>
                    </label>
                    <label className="space-y-2">
                      <div className="text-sm font-medium text-slate-700">Тип скидки</div>
                      <select
                        className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                        value={cohortForm.discount_type}
                        onChange={(e) => setCohortForm({ ...cohortForm, discount_type: e.target.value })}
                      >
                        <option value="none">Без скидки</option>
                        <option value="percent">Скидка %</option>
                        <option value="fixed">Скидка фикс</option>
                      </select>
                    </label>
                    <label className="space-y-2">
                      <div className="text-sm font-medium text-slate-700">Размер скидки</div>
                      <input
                        className="w-full rounded-xl border border-slate-200 px-3 py-2.5"
                        value={cohortForm.discount_value}
                        onChange={(e) => setCohortForm({ ...cohortForm, discount_value: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <label className="space-y-2">
                      <div className="text-sm font-medium text-slate-700">Корректировки лимитов</div>
                      <textarea
                        className="h-56 w-full rounded-2xl border border-slate-200 px-3 py-3 font-mono text-xs"
                        value={cohortForm.limit_adjustments_json}
                        onChange={(e) => setCohortForm({ ...cohortForm, limit_adjustments_json: e.target.value })}
                      />
                    </label>
                    <label className="space-y-2">
                      <div className="text-sm font-medium text-slate-700">Корректировки функций</div>
                      <textarea
                        className="h-56 w-full rounded-2xl border border-slate-200 px-3 py-3 font-mono text-xs"
                        value={cohortForm.feature_adjustments_json}
                        onChange={(e) => setCohortForm({ ...cohortForm, feature_adjustments_json: e.target.value })}
                      />
                    </label>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-base font-semibold text-slate-900">Аккаунты в когорте</h3>
                  <p className="mt-1 text-sm text-slate-500">Предпросмотр matching и ручных назначений.</p>
                  <div className="mt-4 space-y-2">
                    {cohortAccounts.map((account) => (
                      <div key={account.id} className="rounded-2xl border border-slate-200 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-slate-900">{account.name}</div>
                          <div className="text-xs text-slate-500">{account.source === "manual" ? "Ручное" : "Авто"}</div>
                        </div>
                        <div className="mt-1 text-sm text-slate-500">№{account.account_no ?? account.id}</div>
                      </div>
                    ))}
                    {!cohortAccounts.length ? <div className="text-sm text-slate-500">Подходящих аккаунтов пока нет.</div> : null}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {activeTab === "payments" ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Платежи</h2>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">Этот раздел подключим после интеграции YooKassa. Здесь будут попытки оплаты, статусы и разбор ошибок.</p>
        </section>
      ) : null}

      {helpOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/25 px-4">
          <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div><h2 className="text-xl font-semibold text-slate-950">Как это работает</h2><p className="mt-1 text-sm text-slate-500">Revenue v2 разделяет план, версию условий, когорту и точечные исключения.</p></div>
              <Button size="sm" variant="ghost" onClick={() => setHelpOpen(false)}>Закрыть</Button>
            </div>
            <div className="mt-5 space-y-4 text-sm text-slate-600">
              <div><div className="font-medium text-slate-900">Тариф</div><div className="mt-1">Базовая сущность каталога. Саму цену и набор лимитов задаёт версия тарифа.</div></div>
              <div><div className="font-medium text-slate-900">Версия тарифа</div><div className="mt-1">Позволяет держать старые и новые цены одновременно и не ломать grandfathering.</div></div>
              <div><div className="font-medium text-slate-900">Когорта</div><div className="mt-1">Сегмент аккаунтов, которому можно назначить отдельную версию тарифа и скидку.</div></div>
              <div><div className="font-medium text-slate-900">Корректировки аккаунта</div><div className="mt-1">Точечные скидки, спеццены, фичи и лимиты для конкретного аккаунта.</div></div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}


