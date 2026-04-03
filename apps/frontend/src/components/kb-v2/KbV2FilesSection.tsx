import type { KbV2File, KbV2Folder } from "./types";
import { CompactAccessBadges, fileStatusLabel } from "./ui";

export function KbV2FilesSection(props: {
  files: KbV2File[];
  folders: KbV2Folder[];
  selectedFileId: number | null;
  title: string;
  subtitle: string;
  onSelectFile: (id: number) => void;
}) {
  const folderName = new Map(props.folders.map((folder) => [folder.id, folder.name]));
  return (
    <section className="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">{props.title}</div>
          <div className="mt-1 text-sm text-slate-500">{props.subtitle}</div>
        </div>
        <div className="rounded-xl border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-500">Editing flows will move here in v2</div>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-100">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Название</th>
              <th className="px-4 py-3 font-medium">Папка</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium">Доступ</th>
            </tr>
          </thead>
          <tbody>
            {props.files.length === 0 && (
              <tr><td className="px-4 py-6 text-slate-500" colSpan={4}>В этой области пока нет файлов.</td></tr>
            )}
            {props.files.map((file) => (
              <tr
                key={file.id}
                className={`border-t border-slate-100 cursor-pointer ${props.selectedFileId === file.id ? "bg-sky-50" : "bg-white hover:bg-slate-50"}`}
                onClick={() => props.onSelectFile(file.id)}
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-900">{file.filename}</div>
                  <div className="mt-1 text-xs text-slate-400">{file.uploaded_by_name || "—"}</div>
                </td>
                <td className="px-4 py-3 text-slate-600">{file.folder_id ? folderName.get(Number(file.folder_id)) || "Корень" : "Корень"}</td>
                <td className="px-4 py-3 text-slate-600">{fileStatusLabel(file.status)}</td>
                <td className="px-4 py-3"><CompactAccessBadges target={file} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
