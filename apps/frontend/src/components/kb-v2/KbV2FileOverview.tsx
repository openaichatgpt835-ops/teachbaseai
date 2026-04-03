import type { KbV2AclItem, KbV2File } from "./types";
import { aclSummaryText, fileStatusLabel } from "./ui";

export function KbV2FileOverview(props: {
  file: KbV2File;
  folderName: string;
  access: KbV2AclItem[];
  effective: { staff: string; client: string };
}) {
  return (
    <div className="space-y-4">
      <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-xs uppercase tracking-wide text-slate-400">Файл</div>
        <div className="mt-2 text-lg font-semibold text-slate-900">{props.file.filename}</div>
        <div className="mt-2 text-sm text-slate-500">Папка: {props.folderName || "Корень"}</div>
        <div className="mt-1 text-sm text-slate-500">Статус: {fileStatusLabel(props.file.status)}</div>
      </section>
      <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">Текущий доступ</div>
        <div className="mt-4 grid gap-2 text-sm">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Сотрудники</span><span className="font-medium">{props.effective.staff}</span></div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Клиенты</span><span className="font-medium">{props.effective.client}</span></div>
        </div>
        <div className="mt-4 text-sm text-slate-500">{aclSummaryText(props.access)}</div>
      </section>
    </div>
  );
}
