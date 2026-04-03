
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { coreModuleDescription, coreModuleLabel } from "../../../../shared/ui/modules";
import { fetchPortal, fetchWeb, getActiveAccountId, getWebPortalInfo } from "./auth";
import { useLocation } from "react-router-dom";

type KbFile = {
  id: number;
  filename: string;
  folder_id?: number | null;
  mime_type?: string;
  source_type?: string;
  source_url?: string;
  status: string;
  error_message?: string;
  created_at?: string;
  uploaded_by_type?: string;
  uploaded_by_id?: string;
  uploaded_by_name?: string;
  query_count?: number;
  access_badges?: { staff?: string; client?: string };
};

type KbFolder = {
  id: number;
  name: string;
  parent_id?: number | null;
  access_badges?: { staff?: string; client?: string };
  created_at?: string | null;
};
type KbSmartFolder = { id: number; name: string; system_tag?: string; rules?: any };
type KbTopic = { id: string; name: string; count: number; file_ids: number[] };
type KbAclItem = { principal_type: string; principal_id: string; access_level: string };
type KbAclDraftItem = { principal_type: string; principal_id: string; access_level: string };
type KbAccountUser = { membership_id: number; display_name: string; role: string };
type KbAccountGroup = { id: number; name: string; kind: "staff" | "client"; membership_ids: number[] };
type KbAccessSummary = { total_ready_files: number; open_all_clients: number; open_client_groups: number; closed_for_clients: number };
type SearchMatch = {
  file_id: number;
  filename?: string;
  snippet?: string;
  chunk_index?: number | null;
  page_num?: number | null;
  start_ms?: number | null;
};
type Filter = { kind: "all" | "folder" | "smart" | "topic"; id?: number | string };
type KbPageCacheState = {
  kbFiles: KbFile[];
  kbFolders: KbFolder[];
  kbSmartFolders: KbSmartFolder[];
  kbTopics: KbTopic[];
  kbTopicSuggestions: { id: string; name: string; count: number }[];
  kbFilter: Filter;
  smartFoldersOpen: boolean;
  kbSort: "new" | "name" | "status";
  kbTypeFilter: string;
  kbPeopleFilter: string;
  kbFolderFilter: string;
  kbViewMode: "table" | "grid";
};

const SYSTEM_TOPIC_HINTS: Array<{ id: string; name: string; keywords: string[] }> = [
  { id: "product", name: "Продукт и функциональность", keywords: ["rag", "база", "модель", "конструктор", "бот", "сценар"] },
  { id: "pricing", name: "Тарифы и цены", keywords: ["тариф", "цена", "стоимость", "оплат", "прайс"] },
  { id: "integrations", name: "Интеграции и процессы", keywords: ["bitrix", "амо", "crm", "api", "webhook", "telegram"] },
  { id: "sales", name: "Продажи и квалификация", keywords: ["продаж", "лид", "сделк", "воронк"] },
  { id: "support", name: "Поддержка и сервис", keywords: ["поддерж", "ошибк", "инцидент", "тикет"] },
  { id: "hr", name: "HR и команда", keywords: ["сотруд", "hr", "команд", "найм", "ваканс"] },
  { id: "analytics", name: "Аналитика и метрики", keywords: ["аналит", "отчет", "метрик", "retention", "ret3"] },
];

const kbPageCache = new Map<number, KbPageCacheState>();

function fileTypeCategory(filename: string | undefined, mimeType?: string, sourceType?: string) {
  const mt = (mimeType || "").toLowerCase();
  const st = (sourceType || "").toLowerCase();
  if (mt.startsWith("video/") || ["youtube", "rutube", "vk"].includes(st)) return "Видео";
  if (mt.startsWith("audio/")) return "Аудио";
  if (mt.startsWith("image/")) return "Изображения";
  if (mt.includes("pdf")) return "Документы";
  const name = (filename || "").toLowerCase();
  const ext = name.includes(".") ? name.split(".").pop() || "" : "";
  if (["pdf", "doc", "docx", "txt", "rtf"].includes(ext)) return "Документы";
  if (["xls", "xlsx", "csv"].includes(ext)) return "Таблицы";
  if (["ppt", "pptx", "key"].includes(ext)) return "Презентации";
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) return "Изображения";
  if (["mp3", "ogg", "wav", "m4a", "aac"].includes(ext)) return "Аудио";
  if (["mp4", "mov", "avi", "mkv", "webm"].includes(ext)) return "Видео";
  return "Другое";
}

function fileTypeIcon(filename: string | undefined, mimeType?: string, sourceType?: string) {
  const type = fileTypeCategory(filename, mimeType, sourceType);
  const map: Record<string, { label: string; color: string }> = {
    Документы: { label: "DOC", color: "#3b82f6" },
    Таблицы: { label: "XLS", color: "#16a34a" },
    Презентации: { label: "PPT", color: "#f59e0b" },
    Изображения: { label: "IMG", color: "#a855f7" },
    Аудио: { label: "AUD", color: "#0ea5e9" },
    Видео: { label: "VID", color: "#f97316" },
  };
  return map[type] || { label: "FILE", color: "#64748b" };
}

function fileExt(filename: string | undefined) {
  const name = (filename || "").toLowerCase();
  if (!name.includes(".")) return "";
  return `.${name.split(".").pop() || ""}`;
}

function isInlinePreviewable(filename: string | undefined) {
  const ext = fileExt(filename);
  return [
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".rtf",
    ".txt",
    ".csv",
    ".md",
    ".epub",
    ".json",
    ".xml",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".mp3",
    ".ogg",
    ".wav",
    ".m4a",
    ".aac",
  ].includes(ext);
}

function accessBadgeMeta(kind: "staff" | "client", value?: string) {
  if (kind === "staff") {
    if (value === "staff_admin") return { label: "Сотрудники: admin", className: "border-emerald-200 bg-emerald-50 text-emerald-700" };
    if (value === "staff_read") return { label: "Сотрудники: read", className: "border-sky-200 bg-sky-50 text-sky-700" };
    return { label: "Сотрудники: нет", className: "border-slate-200 bg-slate-50 text-slate-500" };
  }
  if (value === "client_all") return { label: "Клиенты: все", className: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700" };
  if (value === "client_groups") return { label: "Клиенты: группы", className: "border-amber-200 bg-amber-50 text-amber-700" };
  return { label: "Клиенты: закрыто", className: "border-slate-200 bg-slate-50 text-slate-500" };
}

function renderAccessBadges(file: KbFile) {
  const staff = accessBadgeMeta("staff", file.access_badges?.staff);
  const client = accessBadgeMeta("client", file.access_badges?.client);
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      <span className={`rounded-full border px-2 py-0.5 text-[11px] ${staff.className}`}>{staff.label}</span>
      <span className={`rounded-full border px-2 py-0.5 text-[11px] ${client.className}`}>{client.label}</span>
    </div>
  );
}

function renderCompactAccessBadges(target: { access_badges?: { staff?: string; client?: string } }) {
  const staff = accessBadgeMeta("staff", target.access_badges?.staff);
  const client = accessBadgeMeta("client", target.access_badges?.client);
  return (
    <div className="flex flex-wrap justify-end gap-1">
      <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${staff.className}`}>{staff.label.replace("Сотрудники: ", "")}</span>
      <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${client.className}`}>{client.label.replace("Клиенты: ", "")}</span>
    </div>
  );
}

function clientBadgeCategory(value?: string) {
  if (value === "client_all") return "all";
  if (value === "client_groups") return "groups";
  return "closed";
}

function projectedClientBadgeForDraft(
  draft: KbAclDraftItem[],
  file: KbFile,
  folderMap: Map<number, KbFolder>,
  groups: KbAccountGroup[],
) {
  if (!draft.length) {
    if (file.folder_id) return clientBadgeCategory(folderMap.get(Number(file.folder_id))?.access_badges?.client);
    return "closed";
  }
  const allowsAllClients = draft.some(
    (item) =>
      item.access_level !== "none" &&
      ((item.principal_type === "audience" && item.principal_id === "client") ||
        (item.principal_type === "role" && item.principal_id === "client")),
  );
  if (allowsAllClients) return "all";
  const allowsClientGroups = draft.some((item) => {
    if (item.principal_type !== "group" || item.access_level === "none") return false;
    const group = groups.find((candidate) => String(candidate.id) === String(item.principal_id));
    return group?.kind === "client";
  });
  if (allowsClientGroups) return "groups";
  return "closed";
}

function buildExternalEmbedUrl(sourceUrl?: string, startMs?: number | null) {
  const raw = (sourceUrl || "").trim();
  if (!raw) return "";
  const sec = startMs ? Math.max(0, Math.floor(Number(startMs) / 1000)) : 0;
  try {
    const u = new URL(raw);
    const h = u.hostname.toLowerCase();
    if (h.includes("youtu.be") || h.includes("youtube.com")) {
      let vid = "";
      if (h.includes("youtu.be")) vid = u.pathname.replace("/", "");
      else vid = u.searchParams.get("v") || "";
      if (!vid) return "";
      const qs = sec > 0 ? `?start=${sec}&autoplay=0` : "";
      return `https://www.youtube.com/embed/${vid}${qs}`;
    }
    if (h.includes("rutube.ru")) {
      const m = u.pathname.match(/\/video\/([a-zA-Z0-9_-]+)/);
      const id = m?.[1] || "";
      if (!id) return "";
      const qs = sec > 0 ? `?t=${sec}` : "";
      return `https://rutube.ru/play/embed/${id}/${qs}`;
    }
    return "";
  } catch {
    return "";
  }
}

function buildOfficeViewerUrl(rawUrl: string | null | undefined) {
  const u = (rawUrl || "").trim();
  if (!u) return "";
  try {
    const abs = u.startsWith("http://") || u.startsWith("https://") ? u : `${window.location.origin}${u}`;
    return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(abs)}`;
  } catch {
    return "";
  }
}

function fileStatusLabel(status: string | undefined) {
  const s = (status || "").toLowerCase();
  if (s === "ready") return "Готово";
  if (s === "processing") return "Индексируется";
  if (s === "queued") return "В очереди";
  if (s === "uploaded") return "Загружен";
  if (s === "error") return "Ошибка";
  return status || "—";
}

function fileOwnerLabel(file: KbFile) {
  if (file.uploaded_by_name) return file.uploaded_by_name;
  if (file.uploaded_by_type && file.uploaded_by_id) return `${file.uploaded_by_type} ${file.uploaded_by_id}`;
  return file.uploaded_by_type || "—";
}

function isTwoPartTopicName(name: string) {
  const n = (name || "").trim().toLowerCase();
  if (!n) return false;
  return /\b[^\W\d_]+\b\s+и\s+\b[^\W\d_]+\b/i.test(n);
}

function fallbackFileIdsByTopic(
  files: KbFile[],
  topicIdOrName: string,
): number[] {
  const key = (topicIdOrName || "").trim().toLowerCase();
  if (!key) return [];
  const hint = SYSTEM_TOPIC_HINTS.find(
    (h) => h.id.toLowerCase() === key || h.name.toLowerCase() === key,
  );
  const words = hint
    ? hint.keywords
    : (key.match(/[a-zA-Zа-яА-ЯёЁ0-9]{4,}/g) || [key]);
  const ids: number[] = [];
  for (const f of files) {
    const hay = `${f.filename || ""} ${f.source_type || ""} ${f.uploaded_by_name || ""}`.toLowerCase();
    if (words.some((w) => hay.includes((w || "").toLowerCase()))) ids.push(Number(f.id));
  }
  return ids;
}

function kbAccessLabel(level: string | undefined) {
  const value = String(level || "none").toLowerCase();
  if (value === "admin") return "Полный доступ";
  if (value === "write") return "Редактирование";
  if (value === "read") return "Чтение и поиск";
  return "Нет доступа";
}

function kbPrincipalLabel(item: KbAclItem, accountUsers?: KbAccountUser[], accountGroups?: KbAccountGroup[]) {
  if (item.principal_type === "role") {
    if (item.principal_id === "owner") return "Владельцы";
    if (item.principal_id === "admin") return "Админы";
    if (item.principal_id === "member") return "Сотрудники";
    if (item.principal_id === "client") return "Клиентские аккаунты";
  }
  if (item.principal_type === "audience") {
    if (item.principal_id === "staff") return "Все сотрудники";
    if (item.principal_id === "client") return "Клиентский бот";
  }
  if (item.principal_type === "membership") {
    const match = (accountUsers || []).find((user) => String(user.membership_id) === String(item.principal_id));
    if (match) return `${match.display_name} (${match.role})`;
    return `Пользователь ${item.principal_id}`;
  }
  if (item.principal_type === "group") {
    const match = (accountGroups || []).find((group) => String(group.id) === String(item.principal_id));
    if (match) return `${match.kind === "client" ? "Клиентская группа" : "Группа"}: ${match.name}`;
    return `Группа ${item.principal_id}`;
  }
  return `${item.principal_type}:${item.principal_id}`;
}

function kbAclTemplate(
  template: "inherit" | "staff" | "clients" | "staff_clients" | "group" | "client_group",
  options?: { groupId?: number | null },
): KbAclDraftItem[] {
  if (template === "inherit") return [];
  const base: KbAclDraftItem[] = [
    { principal_type: "role", principal_id: "owner", access_level: "admin" },
    { principal_type: "role", principal_id: "admin", access_level: "admin" },
  ];
  if (template === "staff") {
    return [...base, { principal_type: "role", principal_id: "member", access_level: "read" }];
  }
  if (template === "clients") {
    return [
      ...base,
      { principal_type: "role", principal_id: "member", access_level: "none" },
      { principal_type: "audience", principal_id: "client", access_level: "read" },
    ];
  }
  if (template === "group") {
    const groupId = Number(options?.groupId || 0);
    return [
      ...base,
      { principal_type: "role", principal_id: "member", access_level: "none" },
      ...(groupId > 0 ? [{ principal_type: "group", principal_id: String(groupId), access_level: "read" } satisfies KbAclDraftItem] : []),
    ];
  }
  if (template === "client_group") {
    const groupId = Number(options?.groupId || 0);
    return [
      ...base,
      { principal_type: "role", principal_id: "member", access_level: "none" },
      { principal_type: "role", principal_id: "client", access_level: "none" },
      ...(groupId > 0 ? [{ principal_type: "group", principal_id: String(groupId), access_level: "read" } satisfies KbAclDraftItem] : []),
    ];
  }
  return [
    ...base,
    { principal_type: "role", principal_id: "member", access_level: "read" },
    { principal_type: "audience", principal_id: "client", access_level: "read" },
  ];
}

function renderAccessOriginCard(opts: {
  title: string;
  tone?: "blue" | "amber" | "emerald";
  body: string;
}) {
  const tone = opts.tone || "blue";
  const toneMap = {
    blue: "border-sky-200 bg-sky-50 text-sky-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
  } as const;
  return (
    <div className={`rounded-xl border px-3 py-3 ${toneMap[tone]}`}>
      <div className="text-xs font-semibold uppercase tracking-wide">{opts.title}</div>
      <div className="mt-1 text-sm">{opts.body}</div>
    </div>
  );
}

function summarizeClientVisibility(items: KbAclItem[], accountGroups: KbAccountGroup[]) {
  if (!items.length) return "Клиентский доступ не задан явно.";
  const allClients = items.some(
    (item) =>
      (item.principal_type === "audience" && item.principal_id === "client" && item.access_level !== "none") ||
      (item.principal_type === "role" && item.principal_id === "client" && item.access_level !== "none"),
  );
  if (allClients) return "Доступно всем клиентам, которые работают через клиентский бот.";
  const groups = items
    .filter((item) => item.principal_type === "group" && item.access_level !== "none")
    .map((item) => accountGroups.find((group) => String(group.id) === String(item.principal_id)))
    .filter((group): group is KbAccountGroup => !!group && group.kind === "client");
  if (groups.length) return `Доступно только клиентским группам: ${groups.map((group) => group.name).join(", ")}.`;
  return "Клиентский доступ ограничен или управляется через другие явные правила.";
}

function audienceOptionLabel(value: string) {
  if (value === "staff") return "Все сотрудники";
  if (value === "client") return "Клиентский бот";
  return value;
}

function roleOptionLabel(value: string) {
  if (value === "owner") return "Владельцы";
  if (value === "admin") return "Администраторы";
  if (value === "member") return "Сотрудники";
  if (value === "client") return "Клиентские аккаунты";
  return value;
}

function buildFolderChildrenMap(folders: KbFolder[]) {
  const map = new Map<number | null, KbFolder[]>();
  folders.forEach((folder) => {
    const key = folder.parent_id ?? null;
    const bucket = map.get(key) || [];
    bucket.push(folder);
    map.set(key, bucket);
  });
  for (const bucket of map.values()) {
    bucket.sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }
  return map;
}

function collectFolderSubtreeIds(childrenMap: Map<number | null, KbFolder[]>, folderId: number): number[] {
  const ids = [folderId];
  const walk = (parentId: number) => {
    const children = childrenMap.get(parentId) || [];
    children.forEach((child) => {
      ids.push(child.id);
      walk(child.id);
    });
  };
  walk(folderId);
  return ids;
}

export function WebKbPage() {
  const location = useLocation();
  const { portalId, portalToken } = getWebPortalInfo();
  const cached = portalId ? kbPageCache.get(portalId) : null;
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const searchTimerRef = useRef<number | null>(null);
  const searchReqSeqRef = useRef(0);
  const tableRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());

  const [kbFiles, setKbFiles] = useState<KbFile[]>(cached?.kbFiles || []);
  const [kbFolders, setKbFolders] = useState<KbFolder[]>(cached?.kbFolders || []);
  const [kbSmartFolders, setKbSmartFolders] = useState<KbSmartFolder[]>(cached?.kbSmartFolders || []);
  const [kbTopics, setKbTopics] = useState<KbTopic[]>(cached?.kbTopics || []);
  const [kbTopicSuggestions, setKbTopicSuggestions] = useState<{ id: string; name: string; count: number }[]>(cached?.kbTopicSuggestions || []);
  const [kbTopicsThreshold, setKbTopicsThreshold] = useState<number>(5);
  const [kbTopicsLoadError, setKbTopicsLoadError] = useState("");
  const [kbFilter, setKbFilter] = useState<Filter>(cached?.kbFilter || { kind: "all" });
  const [newFolderName, setNewFolderName] = useState("");
  const [smartFoldersOpen, setSmartFoldersOpen] = useState(cached?.smartFoldersOpen ?? true);
  const [smartFolderMessage, setSmartFolderMessage] = useState("");

  const [kbSearch, setKbSearch] = useState("");
  const [kbSearchResults, setKbSearchResults] = useState<number[] | null>(null);
  const [kbSearchMatches, setKbSearchMatches] = useState<SearchMatch[]>([]);
  const [kbSearchLoading, setKbSearchLoading] = useState(false);
  const [kbSearchError, setKbSearchError] = useState("");

  const [smartSearchOpen, setSmartSearchOpen] = useState(false);
  const [smartSearchQuery, setSmartSearchQuery] = useState("");
  const [smartSearchAnswer, setSmartSearchAnswer] = useState("");
  const [smartSearchLoading, setSmartSearchLoading] = useState(false);
  const [smartSearchError, setSmartSearchError] = useState("");

  const [kbSort, setKbSort] = useState<"new" | "name" | "status">(cached?.kbSort || "new");
  const [kbTypeFilter, setKbTypeFilter] = useState(cached?.kbTypeFilter || "all");
  const [kbPeopleFilter, setKbPeopleFilter] = useState(cached?.kbPeopleFilter || "all");
  const [kbFolderFilter, setKbFolderFilter] = useState(cached?.kbFolderFilter || "all");
  const [kbViewMode, setKbViewMode] = useState<"table" | "grid">(cached?.kbViewMode || "table");

  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [dragOverFolderId, setDragOverFolderId] = useState<number | null>(null);
  const [draggedFileId, setDraggedFileId] = useState<number | null>(null);
  const [openFileMenuId, setOpenFileMenuId] = useState<number | null>(null);
  const [contextMenu, setContextMenu] = useState<{ id: number; x: number; y: number } | null>(null);
  const [focusedRowId, setFocusedRowId] = useState<number | null>(null);
  const [lastSelectedId, setLastSelectedId] = useState<number | null>(null);
  const [dragSelectBox, setDragSelectBox] = useState<{ x: number; y: number; w: number; h: number; active: boolean } | null>(null);
  const [kbUploadMessage, setKbUploadMessage] = useState("");
  const [focusApplied, setFocusApplied] = useState(false);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [detailsTarget, setDetailsTarget] = useState<{ kind: "folder" | "file"; id: number } | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [detailsSaving, setDetailsSaving] = useState(false);
  const [detailsSaveMessage, setDetailsSaveMessage] = useState("");
  const [isEditingAccess, setIsEditingAccess] = useState(false);
  const [showAdvancedAcl, setShowAdvancedAcl] = useState(false);
  const [aclDraft, setAclDraft] = useState<KbAclDraftItem[]>([]);
  const [accountUsers, setAccountUsers] = useState<KbAccountUser[]>([]);
  const [accountGroups, setAccountGroups] = useState<KbAccountGroup[]>([]);
  const [templateStaffGroupId, setTemplateStaffGroupId] = useState<number>(0);
  const [templateClientGroupId, setTemplateClientGroupId] = useState<number>(0);
  const [selectedFolderAccess, setSelectedFolderAccess] = useState<KbAclItem[]>([]);
  const [selectedFileAccess, setSelectedFileAccess] = useState<KbAclItem[]>([]);
  const [selectedFileEffectiveStaff, setSelectedFileEffectiveStaff] = useState<string>("read");
  const [selectedFileEffectiveClient, setSelectedFileEffectiveClient] = useState<string>("none");
  const [selectedFolderClientCoverage, setSelectedFolderClientCoverage] = useState<KbAccessSummary>({
    total_ready_files: 0,
    open_all_clients: 0,
    open_client_groups: 0,
    closed_for_clients: 0,
  });
  const [bulkAccessOpen, setBulkAccessOpen] = useState(false);
  const [bulkAclDraft, setBulkAclDraft] = useState<KbAclDraftItem[]>([]);
  const [bulkAclSaving, setBulkAclSaving] = useState(false);
  const [bulkAclMessage, setBulkAclMessage] = useState("");
  const [previewFileId, setPreviewFileId] = useState<number | null>(null);
  const [previewStartMs, setPreviewStartMs] = useState<number | null>(null);
  const [previewPage, setPreviewPage] = useState<number | null>(null);
  const [previewInlineUrl, setPreviewInlineUrl] = useState<string | null>(null);
  const [previewDownloadUrl, setPreviewDownloadUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [kbAccessSummary, setKbAccessSummary] = useState<KbAccessSummary>({ total_ready_files: 0, open_all_clients: 0, open_client_groups: 0, closed_for_clients: 0 });
  const loadFiles = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files`);
    const data = await res.json().catch(() => null);
    if (res.ok && Array.isArray(data?.items)) setKbFiles(data.items);
  };

  const loadFolders = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders`);
    const data = await res.json().catch(() => null);
    if (res.ok && Array.isArray(data?.items)) setKbFolders(data.items);
  };

  const loadSmartFolders = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/smart-folders`);
    const data = await res.json().catch(() => null);
    if (res.ok && Array.isArray(data?.items)) setKbSmartFolders(data.items);
  };

  const loadTopics = async () => {
    if (!portalId || !portalToken) return;
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/topics`);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setKbTopicsLoadError(String(data?.error || data?.detail || `HTTP ${res.status}`));
        return;
      }
      const topics = Array.isArray(data?.topics) ? data.topics : [];
      let suggestions = Array.isArray(data?.suggestions) ? data.suggestions : [];
      setKbTopicsThreshold(Number(data?.threshold || 5));
      if (!suggestions.length) {
        suggestions = topics
          .filter((t: any) => Number(t?.count || 0) > 0)
          .sort((a: any, b: any) => Number(b?.count || 0) - Number(a?.count || 0))
          .slice(0, 8)
          .map((t: any) => ({ id: String(t.id || ""), name: String(t.name || ""), count: Number(t.count || 0) }));
      }
      setKbTopics(topics);
      setKbTopicSuggestions(suggestions);
      setKbTopicsLoadError("");
    } catch (e: any) {
      setKbTopicsLoadError(String(e?.message || "topics_load_failed"));
    }
  };

  const loadAccessSummary = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary`);
    const data = await res.json().catch(() => null);
    if (!res.ok) return;
    setKbAccessSummary({
      total_ready_files: Number(data?.total_ready_files || 0),
      open_all_clients: Number(data?.open_all_clients || 0),
      open_client_groups: Number(data?.open_client_groups || 0),
      closed_for_clients: Number(data?.closed_for_clients || 0),
    });
  };

  useEffect(() => {
    if (portalId) {
      const state = kbPageCache.get(portalId);
      if (state) {
        setKbFiles(state.kbFiles || []);
        setKbFolders(state.kbFolders || []);
        setKbSmartFolders(state.kbSmartFolders || []);
        setKbTopics(state.kbTopics || []);
        setKbTopicSuggestions(state.kbTopicSuggestions || []);
        setKbFilter(state.kbFilter || { kind: "all" });
        setSmartFoldersOpen(state.smartFoldersOpen ?? true);
        setKbSort(state.kbSort || "new");
        setKbTypeFilter(state.kbTypeFilter || "all");
        setKbPeopleFilter(state.kbPeopleFilter || "all");
        setKbFolderFilter(state.kbFolderFilter || "all");
        setKbViewMode(state.kbViewMode || "table");
      }
    }
    loadFiles();
    loadFolders();
    loadSmartFolders();
    loadTopics();
    loadAccessSummary();
  }, [portalId, portalToken]);

  useEffect(() => {
    const loadAccountUsers = async () => {
        const accountId = getActiveAccountId();
        if (!accountId) {
          setAccountUsers([]);
          setAccountGroups([]);
          return;
        }
        const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/access-center`);
        const data = await res.json().catch(() => null);
        if (!res.ok) return;
      const items = Array.isArray(data?.items) ? data.items : [];
      setAccountUsers(
        items.map((item: any) => ({
          membership_id: Number(item?.membership_id || 0),
          display_name: String(item?.display_name || item?.web?.email || `Пользователь ${item?.membership_id || ""}`),
            role: String(item?.role || "member"),
          })).filter((item: KbAccountUser) => item.membership_id > 0),
        );
        setAccountGroups(
          (Array.isArray(data?.groups) ? data.groups : []).map((group: any) => ({
            id: Number(group?.id || 0),
            name: String(group?.name || `Группа ${group?.id || ""}`),
            kind: String(group?.kind || "staff") === "client" ? "client" : "staff",
            membership_ids: Array.isArray(group?.membership_ids)
              ? group.membership_ids.map((value: any) => Number(value)).filter((value: number) => Number.isFinite(value))
              : [],
          })).filter((group: KbAccountGroup) => group.id > 0),
        );
      };
      void loadAccountUsers();
    }, [portalId]);

  const staffGroups = useMemo(() => accountGroups.filter((group) => group.kind !== "client"), [accountGroups]);
  const clientGroups = useMemo(() => accountGroups.filter((group) => group.kind === "client"), [accountGroups]);

  useEffect(() => {
    if (!staffGroups.length) {
      setTemplateStaffGroupId(0);
      return;
    }
    if (!staffGroups.some((group) => group.id === templateStaffGroupId)) {
      setTemplateStaffGroupId(staffGroups[0].id);
    }
  }, [staffGroups, templateStaffGroupId]);

  useEffect(() => {
    if (!clientGroups.length) {
      setTemplateClientGroupId(0);
      return;
    }
    if (!clientGroups.some((group) => group.id === templateClientGroupId)) {
      setTemplateClientGroupId(clientGroups[0].id);
    }
  }, [clientGroups, templateClientGroupId]);

  useEffect(() => {
    if (selectedFileIds.length === 0) {
      setBulkAccessOpen(false);
      setBulkAclDraft([]);
      setBulkAclMessage("");
    }
  }, [selectedFileIds]);

  useEffect(() => {
    setFocusApplied(false);
  }, [location.search]);

  useEffect(() => {
    if (!portalId) return;
    kbPageCache.set(portalId, {
      kbFiles,
      kbFolders,
      kbSmartFolders,
      kbTopics,
      kbTopicSuggestions,
      kbFilter,
      smartFoldersOpen,
      kbSort,
      kbTypeFilter,
      kbPeopleFilter,
      kbFolderFilter,
      kbViewMode,
    });
  }, [
    portalId,
    kbFiles,
    kbFolders,
    kbSmartFolders,
    kbTopics,
    kbTopicSuggestions,
    kbFilter,
    smartFoldersOpen,
    kbSort,
    kbTypeFilter,
    kbPeopleFilter,
    kbFolderFilter,
    kbViewMode,
  ]);

  const folderChildrenMap = useMemo(() => buildFolderChildrenMap(kbFolders), [kbFolders]);

  const folderIdsInScope = useMemo(() => {
    if (kbFilter.kind === "folder" && kbFilter.id) {
      return new Set(collectFolderSubtreeIds(folderChildrenMap, Number(kbFilter.id)));
    }
    if (kbFolderFilter !== "all") {
      return new Set(collectFolderSubtreeIds(folderChildrenMap, Number(kbFolderFilter)));
    }
    return null;
  }, [kbFilter, kbFolderFilter, folderChildrenMap]);

  const folderFileCounts = useMemo(() => {
    const counts = new Map<number, number>();
    kbFiles.forEach((file) => {
      if (file.folder_id == null) return;
      counts.set(Number(file.folder_id), (counts.get(Number(file.folder_id)) || 0) + 1);
    });
    const totals = new Map<number, number>();
    const visit = (folderId: number): number => {
      let total = counts.get(folderId) || 0;
      const children = folderChildrenMap.get(folderId) || [];
      children.forEach((child) => {
        total += visit(child.id);
      });
      totals.set(folderId, total);
      return total;
    };
    (folderChildrenMap.get(null) || []).forEach((folder) => visit(folder.id));
    return totals;
  }, [kbFiles, folderChildrenMap]);

  const folderNameMap = useMemo(() => {
    const map = new Map<number, string>();
    kbFolders.forEach((folder) => map.set(folder.id, folder.name));
    return map;
  }, [kbFolders]);

  const filteredKbFiles = useMemo(() => {
    const query = kbSearch.trim().toLowerCase();
    const hasFullText = kbSearchResults !== null;
    let items = kbFiles.slice();

    if (query && !hasFullText) {
      items = items.filter((x) =>
        (x.filename || "").toLowerCase().includes(query) ||
        (x.uploaded_by_name || "").toLowerCase().includes(query)
      );
    }
    if (kbTypeFilter !== "all") {
      items = items.filter((x) => fileTypeCategory(x.filename, x.mime_type, x.source_type) === kbTypeFilter);
    }
    if (kbPeopleFilter !== "all") {
      items = items.filter((x) => (x.uploaded_by_name || "") === kbPeopleFilter);
    }
    if (folderIdsInScope) {
      items = items.filter((x) => {
        if (x.folder_id == null) return false;
        return folderIdsInScope.has(Number(x.folder_id));
      });
    }
    if (hasFullText) {
      const ids = new Set(kbSearchResults || []);
      if (selectedFileIds.length > 0) {
        const selected = new Set(selectedFileIds);
        items = items.filter((x) => selected.has(x.id) || ids.has(x.id));
      } else {
        items = items.filter((x) => ids.has(x.id));
      }
    }
    if (kbFilter.kind === "topic" && kbFilter.id) {
      const topic = kbTopics.find((t) => t.id === String(kbFilter.id));
      const ids = topic?.file_ids || [];
      items = items.filter((x) => ids.includes(x.id));
    }
    if (kbFilter.kind === "smart" && kbFilter.id) {
      const folder = kbSmartFolders.find((s) => s.id === Number(kbFilter.id));
      const topicId = (
        folder?.system_tag ||
        folder?.rules?.topic_id ||
        folder?.rules?.topicId ||
        folder?.rules?.topic ||
        folder?.rules?.id ||
        ""
      ).toString();
      if (topicId) {
        const topic = kbTopics.find((t) => String(t.id) === topicId);
        let ids = (topic?.file_ids || []).map((id) => Number(id));
        if (!ids.length) {
          ids = fallbackFileIdsByTopic(kbFiles, topicId);
        }
        items = items.filter((x) => ids.includes(Number(x.id)));
      } else if (folder?.name) {
        const topic = kbTopics.find((t) => t.name.toLowerCase() === folder.name.toLowerCase());
        let ids = (topic?.file_ids || []).map((id) => Number(id));
        if (!ids.length) {
          ids = fallbackFileIdsByTopic(kbFiles, folder.name);
        }
        items = items.filter((x) => ids.includes(Number(x.id)));
      }
    }
    return items;
  }, [kbFiles, kbSearch, kbSearchResults, kbTypeFilter, kbPeopleFilter, folderIdsInScope, kbFilter, kbTopics, kbSmartFolders, selectedFileIds]);

  const sortedKbFiles = useMemo(() => {
    const items = filteredKbFiles.slice();
    if (kbSort === "name") {
      items.sort((a, b) => (a.filename || "").localeCompare(b.filename || ""));
    } else if (kbSort === "status") {
      items.sort((a, b) => (a.status || "").localeCompare(b.status || ""));
    } else {
      items.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    }
    return items;
  }, [filteredKbFiles, kbSort]);

  const kbTypeOptions = useMemo(() => {
    const types = new Set<string>();
    kbFiles.forEach((f) => types.add(fileTypeCategory(f.filename, f.mime_type, f.source_type)));
    return Array.from(types).sort();
  }, [kbFiles]);

  const kbPeopleOptions = useMemo(() => {
    const people = new Set<string>();
    kbFiles.forEach((f) => {
      if (f.uploaded_by_name) people.add(f.uploaded_by_name);
      else if (f.uploaded_by_type) people.add(f.uploaded_by_type);
    });
    return Array.from(people).sort();
  }, [kbFiles]);

  const selectedFolderName = useMemo(() => {
    if (kbFilter.kind !== "folder" || !kbFilter.id) return "";
    return folderNameMap.get(Number(kbFilter.id)) || "";
  }, [kbFilter, folderNameMap]);

  const selectedFolder = useMemo(
    () => (selectedFolderId ? kbFolders.find((folder) => folder.id === selectedFolderId) || null : null),
    [kbFolders, selectedFolderId],
  );

  const selectedDetailsFile = useMemo(
    () => (detailsTarget?.kind === "file" ? kbFiles.find((file) => file.id === detailsTarget.id) || null : null),
    [detailsTarget, kbFiles],
  );
  const selectedDetailsFileFolder = useMemo(
    () => (selectedDetailsFile?.folder_id ? kbFolders.find((folder) => folder.id === Number(selectedDetailsFile.folder_id)) || null : null),
    [kbFolders, selectedDetailsFile],
  );
  const folderHasExplicitRules = selectedFolderAccess.length > 0;
  const fileHasExplicitRules = selectedFileAccess.length > 0;

  const recommendedKbFiles = useMemo(() => {
    return kbFiles
      .filter((f) => (f.status || "").toLowerCase() === "ready")
      .slice()
      .sort((a, b) => {
        const qa = a.query_count || 0;
        const qb = b.query_count || 0;
        if (qa !== qb) return qb - qa;
        return String(b.created_at || "").localeCompare(String(a.created_at || ""));
      })
      .slice(0, 20);
  }, [kbFiles]);

  const allVisibleSelected = useMemo(() => {
    if (!sortedKbFiles.length) return false;
    return sortedKbFiles.every((f) => selectedFileIds.includes(f.id));
  }, [sortedKbFiles, selectedFileIds]);

  const selectedBulkFiles = useMemo(
    () => kbFiles.filter((file) => selectedFileIds.includes(file.id)),
    [kbFiles, selectedFileIds],
  );

  const bulkClientImpact = useMemo(() => {
    const before = { all: 0, groups: 0, closed: 0 };
    const after = { all: 0, groups: 0, closed: 0 };
    selectedBulkFiles.forEach((file) => {
      const current = clientBadgeCategory(file.access_badges?.client);
      before[current] += 1;
      const projected = projectedClientBadgeForDraft(bulkAclDraft, file, new Map(kbFolders.map((folder) => [folder.id, folder])), accountGroups);
      after[projected] += 1;
    });
    return {
      before,
      after,
      opensToAll: Math.max(0, after.all - before.all),
      opensToGroups: Math.max(0, after.groups - before.groups),
      closesForClients: Math.max(0, after.closed - before.closed),
    };
  }, [selectedBulkFiles, bulkAclDraft, kbFolders, accountGroups]);

  const folderClientImpact = useMemo(() => {
    if (!selectedFolder) return null;
    const current = clientBadgeCategory(selectedFolder.access_badges?.client);
    const projected = projectedClientBadgeForDraft(aclDraft, { id: -1, filename: "", status: "ready" }, new Map(), accountGroups);
    return {
      current,
      projected,
      totalReady: selectedFolderClientCoverage.total_ready_files,
      openAll: selectedFolderClientCoverage.open_all_clients,
      openGroups: selectedFolderClientCoverage.open_client_groups,
      closed: selectedFolderClientCoverage.closed_for_clients,
    };
  }, [selectedFolder, aclDraft, accountGroups, selectedFolderClientCoverage]);

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      const visibleIds = new Set(sortedKbFiles.map((f) => f.id));
      setSelectedFileIds((prev) => prev.filter((id) => !visibleIds.has(id)));
      return;
    }
    const ids = new Set(selectedFileIds);
    sortedKbFiles.forEach((f) => ids.add(f.id));
    setSelectedFileIds(Array.from(ids));
  };

  const selectRange = (startId: number, endId: number) => {
    const ids = sortedKbFiles.map((f) => f.id);
    const startIdx = ids.indexOf(startId);
    const endIdx = ids.indexOf(endId);
    if (startIdx === -1 || endIdx === -1) return;
    const [from, to] = startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx];
    const range = ids.slice(from, to + 1);
    const set = new Set(selectedFileIds);
    range.forEach((id) => set.add(id));
    setSelectedFileIds(Array.from(set));
  };

  const handleRowSelect = (id: number, evt: React.MouseEvent | React.ChangeEvent) => {
    const isShift = "shiftKey" in evt && evt.shiftKey;
    if (isShift && lastSelectedId) {
      selectRange(lastSelectedId, id);
    } else {
      setSelectedFileIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    }
    setLastSelectedId(id);
    setFocusedRowId(id);
  };

  const handleTableKey = (evt: React.KeyboardEvent) => {
    if (!sortedKbFiles.length) return;
    const ids = sortedKbFiles.map((f) => f.id);
    const currentIndex = focusedRowId ? ids.indexOf(focusedRowId) : -1;
    if (evt.key === "ArrowDown") {
      evt.preventDefault();
      const nextId = ids[Math.min(ids.length - 1, Math.max(0, currentIndex + 1))];
      setFocusedRowId(nextId);
      rowRefs.current.get(nextId || 0)?.scrollIntoView({ block: "nearest" });
    }
    if (evt.key === "ArrowUp") {
      evt.preventDefault();
      const nextId = ids[Math.max(0, currentIndex === -1 ? 0 : currentIndex - 1)];
      setFocusedRowId(nextId);
      rowRefs.current.get(nextId || 0)?.scrollIntoView({ block: "nearest" });
    }
    if (evt.key === "Enter" && focusedRowId) {
      evt.preventDefault();
      setSelectedFileIds((prev) =>
        prev.includes(focusedRowId) ? prev.filter((x) => x !== focusedRowId) : [...prev, focusedRowId]
      );
    }
    if (evt.key === "Delete" && focusedRowId) {
      evt.preventDefault();
      deleteFile(focusedRowId);
    }
    if (evt.key === "Escape") {
      evt.preventDefault();
      setSelectedFileIds([]);
      setFocusedRowId(null);
    }
  };

  const startDragSelect = (evt: React.MouseEvent) => {
    if (evt.button !== 0) return;
    const target = evt.target as HTMLElement;
    if (target.closest("button") || target.closest("input") || target.closest("a")) return;
    if (target.closest("[data-row='kb']")) return;
    if (!tableRef.current) return;
    const rect = tableRef.current.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    setDragSelectBox({ x, y, w: 0, h: 0, active: true });
  };

  useEffect(() => {
    if (!dragSelectBox?.active || !tableRef.current) return;
    const rect = tableRef.current.getBoundingClientRect();
    const onMove = (evt: MouseEvent) => {
      const x = Math.max(0, Math.min(evt.clientX - rect.left, rect.width));
      const y = Math.max(0, Math.min(evt.clientY - rect.top, rect.height));
      setDragSelectBox((prev) => {
        if (!prev) return prev;
        return { ...prev, w: x - prev.x, h: y - prev.y, active: true };
      });
    };
    const onUp = () => {
      setDragSelectBox((prev) => (prev ? { ...prev, active: false } : prev));
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragSelectBox?.active]);

  useEffect(() => {
    if (!dragSelectBox || dragSelectBox.active) return;
    if (!tableRef.current) return;
    const rect = tableRef.current.getBoundingClientRect();
    const left = Math.min(dragSelectBox.x, dragSelectBox.x + dragSelectBox.w) + rect.left;
    const right = Math.max(dragSelectBox.x, dragSelectBox.x + dragSelectBox.w) + rect.left;
    const top = Math.min(dragSelectBox.y, dragSelectBox.y + dragSelectBox.h) + rect.top;
    const bottom = Math.max(dragSelectBox.y, dragSelectBox.y + dragSelectBox.h) + rect.top;
    const selected: number[] = [];
    rowRefs.current.forEach((node, id) => {
      if (!node) return;
      const r = node.getBoundingClientRect();
      const overlap = r.left < right && r.right > left && r.top < bottom && r.bottom > top;
      if (overlap) selected.push(id);
    });
    if (selected.length) {
      const set = new Set(selectedFileIds);
      selected.forEach((id) => set.add(id));
      setSelectedFileIds(Array.from(set));
    }
    setDragSelectBox(null);
  }, [dragSelectBox]);

  useEffect(() => {
    const onKey = (evt: KeyboardEvent) => {
      const active = document.activeElement;
      const isInTable = tableRef.current?.contains(active || null);
      if (kbViewMode !== "table") return;
      if (!focusedRowId && !isInTable) return;
      handleTableKey(evt as unknown as React.KeyboardEvent);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [kbViewMode, focusedRowId, sortedKbFiles, selectedFileIds]);

  useEffect(() => {
    if (focusApplied) return;
    const qs = new URLSearchParams(location.search || "");
    const fid = Number(qs.get("focus_file_id") || 0);
    const focusMs = Number(qs.get("focus_ms") || 0);
    const focusPage = Number(qs.get("focus_page") || 0);
    if (!Number.isFinite(fid) || fid <= 0) return;
    const exists = kbFiles.some((f) => Number(f.id) === fid);
    if (!exists) return;
    setKbFilter({ kind: "all" });
    setKbSearchResults([fid]);
    setSelectedFileIds([fid]);
    setFocusedRowId(fid);
    setPreviewInlineUrl(null);
    setPreviewDownloadUrl(null);
    setPreviewFileId(fid);
    setPreviewStartMs(Number.isFinite(focusMs) && focusMs > 0 ? focusMs : null);
    setPreviewPage(Number.isFinite(focusPage) && focusPage > 0 ? focusPage : null);
    if (portalId) void loadPreviewUrls(fid);
    window.setTimeout(() => {
      rowRefs.current.get(fid)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
    setFocusApplied(true);
  }, [location.search, kbFiles, focusApplied]);

  const scheduleSearch = (nextQuery?: string) => {
    const q = (nextQuery ?? kbSearch).trim();
    if (!q) {
      if (searchTimerRef.current) {
        window.clearTimeout(searchTimerRef.current);
        searchTimerRef.current = null;
      }
      searchReqSeqRef.current += 1;
      setKbSearchResults(null);
      setKbSearchMatches([]);
      setKbSearchError("");
      return;
    }
    if (searchTimerRef.current) {
      window.clearTimeout(searchTimerRef.current);
      searchTimerRef.current = null;
    }
    searchTimerRef.current = window.setTimeout(() => {
      runFullTextSearch(q);
    }, 300);
  };

  const runFullTextSearch = async (queryOverride?: string) => {
    if (!portalId || !portalToken) return;
    const q = (queryOverride ?? kbSearch).trim();
    if (!q) {
      searchReqSeqRef.current += 1;
      setKbSearchResults(null);
      setKbSearchMatches([]);
      setKbSearchError("");
      return;
    }
    const reqSeq = ++searchReqSeqRef.current;
    setKbSearchLoading(true);
    setKbSearchError("");
    const scopeParams = new URLSearchParams();
    if (selectedFileIds.length > 0) {
      scopeParams.set("file_ids", selectedFileIds.join(","));
    } else {
      if (kbFilter.kind === "smart" && kbFilter.id) scopeParams.set("smart_folder_ids", String(kbFilter.id));
      if (kbFilter.kind === "topic" && kbFilter.id) scopeParams.set("topic_ids", String(kbFilter.id));
      if (folderIdsInScope) {
        const scopedFileIds = kbFiles
          .filter((file) => file.folder_id != null && folderIdsInScope.has(Number(file.folder_id)))
          .map((file) => file.id);
        if (scopedFileIds.length > 0) scopeParams.set("file_ids", scopedFileIds.join(","));
      }
    }
    const qs = scopeParams.toString();
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/search?q=${encodeURIComponent(q)}&limit=100${qs ? `&${qs}` : ""}`);
    const data = await res.json().catch(() => null);
    if (reqSeq !== searchReqSeqRef.current) return;
    setKbSearchLoading(false);
    if (!res.ok) {
      setKbSearchError(data?.error || data?.detail || "Ошибка поиска");
      setKbSearchResults([]);
      setKbSearchMatches([]);
      return;
    }
    const ids = Array.isArray(data?.file_ids) ? data.file_ids.map((x: any) => Number(x)).filter((x: number) => Number.isFinite(x)) : [];
    setKbSearchResults(ids);
    setKbSearchMatches(Array.isArray(data?.matches) ? data.matches : []);
  };

  const runSmartSearch = async () => {
    if (!portalId || !portalToken) return;
    const q = smartSearchQuery.trim();
    if (!q) return;
    setSmartSearchLoading(true);
    setSmartSearchError("");
    setSmartSearchAnswer("");
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Api-Schema": "v2" },
        body: JSON.stringify({
          query: q,
          scope: selectedFileIds.length > 0
            ? { file_ids: selectedFileIds }
            : {
              file_ids: folderIdsInScope
                ? kbFiles.filter((file) => file.folder_id != null && folderIdsInScope.has(Number(file.folder_id))).map((file) => file.id)
                : undefined,
              smart_folder_ids: kbFilter.kind === "smart" && kbFilter.id ? [Number(kbFilter.id)] : undefined,
              topic_ids: kbFilter.kind === "topic" && kbFilter.id ? [String(kbFilter.id)] : undefined,
            },
        }),
    });
    const data = await res.json().catch(() => null);
    setSmartSearchLoading(false);
    if (!res.ok) {
      setSmartSearchError(data?.error || data?.detail || "Ошибка умного поиска");
      return;
    }
    setSmartSearchAnswer(data?.data?.answer || data?.answer || "");
  };

  const toggleSmartSearch = () => {
    setSmartSearchOpen((prev) => {
      const next = !prev;
      if (next && !smartSearchQuery) setSmartSearchQuery(kbSearch.trim());
      return next;
    });
  };
  const selectKbFilter = (kind: Filter["kind"], id?: number | string) => {
    setKbFilter({ kind, id });
    if (kind === "folder" && id) setKbFolderFilter(String(id));
    if (kind !== "folder") setKbFolderFilter("all");
  };

  const loadPreviewUrls = async (fileId: number) => {
    if (!portalId) return;
    setPreviewLoading(true);
    try {
      const inlineRes = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/signed-url?inline=1`);
      const inlineData = await inlineRes.json().catch(() => null);
      setPreviewInlineUrl(inlineRes.ok && inlineData?.url ? String(inlineData.url) : null);
      const dlRes = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/signed-url?inline=0`);
      const dlData = await dlRes.json().catch(() => null);
      setPreviewDownloadUrl(dlRes.ok && dlData?.url ? String(dlData.url) : null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const openPreview = async (fileId: number, opts?: { page?: number | null; ms?: number | null }) => {
    setPreviewInlineUrl(null);
    setPreviewDownloadUrl(null);
    setPreviewFileId(fileId);
    setPreviewPage(opts?.page ?? null);
    setPreviewStartMs(opts?.ms ?? null);
    if (!portalId) return;
    const fileRec = kbFiles.find((x) => x.id === fileId);
    const sourceKind = (fileRec?.source_type || "").toLowerCase();
    const isExternal = ["youtube", "rutube", "vk"].includes(sourceKind) && !!(fileRec?.source_url || "").trim();
    if (isExternal) return;
    await loadPreviewUrls(fileId);
  };

  const openFolderDetails = (folderId: number) => {
    setSelectedFolderId(folderId);
    setDetailsTarget({ kind: "folder", id: folderId });
    setIsEditingAccess(false);
    setShowAdvancedAcl(false);
    setDetailsSaveMessage("");
  };

  const openFileDetails = (fileId: number) => {
    setFocusedRowId(fileId);
    setDetailsTarget({ kind: "file", id: fileId });
    setIsEditingAccess(false);
    setShowAdvancedAcl(false);
    setDetailsSaveMessage("");
  };

  const openAccessEditor = () => {
    if (!detailsTarget) return;
    setIsEditingAccess(true);
    setShowAdvancedAcl(false);
    setDetailsSaveMessage("");
    setAclDraft(detailsTarget.kind === "folder" ? selectedFolderAccess : selectedFileAccess);
  };

  const closeAccessEditor = () => {
    setIsEditingAccess(false);
    setShowAdvancedAcl(false);
    setDetailsSaveMessage("");
  };

  const createFolder = async () => {
    if (!portalId || !portalToken) return;
    const name = newFolderName.trim();
    if (!name) return;
    const parentId = kbFilter.kind === "folder" && kbFilter.id ? Number(kbFilter.id) : null;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_id: parentId }),
    });
    if (res.ok) {
      setNewFolderName("");
      await loadFolders();
      await loadAccessSummary();
    }
  };

  const onDragEnterFolder = (id: number) => setDragOverFolderId(id);
  const onDragLeaveFolder = (id: number) => setDragOverFolderId((prev) => (prev === id ? null : prev));

  const moveFilesToFolder = async (folderId: number | null, ids: number[]) => {
    if (!portalId || !portalToken || !ids.length) return;
    for (const fileId of ids) {
      await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_id: folderId }),
      });
    }
    await loadFiles();
    await loadFolders();
    await loadTopics();
    await loadAccessSummary();
  };

  const deleteFolder = async (folderId: number) => {
    if (!portalId || !portalToken) return;
    setDetailsSaveMessage("");
    const folder = kbFolders.find((item) => item.id === folderId) || null;
    const coverage = selectedFolderId === folderId ? selectedFolderClientCoverage : null;
    const hasClientExposure = (coverage?.open_all_clients || 0) > 0 || (coverage?.open_client_groups || 0) > 0;
    const hasReadyMaterials = (coverage?.total_ready_files || 0) > 0;
    const warning = hasClientExposure || hasReadyMaterials
      ? [
          `Удалить папку «${folder?.name || folderId}»?`,
          hasReadyMaterials ? `В ветке сейчас ${coverage?.total_ready_files || 0} готовых материалов.` : "",
          hasClientExposure
            ? `Часть материалов доступна клиентам: всем — ${coverage?.open_all_clients || 0}, клиентским группам — ${coverage?.open_client_groups || 0}.`
            : "",
          "Удаление сработает только если папка пуста. Если внутри есть файлы или подпапки, сервер заблокирует операцию.",
        ]
          .filter(Boolean)
          .join("\n")
      : `Удалить папку «${folder?.name || folderId}»?`;
    if (!window.confirm(warning)) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${folderId}`, { method: "DELETE" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setDetailsSaveMessage(String(data?.error || data?.detail || "Не удалось удалить папку."));
      return;
    }
    if (selectedFolderId === folderId) {
      setSelectedFolderId(null);
      setDetailsTarget(null);
      setIsEditingAccess(false);
    }
    await loadFolders();
    await loadFiles();
    await loadTopics();
    await loadAccessSummary();
  };

  const onDropToFolder = async (folderId: number | null, evt: React.DragEvent) => {
    evt.preventDefault();
    setDragOverFolderId(null);
    const ids: number[] = [];
    if (selectedFileIds.length) {
      ids.push(...selectedFileIds);
    } else {
      const payload = evt.dataTransfer.getData("text/plain");
      const parsed = Number(payload);
      if (Number.isFinite(parsed)) ids.push(parsed);
      else if (draggedFileId) ids.push(draggedFileId);
    }
    if (!ids.length) return;
    await moveFilesToFolder(folderId, ids);
  };

  const reindexFile = async (fileId: number) => {
    if (!portalId || !portalToken) return;
    await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/reindex`, { method: "POST" });
    await loadFiles();
  };

  const deleteFile = async (fileId: number) => {
    if (!portalId || !portalToken) return;
    await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}`, { method: "DELETE" });
    await loadFiles();
    await loadFolders();
    await loadTopics();
    await loadAccessSummary();
  };

  const bulkReindexFiles = async () => {
    for (const id of selectedFileIds) await reindexFile(id);
    setSelectedFileIds([]);
  };

  const bulkDeleteFiles = async () => {
    for (const id of selectedFileIds) await deleteFile(id);
    setSelectedFileIds([]);
  };

  const bulkMoveToFolder = async (evt: React.ChangeEvent<HTMLSelectElement>) => {
    const value = evt.target.value;
    const folderId = value === "root" ? null : Number(value);
    const targetFolder = folderId ? kbFolders.find((folder) => folder.id === folderId) || null : null;
    if (targetFolder && selectedFileIds.length > 0) {
      const targetClientMode = clientBadgeCategory(targetFolder.access_badges?.client);
      if (targetClientMode !== "closed") {
        const warning =
          targetClientMode === "all"
            ? `Переместить ${selectedFileIds.length} файлов в папку «${targetFolder.name}»?\n\nФайлы без собственных правил могут стать доступны всем клиентам через наследование папки.`
            : `Переместить ${selectedFileIds.length} файлов в папку «${targetFolder.name}»?\n\nФайлы без собственных правил могут стать доступны клиентским группам через наследование папки.`;
        if (!window.confirm(warning)) {
          evt.target.value = "";
          return;
        }
      }
    }
    await moveFilesToFolder(folderId, selectedFileIds);
    setSelectedFileIds([]);
    evt.target.value = "";
  };
  const openBulkAccessEditor = () => {
    setBulkAclDraft([]);
    setBulkAclMessage("");
    setBulkAccessOpen(true);
  };
  const saveBulkAcl = async () => {
    if (!portalId || !portalToken || selectedFileIds.length === 0) return;
    setBulkAclSaving(true);
    setBulkAclMessage("");
    const payload = { items: bulkAclDraft.map((item) => ({ ...item })) };
    try {
      for (const fileId of selectedFileIds) {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/access`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(String(data?.error || data?.detail || "bulk_acl_save_failed"));
      }
      if (detailsTarget?.kind === "file" && selectedFileIds.includes(detailsTarget.id)) {
        setSelectedFileAccess(payload.items);
      }
      setBulkAclMessage(`Права обновлены для файлов: ${selectedFileIds.length}`);
      setBulkAccessOpen(false);
    } catch (e: any) {
      setBulkAclMessage(String(e?.message || "Не удалось обновить права."));
    } finally {
      setBulkAclSaving(false);
    }
  };

  const openFilePicker = () => fileInputRef.current?.click();

  const uploadFiles = async (files: FileList | null) => {
    if (!portalId || !portalToken || !files || !files.length) return;
    setKbUploadMessage("Загрузка...");
    let okCount = 0;
    for (const f of Array.from(files)) {
      const form = new FormData();
      form.append("file", f);
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/upload`, {
        method: "POST",
        body: form,
      });
      if (res.ok) {
        okCount += 1;
        continue;
      }
      const data = await res.json().catch(() => null);
      setKbUploadMessage(data?.error || data?.detail || `Ошибка загрузки: ${f.name}`);
      await loadFiles();
      await loadFolders();
      await loadTopics();
      await loadAccessSummary();
      return;
    }
    setKbUploadMessage(okCount > 0 ? `Файлы загружены: ${okCount}` : "Ошибка загрузки");
    await loadFiles();
    await loadFolders();
    await loadTopics();
    await loadAccessSummary();
  };

  const onFilePickerChange = (evt: React.ChangeEvent<HTMLInputElement>) => {
    uploadFiles(evt.target.files);
    if (evt.target) evt.target.value = "";
  };

  const onDropFiles = (evt: React.DragEvent) => {
    evt.preventDefault();
    uploadFiles(evt.dataTransfer.files);
  };

  const toggleFileMenu = (fileId: number) => {
    setOpenFileMenuId((prev) => (prev === fileId ? null : fileId));
  };

  const closeFileMenu = () => {
    setOpenFileMenuId(null);
    setContextMenu(null);
  };

  const createSmartFolderFromTopic = async (topicId: string, name: string) => {
    if (!portalId || !portalToken) return;
    const normalized = name.trim().toLowerCase();
    if (kbSmartFolders.some((s) => (s.name || "").trim().toLowerCase() === normalized)) {
      setSmartFolderMessage("Умная папка с таким названием уже есть.");
      return;
    }
    await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/smart-folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, rules: { topic_id: topicId } }),
    });
    await loadSmartFolders();
    await loadTopics();
    setSmartFolderMessage("Умная папка создана.");
  };

  const deleteSmartFolder = async (folderId: number) => {
    if (!portalId || !portalToken) return;
    setSmartFolderMessage("");
    await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/smart-folders/${folderId}`, {
      method: "DELETE",
    });
    await loadSmartFolders();
    await loadTopics();
  };

  const smartFolderNameSet = useMemo(() => {
    return new Set(kbSmartFolders.map((s) => (s.name || "").trim().toLowerCase()));
  }, [kbSmartFolders]);
  const uiFallbackSuggestions = useMemo(() => {
    const byTopic = SYSTEM_TOPIC_HINTS.map((t) => {
      const count = kbFiles.reduce((acc, f) => {
        const hay = `${f.filename || ""} ${f.source_type || ""}`.toLowerCase();
        return acc + (t.keywords.some((k) => hay.includes(k)) ? 1 : 0);
      }, 0);
      return { id: t.id, name: t.name, count };
    })
      .filter((x) => x.count > 0)
      .sort((a, b) => b.count - a.count);
    const minCount = Math.max(1, Number(kbTopicsThreshold || 1));
    const topicSuggestions = byTopic
      .filter((s) => s.count >= minCount)
      .filter((s) => isTwoPartTopicName(s.name))
      .filter((s) => !smartFolderNameSet.has((s.name || "").trim().toLowerCase()));
    const stop = new Set([
      "серия", "сезон", "часть", "video", "audio", "file", "doc", "docx", "pdf", "xlsx", "xls", "mp3", "mp4", "ogg",
      "youtube", "rutube", "vk", "all", "new",
    ]);
    const tokenToFiles = new Map<string, Set<number>>();
    for (const f of kbFiles) {
      const text = `${f.filename || ""} ${f.source_type || ""}`.toLowerCase();
      const tokens = Array.from(new Set((text.match(/[a-zA-Zа-яА-ЯёЁ0-9]{4,}/g) || [])));
      for (const token of tokens) {
        if (stop.has(token) || /^\d+$/.test(token)) continue;
        if (!tokenToFiles.has(token)) tokenToFiles.set(token, new Set<number>());
        tokenToFiles.get(token)!.add(Number(f.id));
      }
    }
    const tokenSuggestions = Array.from(tokenToFiles.entries())
      .map(([token, ids]) => ({ id: `ui:auto:${token}`, name: token.charAt(0).toUpperCase() + token.slice(1), count: ids.size }))
      .filter((x) => x.count >= minCount && isTwoPartTopicName(x.name) && !smartFolderNameSet.has((x.name || "").trim().toLowerCase()))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
      .slice(0, 8);
    const seen = new Set<string>();
    const merged = [...topicSuggestions, ...tokenSuggestions].filter((x) => {
      const k = (x.name || "").trim().toLowerCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    });
    return merged.slice(0, 8);
  }, [kbFiles, smartFolderNameSet, kbTopicsThreshold]);
  const visibleSuggestions = useMemo(() => {
    const real = kbTopicSuggestions.filter((s) => !smartFolderNameSet.has((s.name || "").trim().toLowerCase()));
    if (real.length > 0) return real;
    return uiFallbackSuggestions;
  }, [kbTopicSuggestions, smartFolderNameSet, uiFallbackSuggestions]);

  const renderFolderTree = (parentId: number | null = null, depth = 0): ReactNode => {
    const folders = folderChildrenMap.get(parentId) || [];
    return folders.map((folder) => (
      <div key={folder.id}>
        <button
          className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm ${
            kbFilter.kind === "folder" && kbFilter.id === folder.id
              ? "bg-sky-50 text-sky-700"
              : "text-slate-600 hover:bg-slate-50"
          } ${dragOverFolderId === folder.id ? "ring-2 ring-sky-200" : ""}`}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          onClick={() => {
            selectKbFilter("folder", folder.id);
            openFolderDetails(folder.id);
          }}
          onDragEnter={() => onDragEnterFolder(folder.id)}
          onDragLeave={() => onDragLeaveFolder(folder.id)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => onDropToFolder(folder.id, e)}
        >
          <div className="min-w-0">
            <div className="truncate">{folder.name}</div>
            <div className="mt-1">{renderCompactAccessBadges(folder)}</div>
          </div>
          <span className="ml-3 shrink-0 text-xs text-slate-400">{folderFileCounts.get(folder.id) || 0}</span>
        </button>
        {renderFolderTree(folder.id, depth + 1)}
      </div>
    ));
  };

  const renderAclSummary = (items: KbAclItem[], emptyText: string) => {
    if (!items.length) return <div className="text-sm text-slate-500">{emptyText}</div>;
    return (
      <div className="space-y-2">
        {items.map((item) => (
          <div key={`${item.principal_type}:${item.principal_id}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="text-sm font-medium text-slate-800">{kbPrincipalLabel(item, accountUsers, accountGroups)}</div>
            <div className="mt-1 text-xs text-slate-500">{kbAccessLabel(item.access_level)}</div>
          </div>
        ))}
      </div>
    );
  };

  const applyAclTemplate = (
    template: "inherit" | "staff" | "clients" | "staff_clients" | "group" | "client_group",
    groupIdOverride?: number,
  ) => {
    const groupId =
      groupIdOverride ??
      (template === "client_group" ? templateClientGroupId : template === "group" ? templateStaffGroupId : 0);
    setAclDraft(kbAclTemplate(template, { groupId }));
  };
  const applyBulkAclTemplate = (
    template: "inherit" | "staff" | "clients" | "staff_clients" | "group" | "client_group",
    groupIdOverride?: number,
  ) => {
    const groupId =
      groupIdOverride ??
      (template === "client_group" ? templateClientGroupId : template === "group" ? templateStaffGroupId : 0);
    setBulkAclDraft(kbAclTemplate(template, { groupId }));
  };

  const updateAclDraftItem = (index: number, patch: Partial<KbAclDraftItem>) => {
      setAclDraft((prev) =>
        prev.map((item, itemIndex) => {
          if (itemIndex !== index) return item;
          const next = { ...item, ...patch };
        if (patch.principal_type === "role" && !["owner", "admin", "member", "client"].includes(next.principal_id)) {
          next.principal_id = "member";
        }
        if (patch.principal_type === "audience" && !["staff", "client"].includes(next.principal_id)) {
          next.principal_id = "staff";
        }
          if (patch.principal_type === "membership" && !next.principal_id) {
            next.principal_id = String(accountUsers[0]?.membership_id || "");
          }
          if (patch.principal_type === "group" && !next.principal_id) {
            next.principal_id = String(accountGroups[0]?.id || "");
          }
          return next;
        }),
      );
    };

  const addAclDraftItem = () => {
      const defaultPrincipalType = accountGroups.length > 0 ? "group" : accountUsers.length > 0 ? "membership" : "role";
      const defaultPrincipalId =
        defaultPrincipalType === "group"
          ? String(accountGroups[0]?.id || "")
          : defaultPrincipalType === "membership"
            ? String(accountUsers[0]?.membership_id || "")
            : "member";
      setAclDraft((prev) => [
        ...prev,
        {
          principal_type: defaultPrincipalType,
          principal_id: defaultPrincipalId,
          access_level: "read",
        },
      ]);
    };
  const updateBulkAclDraftItem = (index: number, patch: Partial<KbAclDraftItem>) => {
    setBulkAclDraft((prev) =>
      prev.map((item, itemIndex) => {
        if (itemIndex !== index) return item;
        const next = { ...item, ...patch };
        if (patch.principal_type === "role" && !["owner", "admin", "member", "client"].includes(next.principal_id)) next.principal_id = "member";
        if (patch.principal_type === "audience" && !["staff", "client"].includes(next.principal_id)) next.principal_id = "staff";
        if (patch.principal_type === "membership" && !next.principal_id) next.principal_id = String(accountUsers[0]?.membership_id || "");
        if (patch.principal_type === "group" && !next.principal_id) next.principal_id = String(accountGroups[0]?.id || "");
        return next;
      }),
    );
  };
  const addBulkAclDraftItem = () => {
    const defaultPrincipalType = accountGroups.length > 0 ? "group" : accountUsers.length > 0 ? "membership" : "role";
    const defaultPrincipalId =
      defaultPrincipalType === "group"
        ? String(accountGroups[0]?.id || "")
        : defaultPrincipalType === "membership"
          ? String(accountUsers[0]?.membership_id || "")
          : "member";
    setBulkAclDraft((prev) => [...prev, { principal_type: defaultPrincipalType, principal_id: defaultPrincipalId, access_level: "read" }]);
  };
  const removeBulkAclDraftItem = (index: number) => {
    setBulkAclDraft((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  const removeAclDraftItem = (index: number) => {
    setAclDraft((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  const saveAclDraft = async () => {
    if (!portalId || !portalToken || !detailsTarget) return;
    setDetailsSaving(true);
    setDetailsSaveMessage("");
    try {
      const payload = { items: aclDraft.map((item) => ({ ...item })) };
      const url =
        detailsTarget.kind === "folder"
          ? `/api/v1/bitrix/portals/${portalId}/kb/folders/${detailsTarget.id}/access`
          : `/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access`;
      const res = await fetchPortal(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(String(data?.error || data?.detail || "acl_save_failed"));
      setDetailsSaveMessage("Доступ сохранён.");
      setIsEditingAccess(false);
      if (detailsTarget.kind === "folder") {
        setSelectedFolderAccess(Array.isArray(data?.items) ? data.items : []);
      } else {
        setSelectedFileAccess(Array.isArray(data?.items) ? data.items : []);
        const [staffRes, clientRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access/effective?role=member&audience=staff`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access/effective?role=client&audience=client`),
        ]);
        const staffData = await staffRes.json().catch(() => null);
        const clientData = await clientRes.json().catch(() => null);
        setSelectedFileEffectiveStaff(String(staffData?.effective_access || "read"));
        setSelectedFileEffectiveClient(String(clientData?.effective_access || "none"));
      }
      await loadAccessSummary();
    } catch (e: any) {
      setDetailsSaveMessage(String(e?.message || "acl_save_failed"));
    } finally {
      setDetailsSaving(false);
    }
  };

  useEffect(() => {
    const loadDetails = async () => {
      if (!portalId || !portalToken || !detailsTarget) return;
      setDetailsLoading(true);
      setDetailsError("");
      try {
        if (detailsTarget.kind === "folder") {
          const [accessRes, summaryRes] = await Promise.all([
            fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${detailsTarget.id}/access`),
            fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary?folder_id=${detailsTarget.id}`),
          ]);
          const data = await accessRes.json().catch(() => null);
          const summaryData = await summaryRes.json().catch(() => null);
          if (!accessRes.ok) throw new Error(String(data?.error || data?.detail || "folder_access_load_failed"));
          const items = Array.isArray(data?.items) ? data.items : [];
          setSelectedFolderAccess(items);
          setAclDraft(items);
          setSelectedFolderClientCoverage({
            total_ready_files: Number(summaryData?.total_ready_files || 0),
            open_all_clients: Number(summaryData?.open_all_clients || 0),
            open_client_groups: Number(summaryData?.open_client_groups || 0),
            closed_for_clients: Number(summaryData?.closed_for_clients || 0),
          });
          setSelectedFileAccess([]);
          setSelectedFileEffectiveStaff("read");
          setSelectedFileEffectiveClient("none");
          return;
        }
        const [accessRes, staffRes, clientRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access/effective?role=member&audience=staff`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${detailsTarget.id}/access/effective?role=client&audience=client`),
        ]);
        const accessData = await accessRes.json().catch(() => null);
        const staffData = await staffRes.json().catch(() => null);
        const clientData = await clientRes.json().catch(() => null);
        if (!accessRes.ok) throw new Error(String(accessData?.error || accessData?.detail || "file_access_load_failed"));
        const items = Array.isArray(accessData?.items) ? accessData.items : [];
        setSelectedFileAccess(items);
        setAclDraft(items);
        setSelectedFolderClientCoverage({ total_ready_files: 0, open_all_clients: 0, open_client_groups: 0, closed_for_clients: 0 });
        setSelectedFileEffectiveStaff(String(staffData?.effective_access || "read"));
        setSelectedFileEffectiveClient(String(clientData?.effective_access || "none"));
        setSelectedFolderAccess([]);
      } catch (e: any) {
        setDetailsError(String(e?.message || "details_load_failed"));
      } finally {
        setDetailsLoading(false);
      }
    };
    void loadDetails();
  }, [portalId, portalToken, detailsTarget]);

  return (
    <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
      <aside className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">Структура</div>
        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onFilePickerChange} />
        <div
          className="mt-4 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-center cursor-pointer"
          onClick={openFilePicker}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDropFiles}
        >
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-sky-100 text-sky-600 text-xl">+</div>
          <div className="text-sm font-semibold text-slate-700">Добавить файлы</div>
          <div className="text-xs text-slate-500 mt-1">Перетащите сюда или нажмите</div>
        </div>
        {kbUploadMessage && <div className="mt-2 text-xs text-slate-500">{kbUploadMessage}</div>}

        <button
          className={`mt-4 w-full rounded-xl px-3 py-2 text-sm ${
            kbFilter.kind === "all" ? "bg-sky-50 text-sky-700" : "bg-slate-50 text-slate-600"
          } ${dragOverFolderId === 0 ? "ring-2 ring-sky-200" : ""}`}
          onClick={() => selectKbFilter("all")}
          onDragEnter={() => onDragEnterFolder(0)}
          onDragLeave={() => onDragLeaveFolder(0)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => onDropToFolder(null, e)}
        >
          Все файлы
        </button>

        <div className="mt-5">
          <div className="text-xs uppercase tracking-wide text-slate-400">Папки</div>
          <div className="mt-2 space-y-1">
            {renderFolderTree()}
            {kbFolders.length === 0 && <div className="text-xs text-slate-400">Папок пока нет.</div>}
          </div>
          <div className="mt-3 space-y-2">
            <input
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="Новая папка"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
            />
            <button className="w-full rounded-xl bg-sky-600 px-3 py-2 text-sm font-semibold text-white" onClick={createFolder}>
              {selectedFolderName ? `Создать в «${selectedFolderName}»` : "Создать в корне"}
            </button>
            <div className="text-xs text-slate-400">Если папка выбрана слева, новая папка создаётся внутри неё.</div>
          </div>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-xs uppercase tracking-wide text-slate-400">
            <span>Умные папки</span>
            <button className="text-xs text-sky-600" onClick={() => setSmartFoldersOpen((prev) => !prev)}>
              {smartFoldersOpen ? "Свернуть" : "Показать"}
            </button>
          </div>
          {smartFoldersOpen && (
            <div className="mt-2 space-y-1">
              {kbSmartFolders.map((s) => (
                <button
                  key={s.id}
                  className={`w-full flex items-center justify-between rounded-xl px-3 py-2 text-sm ${kbFilter.kind === "smart" && kbFilter.id === s.id ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
                  onClick={() => selectKbFilter("smart", s.id)}
                >
                  <span>{s.name}</span>
                  <span
                    className="rounded-lg border border-slate-200 px-2 py-0.5 text-[10px] text-slate-500 hover:bg-slate-50"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSmartFolder(s.id);
                    }}
                  >
                    Удалить
                  </span>
                </button>
              ))}
              {kbSmartFolders.length === 0 && <div className="text-xs text-slate-400">Умных папок пока нет.</div>}
              {smartFolderMessage && <div className="text-xs text-slate-500">{smartFolderMessage}</div>}
              {visibleSuggestions.length > 0 && (
                <div className="mt-2 rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Рекомендации</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {visibleSuggestions.map((s) => (
                      <button
                        key={s.id}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600"
                        onClick={() => createSmartFolderFromTopic(s.id, s.name)}
                      >
                        + «{s.name}»
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {visibleSuggestions.length === 0 && (
                <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                  <div className="font-semibold">Диагностика тем</div>
                  <div className="mt-1">Порог: {kbTopicsThreshold}. Рекомендации пустые.</div>
                  <div className="mt-1">Темы и count: {kbTopics.length ? kbTopics.map((t) => `${t.name}=${t.count}`).join(", ") : "—"}</div>
                  {kbTopicsLoadError && <div className="mt-1 text-rose-600">Ошибка загрузки тем: {kbTopicsLoadError}</div>}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      <section className="space-y-6" onClick={closeFileMenu}>
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">{coreModuleLabel("kb", "База знаний")}</h2>
          <p className="text-sm text-slate-500 mt-1">{coreModuleDescription("kb", "Управляйте документами и доступами в едином пространстве.")}</p>
          <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">Покрытие клиентского бота</div>
                <p className="mt-1 text-xs text-slate-600">
                  Сводка считает готовые материалы базы знаний и показывает, какие из них доступны всем клиентам, только
                  клиентским группам или полностью закрыты для клиентского бота.
                </p>
              </div>
              <a href="/app/users" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50">
                Пользователи и доступы
              </a>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
                <div className="text-[11px] uppercase tracking-wide text-slate-400">Готовые материалы</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{kbAccessSummary.total_ready_files}</div>
                <div className="mt-1 text-xs text-slate-500">Все файлы со статусом `ready`.</div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
                <div className="text-[11px] uppercase tracking-wide text-slate-400">Всем клиентам</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{kbAccessSummary.open_all_clients}</div>
                <div className="mt-1 text-xs text-slate-500">Клиентский бот отвечает по этим материалам без привязки к группе.</div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
                <div className="text-[11px] uppercase tracking-wide text-slate-400">Клиентским группам</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{kbAccessSummary.open_client_groups}</div>
                <div className="mt-1 text-xs text-slate-500">Материалы видны только выбранным клиентским группам.</div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
                <div className="text-[11px] uppercase tracking-wide text-slate-400">Закрыты для клиентов</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{kbAccessSummary.closed_for_clients}</div>
                <div className="mt-1 text-xs text-slate-500">Эти материалы не попадут в ответы клиентского бота.</div>
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <div className="flex-1 min-w-[240px]">
              <input
                value={kbSearch}
                onChange={(e) => {
                  const next = e.target.value;
                  setKbSearch(next);
                  scheduleSearch(next);
                }}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                placeholder="Поиск по базе знаний"
              />
            </div>
            <button className="rounded-xl border border-slate-200 px-4 py-2 text-sm" onClick={toggleSmartSearch}>
              Умный поиск
            </button>
          </div>
          <div className="mt-2 min-h-[18px] text-xs">
            {kbSearchLoading && <div className="text-slate-500">Ищем…</div>}
            {!kbSearchLoading && selectedFileIds.length > 0 && (
              <div className="text-sky-700">Поиск ограничен выбранными файлами: {selectedFileIds.length}</div>
            )}
            {!kbSearchLoading && kbSearchError && <div className="text-rose-500">{kbSearchError}</div>}
            {!kbSearchLoading && !kbSearchError && kbSearchResults !== null && (
              <div className="text-slate-500">Найдено: {kbSearchResults.length}</div>
            )}
          </div>
          <div className={`overflow-hidden transition-all duration-200 ${kbSearchMatches.length > 0 ? "max-h-[420px] opacity-100" : "max-h-0 opacity-0"}`}>
            {kbSearchMatches.length > 0 && (
              <details className="mt-1" open={!smartSearchOpen}>
                <summary className="cursor-pointer text-xs text-slate-500">
                  Найденные фрагменты ({kbSearchMatches.length})
                </summary>
                <div className="mt-2 grid gap-2">
                  {kbSearchMatches.slice(0, 8).map((m, idx) => (
                    <button
                      key={`${m.file_id}:${m.chunk_index ?? idx}`}
                      type="button"
                      className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-left hover:bg-slate-100"
                      onClick={() => {
                        setKbSearchResults([m.file_id]);
                        void openPreview(m.file_id, {
                          page: m.page_num ?? null,
                          ms: m.start_ms ?? null,
                        });
                      }}
                    >
                      <div className="text-sm text-slate-700">{m.filename}</div>
                      {m.snippet && <div className="mt-1 text-xs text-slate-500">{m.snippet}</div>}
                    </button>
                  ))}
                </div>
              </details>
            )}
          </div>
        </div>

        {smartSearchOpen && (
          <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">Умный поиск</div>
            <div className="mt-3 flex flex-wrap gap-3">
              <input
                className="flex-1 min-w-[240px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                placeholder="Например: какие есть тарифы?"
                value={smartSearchQuery}
                onChange={(e) => setSmartSearchQuery(e.target.value)}
              />
              <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white" onClick={runSmartSearch}>
                {smartSearchLoading ? "Ищу..." : "Спросить"}
              </button>
            </div>
            {smartSearchError && <div className="mt-2 text-xs text-rose-500">{smartSearchError}</div>}
            {smartSearchAnswer && <div className="mt-3 text-sm text-slate-700 whitespace-pre-line">{smartSearchAnswer}</div>}
          </div>
        )}

        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbTypeFilter} onChange={(e) => setKbTypeFilter(e.target.value)}>
              <option value="all">Тип: все</option>
              {kbTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbPeopleFilter} onChange={(e) => setKbPeopleFilter(e.target.value)}>
              <option value="all">Люди: все</option>
              {kbPeopleOptions.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbFolderFilter} onChange={(e) => setKbFolderFilter(e.target.value)}>
              <option value="all">Местоположение: все</option>
              {kbFolders.map((folder) => <option key={folder.id} value={String(folder.id)}>{folder.name}</option>)}
            </select>
            <select className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSort} onChange={(e) => setKbSort(e.target.value as any)}>
              <option value="new">Сначала новые</option>
              <option value="name">По имени</option>
              <option value="status">По статусу</option>
            </select>
            <div className="ml-auto flex items-center gap-2">
              <button className={`rounded-xl px-3 py-2 text-sm ${kbViewMode === "table" ? "bg-sky-600 text-white" : "border border-slate-200"}`} onClick={() => setKbViewMode("table")}>Таблица</button>
              <button className={`rounded-xl px-3 py-2 text-sm ${kbViewMode === "grid" ? "bg-sky-600 text-white" : "border border-slate-200"}`} onClick={() => setKbViewMode("grid")}>Плитки</button>
            </div>
          </div>
        </div>

        {false && (
          <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-900">Рекомендуемые файлы</div>
            </div>
            <div className="mt-3 grid gap-2">
              {recommendedKbFiles.length === 0 && <div className="text-sm text-slate-500">Рекомендаций пока нет.</div>}
              {recommendedKbFiles.map((f) => (
                <div key={f.id} className="grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-3 text-sm text-slate-700">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs text-white" style={{ backgroundColor: fileTypeIcon(f.filename, f.mime_type, f.source_type).color }}>{fileTypeIcon(f.filename, f.mime_type, f.source_type).label}</span>
                    {f.filename}
                  </div>
                  <div>{(f.query_count || 0) > 0 ? `${f.query_count} запросов` : "Новый файл"}</div>
                  <div>{fileOwnerLabel(f)}</div>
                  <div>{f.folder_id ? folderNameMap.get(Number(f.folder_id)) || "Корень" : "Корень"}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="h-[56px]">
            <div className="flex h-full items-center rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-sm">
              {selectedFileIds.length > 0 ? (
                  <div className="flex min-w-0 flex-nowrap items-center gap-2">
                    <div className="shrink-0">Выбрано: {selectedFileIds.length}</div>
                    <select className="shrink-0 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" onChange={bulkMoveToFolder}>
                      <option value="">Переместить в папку</option>
                      <option value="root">В корень</option>
                      {kbFolders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
                    </select>
                    <button className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm" onClick={openBulkAccessEditor}>Доступ</button>
                    <button className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm" onClick={bulkReindexFiles}>Переиндексировать</button>
                    <button className="shrink-0 rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-600" onClick={bulkDeleteFiles}>Удалить</button>
                    <button className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm" onClick={() => setSelectedFileIds([])}>Снять выделение</button>
                  </div>
                ) : (
                <div className="text-sm font-semibold text-slate-900">Файлы</div>
              )}
            </div>
          </div>
          {bulkAccessOpen && selectedFileIds.length > 0 && (
            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Массовое изменение доступа</div>
                  <div className="mt-1 text-xs text-slate-500">Изменения применятся ко всем выбранным файлам: {selectedFileIds.length}</div>
                </div>
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600" onClick={() => setBulkAccessOpen(false)}>Закрыть</button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("inherit")}>Наследовать от папки</button>
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("staff")}>Общие материалы</button>
                    {staffGroups.length > 0 && (
                      <>
                        <select
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                          value={String(templateStaffGroupId || staffGroups[0]?.id || "")}
                          onChange={(e) => setTemplateStaffGroupId(Number(e.target.value) || 0)}
                        >
                          {staffGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                        </select>
                        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("group", templateStaffGroupId || staffGroups[0]?.id || 0)}>Отдел / группа</button>
                      </>
                    )}
                    {clientGroups.length > 0 && (
                      <>
                        <select
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                          value={String(templateClientGroupId || clientGroups[0]?.id || "")}
                          onChange={(e) => setTemplateClientGroupId(Number(e.target.value) || 0)}
                        >
                          {clientGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                        </select>
                        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("client_group", templateClientGroupId || clientGroups[0]?.id || 0)}>Клиенты / группа</button>
                      </>
                    )}
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("clients")}>Только клиенты</button>
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyBulkAclTemplate("staff_clients")}>Сотрудники и клиенты</button>
              </div>
              <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <div className="font-semibold">Предварительное влияние на клиентский бот</div>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <div className="rounded-xl bg-white/70 px-3 py-2">
                    <div className="font-medium">Сейчас</div>
                    <div className="mt-1 text-amber-800">
                      Всем клиентам: {bulkClientImpact.before.all} · Группам: {bulkClientImpact.before.groups} · Закрыто: {bulkClientImpact.before.closed}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white/70 px-3 py-2">
                    <div className="font-medium">После сохранения</div>
                    <div className="mt-1 text-amber-800">
                      Всем клиентам: {bulkClientImpact.after.all} · Группам: {bulkClientImpact.after.groups} · Закрыто: {bulkClientImpact.after.closed}
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-amber-800">
                  Откроется всем клиентам: {bulkClientImpact.opensToAll} · Откроется клиентским группам: {bulkClientImpact.opensToGroups} · Закроется для клиентов: {bulkClientImpact.closesForClients}
                </div>
              </div>
              <div className="mt-3 space-y-2">
                {bulkAclDraft.map((item, index) => (
                  <div key={`${item.principal_type}:${item.principal_id}:${index}`} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
                    <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_type} onChange={(e) => updateBulkAclDraftItem(index, { principal_type: e.target.value, principal_id: e.target.value === "audience" ? "staff" : e.target.value === "membership" ? String(accountUsers[0]?.membership_id || "") : e.target.value === "group" ? String(accountGroups[0]?.id || "") : "member" })}>
                      <option value="role">Роль</option>
                      <option value="audience">Аудитория</option>
                      {accountGroups.length > 0 && <option value="group">Группа</option>}
                      {accountUsers.length > 0 && <option value="membership">Конкретный пользователь</option>}
                    </select>
                    <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_id} onChange={(e) => updateBulkAclDraftItem(index, { principal_id: e.target.value })}>
                      {item.principal_type === "audience" ? (
                        <>
                          <option value="staff">{audienceOptionLabel("staff")}</option>
                          <option value="client">{audienceOptionLabel("client")}</option>
                        </>
                      ) : item.principal_type === "group" ? (
                        <>
                          {accountGroups.map((group) => <option key={group.id} value={String(group.id)}>{group.name}</option>)}
                        </>
                      ) : item.principal_type === "membership" ? (
                        <>
                          {accountUsers.map((user) => <option key={user.membership_id} value={String(user.membership_id)}>{user.display_name}</option>)}
                        </>
                      ) : (
                        <>
                          <option value="owner">{roleOptionLabel("owner")}</option>
                          <option value="admin">{roleOptionLabel("admin")}</option>
                          <option value="member">{roleOptionLabel("member")}</option>
                          <option value="client">{roleOptionLabel("client")}</option>
                        </>
                      )}
                    </select>
                    <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.access_level} onChange={(e) => updateBulkAclDraftItem(index, { access_level: e.target.value })}>
                      <option value="none">Нет доступа</option>
                      <option value="read">Чтение</option>
                      <option value="write">Редактирование</option>
                      <option value="admin">Администрирование</option>
                    </select>
                    <button className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs text-rose-600" onClick={() => removeBulkAclDraftItem(index)}>Убрать</button>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" onClick={addBulkAclDraftItem}>Добавить правило</button>
                <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-semibold text-white" onClick={saveBulkAcl}>
                  {bulkAclSaving ? "Сохраняем..." : "Применить ко всем"}
                </button>
                {bulkAclMessage && <div className="self-center text-xs text-slate-500">{bulkAclMessage}</div>}
              </div>
            </div>
          )}

          {kbViewMode === "table" && (
            <div className="mt-4 rounded-xl border border-slate-100" onMouseDown={startDragSelect}>
              <div
                ref={tableRef}
                className="relative max-h-[520px] overflow-auto outline-none"
                tabIndex={0}
                onKeyDown={handleTableKey}
                onClick={(e) => {
                  const target = e.target as HTMLElement;
                  const isInteractive = !!target.closest("button, input, select, a, textarea");
                  if (!isInteractive) {
                    tableRef.current?.focus({ preventScroll: true });
                  }
                  if (!(e.target as HTMLElement).closest("[data-row='kb']")) {
                    setSelectedFileIds([]);
                    setFocusedRowId(null);
                  }
                }}
              >
                <div className="sticky top-0 z-10 grid grid-cols-[1.6fr_1fr_1fr_1fr_120px] gap-3 border-b border-slate-100 bg-white px-3 py-2 text-[11px] uppercase tracking-wide text-slate-400">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAllVisible} />
                    Название
                  </label>
                  <div>Владелец</div>
                  <div>Папка</div>
                  <div>Статус</div>
                  <div className="text-right">Действия</div>
                </div>
                {sortedKbFiles.map((f) => (
                  <div
                    key={f.id}
                    draggable
                    onDragStart={(e) => {
                      setDraggedFileId(f.id);
                      e.dataTransfer.setData("text/plain", String(f.id));
                    }}
                    onDragEnd={() => setDraggedFileId(null)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setContextMenu({ id: f.id, x: e.clientX, y: e.clientY });
                    }}
                    ref={(node) => rowRefs.current.set(f.id, node)}
                    className={`group grid grid-cols-[1.6fr_1fr_1fr_1fr_120px] gap-3 items-center border-b border-slate-100 px-3 py-2.5 text-sm hover:bg-slate-50 ${
                      focusedRowId === f.id ? "bg-slate-50 ring-1 ring-sky-200" : ""
                    }`}
                    data-row="kb"
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest("button") || (e.target as HTMLElement).closest("input")) return;
                      openFileDetails(f.id);
                      if (e.shiftKey && lastSelectedId) {
                        selectRange(lastSelectedId, f.id);
                      }
                    }}
                  >
                    <label className="flex items-center gap-2 min-w-0">
                      <input
                        type="checkbox"
                        checked={selectedFileIds.includes(f.id)}
                        onChange={(e) => handleRowSelect(f.id, e)}
                        className={`transition-opacity ${selectedFileIds.includes(f.id) ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                      />
                      <span
                        className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[10px] font-semibold text-white"
                        style={{ backgroundColor: fileTypeIcon(f.filename, f.mime_type, f.source_type).color }}
                      >
                        {fileTypeIcon(f.filename, f.mime_type, f.source_type).label}
                      </span>
                      <button
                        type="button"
                        className="truncate text-left text-slate-800 underline decoration-transparent transition hover:decoration-slate-400"
                        title={f.filename}
                        onClick={(e) => {
                          e.stopPropagation();
                          void openPreview(f.id);
                        }}
                        >
                          {f.filename}
                        </button>
                      <div className="min-w-0">{renderAccessBadges(f)}</div>
                    </label>
                    <div className="truncate text-slate-600">{fileOwnerLabel(f)}</div>
                    <div className="truncate text-slate-600">{f.folder_id ? folderNameMap.get(Number(f.folder_id)) || "Корень" : "Корень"}</div>
                    <div className="text-[11px] rounded-full px-2 py-0.5 bg-slate-100 text-slate-600 w-fit">{fileStatusLabel(f.status)}</div>
                    <div className="relative flex items-center justify-end gap-2">
                      <button
                        className="opacity-0 group-hover:opacity-100 text-xs text-slate-500 hover:text-slate-900"
                        title="Переместить"
                        onClick={(e) => {
                          e.stopPropagation();
                          openFileDetails(f.id);
                        }}
                      >
                        Переместить
                      </button>
                      <button
                        className="opacity-0 group-hover:opacity-100 text-xs text-rose-500 hover:text-rose-700"
                        title="Удалить"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteFile(f.id);
                        }}
                      >
                        Удалить
                      </button>
                      <button
                        className="text-slate-400 opacity-0 group-hover:opacity-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          openFileDetails(f.id);
                          toggleFileMenu(f.id);
                        }}
                      >
                        ⋮
                      </button>
                      {openFileMenuId === f.id && (
                        <div className="absolute right-0 top-6 z-20 w-44 rounded-xl border border-slate-200 bg-white shadow-lg">
                          <button className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => reindexFile(f.id)}>Переиндексировать</button>
                          <button className="block w-full px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50" onClick={() => deleteFile(f.id)}>Удалить</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {sortedKbFiles.length === 0 && <div className="px-3 py-4 text-sm text-slate-500">Файлов пока нет.</div>}
                {dragSelectBox && (
                  <div
                    className="pointer-events-none absolute top-0 left-0 border border-sky-300 bg-sky-100/30"
                    style={{
                      left: Math.min(dragSelectBox.x, dragSelectBox.x + dragSelectBox.w),
                      top: Math.min(dragSelectBox.y, dragSelectBox.y + dragSelectBox.h),
                      width: Math.abs(dragSelectBox.w),
                      height: Math.abs(dragSelectBox.h),
                    }}
                  />
                )}
              </div>
            </div>
          )}

          {kbViewMode === "grid" && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {sortedKbFiles.map((f) => (
                <div
                  key={f.id}
                  draggable
                  onDragStart={(e) => {
                    setDraggedFileId(f.id);
                    e.dataTransfer.setData("text/plain", String(f.id));
                  }}
                  onDragEnd={() => setDraggedFileId(null)}
                  className="rounded-2xl border border-slate-100 p-4 hover:bg-slate-50"
                >
                  <div className="flex items-center justify-between">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-xs text-white" style={{ backgroundColor: fileTypeIcon(f.filename, f.mime_type, f.source_type).color }}>{fileTypeIcon(f.filename, f.mime_type, f.source_type).label}</span>
                    <button className="text-slate-400" onClick={(e) => { e.stopPropagation(); openFileDetails(f.id); toggleFileMenu(f.id); }}>⋮</button>
                  </div>
                  <button
                    type="button"
                    className="mt-3 block text-left text-sm font-semibold text-slate-900 underline decoration-transparent transition hover:decoration-slate-400"
                    onClick={() => {
                      void openPreview(f.id);
                    }}
                  >
                    {f.filename}
                  </button>
                  {renderAccessBadges(f)}
                  <div className="mt-1 text-xs text-slate-500">{fileOwnerLabel(f)}</div>
                  <div className="mt-1 text-xs text-slate-400">{f.folder_id ? folderNameMap.get(Number(f.folder_id)) || "Корень" : "Корень"}</div>
                  <div className="mt-2 text-xs rounded-full px-2 py-1 bg-slate-100 w-fit">{fileStatusLabel(f.status)}</div>
                  {openFileMenuId === f.id && (
                    <div className="mt-2 rounded-xl border border-slate-200 bg-white shadow-lg">
                      <button className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => reindexFile(f.id)}>Переиндексировать</button>
                      <button className="block w-full px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50" onClick={() => deleteFile(f.id)}>Удалить</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        {contextMenu && (
          <div
            className="fixed z-50 w-44 rounded-xl border border-slate-200 bg-white shadow-lg"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
              onClick={() => {
                reindexFile(contextMenu.id);
                setContextMenu(null);
              }}
            >
              Переиндексировать
            </button>
            <button
              className="block w-full px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50"
              onClick={() => {
                deleteFile(contextMenu.id);
                setContextMenu(null);
              }}
            >
              Удалить
            </button>
          </div>
        )}
        {previewFileId && (() => {
          const f = kbFiles.find((x) => x.id === previewFileId);
          if (!f) return null;
          const ext = fileExt(f.filename);
          const baseSrc = previewInlineUrl || "";
          const sourceKind = (f.source_type || "").toLowerCase();
          const isExternal = ["youtube", "rutube", "vk"].includes(sourceKind) && !!(f.source_url || "").trim();
          const externalEmbedUrl = buildExternalEmbedUrl(f.source_url, previewStartMs);
          const pageSuffix = ext === ".pdf" && previewPage ? `#page=${previewPage}` : "";
          const mediaSec = previewStartMs ? Math.max(0, Math.floor(previewStartMs / 1000)) : 0;
          const mediaSuffix = mediaSec > 0 ? `#t=${mediaSec}` : "";
          const src = `${baseSrc}${ext === ".pdf" ? pageSuffix : mediaSuffix}`;
          const officeSrc = buildOfficeViewerUrl(baseSrc);
          const externalUrl = (() => {
            const raw = (f.source_url || "").trim();
            if (!raw) return "";
            if (mediaSec <= 0) return raw;
            try {
              const u = new URL(raw);
              u.searchParams.set("t", String(mediaSec));
              return u.toString();
            } catch {
              return raw;
            }
          })();
          return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6">
              <div className="flex h-[85vh] w-[92vw] max-w-6xl flex-col rounded-2xl bg-white shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <div className="truncate text-sm font-semibold text-slate-900">{f.filename}</div>
                  <div className="flex items-center gap-2">
                    {previewDownloadUrl && (
                      <a className="rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-700" href={previewDownloadUrl} target="_blank" rel="noreferrer">
                        Скачать
                      </a>
                    )}
                    <button
                      className="rounded-lg border border-slate-200 px-3 py-1 text-sm"
                      onClick={() => {
                        setPreviewFileId(null);
                        setPreviewInlineUrl(null);
                        setPreviewDownloadUrl(null);
                      }}
                    >
                      Закрыть
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto bg-slate-50 p-3">
                  {previewLoading && (
                    <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Загрузка файла...</div>
                  )}
                  {!previewLoading && isExternal && (
                    <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
                      {externalEmbedUrl ? (
                        <iframe
                          title={f.filename || "external-video"}
                          src={externalEmbedUrl}
                          className="h-[64vh] w-full rounded-xl border border-slate-200 bg-white"
                          allow="autoplay; encrypted-media; picture-in-picture"
                          allowFullScreen
                        />
                      ) : (
                        <div>Встроенный плеер недоступен для этого источника.</div>
                      )}
                      <a className="mt-3 inline-block rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-700" href={externalUrl} target="_blank" rel="noreferrer">
                        Открыть источник
                      </a>
                    </div>
                  )}
                  {!previewLoading && !isExternal && !baseSrc && (
                    <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                      Не удалось получить файл для предпросмотра. Повтори попытку.
                      <button
                        className="ml-3 rounded-lg border border-slate-200 px-3 py-1 text-sm"
                        onClick={() => {
                          void openPreview(f.id, { ms: previewStartMs, page: previewPage });
                        }}
                      >
                        Повторить
                      </button>
                    </div>
                  )}
                  {!previewLoading && !!baseSrc && ext === ".pdf" && (
                    <iframe title={f.filename} src={src} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
                  )}
                  {!previewLoading && !!baseSrc && [".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext) && (
                    <img src={baseSrc} alt={f.filename} className="mx-auto max-h-full max-w-full rounded-xl border border-slate-200 bg-white" />
                  )}
                  {!previewLoading && !!baseSrc && [".mp4", ".mov", ".avi", ".mkv", ".webm"].includes(ext) && (
                    <video key={src} src={src} controls autoPlay className="h-full w-full rounded-xl border border-slate-200 bg-black" />
                  )}
                  {!previewLoading && !!baseSrc && [".mp3", ".ogg", ".wav", ".m4a", ".aac"].includes(ext) && (
                    <div className="rounded-xl border border-slate-200 bg-white p-6">
                      <audio key={src} src={src} controls autoPlay className="w-full" />
                    </div>
                  )}
                  {!previewLoading && !!baseSrc && [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf"].includes(ext) && (
                    officeSrc ? (
                      <iframe title={f.filename} src={officeSrc} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
                    ) : (
                      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Не удалось сформировать предпросмотр Office-документа. Используйте скачивание.</div>
                    )
                  )}
                  {!previewLoading && !!baseSrc && [".txt", ".csv", ".md", ".epub", ".json", ".xml", ".log"].includes(ext) && (
                    <iframe title={f.filename} src={baseSrc} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
                  )}
                  {!previewLoading && !!baseSrc && !isInlinePreviewable(f.filename) && (
                    <div className="rounded-xl border border-slate-200 bg-white p-6">
                      <div className="text-sm text-slate-600">Для этого типа файла предпросмотр недоступен.</div>
                      <a className="mt-3 inline-block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700" href={previewDownloadUrl || "#"} target="_blank" rel="noreferrer">
                        Скачать файл
                      </a>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })()}
      </section>

      <aside className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-900">Свойства и доступ</div>
            <div className="mt-1 text-xs text-slate-500">Показываем, кто сможет искать и открывать материалы.</div>
          </div>
          <div className="flex items-center gap-2">
            {detailsTarget && !detailsLoading && !detailsError && (
              <div className="flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1">
                <button
                  className={`rounded-lg px-3 py-1.5 text-xs ${!isEditingAccess ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"}`}
                  onClick={closeAccessEditor}
                >
                  Обзор
                </button>
                <button
                  className={`rounded-lg px-3 py-1.5 text-xs ${isEditingAccess ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"}`}
                  onClick={openAccessEditor}
                >
                  Настроить доступ
                </button>
              </div>
            )}
            {detailsTarget && (
              <button
                className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-600"
                onClick={() => {
                  setDetailsTarget(null);
                  setSelectedFolderId(null);
                  setDetailsError("");
                  setDetailsSaveMessage("");
                  setIsEditingAccess(false);
                  setShowAdvancedAcl(false);
                }}
              >
                Очистить
              </button>
            )}
          </div>
        </div>

        {!detailsTarget && (
          <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            Выбери папку слева или файл в списке. Здесь будет видно, кто имеет доступ к поиску и просмотру.
          </div>
        )}

        {detailsTarget && detailsLoading && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            Загружаем свойства и доступ...
          </div>
        )}

        {detailsTarget && !detailsLoading && detailsError && (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-600">
            {detailsError}
          </div>
        )}

        {detailsTarget?.kind === "folder" && selectedFolder && !detailsLoading && !detailsError && (
          <div className="mt-4 space-y-4">
            <div className="rounded-2xl border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-400">Папка</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{selectedFolder.name}</div>
                </div>
                <button
                  className="rounded-xl border border-rose-200 px-3 py-2 text-xs font-medium text-rose-600"
                  onClick={() => {
                    void deleteFolder(selectedFolder.id);
                  }}
                >
                  Удалить папку
                </button>
              </div>
              <div className="mt-2 text-sm text-slate-500">
                {selectedFolder.parent_id ? `Внутри: ${folderNameMap.get(Number(selectedFolder.parent_id)) || "—"}` : "Корень базы знаний"}
              </div>
              <div className="mt-1 text-sm text-slate-500">
                Файлов в ветке: {folderFileCounts.get(selectedFolder.id) || 0}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 p-4">
              <div className="text-sm font-semibold text-slate-900">Покрытие клиентского бота в папке</div>
              <div className="mt-2 grid gap-2">
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                  <span className="text-slate-600">Готовые материалы</span>
                  <span className="font-medium text-slate-900">{selectedFolderClientCoverage.total_ready_files}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                  <span className="text-slate-600">Всем клиентам</span>
                  <span className="font-medium text-slate-900">{selectedFolderClientCoverage.open_all_clients}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                  <span className="text-slate-600">Клиентским группам</span>
                  <span className="font-medium text-slate-900">{selectedFolderClientCoverage.open_client_groups}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                  <span className="text-slate-600">Закрыты для клиентов</span>
                  <span className="font-medium text-slate-900">{selectedFolderClientCoverage.closed_for_clients}</span>
                </div>
              </div>
              <div className="mt-3 text-xs text-slate-500">
                Сводка учитывает всю ветку папки, включая подпапки. После изменения правил цифры обновляются сразу.
              </div>
              {(selectedFolderClientCoverage.open_all_clients > 0 || selectedFolderClientCoverage.open_client_groups > 0) && (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Внимание: в этой ветке есть материалы, доступные клиентам. Удаление папки или перенос файлов в другие папки может изменить доступ клиентского бота.
                </div>
              )}
            </div>

            {!isEditingAccess ? (
              <div className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Доступ</div>
                    <div className="mt-2 text-xs text-slate-500">
                      Если правил нет, папка доступна сотрудникам аккаунта по умолчанию. Клиенты по умолчанию не ищут по этим материалам.
                    </div>
                  </div>
                  <button className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700" onClick={openAccessEditor}>
                    Настроить доступ
                  </button>
                </div>
                <div className="mt-3">
                  {folderHasExplicitRules
                    ? renderAccessOriginCard({
                        title: "Явные правила на папке",
                        tone: "emerald",
                        body: "Для этой папки заданы собственные правила. Они определяют, кто может искать и открывать материалы в этой ветке.",
                      })
                    : renderAccessOriginCard({
                        title: "Наследование по умолчанию",
                        tone: "blue",
                        body: "На папке нет собственных правил. Сейчас действует базовый доступ аккаунта: сотрудники видят материалы, клиенты — нет.",
                      })}
                </div>
                {detailsSaveMessage && <div className={`mt-3 text-xs ${detailsSaveMessage.includes("сохран") ? "text-emerald-600" : "text-rose-600"}`}>{detailsSaveMessage}</div>}
                <div className="mt-3">
                  {renderAclSummary(selectedFolderAccess, "Явных правил нет. Сейчас действует доступ по умолчанию для сотрудников аккаунта.")}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 p-4">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Настроить доступ к папке</div>
                    <div className="mt-1 text-xs text-slate-500">
                      Сначала выбери подходящий сценарий. Тонкую настройку используй только если шаблоны не подходят.
                    </div>
                  </div>
                  <button className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700" onClick={closeAccessEditor}>
                    Вернуться к обзору
                  </button>
                </div>
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-semibold text-slate-900">Выбери сценарий доступа</div>
                  <div className="text-xs text-slate-500">
                    Для большинства случаев достаточно выбрать один шаблон для всей папки. Индивидуальные правила нужны только для редких исключений.
                  </div>
                    {folderClientImpact && (
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                        <div className="font-semibold">Предварительное влияние на клиентский бот</div>
                        <div className="mt-2 text-xs text-amber-800">
                          Изменение правил папки влияет на всю ветку, включая подпапки. Явные правила на вложенных папках и файлах могут сохранить свои ограничения.
                        </div>
                        <div className="mt-3 grid gap-2">
                          <div className="flex items-center justify-between rounded-xl bg-white/70 px-3 py-2">
                            <span>Текущий режим ветки</span>
                            <span className="font-medium">
                              {folderClientImpact.current === "all"
                                ? "Всем клиентам"
                                : folderClientImpact.current === "groups"
                                  ? "Клиентским группам"
                                  : "Закрыто для клиентов"}
                            </span>
                          </div>
                          <div className="flex items-center justify-between rounded-xl bg-white/70 px-3 py-2">
                            <span>После сохранения</span>
                            <span className="font-medium">
                              {folderClientImpact.projected === "all"
                                ? "Всем клиентам"
                                : folderClientImpact.projected === "groups"
                                  ? "Клиентским группам"
                                  : "Закрыто для клиентов"}
                            </span>
                          </div>
                        </div>
                        <div className="mt-3 text-xs text-amber-800">
                          В этой ветке сейчас: готовых материалов — {folderClientImpact.totalReady}, всем клиентам — {folderClientImpact.openAll}, клиентским группам — {folderClientImpact.openGroups}, закрыто — {folderClientImpact.closed}.
                        </div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("inherit")}>Наследовать по умолчанию</button>
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("staff")}>Общие материалы</button>
                      {staffGroups.length > 0 && (
                        <>
                          <select
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                            value={String(templateStaffGroupId || staffGroups[0]?.id || "")}
                            onChange={(e) => setTemplateStaffGroupId(Number(e.target.value) || 0)}
                          >
                            {staffGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                          </select>
                          <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("group", templateStaffGroupId || staffGroups[0]?.id || 0)}>Отдел / группа</button>
                        </>
                      )}
                      {clientGroups.length > 0 && (
                        <>
                          <select
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                            value={String(templateClientGroupId || clientGroups[0]?.id || "")}
                            onChange={(e) => setTemplateClientGroupId(Number(e.target.value) || 0)}
                          >
                            {clientGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                          </select>
                          <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("client_group", templateClientGroupId || clientGroups[0]?.id || 0)}>Клиенты / группа</button>
                        </>
                      )}
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("clients")}>Только клиенты</button>
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("staff_clients")}>Сотрудники и клиенты</button>
                    </div>
                  <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-slate-200 bg-white px-3 py-3">
                    <div>
                      <div className="text-sm font-medium text-slate-800">Тонкая настройка</div>
                      <div className="mt-1 text-xs text-slate-500">Используй только если шаблоны выше не подходят под сценарий.</div>
                    </div>
                    <button
                      className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700"
                      onClick={() => setShowAdvancedAcl((prev) => !prev)}
                    >
                      {showAdvancedAcl ? "Скрыть правила" : "Показать правила"}
                    </button>
                  </div>
                  {showAdvancedAcl && (
                    <>
                      <div className="space-y-2">
                        {aclDraft.map((item, index) => (
                          <div key={`${item.principal_type}:${item.principal_id}:${index}`} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_type} onChange={(e) => updateAclDraftItem(index, { principal_type: e.target.value, principal_id: e.target.value === "audience" ? "staff" : e.target.value === "membership" ? String(accountUsers[0]?.membership_id || "") : e.target.value === "group" ? String(accountGroups[0]?.id || "") : "member" })}>
                              <option value="role">Роль</option>
                              <option value="audience">Аудитория</option>
                              {accountGroups.length > 0 && <option value="group">Группа</option>}
                              {accountUsers.length > 0 && <option value="membership">Конкретный пользователь</option>}
                            </select>
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_id} onChange={(e) => updateAclDraftItem(index, { principal_id: e.target.value })}>
                              {item.principal_type === "audience" ? (
                                <>
                                  <option value="staff">{audienceOptionLabel("staff")}</option>
                                  <option value="client">{audienceOptionLabel("client")}</option>
                                </>
                              ) : item.principal_type === "group" ? (
                                <>
                                  {accountGroups.map((group) => <option key={group.id} value={String(group.id)}>{group.name}</option>)}
                                </>
                              ) : item.principal_type === "membership" ? (
                                <>
                                  {accountUsers.map((user) => <option key={user.membership_id} value={String(user.membership_id)}>{user.display_name}</option>)}
                                </>
                              ) : (
                                <>
                                  <option value="owner">{roleOptionLabel("owner")}</option>
                                  <option value="admin">{roleOptionLabel("admin")}</option>
                                  <option value="member">{roleOptionLabel("member")}</option>
                                  <option value="client">{roleOptionLabel("client")}</option>
                                </>
                              )}
                            </select>
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.access_level} onChange={(e) => updateAclDraftItem(index, { access_level: e.target.value })}>
                              <option value="none">Нет доступа</option>
                              <option value="read">Чтение</option>
                              <option value="write">Редактирование</option>
                              <option value="admin">Администрирование</option>
                            </select>
                            <button className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs text-rose-600" onClick={() => removeAclDraftItem(index)}>Убрать</button>
                          </div>
                        ))}
                      </div>
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" onClick={addAclDraftItem}>Добавить правило</button>
                    </>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-semibold text-white" onClick={saveAclDraft}>{detailsSaving ? "Сохраняем..." : "Сохранить доступ"}</button>
                  </div>
                  {detailsSaveMessage && <div className={`text-xs ${detailsSaveMessage.includes("сохран") ? "text-emerald-600" : "text-rose-600"}`}>{detailsSaveMessage}</div>}
                </div>
              </div>
            )}
          </div>
        )}

        {detailsTarget?.kind === "file" && selectedDetailsFile && !detailsLoading && !detailsError && (
          <div className="mt-4 space-y-4">
            <div className="rounded-2xl border border-slate-200 p-4">
              <div className="text-xs uppercase tracking-wide text-slate-400">Файл</div>
              <div className="mt-2 text-base font-semibold text-slate-900">{selectedDetailsFile.filename}</div>
              <div className="mt-2 text-sm text-slate-500">
                Папка: {selectedDetailsFile.folder_id ? folderNameMap.get(Number(selectedDetailsFile.folder_id)) || "Корень" : "Корень"}
              </div>
              <div className="mt-1 text-sm text-slate-500">Владелец: {fileOwnerLabel(selectedDetailsFile)}</div>
              <div className="mt-1 text-sm text-slate-500">Статус: {fileStatusLabel(selectedDetailsFile.status)}</div>
            </div>

            <div className="rounded-2xl border border-slate-200 p-4">
              <div className="text-sm font-semibold text-slate-900">Кто сможет искать по этому файлу</div>
              <div className="mt-3">
                {fileHasExplicitRules
                  ? renderAccessOriginCard({
                      title: "Явные правила на файле",
                      tone: "emerald",
                      body: "У файла есть собственные правила. Они важнее наследования от папки и сразу влияют на поиск и ответы модели.",
                    })
                  : selectedDetailsFileFolder
                    ? renderAccessOriginCard({
                        title: "Наследование от папки",
                        tone: "amber",
                        body: `Файл сейчас наследует доступ от папки «${selectedDetailsFileFolder.name}». Изменение правил папки сразу изменит доступ к этому файлу.`,
                      })
                    : renderAccessOriginCard({
                        title: "Общие правила аккаунта",
                        tone: "blue",
                        body: "Файл лежит в корне без собственных правил. Сейчас действует базовый доступ аккаунта.",
                      })}
              </div>
              <div className="mt-3 grid gap-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Сотрудники</div>
                  <div className="mt-1 text-sm text-slate-800">{kbAccessLabel(selectedFileEffectiveStaff)}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Клиенты</div>
                  <div className="mt-1 text-sm text-slate-800">{kbAccessLabel(selectedFileEffectiveClient)}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {summarizeClientVisibility(selectedFileAccess, accountGroups)}
                  </div>
                </div>
              </div>
            </div>

            {!isEditingAccess ? (
              <div className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Явные правила</div>
                    <div className="mt-2 text-xs text-slate-500">
                      Если правил нет, файл наследует доступ от папки или общие правила роли.
                    </div>
                  </div>
                  <button className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700" onClick={openAccessEditor}>
                    Настроить доступ
                  </button>
                </div>
                {detailsSaveMessage && <div className={`mt-3 text-xs ${detailsSaveMessage.includes("сохран") ? "text-emerald-600" : "text-rose-600"}`}>{detailsSaveMessage}</div>}
                <div className="mt-3">
                  {renderAclSummary(selectedFileAccess, "Явных правил на файл нет. Сейчас действует наследование от папки или правила роли.")}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 p-4">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Настроить доступ к файлу</div>
                    <div className="mt-1 text-xs text-slate-500">
                      По умолчанию файл должен наследовать доступ от папки. Исключения настраивай только для отдельных случаев.
                    </div>
                  </div>
                  <button className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700" onClick={closeAccessEditor}>
                    Вернуться к обзору
                  </button>
                </div>
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-semibold text-slate-900">Как управлять этим файлом</div>
                  {!fileHasExplicitRules ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                      <div className="font-medium text-amber-900">Сейчас файл наследует доступ</div>
                      <div className="mt-1 text-xs text-amber-800">
                        Это рекомендуемый режим. Меняй правила на файле только если нужно сделать исключение из правил папки.
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                      <div className="font-medium text-emerald-900">На файле есть исключение</div>
                      <div className="mt-1 text-xs text-emerald-800">
                        У файла заданы собственные правила. Они важнее правил папки и сразу влияют на поиск и ответы модели.
                      </div>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("inherit")}>Оставить наследование</button>
                    <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("staff")}>Сделать общим</button>
                    {staffGroups.length > 0 && (
                      <>
                        <select
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                          value={String(templateStaffGroupId || staffGroups[0]?.id || "")}
                          onChange={(e) => setTemplateStaffGroupId(Number(e.target.value) || 0)}
                        >
                          {staffGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                        </select>
                        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("group", templateStaffGroupId || staffGroups[0]?.id || 0)}>Исключение для отдела</button>
                      </>
                    )}
                    {clientGroups.length > 0 && (
                      <>
                        <select
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                          value={String(templateClientGroupId || clientGroups[0]?.id || "")}
                          onChange={(e) => setTemplateClientGroupId(Number(e.target.value) || 0)}
                        >
                          {clientGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                        </select>
                        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("client_group", templateClientGroupId || clientGroups[0]?.id || 0)}>Исключение для клиентской группы</button>
                      </>
                    )}
                    <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("clients")}>Открыть клиентам</button>
                    <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" onClick={() => applyAclTemplate("staff_clients")}>Сотрудники и клиенты</button>
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-slate-200 bg-white px-3 py-3">
                    <div>
                      <div className="text-sm font-medium text-slate-800">Тонкая настройка</div>
                      <div className="mt-1 text-xs text-slate-500">Используй только для редких исключений, когда шаблоны не подходят.</div>
                    </div>
                    <button
                      className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-700"
                      onClick={() => setShowAdvancedAcl((prev) => !prev)}
                    >
                      {showAdvancedAcl ? "Скрыть правила" : "Показать правила"}
                    </button>
                  </div>
                  {showAdvancedAcl && (
                    <>
                      <div className="space-y-2">
                        {aclDraft.map((item, index) => (
                          <div key={`${item.principal_type}:${item.principal_id}:${index}`} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_type} onChange={(e) => updateAclDraftItem(index, { principal_type: e.target.value, principal_id: e.target.value === "audience" ? "staff" : e.target.value === "membership" ? String(accountUsers[0]?.membership_id || "") : e.target.value === "group" ? String(accountGroups[0]?.id || "") : "member" })}>
                              <option value="role">Роль</option>
                              <option value="audience">Аудитория</option>
                              {accountGroups.length > 0 && <option value="group">Группа</option>}
                              {accountUsers.length > 0 && <option value="membership">Конкретный пользователь</option>}
                            </select>
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.principal_id} onChange={(e) => updateAclDraftItem(index, { principal_id: e.target.value })}>
                              {item.principal_type === "audience" ? (
                                <>
                                  <option value="staff">{audienceOptionLabel("staff")}</option>
                                  <option value="client">{audienceOptionLabel("client")}</option>
                                </>
                              ) : item.principal_type === "group" ? (
                                <>
                                  {accountGroups.map((group) => <option key={group.id} value={String(group.id)}>{group.name}</option>)}
                                </>
                              ) : item.principal_type === "membership" ? (
                                <>
                                  {accountUsers.map((user) => <option key={user.membership_id} value={String(user.membership_id)}>{user.display_name}</option>)}
                                </>
                              ) : (
                                <>
                                  <option value="owner">{roleOptionLabel("owner")}</option>
                                  <option value="admin">{roleOptionLabel("admin")}</option>
                                  <option value="member">{roleOptionLabel("member")}</option>
                                  <option value="client">{roleOptionLabel("client")}</option>
                                </>
                              )}
                            </select>
                            <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={item.access_level} onChange={(e) => updateAclDraftItem(index, { access_level: e.target.value })}>
                              <option value="none">Нет доступа</option>
                              <option value="read">Чтение</option>
                              <option value="write">Редактирование</option>
                              <option value="admin">Администрирование</option>
                            </select>
                            <button className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs text-rose-600" onClick={() => removeAclDraftItem(index)}>Убрать</button>
                          </div>
                        ))}
                      </div>
                      <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" onClick={addAclDraftItem}>Добавить правило</button>
                    </>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-semibold text-white" onClick={saveAclDraft}>{detailsSaving ? "Сохраняем..." : "Сохранить доступ"}</button>
                  </div>
                  {detailsSaveMessage && <div className={`text-xs ${detailsSaveMessage.includes("сохран") ? "text-emerald-600" : "text-rose-600"}`}>{detailsSaveMessage}</div>}
                </div>
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
