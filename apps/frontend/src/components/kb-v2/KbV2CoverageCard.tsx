import type { KbV2AccessSummary } from "./types";

export function KbV2CoverageCard(props: { title: string; summary: KbV2AccessSummary; hint: string }) {
  return (
    <section className="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="text-sm font-semibold text-slate-900">{props.title}</div>
      <div className="mt-1 text-sm text-slate-500">{props.hint}</div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div className="text-xs text-slate-400">Готовые</div><div className="mt-2 text-2xl font-semibold text-slate-900">{props.summary.total_ready_files}</div></div>
        <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div className="text-xs text-slate-400">Всем клиентам</div><div className="mt-2 text-2xl font-semibold text-slate-900">{props.summary.open_all_clients}</div></div>
        <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div className="text-xs text-slate-400">Клиентским группам</div><div className="mt-2 text-2xl font-semibold text-slate-900">{props.summary.open_client_groups}</div></div>
        <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div className="text-xs text-slate-400">Закрыты для клиентов</div><div className="mt-2 text-2xl font-semibold text-slate-900">{props.summary.closed_for_clients}</div></div>
      </div>
    </section>
  );
}
