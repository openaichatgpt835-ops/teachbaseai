import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

type Plan = {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  price_month: number;
  currency: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
};

type AccountItem = {
  id: number;
  account_no: number | null;
  name: string;
  status: string;
  owner_email: string | null;
  subscription: { status: string; plan: Plan | null } | null;
};

type EffectivePolicy = {
  source: string;
  plan_code: string;
  subscription_status: string | null;
  limits: Record<string, number>;
  features: Record<string, boolean>;
  override: { id: number; reason: string | null } | null;
};

type OverrideItem = {
  id: number;
  reason: string | null;
  valid_from: string | null;
  valid_to: string | null;
  limits: Record<string, number>;
  features: Record<string, boolean>;
};

type UsageItem = { id: number; portal_id: number; kind: string; model: string | null; tokens_total: number | null; cost_rub: number; status: string; created_at: string | null };
type PortalItem = { id: number; domain: string };
type Pricing = { chat_rub_per_1k?: number; embed_rub_per_1k?: number };

const emptyPlan = { code: "", name: "", price_month: "", currency: "RUB", is_active: true, limits: "{}", features: "{}" };
const emptyOverride = { id: 0, reason: "", valid_from: "", valid_to: "", limits: "{}", features: "{}" };

function parseJson(value: string, label: string) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    throw new Error(`Некорректный JSON: ${label}`);
  }
}

function prettyDate(value?: string | null) {
  return value ? value.replace("T", " ").slice(0, 19) : "—";
}

function card(label: string, value: string, hint?: string) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-500">{hint}</div> : null}
    </div>
  );
}

export function RevenueHomePage() {
  const qc = useQueryClient();
  const [selectedPlanId, setSelectedPlanId] = useState<number | "new">("new");
  const [selectedAccountId, setSelectedAccountId] = useState<number | "">("");
  const [planForm, setPlanForm] = useState(emptyPlan);
  const [overrideForm, setOverrideForm] = useState(emptyOverride);
  const [subscriptionForm, setSubscriptionForm] = useState({ plan_id: "", status: "active" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const plansQ = useQuery({ queryKey: ["billing-plans"], queryFn: () => api.get("/v1/admin/billing/plans") as Promise<{ items: Plan[] }> });
  const accountsQ = useQuery({ queryKey: ["billing-accounts"], queryFn: () => api.get("/v1/admin/billing/accounts") as Promise<{ items: AccountItem[] }> });
  const pricingQ = useQuery({ queryKey: ["billing-pricing"], queryFn: () => api.get("/v1/admin/billing/pricing") as Promise<Pricing>, refetchInterval: 30000 });
  const usageQ = useQuery({ queryKey: ["billing-usage"], queryFn: () => api.get("/v1/admin/billing/usage?limit=40") as Promise<{ items: UsageItem[] }>, refetchInterval: 30000 });
  const portalsQ = useQuery({ queryKey: ["billing-portals"], queryFn: () => api.get("/v1/admin/portals") as Promise<{ items: PortalItem[] }>, refetchInterval: 30000 });
  const subQ = useQuery({
    queryKey: ["billing-subscription", selectedAccountId],
    queryFn: () => api.get(`/v1/admin/billing/accounts/${selectedAccountId}/subscription`) as Promise<{ subscription: AccountItem["subscription"] }>,
    enabled: selectedAccountId !== "",
  });
  const policyQ = useQuery({
    queryKey: ["billing-policy", selectedAccountId],
    queryFn: () => api.get(`/v1/admin/billing/accounts/${selectedAccountId}/effective-policy`) as Promise<EffectivePolicy>,
    enabled: selectedAccountId !== "",
  });
  const overridesQ = useQuery({
    queryKey: ["billing-overrides", selectedAccountId],
    queryFn: () => api.get(`/v1/admin/billing/accounts/${selectedAccountId}/overrides`) as Promise<{ items: OverrideItem[] }>,
    enabled: selectedAccountId !== "",
  });

  const plans = plansQ.data?.items ?? [];
  const accounts = accountsQ.data?.items ?? [];
  const usage = usageQ.data?.items ?? [];
  const portalMap = new Map((portalsQ.data?.items ?? []).map((p) => [p.id, p.domain]));
  const selectedPlan = selectedPlanId === "new" ? null : plans.find((p) => p.id === selectedPlanId) || null;
  const selectedAccount = accounts.find((a) => a.id === selectedAccountId) || null;

  useEffect(() => {
    if (plans.length && selectedPlanId === "new") setSelectedPlanId(plans[0].id);
    if (accounts.length && selectedAccountId === "") setSelectedAccountId(accounts[0].id);
  }, [plans, accounts, selectedPlanId, selectedAccountId]);

  useEffect(() => {
    if (!selectedPlan) {
      setPlanForm(emptyPlan);
      return;
    }
    setPlanForm({
      code: selectedPlan.code,
      name: selectedPlan.name,
      price_month: String(selectedPlan.price_month),
      currency: selectedPlan.currency,
      is_active: selectedPlan.is_active,
      limits: JSON.stringify(selectedPlan.limits, null, 2),
      features: JSON.stringify(selectedPlan.features, null, 2),
    });
  }, [selectedPlan]);

  useEffect(() => {
    const sub = subQ.data?.subscription;
    setSubscriptionForm({ plan_id: sub?.plan?.id ? String(sub.plan.id) : "", status: sub?.status || "active" });
  }, [subQ.data]);

  useEffect(() => {
    const first = overridesQ.data?.items?.[0];
    setOverrideForm(first ? { id: first.id, reason: first.reason || "", valid_from: first.valid_from?.slice(0, 16) || "", valid_to: first.valid_to?.slice(0, 16) || "", limits: JSON.stringify(first.limits, null, 2), features: JSON.stringify(first.features, null, 2) } : emptyOverride);
  }, [overridesQ.data]);

  async function refresh() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["billing-plans"] }),
      qc.invalidateQueries({ queryKey: ["billing-accounts"] }),
      qc.invalidateQueries({ queryKey: ["billing-subscription", selectedAccountId] }),
      qc.invalidateQueries({ queryKey: ["billing-policy", selectedAccountId] }),
      qc.invalidateQueries({ queryKey: ["billing-overrides", selectedAccountId] }),
    ]);
  }

  const savePlan = useMutation({
    mutationFn: async () => {
      const payload = { code: planForm.code.trim(), name: planForm.name.trim(), price_month: Number(planForm.price_month || 0), currency: planForm.currency.trim() || "RUB", is_active: planForm.is_active, limits: parseJson(planForm.limits, "лимиты"), features: parseJson(planForm.features, "фичи") };
      return selectedPlan ? api.put(`/v1/admin/billing/plans/${selectedPlan.id}`, payload) : api.post("/v1/admin/billing/plans", payload);
    },
    onSuccess: async () => { setMessage(selectedPlan ? "План обновлён." : "План создан."); setError(""); await refresh(); },
    onError: (e: Error) => { setError(e.message); setMessage(""); },
  });
  const togglePlan = useMutation({
    mutationFn: async () => selectedPlan ? api.post(`/v1/admin/billing/plans/${selectedPlan.id}/${selectedPlan.is_active ? "deactivate" : "activate"}`) : null,
    onSuccess: async () => { setMessage("Статус плана обновлён."); setError(""); await refresh(); },
    onError: (e: Error) => { setError(e.message); setMessage(""); },
  });
  const saveSubscription = useMutation({
    mutationFn: async () => api.put(`/v1/admin/billing/accounts/${selectedAccountId}/subscription`, { plan_id: Number(subscriptionForm.plan_id), status: subscriptionForm.status }),
    onSuccess: async () => { setMessage("Подписка обновлена."); setError(""); await refresh(); },
    onError: (e: Error) => { setError(e.message); setMessage(""); },
  });
  const saveOverride = useMutation({
    mutationFn: async () => {
      const payload = { reason: overrideForm.reason || null, valid_from: overrideForm.valid_from || null, valid_to: overrideForm.valid_to || null, limits: parseJson(overrideForm.limits, "override limits"), features: parseJson(overrideForm.features, "override features") };
      return overrideForm.id
        ? api.put(`/v1/admin/billing/accounts/${selectedAccountId}/overrides/${overrideForm.id}`, payload)
        : api.post(`/v1/admin/billing/accounts/${selectedAccountId}/overrides`, payload);
    },
    onSuccess: async () => { setMessage(overrideForm.id ? "Override обновлён." : "Override создан."); setError(""); await refresh(); },
    onError: (e: Error) => { setError(e.message); setMessage(""); },
  });
  const deleteOverride = useMutation({
    mutationFn: async () => api.delete(`/v1/admin/billing/accounts/${selectedAccountId}/overrides/${overrideForm.id}`),
    onSuccess: async () => { setMessage("Override удалён."); setError(""); setOverrideForm(emptyOverride); await refresh(); },
    onError: (e: Error) => { setError(e.message); setMessage(""); },
  });

  const totalCost = usage.reduce((sum, row) => sum + Number(row.cost_rub || 0), 0);
  const totalTokens = usage.reduce((sum, row) => sum + Number(row.tokens_total || 0), 0);
  const blocked = usage.filter((x) => x.status === "blocked").length;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {card("Стоимость", `${totalCost.toFixed(2)} RUB`, "По последним usage")}
        {card("Токены", String(totalTokens), "Prompt + completion")}
        {card("Blocked", String(blocked), "Ограниченные обращения")}
        {card("Текущий прайс", `${Number(pricingQ.data?.chat_rub_per_1k ?? 0).toFixed(2)} / 1k`, `embed ${Number(pricingQ.data?.embed_rub_per_1k ?? 0).toFixed(2)} / 1k`)}
      </section>

      {message ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</div> : null}
      {error ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div> : null}

      <section className="grid gap-6 2xl:grid-cols-[1fr_1.25fr]">
        <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div><h2 className="text-lg font-semibold text-slate-900">Тарифные планы</h2><p className="mt-1 text-sm text-slate-500">Каталог тарифов и базовых ограничений.</p></div>
            <button type="button" onClick={() => { setSelectedPlanId("new"); setPlanForm(emptyPlan); setMessage(""); setError(""); }} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Новый план</button>
          </div>
          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-2">{plans.map((plan) => <button key={plan.id} type="button" onClick={() => setSelectedPlanId(plan.id)} className={["w-full rounded-2xl border p-4 text-left", selectedPlanId === plan.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50"].join(" ")}><div className="flex items-center justify-between"><div className="font-semibold text-slate-900">{plan.name}</div><span className={plan.is_active ? "text-xs font-medium text-emerald-700" : "text-xs font-medium text-slate-500"}>{plan.is_active ? "Активен" : "Неактивен"}</span></div><div className="mt-1 text-sm text-slate-500">{plan.code} · {plan.price_month} {plan.currency}/мес</div></button>)}</div>
            <div className="space-y-4 rounded-2xl border border-slate-200 p-4">
              <div className="grid gap-4 md:grid-cols-2">
                <input className="rounded-xl border border-slate-200 px-3 py-2" placeholder="code" value={planForm.code} disabled={!!selectedPlan} onChange={(e) => setPlanForm({ ...planForm, code: e.target.value })} />
                <input className="rounded-xl border border-slate-200 px-3 py-2" placeholder="name" value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} />
                <input className="rounded-xl border border-slate-200 px-3 py-2" placeholder="price_month" value={planForm.price_month} onChange={(e) => setPlanForm({ ...planForm, price_month: e.target.value })} />
                <input className="rounded-xl border border-slate-200 px-3 py-2" placeholder="currency" value={planForm.currency} onChange={(e) => setPlanForm({ ...planForm, currency: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={planForm.is_active} onChange={(e) => setPlanForm({ ...planForm, is_active: e.target.checked })} />План активен</label>
              <div className="grid gap-4 xl:grid-cols-2">
                <textarea className="h-56 rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs" value={planForm.limits} onChange={(e) => setPlanForm({ ...planForm, limits: e.target.value })} />
                <textarea className="h-56 rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs" value={planForm.features} onChange={(e) => setPlanForm({ ...planForm, features: e.target.value })} />
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => savePlan.mutate()} className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700">{savePlan.isPending ? "Сохранение..." : selectedPlan ? "Сохранить план" : "Создать план"}</button>
                {selectedPlan ? <button type="button" onClick={() => togglePlan.mutate()} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">{selectedPlan.is_active ? "Деактивировать" : "Активировать"}</button> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div><h2 className="text-lg font-semibold text-slate-900">Аккаунт</h2><p className="mt-1 text-sm text-slate-500">Подписка, effective policy и override-правки.</p></div>
              <select className="rounded-xl border border-slate-200 px-3 py-2 text-sm" value={selectedAccountId} onChange={(e) => setSelectedAccountId(e.target.value ? Number(e.target.value) : "")}>{accounts.map((a) => <option key={a.id} value={a.id}>{a.name} · №{a.account_no ?? a.id}</option>)}</select>
            </div>
            {selectedAccount ? <>
              <div className="mt-4 rounded-2xl border border-slate-200 p-4"><div className="text-lg font-semibold text-slate-900">{selectedAccount.name}</div><div className="mt-1 text-sm text-slate-500">№{selectedAccount.account_no ?? selectedAccount.id} · {selectedAccount.status} · {selectedAccount.owner_email || "owner не задан"}</div></div>
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 p-4">
                  <div className="text-sm font-semibold text-slate-900">Подписка</div>
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    <select className="rounded-xl border border-slate-200 px-3 py-2" value={subscriptionForm.plan_id} onChange={(e) => setSubscriptionForm({ ...subscriptionForm, plan_id: e.target.value })}><option value="">Выберите план</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name} ({plan.code})</option>)}</select>
                    <select className="rounded-xl border border-slate-200 px-3 py-2" value={subscriptionForm.status} onChange={(e) => setSubscriptionForm({ ...subscriptionForm, status: e.target.value })}><option value="trial">trial</option><option value="active">active</option><option value="paused">paused</option><option value="canceled">canceled</option></select>
                  </div>
                  <div className="mt-3 text-sm text-slate-500">Текущий план: {subQ.data?.subscription?.plan?.name || "не назначен"} · статус {subQ.data?.subscription?.status || "—"}</div>
                  <button type="button" onClick={() => saveSubscription.mutate()} disabled={!subscriptionForm.plan_id} className="mt-4 rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-60">{saveSubscription.isPending ? "Сохранение..." : "Сменить план"}</button>
                </div>
                <div className="grid gap-4">
                  <div className="rounded-2xl border border-slate-200 p-4"><div className="text-sm font-semibold text-slate-900">Источник политики</div><div className="mt-3 space-y-1 text-sm text-slate-600"><div>Источник: <span className="font-medium text-slate-900">{policyQ.data?.source || "—"}</span></div><div>Plan code: <span className="font-medium text-slate-900">{policyQ.data?.plan_code || "—"}</span></div><div>Subscription status: <span className="font-medium text-slate-900">{policyQ.data?.subscription_status || "—"}</span></div><div>Active override: <span className="font-medium text-slate-900">{policyQ.data?.override?.reason || "—"}</span></div></div></div>
                  <pre className="overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">{JSON.stringify({ limits: policyQ.data?.limits || {}, features: policyQ.data?.features || {} }, null, 2)}</pre>
                </div>
              </div>
            </> : <div className="mt-4 text-sm text-slate-500">Аккаунты не найдены.</div>}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div><h2 className="text-lg font-semibold text-slate-900">Overrides</h2><p className="mt-1 text-sm text-slate-500">Точечные исключения поверх плана.</p></div>
              <button type="button" onClick={() => setOverrideForm(emptyOverride)} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Новый override</button>
            </div>
            <div className="mt-4 grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
              <div className="space-y-2">{(overridesQ.data?.items ?? []).map((item) => <button key={item.id} type="button" onClick={() => setOverrideForm({ id: item.id, reason: item.reason || "", valid_from: item.valid_from?.slice(0,16) || "", valid_to: item.valid_to?.slice(0,16) || "", limits: JSON.stringify(item.limits, null, 2), features: JSON.stringify(item.features, null, 2) })} className={["w-full rounded-2xl border p-4 text-left", overrideForm.id === item.id ? "border-sky-300 bg-sky-50" : "border-slate-200 hover:bg-slate-50"].join(" ")}><div className="font-semibold text-slate-900">{item.reason || `Override #${item.id}`}</div><div className="mt-1 text-sm text-slate-500">{prettyDate(item.valid_from)} → {prettyDate(item.valid_to)}</div></button>)}</div>
              <div className="space-y-4 rounded-2xl border border-slate-200 p-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <input className="rounded-xl border border-slate-200 px-3 py-2" placeholder="reason" value={overrideForm.reason} onChange={(e) => setOverrideForm({ ...overrideForm, reason: e.target.value })} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <input type="datetime-local" className="rounded-xl border border-slate-200 px-3 py-2" value={overrideForm.valid_from} onChange={(e) => setOverrideForm({ ...overrideForm, valid_from: e.target.value })} />
                    <input type="datetime-local" className="rounded-xl border border-slate-200 px-3 py-2" value={overrideForm.valid_to} onChange={(e) => setOverrideForm({ ...overrideForm, valid_to: e.target.value })} />
                  </div>
                </div>
                <div className="grid gap-4 xl:grid-cols-2">
                  <textarea className="h-52 rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs" value={overrideForm.limits} onChange={(e) => setOverrideForm({ ...overrideForm, limits: e.target.value })} />
                  <textarea className="h-52 rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs" value={overrideForm.features} onChange={(e) => setOverrideForm({ ...overrideForm, features: e.target.value })} />
                </div>
                <div className="flex gap-3">
                  <button type="button" onClick={() => saveOverride.mutate()} className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700">{saveOverride.isPending ? "Сохранение..." : overrideForm.id ? "Сохранить override" : "Создать override"}</button>
                  {overrideForm.id ? <button type="button" onClick={() => deleteOverride.mutate()} className="rounded-xl border border-rose-200 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50">{deleteOverride.isPending ? "Удаление..." : "Удалить override"}</button> : null}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div><h2 className="text-lg font-semibold text-slate-900">Последние usage rows</h2><p className="mt-1 text-sm text-slate-500">Последние записи стоимости и токенов.</p></div>
              <Link to="/admin/portals" className="text-sm font-medium text-sky-700 hover:underline">К порталам</Link>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm"><thead className="border-b border-slate-200 text-left text-slate-500"><tr><th className="px-2 py-2 font-medium">Время</th><th className="px-2 py-2 font-medium">Портал</th><th className="px-2 py-2 font-medium">Kind</th><th className="px-2 py-2 font-medium">Model</th><th className="px-2 py-2 font-medium">Tokens</th><th className="px-2 py-2 font-medium">Cost</th><th className="px-2 py-2 font-medium">Status</th></tr></thead>
                <tbody>{usage.map((row) => <tr key={row.id} className="border-b border-slate-100"><td className="px-2 py-2 text-slate-600">{prettyDate(row.created_at)}</td><td className="px-2 py-2 text-slate-900">{portalMap.get(row.portal_id) || `portal ${row.portal_id}`}</td><td className="px-2 py-2 text-slate-600">{row.kind}</td><td className="px-2 py-2 text-slate-600">{row.model || "—"}</td><td className="px-2 py-2 text-slate-600">{row.tokens_total ?? 0}</td><td className="px-2 py-2 text-slate-900">{Number(row.cost_rub || 0).toFixed(4)}</td><td className="px-2 py-2"><span className={row.status === "ok" ? "text-emerald-700" : row.status === "blocked" ? "text-amber-700" : "text-rose-700"}>{row.status}</span></td></tr>)}</tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
