import type { KbV2AclItem, KbV2File, KbV2Folder } from "./types";

export function accessBadgeMeta(kind: "staff" | "client", value?: string) {
  if (kind === "staff") {
    if (value === "staff_admin") return { label: "admin", className: "border-emerald-200 bg-emerald-50 text-emerald-700" };
    if (value === "staff_read") return { label: "read", className: "border-sky-200 bg-sky-50 text-sky-700" };
    return { label: "нет", className: "border-slate-200 bg-slate-50 text-slate-500" };
  }
  if (value === "client_all") return { label: "все", className: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700" };
  if (value === "client_groups") return { label: "группы", className: "border-amber-200 bg-amber-50 text-amber-700" };
  return { label: "закрыто", className: "border-slate-200 bg-slate-50 text-slate-500" };
}

export function CompactAccessBadges({ target }: { target: { access_badges?: { staff?: string; client?: string } } }) {
  const staff = accessBadgeMeta("staff", target.access_badges?.staff);
  const client = accessBadgeMeta("client", target.access_badges?.client);
  return (
    <div className="flex flex-wrap gap-1">
      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${staff.className}`}>Сотр: {staff.label}</span>
      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${client.className}`}>Кл: {client.label}</span>
    </div>
  );
}

export function fileStatusLabel(status?: string) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "ready") return "Готов";
  if (normalized === "processing") return "Обработка";
  if (normalized === "error") return "Ошибка";
  return status || "—";
}

export function aclSummaryText(items: KbV2AclItem[]) {
  if (!items.length) return "Явных правил нет";
  return `${items.length} правил`;
}

export function folderBranchCount(folderId: number, folders: KbV2Folder[], files: KbV2File[]) {
  const children = new Map<number | null, number[]>();
  folders.forEach((folder) => {
    const key = folder.parent_id == null ? null : Number(folder.parent_id);
    const list = children.get(key) || [];
    list.push(folder.id);
    children.set(key, list);
  });
  const ids = new Set<number>();
  const walk = (id: number) => {
    ids.add(id);
    (children.get(id) || []).forEach(walk);
  };
  walk(folderId);
  return files.filter((file) => file.folder_id != null && ids.has(Number(file.folder_id))).length;
}
