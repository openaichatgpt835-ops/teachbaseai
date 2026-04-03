import type { KbV2AccessSummary, KbV2AclItem, KbV2File, KbV2Folder } from "./types";
import { aclSummaryText } from "./ui";

export function KbV2FolderOverview(props: {
  folder: KbV2Folder;
  files: KbV2File[];
  parentName: string;
  coverage: KbV2AccessSummary;
  access: KbV2AclItem[];
}) {
  return (
    <div className="space-y-4">
      <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-xs uppercase tracking-wide text-slate-400">Папка</div>
        <div className="mt-2 text-lg font-semibold text-slate-900">{props.folder.name}</div>
        <div className="mt-2 text-sm text-slate-500">{props.parentName ? `Внутри: ${props.parentName}` : "Корень базы знаний"}</div>
        <div className="mt-1 text-sm text-slate-500">Файлов в ветке: {props.files.length}</div>
      </section>
      <section className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">Доступ</div>
        <div className="mt-2 text-sm text-slate-500">{aclSummaryText(props.access)}</div>
        <div className="mt-4 grid gap-2 text-sm">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Готовые материалы</span><span className="font-medium">{props.coverage.total_ready_files}</span></div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Всем клиентам</span><span className="font-medium">{props.coverage.open_all_clients}</span></div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Клиентским группам</span><span className="font-medium">{props.coverage.open_client_groups}</span></div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2"><span>Закрыты для клиентов</span><span className="font-medium">{props.coverage.closed_for_clients}</span></div>
        </div>
      </section>
    </div>
  );
}
