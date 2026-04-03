import type { KbV2File, KbV2Folder } from "./types";
import { CompactAccessBadges, folderBranchCount } from "./ui";

export function KbV2FolderTree(props: {
  folders: KbV2Folder[];
  files: KbV2File[];
  selectedFolderId: number | null;
  onSelectFolder: (id: number) => void;
}) {
  const children = new Map<number | null, KbV2Folder[]>();
  props.folders.forEach((folder) => {
    const key = folder.parent_id == null ? null : Number(folder.parent_id);
    const list = children.get(key) || [];
    list.push(folder);
    children.set(key, list);
  });

  const renderNode = (parentId: number | null = null, depth = 0): JSX.Element[] =>
    (children.get(parentId) || []).map((folder) => (
      <div key={folder.id} className="space-y-1">
        <button
          className={`w-full rounded-2xl border px-3 py-3 text-left ${props.selectedFolderId === folder.id ? "border-sky-200 bg-sky-50" : "border-slate-100 bg-slate-50 hover:bg-slate-100"}`}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          onClick={() => props.onSelectFolder(folder.id)}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-slate-900">{folder.name}</div>
              <div className="mt-2">
                <CompactAccessBadges target={folder} />
              </div>
            </div>
            <span className="shrink-0 text-xs text-slate-400">{folderBranchCount(folder.id, props.folders, props.files)}</span>
          </div>
        </button>
        {renderNode(folder.id, depth + 1)}
      </div>
    ));

  return (
    <div>
      <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Папки</div>
      <div className="space-y-2">
        <button
          className={`w-full rounded-2xl border px-3 py-3 text-left ${props.selectedFolderId == null ? "border-sky-200 bg-sky-50" : "border-slate-100 bg-slate-50 hover:bg-slate-100"}`}
          onClick={() => props.onSelectFolder(0)}
        >
          <div className="text-sm font-medium text-slate-900">Все файлы</div>
        </button>
        {renderNode()}
      </div>
    </div>
  );
}
