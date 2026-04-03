import type { ReactNode } from "react";

export function KbV2Sidebar(props: { upload: ReactNode; tree: ReactNode }) {
  return (
    <div className="space-y-4 rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
      <div>
        <div className="text-sm font-semibold text-slate-900">Структура</div>
        <div className="mt-1 text-xs text-slate-500">Папки задают основную политику доступа. Файлы наследуют её по умолчанию.</div>
      </div>
      {props.upload}
      {props.tree}
    </div>
  );
}
