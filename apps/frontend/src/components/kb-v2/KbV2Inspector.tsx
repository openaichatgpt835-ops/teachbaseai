import type { ReactNode } from "react";

export function KbV2Inspector(props: { title: string; subtitle: string; body: ReactNode }) {
  return (
    <div className="space-y-4">
      <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">{props.title}</div>
        <div className="mt-1 text-sm text-slate-500">{props.subtitle}</div>
      </section>
      {props.body}
    </div>
  );
}
