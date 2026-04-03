import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from "react";
import {
  ChevronDown,
  ChevronRight,
  Eye,
  Folder,
  FolderOpen,
  Info,
  PlayCircle,
  Search,
  Upload,
  X,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { InspectorPanel } from "../../components/ui/InspectorPanel";
import { Panel, PanelBody, PanelHeader } from "../../components/ui/Panel";
import { WorkspaceSplit } from "../../components/ui/WorkspaceSplit";
import { fetchPortal, fetchWeb, getActiveAccountId, getWebPortalInfo } from "./auth";

type InspectorMode = "overview" | "access";
type RootSpace = "all" | "shared" | "departments" | "clients";
type ViewMode = "list" | "compact";
type Selection =
  | { kind: "folder"; id: number }
  | { kind: "file"; id: number }
  | null;

type KbFile = {
  id: number;
  filename: string;
  folder_id?: number | null;
  mime_type?: string;
  source_type?: string;
  source_url?: string;
  status: string;
  uploaded_by_name?: string;
  query_count?: number;
  access_badges?: { staff?: string; client?: string };
};

type KbFolder = {
  id: number;
  name: string;
  parent_id?: number | null;
  root_space?: RootSpace | null;
  is_space_root?: boolean;
  access_badges?: { staff?: string; client?: string };
};

type KbAclItem = {
  principal_type: string;
  principal_id: string;
  access_level: string;
};

type KbAclDraftItem = {
  principal_type: string;
  principal_id: string;
  access_level: string;
};

type KbAccessSummary = {
  total_ready_files: number;
  open_all_clients: number;
  open_client_groups: number;
  closed_for_clients: number;
};

type KbAccountGroup = {
  id: number;
  name: string;
  kind: "staff" | "client";
};

type DetailsState = {
  loading: boolean;
  folderAccess: KbAclItem[];
  fileAccess: KbAclItem[];
  folderCoverage: KbAccessSummary;
  effectiveStaff: string;
  effectiveClient: string;
};

type KbTemplate = "inherit" | "staff" | "clients" | "staff_clients" | "group" | "client_group";

type FolderDialogState =
  | { open: false }
  | { open: true; mode: "create"; parentId: number | null; name: string }
  | { open: true; mode: "rename"; folderId: number; name: string };

type DeleteDialogState =
  | { open: false }
  | { open: true; kind: "files"; ids: number[]; title: string; body: string }
  | { open: true; kind: "folder"; folderId: number; title: string; body: string };

type MoveDialogState =
  | { open: false }
  | { open: true; folderId: number | null; ids: number[]; title: string; body: string };

type UploadDialogState = {
  open: boolean;
  mode: "choose" | "url";
  url: string;
  saving: boolean;
  message: string;
};

const KB_LAST_FOLDER_KEY = "kb_v2_last_folder_id";

const EMPTY_SUMMARY: KbAccessSummary = {
  total_ready_files: 0,
  open_all_clients: 0,
  open_client_groups: 0,
  closed_for_clients: 0,
};

const ONBOARDING_STEPS = [
  {
    title: "Папки задают доступ",
    body: "Материалы обычно наследуют правила папки. Это основной и самый безопасный способ управлять доступом к знаниям.",
    mediaTitle: "Открытие папки и просмотр инспектора",
  },
  {
    title: "Клиентский бот видит только разрешённые материалы",
    body: "Открывай доступ на папке, если хочешь, чтобы бот сразу начал искать по всей ветке, а не по отдельным файлам.",
    mediaTitle: "Политика папки меняет покрытие клиентского бота",
  },
  {
    title: "Исключения нужны редко",
    body: "Если файлу нужен особый доступ, создай исключение. Но по умолчанию лучше сохранять наследование от папки.",
    mediaTitle: "Файл наследует, исключение задаётся вручную",
  },
] as const;

function normalizeSummary(data: any): KbAccessSummary {
  return {
    total_ready_files: Number(data?.total_ready_files || 0),
    open_all_clients: Number(data?.open_all_clients || 0),
    open_client_groups: Number(data?.open_client_groups || 0),
    closed_for_clients: Number(data?.closed_for_clients || 0),
  };
}

function buildFolderChildrenMap(folders: KbFolder[]) {
  const map = new Map<number | null, KbFolder[]>();
  folders.forEach((folder) => {
    const key = folder.parent_id ?? null;
    map.set(key, [...(map.get(key) || []), folder]);
  });
  Array.from(map.keys()).forEach((key) => {
    map.set(key, (map.get(key) || []).slice().sort((a, b) => a.name.localeCompare(b.name, "ru")));
  });
  return map;
}

function collectFolderSubtreeIds(childrenMap: Map<number | null, KbFolder[]>, folderId: number): number[] {
  const result = [folderId];
  const walk = (id: number) => {
    (childrenMap.get(id) || []).forEach((child) => {
      result.push(child.id);
      walk(child.id);
    });
  };
  walk(folderId);
  return result;
}

function buildFolderPath(folderId: number | null, folderMap: Map<number, KbFolder>): string {
  if (folderId == null) return "Корень базы знаний";
  const parts: string[] = [];
  let current = folderMap.get(Number(folderId));
  while (current) {
    parts.unshift(current.name);
    current = current.parent_id != null ? folderMap.get(Number(current.parent_id)) : undefined;
  }
  return parts.join(" / ") || "Корень базы знаний";
}

function rootSpaceForFolder(folder: KbFolder, folderMap: Map<number, KbFolder>): RootSpace {
  const direct = String(folder.root_space || "").trim().toLowerCase();
  if (direct === "shared" || direct === "departments" || direct === "clients") return direct;
  let current = folder.parent_id != null ? folderMap.get(Number(folder.parent_id)) : undefined;
  const visited = new Set<number>();
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    const space = String(current.root_space || "").trim().toLowerCase();
    if (space === "shared" || space === "departments" || space === "clients") return space;
    current = current.parent_id != null ? folderMap.get(Number(current.parent_id)) : undefined;
  }
  return "all";
}

function rootSpaceForFile(file: KbFile, folderMap: Map<number, KbFolder>): RootSpace {
  if (file.folder_id == null) return "all";
  const folder = folderMap.get(Number(file.folder_id));
  return folder ? rootSpaceForFolder(folder, folderMap) : "all";
}

function rootSpaceLabel(value: RootSpace) {
  if (value === "shared") return "Общие";
  if (value === "departments") return "Отделы";
  if (value === "clients") return "Клиенты";
  return "Все материалы";
}

function normalizeStatus(status: string | undefined) {
  const value = String(status || "").toLowerCase();
  if (value === "uploaded") return "draft";
  if (value === "queued") return "processing";
  return value || "draft";
}

function statusLabel(status: string) {
  const value = normalizeStatus(status);
  if (value === "ready") return "Готово";
  if (value === "processing") return "Индексируется";
  if (value === "draft") return "Черновик";
  if (value === "error") return "Ошибка";
  return status || "—";
}

function statusTone(status: string): "neutral" | "sky" | "emerald" | "amber" | "rose" {
  const value = normalizeStatus(status);
  if (value === "ready") return "emerald";
  if (value === "processing") return "sky";
  if (value === "error") return "rose";
  return "amber";
}

function fileTypeLabel(file: KbFile) {
  const mime = String(file.mime_type || "").toLowerCase();
  const source = String(file.source_type || "").toLowerCase();
  const ext = String(file.filename || "").toLowerCase().split(".").pop() || "";
  if (mime.startsWith("video/") || ["youtube", "rutube", "vk"].includes(source)) return "Видео";
  if (mime.startsWith("audio/")) return "Аудио";
  if (mime.startsWith("image/")) return "Изображение";
  if (["pdf", "doc", "docx", "txt", "rtf"].includes(ext)) return "Документ";
  if (["xls", "xlsx", "csv"].includes(ext)) return "Таблица";
  if (["ppt", "pptx"].includes(ext)) return "Презентация";
  return "Файл";
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
    ".odt",
    ".ppt",
    ".pptx",
    ".odp",
    ".xls",
    ".xlsx",
    ".ods",
    ".rtf",
    ".txt",
    ".csv",
    ".md",
    ".epub",
    ".fb2",
    ".html",
    ".htm",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".ini",
    ".toml",
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

function buildExternalEmbedUrl(sourceUrl?: string) {
  const raw = (sourceUrl || "").trim();
  if (!raw) return "";
  try {
    const u = new URL(raw);
    const h = u.hostname.toLowerCase();
    if (h.includes("youtu.be") || h.includes("youtube.com")) {
      let vid = "";
      if (h.includes("youtu.be")) vid = u.pathname.replace("/", "");
      else vid = u.searchParams.get("v") || "";
      if (!vid) return "";
      return `https://www.youtube.com/embed/${vid}`;
    }
    if (h.includes("rutube.ru")) {
      const m = u.pathname.match(/\/video\/([a-zA-Z0-9_-]+)/);
      const id = m?.[1] || "";
      if (!id) return "";
      return `https://rutube.ru/play/embed/${id}/`;
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

function accessBadgeMeta(kind: "staff" | "client", value?: string) {
  if (kind === "staff") {
    if (value === "staff_admin") return { label: "Сотрудники: администрирование", shortLabel: "С: админ", tone: "emerald" as const };
    if (value === "staff_read") return { label: "Сотрудники: чтение", shortLabel: "С: чтение", tone: "sky" as const };
    return { label: "Сотрудники: закрыто", shortLabel: "С: закрыто", tone: "rose" as const };
  }
  if (value === "client_all") return { label: "Клиенты: всем", shortLabel: "К: всем", tone: "emerald" as const };
  if (value === "client_groups") return { label: "Клиенты: группам", shortLabel: "К: группам", tone: "fuchsia" as const };
  return { label: "Клиенты: закрыто", shortLabel: "К: закрыто", tone: "rose" as const };
}

function compactTone(tone: "neutral" | "sky" | "emerald" | "amber" | "rose" | "fuchsia") {
  return {
    neutral: "border-slate-200 bg-slate-50 text-slate-500",
    sky: "border-sky-200 bg-sky-50 text-sky-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    fuchsia: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
  }[tone];
}

function effectiveAccessLabel(value: string) {
  if (value === "admin") return "администрирование";
  if (value === "write") return "изменение";
  if (value === "read") return "чтение";
  return "нет";
}

function effectiveAccessTone(value: string): "neutral" | "sky" | "emerald" | "amber" | "rose" {
  if (value === "admin") return "emerald";
  if (value === "write") return "amber";
  if (value === "read") return "sky";
  return "rose";
}

function folderPolicySummary(items: KbAclItem[], groups: KbAccountGroup[]) {
  if (!items.length) return "Наследование по умолчанию аккаунта";
  const clientGroups = items
    .filter((item) => item.principal_type === "group" && item.access_level !== "none")
    .map((item) => groups.find((group) => group.id === Number(item.principal_id)))
    .filter((group): group is KbAccountGroup => !!group && group.kind === "client");
  if (items.some((item) => item.principal_type === "audience" && item.principal_id === "client" && item.access_level !== "none")) return "Открыто всем клиентам";
  if (clientGroups.length) return `Только клиентская группа: ${clientGroups.map((group) => group.name).join(", ")}`;
  if (items.some((item) => item.principal_type === "role" && item.principal_id === "member" && item.access_level === "read")) return "Открыто сотрудникам";
  return "Настроены явные ограничения";
}

function countReadyFiles(items: KbFile[]) {
  return items.filter((file) => normalizeStatus(file.status) === "ready").length;
}

function countFilesForRootSpace(files: KbFile[], folderMap: Map<number, KbFolder>, rootSpace: RootSpace) {
  if (rootSpace === "all") return files.length;
  return files.filter((file) => rootSpaceForFile(file, folderMap) === rootSpace).length;
}

function clientVisibilityCategory(value?: string) {
  if (value === "client_all") return "all";
  if (value === "client_groups") return "groups";
  return "closed";
}

function hasExplicitFileRules(file: KbFile) {
  return file.access_badges?.client === "client_groups" || file.access_badges?.client === "client_all" || file.access_badges?.staff === "staff_admin";
}

function kbAclTemplate(template: KbTemplate, options?: { groupId?: number | null }): KbAclDraftItem[] {
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
      ...(groupId > 0 ? [{ principal_type: "group", principal_id: String(groupId), access_level: "read" }] : []),
    ];
  }
  if (template === "client_group") {
    const groupId = Number(options?.groupId || 0);
    return [
      ...base,
      { principal_type: "role", principal_id: "member", access_level: "none" },
      ...(groupId > 0 ? [{ principal_type: "group", principal_id: String(groupId), access_level: "read" }] : []),
    ];
  }
  return [
    ...base,
    { principal_type: "role", principal_id: "member", access_level: "read" },
    { principal_type: "audience", principal_id: "client", access_level: "read" },
  ];
}
export function WebKbPageV2() {
  const { portalId, portalToken } = getWebPortalInfo();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [mode, setMode] = useState<InspectorMode>("overview");
  const [rootSpace, setRootSpace] = useState<RootSpace>("all");
  const [expandedRootSpace, setExpandedRootSpace] = useState<RootSpace | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selection, setSelection] = useState<Selection>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [folders, setFolders] = useState<KbFolder[]>([]);
  const [files, setFiles] = useState<KbFile[]>([]);
  const [coverage, setCoverage] = useState<KbAccessSummary>(EMPTY_SUMMARY);
  const [groups, setGroups] = useState<KbAccountGroup[]>([]);
  const [accessDraft, setAccessDraft] = useState<KbAclDraftItem[]>([]);
  const [bulkAccessDraft, setBulkAccessDraft] = useState<KbAclDraftItem[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [draggedFileId, setDraggedFileId] = useState<number | null>(null);
  const [dragOverFolderId, setDragOverFolderId] = useState<number | null | undefined>(undefined);
  const restoreSelectionRef = useRef(false);
  const [bulkAccessOpen, setBulkAccessOpen] = useState(false);
  const [templateStaffGroupId, setTemplateStaffGroupId] = useState(0);
  const [templateClientGroupId, setTemplateClientGroupId] = useState(0);
  const [detailsSaving, setDetailsSaving] = useState(false);
  const [detailsMessage, setDetailsMessage] = useState("");
  const [details, setDetails] = useState<DetailsState>({
    loading: false,
    folderAccess: [],
    fileAccess: [],
    folderCoverage: EMPTY_SUMMARY,
    effectiveStaff: "read",
    effectiveClient: "none",
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [visibilityFilter, setVisibilityFilter] = useState("all");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [rootFilesMode, setRootFilesMode] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [knowledgeInfoOpen, setKnowledgeInfoOpen] = useState(false);
  const [folderDialog, setFolderDialog] = useState<FolderDialogState>({ open: false });
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({ open: false });
  const [moveDialog, setMoveDialog] = useState<MoveDialogState>({ open: false });
  const [previewFileId, setPreviewFileId] = useState<number | null>(null);
  const [previewInlineUrl, setPreviewInlineUrl] = useState<string | null>(null);
  const [previewDownloadUrl, setPreviewDownloadUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [uploadDialog, setUploadDialog] = useState<UploadDialogState>({
    open: false,
    mode: "choose",
    url: "",
    saving: false,
    message: "",
  });

  const folderMap = useMemo(() => new Map(folders.map((folder) => [folder.id, folder])), [folders]);
  const childrenMap = useMemo(() => buildFolderChildrenMap(folders), [folders]);
  const spaceRoots = useMemo(() => ({
    shared: folders.find((folder) => folder.is_space_root && folder.root_space === "shared") ?? null,
    departments: folders.find((folder) => folder.is_space_root && folder.root_space === "departments") ?? null,
    clients: folders.find((folder) => folder.is_space_root && folder.root_space === "clients") ?? null,
  }), [folders]);
  const ownerOptions = useMemo(() => Array.from(new Set(files.map((file) => file.uploaded_by_name || "Не указан"))).sort((a, b) => a.localeCompare(b, "ru")), [files]);
  const typeOptions = useMemo(() => Array.from(new Set(files.map((file) => fileTypeLabel(file)))).sort((a, b) => a.localeCompare(b, "ru")), [files]);
  const staffGroups = useMemo(() => groups.filter((group) => group.kind === "staff"), [groups]);
  const clientGroups = useMemo(() => groups.filter((group) => group.kind === "client"), [groups]);

  const loadKbData = async () => {
    if (!portalId || !portalToken) return;
    const [filesRes, foldersRes, coverageRes] = await Promise.all([
      fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files`),
      fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders`),
      fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary`),
    ]);
    const [filesData, foldersData, coverageData] = await Promise.all([
      filesRes.json().catch(() => null),
      foldersRes.json().catch(() => null),
      coverageRes.json().catch(() => null),
    ]);
    if (!filesRes.ok || !foldersRes.ok || !coverageRes.ok) throw new Error("kb_reload_failed");
    const nextFiles = Array.isArray(filesData?.items) ? filesData.items : [];
    const nextFolders = Array.isArray(foldersData?.items) ? foldersData.items : [];
    setFiles(nextFiles);
    setFolders(nextFolders);
    setCoverage(normalizeSummary(coverageData));
    setExpanded((current) => {
      const next = { ...current };
      nextFolders.forEach((folder: KbFolder) => {
        if (folder.parent_id == null) next[folder.id] = true;
      });
      return next;
    });
  };

  useEffect(() => {
    if (!portalId || !portalToken) {
      setError("Портал не выбран.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [filesRes, foldersRes, coverageRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary`),
        ]);
        const [filesData, foldersData, coverageData] = await Promise.all([
          filesRes.json().catch(() => null),
          foldersRes.json().catch(() => null),
          coverageRes.json().catch(() => null),
        ]);
        if (cancelled) return;
        if (!filesRes.ok || !foldersRes.ok || !coverageRes.ok) {
          setError("Не удалось загрузить базу знаний.");
          return;
        }
        const nextFiles = Array.isArray(filesData?.items) ? filesData.items : [];
        const nextFolders = Array.isArray(foldersData?.items) ? foldersData.items : [];
        setFiles(nextFiles);
        setFolders(nextFolders);
        setCoverage(normalizeSummary(coverageData));
        setExpanded((current) => {
          const next = { ...current };
          nextFolders.forEach((folder: KbFolder) => {
            if (folder.parent_id == null) next[folder.id] = true;
          });
          return next;
        });
        setSelection((current) => {
          if (current?.kind === "folder" && nextFolders.some((folder: KbFolder) => folder.id === current.id)) return current;
          if (current?.kind === "file" && nextFiles.some((file: KbFile) => file.id === current.id)) return current;
          const map = new Map<number, KbFolder>(nextFolders.map((item: KbFolder) => [item.id, item]));
          const firstClientFolder = nextFolders.find((folder: KbFolder) => !folder.is_space_root && rootSpaceForFolder(folder, map) === "clients");
          const fallback = firstClientFolder || nextFolders[0];
          return fallback ? { kind: "folder", id: fallback.id } : null;
        });
      } catch {
        if (!cancelled) setError("Не удалось загрузить базу знаний.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!staffGroups.length) {
      setTemplateStaffGroupId(0);
    } else if (!staffGroups.some((group) => group.id === templateStaffGroupId)) {
      setTemplateStaffGroupId(staffGroups[0].id);
    }
  }, [staffGroups, templateStaffGroupId]);

  useEffect(() => {
    if (!clientGroups.length) {
      setTemplateClientGroupId(0);
    } else if (!clientGroups.some((group) => group.id === templateClientGroupId)) {
      setTemplateClientGroupId(clientGroups[0].id);
    }
  }, [clientGroups, templateClientGroupId]);

  useEffect(() => {
    const accountId = getActiveAccountId();
    if (!accountId) {
      setGroups([]);
      return;
    }
    let cancelled = false;
    const loadGroups = async () => {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/access-center`);
      const data = await res.json().catch(() => null);
      if (cancelled || !res.ok) return;
      setGroups(
        (Array.isArray(data?.groups) ? data.groups : [])
          .map((group: any) => ({
            id: Number(group?.id || 0),
            name: String(group?.name || ""),
            kind: String(group?.kind || "staff") === "client" ? "client" : "staff",
          }))
          .filter((group: KbAccountGroup) => group.id > 0),
      );
    };
    void loadGroups();
    return () => {
      cancelled = true;
    };
  }, [portalId]);

  useEffect(() => {
    if (!portalId || !selection) {
      setDetails({
        loading: false,
        folderAccess: [],
        fileAccess: [],
        folderCoverage: EMPTY_SUMMARY,
        effectiveStaff: "read",
        effectiveClient: "none",
      });
      return;
    }
    let cancelled = false;
    const loadDetails = async () => {
      setDetails((current) => ({ ...current, loading: true }));
      try {
        if (selection.kind === "folder") {
          const [accessRes, coverageRes] = await Promise.all([
            fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${selection.id}/access`),
            fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary?folder_id=${selection.id}`),
          ]);
          const [accessData, coverageData] = await Promise.all([
            accessRes.json().catch(() => null),
            coverageRes.json().catch(() => null),
          ]);
          if (cancelled) return;
          setDetails({
            loading: false,
            folderAccess: Array.isArray(accessData?.items) ? accessData.items : [],
            fileAccess: [],
            folderCoverage: normalizeSummary(coverageData),
            effectiveStaff: "read",
            effectiveClient: "none",
          });
          return;
        }
        const [accessRes, staffRes, clientRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=member&audience=staff`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=client&audience=client`),
        ]);
        const [accessData, staffData, clientData] = await Promise.all([
          accessRes.json().catch(() => null),
          staffRes.json().catch(() => null),
          clientRes.json().catch(() => null),
        ]);
        if (cancelled) return;
        setDetails({
          loading: false,
          folderAccess: [],
          fileAccess: Array.isArray(accessData?.items) ? accessData.items : [],
          folderCoverage: EMPTY_SUMMARY,
          effectiveStaff: String(staffData?.effective_access || "read"),
          effectiveClient: String(clientData?.effective_access || "none"),
        });
      } catch {
        if (!cancelled) setDetails((current) => ({ ...current, loading: false }));
      }
    };
    void loadDetails();
    return () => {
      cancelled = true;
    };
  }, [portalId, selection]);

  useEffect(() => {
    if (!selection) {
      setAccessDraft([]);
      setDetailsMessage("");
      return;
    }
    setAccessDraft(selection.kind === "folder" ? details.folderAccess : details.fileAccess);
    setDetailsMessage("");
  }, [details.fileAccess, details.folderAccess, selection]);

  useEffect(() => {
    if (!selectedFileIds.length) {
      setBulkAccessOpen(false);
      setBulkAccessDraft([]);
    }
  }, [selectedFileIds]);

  useEffect(() => {
    if (restoreSelectionRef.current) return;
    if (!folders.length) return;
    restoreSelectionRef.current = true;
    const raw = window.localStorage.getItem(KB_LAST_FOLDER_KEY);
    const lastFolderId = raw ? Number(raw) : NaN;
    if (Number.isFinite(lastFolderId) && folderMap.has(lastFolderId)) {
      const folder = folderMap.get(lastFolderId)!;
      setSelection({ kind: "folder", id: lastFolderId });
      setRootFilesMode(false);
      const folderRootSpace = rootSpaceForFolder(folder, folderMap);
      setRootSpace(folderRootSpace);
      setExpandedRootSpace(folderRootSpace);
      const parentChain: number[] = [];
      let current = folder.parent_id != null ? folderMap.get(Number(folder.parent_id)) : undefined;
      while (current) {
        parentChain.push(current.id);
        current = current.parent_id != null ? folderMap.get(Number(current.parent_id)) : undefined;
      }
      setExpanded((existing) => {
        const next = { ...existing };
        parentChain.forEach((id) => {
          next[id] = true;
        });
        return next;
      });
    }
  }, [folderMap, folders.length]);

  useEffect(() => {
    if (selection?.kind === "folder") {
      window.localStorage.setItem(KB_LAST_FOLDER_KEY, String(selection.id));
    }
  }, [selection]);

  const applyTemplate = (template: KbTemplate) => {
    const groupId = template === "group" ? templateStaffGroupId : template === "client_group" ? templateClientGroupId : 0;
    setAccessDraft(kbAclTemplate(template, { groupId }));
    setDetailsMessage("");
  };

  const applyBulkTemplate = (template: KbTemplate) => {
    const groupId = template === "group" ? templateStaffGroupId : template === "client_group" ? templateClientGroupId : 0;
    setBulkAccessDraft(kbAclTemplate(template, { groupId }));
    setDetailsMessage("");
  };

  const refreshSelection = () => {
    setSelection((current) => {
      if (!current) return current;
      return current.kind === "folder" ? { kind: "folder", id: current.id } : { kind: "file", id: current.id };
    });
  };

  const saveAccessDraft = async () => {
    if (!portalId || !selection) return;
    setDetailsSaving(true);
    setDetailsMessage("");
    try {
      const url =
        selection.kind === "folder"
          ? `/api/v1/bitrix/portals/${portalId}/kb/folders/${selection.id}/access`
          : `/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access`;
      const res = await fetchPortal(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: accessDraft }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(String(data?.error || data?.detail || "acl_save_failed"));
      await loadKbData();
      if (selection.kind === "folder") {
        const [accessRes, coverageRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${selection.id}/access`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/access-summary?folder_id=${selection.id}`),
        ]);
        const [accessData, coverageData] = await Promise.all([
          accessRes.json().catch(() => null),
          coverageRes.json().catch(() => null),
        ]);
        setDetails({
          loading: false,
          folderAccess: Array.isArray(accessData?.items) ? accessData.items : [],
          fileAccess: [],
          folderCoverage: normalizeSummary(coverageData),
          effectiveStaff: "read",
          effectiveClient: "none",
        });
      } else {
        const [accessRes, staffRes, clientRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=member&audience=staff`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=client&audience=client`),
        ]);
        const [accessData, staffData, clientData] = await Promise.all([
          accessRes.json().catch(() => null),
          staffRes.json().catch(() => null),
          clientRes.json().catch(() => null),
        ]);
        setDetails({
          loading: false,
          folderAccess: [],
          fileAccess: Array.isArray(accessData?.items) ? accessData.items : [],
          folderCoverage: EMPTY_SUMMARY,
          effectiveStaff: String(staffData?.effective_access || "read"),
          effectiveClient: String(clientData?.effective_access || "none"),
        });
      }
      setDetailsMessage("Доступ сохранён.");
      setMode("overview");
    } catch (error: any) {
      setDetailsMessage(String(error?.message || "acl_save_failed"));
    } finally {
      setDetailsSaving(false);
    }
  };

  const saveBulkAccessDraft = async () => {
    if (!portalId || !selectedFileIds.length) return;
    setDetailsSaving(true);
    setDetailsMessage("");
    try {
      for (const fileId of selectedFileIds) {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/access`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items: bulkAccessDraft }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(String(data?.error || data?.detail || "bulk_acl_save_failed"));
      }
      await loadKbData();
      setBulkAccessOpen(false);
      setSelectedFileIds([]);
      setDetailsMessage("Права обновлены для выбранных файлов.");
      if (selection?.kind === "file") {
        const [accessRes, staffRes, clientRes] = await Promise.all([
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=member&audience=staff`),
          fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${selection.id}/access/effective?role=client&audience=client`),
        ]);
        const [accessData, staffData, clientData] = await Promise.all([
          accessRes.json().catch(() => null),
          staffRes.json().catch(() => null),
          clientRes.json().catch(() => null),
        ]);
        setDetails({
          loading: false,
          folderAccess: [],
          fileAccess: Array.isArray(accessData?.items) ? accessData.items : [],
          folderCoverage: EMPTY_SUMMARY,
          effectiveStaff: String(staffData?.effective_access || "read"),
          effectiveClient: String(clientData?.effective_access || "none"),
        });
      }
    } catch (error: any) {
      setDetailsMessage(String(error?.message || "bulk_acl_save_failed"));
    } finally {
      setDetailsSaving(false);
    }
  };

  const openFilePicker = () => {
    setUploadDialog({ open: false, mode: "choose", url: "", saving: false, message: "" });
    fileInputRef.current?.click();
  };

  const openUploadDialog = () => {
    setUploadDialog({ open: true, mode: "choose", url: "", saving: false, message: "" });
  };

  const uploadFiles = async (items: FileList | null) => {
    if (!portalId || !portalToken || !items?.length) return;
    setActionMessage("Загружаю материалы...");
    try {
      let uploaded = 0;
      for (const file of Array.from(items)) {
        const form = new FormData();
        form.append("file", file);
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/upload`, {
          method: "POST",
          body: form,
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(String(data?.error || data?.detail || `upload_failed:${file.name}`));
        uploaded += 1;
      }
      await loadKbData();
      refreshSelection();
      setUploadDialog({ open: false, mode: "choose", url: "", saving: false, message: "" });
      setActionMessage(uploaded > 0 ? `Загружено материалов: ${uploaded}` : "Материалы не выбраны.");
    } catch (error: any) {
      setActionMessage(String(error?.message || "upload_failed"));
    }
  };

  const createUrlSource = async () => {
    if (!portalId || !portalToken) return;
    const url = uploadDialog.url.trim();
    if (!url) {
      setUploadDialog((current) => ({ ...current, message: "Вставь ссылку на документ, видео или другую поддерживаемую страницу." }));
      return;
    }
    setUploadDialog((current) => ({ ...current, saving: true, message: "" }));
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/sources/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(String(data?.error || data?.detail || "source_create_failed"));
      await loadKbData();
      refreshSelection();
      setUploadDialog({ open: false, mode: "choose", url: "", saving: false, message: "" });
      setActionMessage("Источник добавлен. Материал появится после обработки.");
    } catch (error: any) {
      setUploadDialog((current) => ({ ...current, saving: false, message: String(error?.message || "source_create_failed") }));
    }
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

  const openPreview = async (fileId: number) => {
    setSelection({ kind: "file", id: fileId });
    setMode("overview");
    setPreviewFileId(fileId);
    setPreviewInlineUrl(null);
    setPreviewDownloadUrl(null);
    const fileRec = files.find((item) => item.id === fileId);
    const sourceKind = String(fileRec?.source_type || "").toLowerCase();
    const isExternal = ["youtube", "rutube", "vk"].includes(sourceKind) && !!String(fileRec?.source_url || "").trim();
    if (isExternal) {
      setPreviewLoading(false);
      return;
    }
    await loadPreviewUrls(fileId);
  };

  const moveFilesToFolder = async (folderId: number | null, ids: number[]) => {
    if (!portalId || !portalToken || !ids.length) return;
    setActionMessage("Перемещаю материалы...");
    try {
      for (const fileId of ids) {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}/folder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_id: folderId }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(String(data?.error || data?.detail || "move_failed"));
      }
      await loadKbData();
      refreshSelection();
      setSelectedFileIds([]);
      setActionMessage(ids.length === 1 ? "Материал перемещён." : `Материалы перемещены: ${ids.length}`);
    } catch (error: any) {
      setActionMessage(String(error?.message || "move_failed"));
    }
  };

  const requestMoveFilesToFolder = (folderId: number | null, ids: number[]) => {
    if (!ids.length) return;
    const targetFolder = folderId != null ? folders.find((folder) => folder.id === folderId) || null : null;
    const targetClientMode = clientVisibilityCategory(targetFolder?.access_badges?.client);
    if (targetFolder && targetClientMode !== "closed") {
      setMoveDialog({
        open: true,
        folderId,
        ids,
        title: `Переместить в папку «${targetFolder.name}»?`,
        body:
          targetClientMode === "all"
            ? `Файлы без собственных правил могут стать доступны всем клиентам через наследование папки. Будет затронуто файлов: ${ids.length}.`
            : `Файлы без собственных правил могут стать доступны клиентским группам через наследование папки. Будет затронуто файлов: ${ids.length}.`,
      });
      return;
    }
    void moveFilesToFolder(folderId, ids);
  };

  const onDragEnterFolder = (folderId: number | null) => {
    setDragOverFolderId(folderId);
  };

  const onDragLeaveFolder = (folderId: number | null) => {
    setDragOverFolderId((current) => (current === folderId ? undefined : current));
  };

  const onDropToFolder = (folderId: number | null, event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOverFolderId(undefined);
    const ids: number[] = [];
    if (selectedFileIds.length) {
      ids.push(...selectedFileIds);
    } else {
      const payload = event.dataTransfer.getData("text/plain");
      const parsed = Number(payload);
      if (Number.isFinite(parsed)) ids.push(parsed);
      else if (draggedFileId != null) ids.push(draggedFileId);
    }
    if (!ids.length) return;
    requestMoveFilesToFolder(folderId, ids);
    setDraggedFileId(null);
  };

  const createFolder = () => {
    const parentId =
      selection?.kind === "folder"
        ? selection.id
        : rootSpace === "shared"
          ? spaceRoots.shared?.id ?? null
          : rootSpace === "departments"
            ? spaceRoots.departments?.id ?? null
            : rootSpace === "clients"
              ? spaceRoots.clients?.id ?? null
              : null;
    setFolderDialog({ open: true, mode: "create", parentId, name: "" });
  };

  const renameFolder = (folderId: number) => {
    const folder = folderMap.get(folderId);
    if (!folder) return;
    setFolderDialog({ open: true, mode: "rename", folderId, name: folder.name });
  };

  const submitFolderDialog = async () => {
    if (!portalId || !portalToken || !folderDialog.open) return;
    const trimmed = folderDialog.name.trim();
    if (!trimmed) return;
    setActionMessage(folderDialog.mode === "create" ? "Создаю папку..." : "Переименовываю папку...");
    try {
      const res =
        folderDialog.mode === "create"
          ? await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: trimmed, parent_id: folderDialog.parentId }),
            })
          : await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${folderDialog.folderId}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: trimmed }),
            });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(String(data?.error || data?.detail || (folderDialog.mode === "create" ? "folder_create_failed" : "folder_rename_failed")));
      await loadKbData();
      if (folderDialog.mode === "create" && data?.id) {
        setSelection({ kind: "folder", id: Number(data.id) });
        setMode("overview");
      } else {
        refreshSelection();
      }
      setFolderDialog({ open: false });
      setActionMessage(folderDialog.mode === "create" ? `Папка создана: ${trimmed}` : `Папка переименована: ${trimmed}`);
    } catch (error: any) {
      setActionMessage(String(error?.message || (folderDialog.mode === "create" ? "folder_create_failed" : "folder_rename_failed")));
    }
  };

  const deleteFolder = (folderId: number) => {
    const folder = folderMap.get(folderId);
    const summary = selection?.kind === "folder" && selection.id === folderId ? details.folderCoverage : EMPTY_SUMMARY;
    setDeleteDialog({
      open: true,
      kind: "folder",
      folderId,
      title: `Удалить папку «${folder?.name || folderId}»?`,
      body: [
        summary.total_ready_files ? `В ветке готовых материалов: ${summary.total_ready_files}.` : "",
        summary.open_all_clients || summary.open_client_groups ? `Клиентский доступ: всем — ${summary.open_all_clients}, группам — ${summary.open_client_groups}.` : "",
        "Сервер удалит папку только если в ней нет файлов и подпапок.",
      ].filter(Boolean).join(" "),
    });
  };

  const deleteFiles = (ids: number[]) => {
    if (!ids.length) return;
    setDeleteDialog({
      open: true,
      kind: "files",
      ids,
      title: ids.length === 1 ? "Удалить выбранный материал?" : `Удалить выбранные материалы: ${ids.length}?`,
      body: "Поиск и клиентский бот сразу перестанут использовать эти файлы.",
    });
  };

  const confirmDelete = async () => {
    if (!portalId || !portalToken || !deleteDialog.open) return;
    setActionMessage(deleteDialog.kind === "folder" ? "Удаляю папку..." : "Удаляю материалы...");
    try {
      if (deleteDialog.kind === "folder") {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/folders/${deleteDialog.folderId}`, { method: "DELETE" });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(String(data?.error || data?.detail || "folder_delete_failed"));
        setSelection((current) => (current?.kind === "folder" && current.id === deleteDialog.folderId ? null : current));
        setMode("overview");
        setActionMessage("Папка удалена.");
      } else {
        for (const fileId of deleteDialog.ids) {
          const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${fileId}`, { method: "DELETE" });
          const data = await res.json().catch(() => null);
          if (!res.ok) throw new Error(String(data?.error || data?.detail || "delete_failed"));
        }
        setSelectedFileIds([]);
        setSelection((current) => (current?.kind === "file" && deleteDialog.ids.includes(current.id) ? null : current));
        setActionMessage(deleteDialog.ids.length === 1 ? "Материал удалён." : `Материалы удалены: ${deleteDialog.ids.length}`);
      }
      await loadKbData();
      refreshSelection();
      setDeleteDialog({ open: false });
    } catch (error: any) {
      setActionMessage(String(error?.message || (deleteDialog.kind === "folder" ? "folder_delete_failed" : "delete_failed")));
    }
  };

  const confirmMove = async () => {
    if (!moveDialog.open) return;
    await moveFilesToFolder(moveDialog.folderId, moveDialog.ids);
    setMoveDialog({ open: false });
  };

  const selectedFolder = selection?.kind === "folder" ? folderMap.get(selection.id) ?? null : null;
  const selectedFile = selection?.kind === "file" ? files.find((file) => file.id === selection.id) ?? null : null;
  const rootStats = useMemo(
    () => ({
      all: { fileCount: countFilesForRootSpace(files, folderMap, "all"), folderCount: folders.filter((folder) => !folder.is_space_root).length },
      shared: { fileCount: countFilesForRootSpace(files, folderMap, "shared"), folderCount: folders.filter((folder) => !folder.is_space_root && rootSpaceForFolder(folder, folderMap) === "shared").length },
      departments: { fileCount: countFilesForRootSpace(files, folderMap, "departments"), folderCount: folders.filter((folder) => !folder.is_space_root && rootSpaceForFolder(folder, folderMap) === "departments").length },
      clients: { fileCount: countFilesForRootSpace(files, folderMap, "clients"), folderCount: folders.filter((folder) => !folder.is_space_root && rootSpaceForFolder(folder, folderMap) === "clients").length },
    }),
    [files, folderMap, folders],
  );
  const rootFileCounts = useMemo(
    () => ({
      all: files.filter((file) => file.folder_id == null).length,
      shared: files.filter((file) => file.folder_id != null && file.folder_id === spaceRoots.shared?.id).length,
      departments: files.filter((file) => file.folder_id != null && file.folder_id === spaceRoots.departments?.id).length,
      clients: files.filter((file) => file.folder_id != null && file.folder_id === spaceRoots.clients?.id).length,
    }),
    [files, spaceRoots.clients?.id, spaceRoots.departments?.id, spaceRoots.shared?.id],
  );
  const selectedFolderIds = useMemo(() => {
    if (!selectedFolder) return null;
    return new Set(collectFolderSubtreeIds(childrenMap, selectedFolder.id));
  }, [childrenMap, selectedFolder]);

  const filteredFiles = useMemo(() => {
    let items = files.slice();
    if (rootSpace !== "all") items = items.filter((file) => rootSpaceForFile(file, folderMap) === rootSpace);
    if (rootFilesMode) {
      const rootFolderId =
        rootSpace === "shared"
          ? spaceRoots.shared?.id ?? null
          : rootSpace === "departments"
            ? spaceRoots.departments?.id ?? null
            : rootSpace === "clients"
              ? spaceRoots.clients?.id ?? null
              : null;
      items = items.filter((file) => (rootSpace === "all" ? file.folder_id == null : file.folder_id === rootFolderId));
    } else if (selectedFolderIds) {
      items = items.filter((file) => file.folder_id != null && selectedFolderIds.has(Number(file.folder_id)));
    }
    const q = search.trim().toLowerCase();
    if (q) {
      items = items.filter((file) => {
        const name = String(file.filename || "").toLowerCase();
        const owner = String(file.uploaded_by_name || "").toLowerCase();
        const path = buildFolderPath(file.folder_id ?? null, folderMap).toLowerCase();
        return name.includes(q) || owner.includes(q) || path.includes(q);
      });
    }
    if (statusFilter !== "all") items = items.filter((file) => normalizeStatus(file.status) === statusFilter);
    if (visibilityFilter !== "all") items = items.filter((file) => String(file.access_badges?.client || "client_closed") === visibilityFilter);
    if (ownerFilter !== "all") items = items.filter((file) => (file.uploaded_by_name || "Не указан") === ownerFilter);
    if (typeFilter !== "all") items = items.filter((file) => fileTypeLabel(file) === typeFilter);
    return items.sort((a, b) => String(a.filename || "").localeCompare(String(b.filename || ""), "ru"));
  }, [files, folderMap, ownerFilter, rootSpace, search, selectedFolderIds, spaceRoots.clients?.id, spaceRoots.departments?.id, spaceRoots.shared?.id, statusFilter, typeFilter, visibilityFilter]);

  const activeCoverage = selectedFolder ? details.folderCoverage : coverage;
  const currentTitle = selectedFolder ? buildFolderPath(selectedFolder.id, folderMap) : rootFilesMode ? "Без папки" : rootSpaceLabel(rootSpace);
  const currentSubtitle = selectedFolder
    ? `${countReadyFiles(filteredFiles)} материалов · ${activeCoverage.open_all_clients + activeCoverage.open_client_groups} доступны клиентскому боту`
    : rootFilesMode
      ? `${countReadyFiles(filteredFiles)} материалов лежат ${rootSpace === "all" ? "в корне базы знаний" : `в корне пространства «${rootSpaceLabel(rootSpace)}»`}`
      : `${countReadyFiles(filteredFiles)} материалов в текущем представлении`;

  return (
    <div className="space-y-3 bg-[#F5F7FA] px-6 py-0.5">
      <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(event) => { void uploadFiles(event.target.files); event.target.value = ""; }} />
      <OnboardingDialog open={onboardingOpen} step={onboardingStep} onOpenChange={setOnboardingOpen} onNext={() => setOnboardingStep((step) => Math.min(step + 1, ONBOARDING_STEPS.length - 1))} onPrev={() => setOnboardingStep((step) => Math.max(step - 1, 0))} />
      <KnowledgeInfoDialog open={knowledgeInfoOpen} onOpenChange={setKnowledgeInfoOpen} />
      <UploadMethodDialog
        state={uploadDialog}
        onOpenChange={(open) => setUploadDialog((current) => ({ ...current, open, saving: false, message: open ? current.message : "" }))}
        onPickFile={openFilePicker}
        onPickUrl={() => setUploadDialog((current) => ({ ...current, mode: "url", message: "" }))}
        onBack={() => setUploadDialog((current) => ({ ...current, mode: "choose", message: "" }))}
        onUrlChange={(url) => setUploadDialog((current) => ({ ...current, url, message: "" }))}
        onSubmitUrl={() => void createUrlSource()}
      />
      <FolderDialog
        state={folderDialog}
        folderMap={folderMap}
        onOpenChange={(open) => { if (!open) setFolderDialog({ open: false }); }}
        onNameChange={(name) => setFolderDialog((current) => current.open ? { ...current, name } : current)}
        onSubmit={() => void submitFolderDialog()}
      />
      <ConfirmDialog
        state={deleteDialog}
        confirmLabel={deleteDialog.open && deleteDialog.kind === "folder" ? "Удалить папку" : "Удалить"}
        onOpenChange={(open) => { if (!open) setDeleteDialog({ open: false }); }}
        onConfirm={() => void confirmDelete()}
      />
      <MoveConfirmDialog
        state={moveDialog}
        onOpenChange={(open) => { if (!open) setMoveDialog({ open: false }); }}
        onConfirm={() => void confirmMove()}
      />
      <PreviewDialog
        file={previewFileId ? files.find((file) => file.id === previewFileId) || null : null}
        inlineUrl={previewInlineUrl}
        downloadUrl={previewDownloadUrl}
        loading={previewLoading}
        onClose={() => {
          setPreviewFileId(null);
          setPreviewInlineUrl(null);
          setPreviewDownloadUrl(null);
        }}
        onRetry={() => {
          if (previewFileId) void openPreview(previewFileId);
        }}
      />
      <PageShellHeader onOpenOnboarding={() => setOnboardingOpen(true)} onOpenInfo={() => setKnowledgeInfoOpen(true)} />
      {error ? <Panel tone="elevated" className="border-rose-200 bg-rose-50"><PanelBody className="mt-0 text-sm text-rose-700">{error}</PanelBody></Panel> : null}
      {actionMessage ? (
        <div className="pointer-events-none fixed right-8 top-20 z-40 flex max-w-[420px] items-start gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-[0_12px_30px_rgba(15,23,42,0.12)]">
          <div className="min-w-0 flex-1 leading-6">{actionMessage}</div>
          <button type="button" className="pointer-events-auto text-slate-400 transition hover:text-slate-700" onClick={() => setActionMessage("")}><X className="h-4 w-4" /></button>
        </div>
      ) : null}
      <WorkspaceSplit
        className="gap-4 xl:grid-cols-[304px_minmax(0,1fr)_400px]"
        sidebar={<LibraryRail rootSpace={rootSpace} expandedRootSpace={expandedRootSpace} onRootSpaceChange={(value) => { setRootSpace(value); setExpandedRootSpace((current) => current === value ? null : value); setSelection(null); setRootFilesMode(false); setMode("overview"); }} folders={folders} folderMap={folderMap} childrenMap={childrenMap} expanded={expanded} selection={selection} rootFilesMode={rootFilesMode} onToggle={(id) => setExpanded((current) => ({ ...current, [id]: !current[id] }))} onSelectFolder={(id) => { const folder = folderMap.get(id); setRootFilesMode(false); setSelection({ kind: "folder", id }); setMode("overview"); if (folder) { const folderRootSpace = rootSpaceForFolder(folder, folderMap); setRootSpace(folderRootSpace); setExpandedRootSpace(folderRootSpace); } }} onSelectRootFiles={() => { setSelection(null); setRootFilesMode(true); setMode("overview"); setExpandedRootSpace(rootSpace); }} onOpenUploadDialog={openUploadDialog} onCreateFolder={createFolder} rootStats={rootStats} rootFileCounts={rootFileCounts} dragOverFolderId={dragOverFolderId} onDragEnterFolder={onDragEnterFolder} onDragLeaveFolder={onDragLeaveFolder} onDropToFolder={onDropToFolder} setActionMessage={setActionMessage} draggedFileId={draggedFileId} selectedFileIds={selectedFileIds} onRequestMoveFilesToFolder={requestMoveFilesToFolder} spaceRoots={spaceRoots} />}
        main={<div className="space-y-4"><MaterialsHeader title={currentTitle} subtitle={currentSubtitle} loading={loading} search={search} onSearchChange={setSearch} typeFilter={typeFilter} onTypeFilterChange={setTypeFilter} statusFilter={statusFilter} onStatusFilterChange={setStatusFilter} visibilityFilter={visibilityFilter} onVisibilityFilterChange={setVisibilityFilter} ownerFilter={ownerFilter} onOwnerFilterChange={setOwnerFilter} ownerOptions={ownerOptions} typeOptions={typeOptions} viewMode={viewMode} onViewModeChange={setViewMode} /><MaterialsList files={filteredFiles} folderMap={folderMap} folders={folders.filter((folder) => !folder.is_space_root)} spaceRoots={spaceRoots} viewMode={viewMode} loading={loading} selectedFileId={selectedFile?.id ?? null} selectedFileIds={selectedFileIds} onSelectFile={(id) => { setSelection({ kind: "file", id }); setMode("overview"); }} onToggleSelectedFile={(id) => setSelectedFileIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))} onToggleSelectAll={() => setSelectedFileIds((current) => { const visibleIds = filteredFiles.map((file) => file.id); const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => current.includes(id)); return allVisibleSelected ? current.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...current, ...visibleIds])); })} onOpenBulkAccess={() => { setBulkAccessOpen(true); setMode("access"); }} onBulkMove={(value) => requestMoveFilesToFolder(value === "root" ? null : Number(value), selectedFileIds)} onBulkDelete={() => deleteFiles(selectedFileIds)} onClearSelection={() => setSelectedFileIds([])} onPreviewFile={(id) => void openPreview(id)} onDragStartFile={setDraggedFileId} onDragEndFile={() => setDraggedFileId(null)} /></div>}
        inspector={
          <div className="space-y-4">
          <InspectorPanel
            title={selectedFolder ? selectedFolder.name : selectedFile ? selectedFile.filename : "Инспектор"}
            subtitle={selectedFolder ? "Папка" : selectedFile ? "Файл" : "Выбери объект"}
            mode={mode}
            modes={selection ? [{ value: "overview", label: "Обзор" }, { value: "access", label: "Доступ" }] : undefined}
            onModeChange={selection ? (value) => setMode(value as InspectorMode) : undefined}
            actions={selection ? <div className="flex flex-wrap items-center gap-2">{selectedFolder ? <><Button size="sm" variant="secondary" onClick={() => void renameFolder(selectedFolder.id)}>Переименовать</Button><Button size="sm" variant="danger" onClick={() => void deleteFolder(selectedFolder.id)}>Удалить</Button></> : null}{selectedFile ? <Button size="sm" variant="danger" onClick={() => void deleteFiles([selectedFile.id])}>Удалить</Button> : null}<Button size="sm" variant="ghost" onClick={() => { setSelection(null); setMode("overview"); }}>Очистить</Button></div> : undefined}
          >
            {bulkAccessOpen && selectedFileIds.length ? (<BulkAccessShell selectedCount={selectedFileIds.length} draft={bulkAccessDraft} groups={groups} staffGroups={staffGroups} clientGroups={clientGroups} templateStaffGroupId={templateStaffGroupId} templateClientGroupId={templateClientGroupId} onTemplateStaffGroupIdChange={setTemplateStaffGroupId} onTemplateClientGroupIdChange={setTemplateClientGroupId} onApplyTemplate={applyBulkTemplate} onSave={saveBulkAccessDraft} saving={detailsSaving} message={detailsMessage} />) : !selection ? (
              <EmptyInspector />
            ) : selectedFolder ? (
              mode === "overview" ? (
                <FolderOverview folder={selectedFolder} folderMap={folderMap} access={details.folderAccess} coverage={details.folderCoverage} loading={details.loading} groups={groups} />
              ) : (
                <FolderAccessShell
                  folder={selectedFolder}
                  access={accessDraft}
                  groups={groups}
                  loading={details.loading}
                  staffGroups={staffGroups}
                  clientGroups={clientGroups}
                  templateStaffGroupId={templateStaffGroupId}
                  templateClientGroupId={templateClientGroupId}
                  onTemplateStaffGroupIdChange={setTemplateStaffGroupId}
                  onTemplateClientGroupIdChange={setTemplateClientGroupId}
                  onApplyTemplate={applyTemplate}
                  onSave={saveAccessDraft}
                  saving={detailsSaving}
                  message={detailsMessage}
                />
              )
            ) : selectedFile ? (
              mode === "overview" ? (
                <FileOverview file={selectedFile} folderMap={folderMap} access={details.fileAccess} effectiveStaff={details.effectiveStaff} effectiveClient={details.effectiveClient} loading={details.loading} groups={groups} />
              ) : (
                <FileAccessShell
                  file={selectedFile}
                  folderMap={folderMap}
                  access={accessDraft}
                  groups={groups}
                  loading={details.loading}
                  staffGroups={staffGroups}
                  clientGroups={clientGroups}
                  templateStaffGroupId={templateStaffGroupId}
                  templateClientGroupId={templateClientGroupId}
                  onTemplateStaffGroupIdChange={setTemplateStaffGroupId}
                  onTemplateClientGroupIdChange={setTemplateClientGroupId}
                  onApplyTemplate={applyTemplate}
                  onSave={saveAccessDraft}
                  saving={detailsSaving}
                  message={detailsMessage}
                />
              )
            ) : null}
          </InspectorPanel>
          </div>
        }
      />
    </div>
  );
}
function PageShellHeader(props: { onOpenOnboarding: () => void; onOpenInfo: () => void }) {
  return (
    <div className="rounded-[24px] border border-slate-200/80 bg-white px-6 py-2 shadow-[0_8px_24px_rgba(15,23,42,0.04)]">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="text-[24px] font-bold leading-none tracking-tight text-slate-950">База знаний</div>
          <div className="mt-0.5 flex items-center gap-2 text-sm text-slate-500">
            <span>Папки задают доступ, файл наследует его по умолчанию.</span>
            <button type="button" onClick={props.onOpenInfo} className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-700" aria-label="Открыть справку">
              <Info className="h-4 w-4" />
            </button>
          </div>
        </div>
        <Button size="sm" variant="secondary" onClick={props.onOpenOnboarding} className="shrink-0"><PlayCircle className="mr-2 h-4 w-4" /> Как это работает</Button>
      </div>
    </div>
  );
}

function LibraryRail(props: { rootSpace: RootSpace; expandedRootSpace: RootSpace | null; onRootSpaceChange: (value: RootSpace) => void; folders: KbFolder[]; folderMap: Map<number, KbFolder>; childrenMap: Map<number | null, KbFolder[]>; expanded: Record<number, boolean>; selection: Selection; rootFilesMode: boolean; onToggle: (id: number) => void; onSelectFolder: (id: number) => void; onSelectRootFiles: () => void; onOpenUploadDialog: () => void; onCreateFolder: () => void; rootStats: Record<RootSpace, { fileCount: number; folderCount: number }>; rootFileCounts: Record<RootSpace, number>; dragOverFolderId: number | null | undefined; onDragEnterFolder: (folderId: number | null) => void; onDragLeaveFolder: (folderId: number | null) => void; onDropToFolder: (folderId: number | null, event: DragEvent) => void; setActionMessage: (value: string) => void; draggedFileId: number | null; selectedFileIds: number[]; onRequestMoveFilesToFolder: (folderId: number | null, ids: number[]) => void; spaceRoots: { shared: KbFolder | null; departments: KbFolder | null; clients: KbFolder | null }; }) {
  const rootSections: Array<{ value: RootSpace; title: string; subtitle: string; accent: string }> = [
    { value: "all", title: "Все материалы", subtitle: "Полная библиотека аккаунта", accent: "bg-slate-900" },
    { value: "shared", title: "Общие", subtitle: "Материалы для сотрудников", accent: "bg-sky-500" },
    { value: "departments", title: "Отделы", subtitle: "Внутренние рабочие папки", accent: "bg-violet-500" },
    { value: "clients", title: "Клиенты", subtitle: "Клиентские материалы и группы", accent: "bg-emerald-500" },
  ];
  const [activeBadgeHintFolderId, setActiveBadgeHintFolderId] = useState<number | null>(null);

  useEffect(() => {
    if (activeBadgeHintFolderId == null) return;
    const close = () => setActiveBadgeHintFolderId(null);
    const handlePointerDown = () => close();
    const handleScroll = () => close();
    const handleKeyDown = () => close();
    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("wheel", handleScroll, { passive: true });
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("scroll", handleScroll, true);
      window.removeEventListener("wheel", handleScroll);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeBadgeHintFolderId]);

  const resolveDraggedIds = (event: DragEvent) => {
    const ids: number[] = [];
    if (props.selectedFileIds.length) ids.push(...props.selectedFileIds);
    else {
      const payload = event.dataTransfer.getData("text/plain");
      const parsed = Number(payload);
      if (Number.isFinite(parsed)) ids.push(parsed);
      else if (props.draggedFileId != null) ids.push(props.draggedFileId);
    }
    return ids;
  };

  const onDropToRootSpace = (space: RootSpace, event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setActiveBadgeHintFolderId(null);
    const ids = resolveDraggedIds(event);
    if (!ids.length) return;
    if (space === "all") {
      props.onRequestMoveFilesToFolder(null, ids);
      return;
    }
    const rootFolder =
      space === "shared"
        ? props.spaceRoots.shared
        : space === "departments"
          ? props.spaceRoots.departments
          : props.spaceRoots.clients;
    if (!rootFolder) return;
    props.onRequestMoveFilesToFolder(rootFolder.id, ids);
  };

  return (
    <Panel tone="elevated">
      <PanelBody className="mt-0 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Навигация</div>
          </div>
          <Button size="sm" variant="secondary" onClick={props.onOpenUploadDialog}><Upload className="mr-2 h-4 w-4" /> Загрузить</Button>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Пространства</div>
          <div className="mt-3 space-y-2">
              {rootSections.map((section) => {
                const active = props.expandedRootSpace === section.value;
                const stats = props.rootStats[section.value];
                const sectionFolders =
                  section.value === "all"
                    ? props.folders.filter((folder) => folder.parent_id == null && !folder.is_space_root)
                    : section.value === "shared"
                      ? (props.spaceRoots.shared ? props.childrenMap.get(props.spaceRoots.shared.id) || [] : [])
                      : section.value === "departments"
                        ? (props.spaceRoots.departments ? props.childrenMap.get(props.spaceRoots.departments.id) || [] : [])
                        : (props.spaceRoots.clients ? props.childrenMap.get(props.spaceRoots.clients.id) || [] : []);
                const sectionDropFolderId =
                  section.value === "all"
                    ? null
                    : section.value === "shared"
                      ? props.spaceRoots.shared?.id ?? null
                      : section.value === "departments"
                        ? props.spaceRoots.departments?.id ?? null
                        : props.spaceRoots.clients?.id ?? null;
                const isSpaceDropTarget = props.dragOverFolderId === sectionDropFolderId;
                return (
                  <div key={section.value} className={`overflow-hidden rounded-[18px] border transition ${active ? "border-slate-300 bg-slate-50/70" : "border-slate-200 bg-white"} ${isSpaceDropTarget ? "ring-2 ring-sky-200 ring-offset-1" : ""}`}>
                    <button
                      type="button"
                      onClick={() => props.onRootSpaceChange(section.value)}
                      onDragEnter={() => props.onDragEnterFolder(sectionDropFolderId)}
                      onDragLeave={() => props.onDragLeaveFolder(sectionDropFolderId)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => onDropToRootSpace(section.value, event)}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left"
                    >
                      <span className={`mt-1 h-6 w-1.5 shrink-0 rounded-full ${section.accent}`} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-3">
                          <span className="text-sm font-semibold text-slate-900">{section.title}</span>
                          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{stats.fileCount}</span>
                        </span>
                        <span className="mt-1 block text-xs leading-5 text-slate-500">{section.subtitle}</span>
                        <span className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
                          <span>Материалов: {stats.fileCount}</span>
                          <span className="text-slate-300">•</span>
                          <span>Папок: {stats.folderCount}</span>
                        </span>
                      </span>
                    </button>
                    {active ? (
                      <div className="border-t border-slate-200/80 px-3 pb-3 pt-3">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Дерево</div>
                          <Button size="sm" variant="secondary" onClick={props.onCreateFolder}>+ Новая папка</Button>
                        </div>
                        <button
                          type="button"
                          onClick={props.onSelectRootFiles}
                          onDragEnter={() => props.onDragEnterFolder(section.value === "all" ? null : (section.value === "shared" ? props.spaceRoots.shared?.id ?? null : section.value === "departments" ? props.spaceRoots.departments?.id ?? null : props.spaceRoots.clients?.id ?? null))}
                          onDragLeave={() => props.onDragLeaveFolder(section.value === "all" ? null : (section.value === "shared" ? props.spaceRoots.shared?.id ?? null : section.value === "departments" ? props.spaceRoots.departments?.id ?? null : props.spaceRoots.clients?.id ?? null))}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => props.onDropToFolder(section.value === "all" ? null : (section.value === "shared" ? props.spaceRoots.shared?.id ?? null : section.value === "departments" ? props.spaceRoots.departments?.id ?? null : props.spaceRoots.clients?.id ?? null), event)}
                          className={`mb-2 flex w-full items-center justify-between rounded-2xl border px-3 py-2.5 text-left transition ${props.rootFilesMode ? "border-sky-200 bg-sky-50 text-slate-900" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"} ${props.dragOverFolderId === (section.value === "all" ? null : section.value === "shared" ? props.spaceRoots.shared?.id ?? null : section.value === "departments" ? props.spaceRoots.departments?.id ?? null : props.spaceRoots.clients?.id ?? null) ? "ring-2 ring-sky-200 ring-offset-1" : ""}`}
                        >
                          <span>
                            <span className="block text-sm font-medium">Без папки</span>
                            <span className="mt-1 block text-xs text-slate-500">{section.value === "all" ? "Материалы, которые лежат в корне базы знаний" : `Материалы, которые лежат в корне пространства «${section.title}»`}</span>
                          </span>
                          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{props.rootFileCounts[section.value]}</span>
                        </button>
                        <div className="space-y-2">
                          {sectionFolders.length ? sectionFolders.map((folder) => <FolderNode key={folder.id} folder={folder} folderMap={props.folderMap} childrenMap={props.childrenMap} expanded={props.expanded} selection={props.selection} onToggle={props.onToggle} onSelectFolder={props.onSelectFolder} level={0} dragOverFolderId={props.dragOverFolderId} onDragEnterFolder={props.onDragEnterFolder} onDragLeaveFolder={props.onDragLeaveFolder} onDropToFolder={props.onDropToFolder} activeBadgeHintFolderId={activeBadgeHintFolderId} onToggleBadgeHint={(folderId) => setActiveBadgeHintFolderId((current) => current === folderId ? null : folderId)} onCloseBadgeHint={() => setActiveBadgeHintFolderId(null)} />) : <div className="rounded-[20px] border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm leading-6 text-slate-500">В этом пространстве пока нет папок.</div>}
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}

function FolderNode(props: { folder: KbFolder; folderMap: Map<number, KbFolder>; childrenMap: Map<number | null, KbFolder[]>; expanded: Record<number, boolean>; selection: Selection; onToggle: (id: number) => void; onSelectFolder: (id: number) => void; level: number; dragOverFolderId: number | null | undefined; onDragEnterFolder: (folderId: number | null) => void; onDragLeaveFolder: (folderId: number | null) => void; onDropToFolder: (folderId: number | null, event: DragEvent) => void; activeBadgeHintFolderId: number | null; onToggleBadgeHint: (folderId: number) => void; onCloseBadgeHint: () => void; }) {
  const children = props.childrenMap.get(props.folder.id) || [];
  const isExpanded = props.expanded[props.folder.id] ?? false;
  const selected = props.selection?.kind === "folder" && props.selection.id === props.folder.id;
  const showBadgeHint = props.activeBadgeHintFolderId === props.folder.id;
  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => props.onSelectFolder(props.folder.id)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            props.onSelectFolder(props.folder.id);
          }
        }}
        onDragEnter={() => props.onDragEnterFolder(props.folder.id)}
        onDragLeave={() => props.onDragLeaveFolder(props.folder.id)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => props.onDropToFolder(props.folder.id, event)}
        className={`rounded-[18px] border transition ${
          selected
            ? "border-sky-200 bg-sky-50"
            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
        } ${props.dragOverFolderId === props.folder.id ? "ring-2 ring-sky-200 ring-offset-1" : ""}`}
        style={{ marginLeft: props.level * 12 }}
      >
        <div className="flex items-center gap-2 px-3 py-2.5">
          <button
            type="button"
            className={`flex h-7 w-7 items-center justify-center rounded-xl transition ${selected ? "text-sky-700 hover:bg-white/60" : "text-slate-400 hover:bg-slate-100"}`}
            onClick={(event) => {
              event.stopPropagation();
              props.onToggle(props.folder.id);
            }}
          >
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className={`h-4 w-4 ${children.length ? "" : "opacity-35"}`} />}
          </button>
          <span className="flex min-w-0 flex-1 items-center gap-3 text-left">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl ${selected ? "bg-white text-sky-700" : "bg-slate-100 text-slate-600"}`}>
              {isExpanded ? <FolderOpen className="h-4 w-4" /> : <Folder className="h-4 w-4" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className={`block truncate text-sm font-semibold ${selected ? "text-slate-950" : "text-slate-900"}`}>{props.folder.name}</span>
              <span className={`mt-0.5 block text-xs ${selected ? "text-slate-500" : "text-slate-500"}`}>{children.length ? `Подпапок: ${children.length}` : "Без подпапок"}</span>
            </span>
          </span>
        </div>
        <div className="relative flex flex-wrap gap-1.5 px-3 pb-2.5">
          <CompactAccessBadges
            target={props.folder}
            selected={selected}
            onClick={(event) => {
              event.stopPropagation();
              props.onToggleBadgeHint(props.folder.id);
            }}
          />
          {showBadgeHint ? (
            <div className="absolute left-3 top-full z-10 mt-2 w-56 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-left text-xs leading-5 text-slate-600 shadow-[0_10px_30px_rgba(15,23,42,0.12)]">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  props.onCloseBadgeHint();
                }}
                className="absolute right-2 top-2 rounded-full border border-slate-200 p-1 text-slate-400 transition hover:border-slate-300 hover:text-slate-600"
                aria-label="Закрыть подсказку"
              >
                <X className="h-3 w-3" />
              </button>
              Бейдж показывает доступ клиентов к папке: `К: всем` — видно всем клиентам, `К: группам` — только клиентским группам, `К: закрыто` — бот не использует материалы из этой папки.
            </div>
          ) : null}
        </div>
      </div>
      {children.length && isExpanded ? <div className="space-y-2">{children.map((child) => <FolderNode key={child.id} folder={child} folderMap={props.folderMap} childrenMap={props.childrenMap} expanded={props.expanded} selection={props.selection} onToggle={props.onToggle} onSelectFolder={props.onSelectFolder} level={props.level + 1} dragOverFolderId={props.dragOverFolderId} onDragEnterFolder={props.onDragEnterFolder} onDragLeaveFolder={props.onDragLeaveFolder} onDropToFolder={props.onDropToFolder} activeBadgeHintFolderId={props.activeBadgeHintFolderId} onToggleBadgeHint={props.onToggleBadgeHint} onCloseBadgeHint={props.onCloseBadgeHint} />)}</div> : null}
    </div>
  );
}

function MaterialsHeader(props: { title: string; subtitle: string; loading: boolean; search: string; onSearchChange: (value: string) => void; typeFilter: string; onTypeFilterChange: (value: string) => void; statusFilter: string; onStatusFilterChange: (value: string) => void; visibilityFilter: string; onVisibilityFilterChange: (value: string) => void; ownerFilter: string; onOwnerFilterChange: (value: string) => void; ownerOptions: string[]; typeOptions: string[]; viewMode: ViewMode; onViewModeChange: (value: ViewMode) => void; }) {
  return (
    <Panel tone="elevated">
      <PanelBody className="mt-0 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Текущее пространство</div>
            <div className="mt-1.5 text-[24px] font-semibold leading-none tracking-tight text-slate-950">{props.title}</div>
            <div className="mt-1 text-sm leading-6 text-slate-500">{props.subtitle}</div>
          </div>
          <div className="flex items-center gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1">
            <button type="button" onClick={() => props.onViewModeChange("list")} className={`rounded-xl px-3 py-2 text-sm ${props.viewMode === "list" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>Список</button>
            <button type="button" onClick={() => props.onViewModeChange("compact")} className={`rounded-xl px-3 py-2 text-sm ${props.viewMode === "compact" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>Компактно</button>
          </div>
        </div>
        <div className="space-y-2.5">
          <div className="flex min-w-0 items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} placeholder="Поиск материалов, владельцев и папок" className="w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400" />
            {props.loading ? <span className="text-xs text-slate-400">Загрузка...</span> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SelectBox className="min-w-[120px]" value={props.typeFilter} onChange={props.onTypeFilterChange} options={[{ value: "all", label: "Тип" }, ...props.typeOptions.map((value) => ({ value, label: value }))]} />
            <SelectBox className="min-w-[120px]" value={props.statusFilter} onChange={props.onStatusFilterChange} options={[{ value: "all", label: "Статус" }, { value: "ready", label: "Готово" }, { value: "processing", label: "Индексируется" }, { value: "draft", label: "Черновик" }, { value: "error", label: "Ошибка" }]} />
            <SelectBox className="min-w-[140px]" value={props.visibilityFilter} onChange={props.onVisibilityFilterChange} options={[{ value: "all", label: "Видимость" }, { value: "client_all", label: "Клиентам: всем" }, { value: "client_groups", label: "Клиентам: группам" }, { value: "client_closed", label: "Клиентам: закрыто" }]} />
            <SelectBox className="min-w-[140px]" value={props.ownerFilter} onChange={props.onOwnerFilterChange} options={[{ value: "all", label: "Владелец" }, ...props.ownerOptions.map((value) => ({ value, label: value }))]} />
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}

function MaterialsList(props: { files: KbFile[]; folderMap: Map<number, KbFolder>; folders: KbFolder[]; spaceRoots: { shared: KbFolder | null; departments: KbFolder | null; clients: KbFolder | null }; viewMode: ViewMode; loading: boolean; selectedFileId: number | null; selectedFileIds: number[]; onSelectFile: (id: number) => void; onToggleSelectedFile: (id: number) => void; onToggleSelectAll: () => void; onOpenBulkAccess: () => void; onBulkMove: (value: string) => void; onBulkDelete: () => void; onClearSelection: () => void; onPreviewFile: (id: number) => void; onDragStartFile: (id: number) => void; onDragEndFile: () => void; }) {
  const allSelected = !!props.files.length && props.files.every((file) => props.selectedFileIds.includes(file.id));
  const moveOptions = [
    { value: "", label: "Переместить" },
    { value: "root", label: "В корень базы знаний" },
    ...(props.spaceRoots.shared ? [{ value: String(props.spaceRoots.shared.id), label: "В пространство «Общие»" }] : []),
    ...(props.spaceRoots.departments ? [{ value: String(props.spaceRoots.departments.id), label: "В пространство «Отделы»" }] : []),
    ...(props.spaceRoots.clients ? [{ value: String(props.spaceRoots.clients.id), label: "В пространство «Клиенты»" }] : []),
    ...props.folders.map((folder) => ({ value: String(folder.id), label: buildFolderPath(folder.id, props.folderMap) })),
  ];
  return (
    <Panel tone="elevated">
      <PanelHeader title="Материалы" subtitle="Доступ и наследование видны сразу в списке." />
      <PanelBody>
        <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5">
          <div className="flex min-h-[40px] items-center gap-3">
          <label className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium text-slate-700">
            <input type="checkbox" checked={allSelected} onChange={props.onToggleSelectAll} className="h-4 w-4 rounded border-slate-300 accent-sky-600" />
            Выбрать все
          </label>
          {props.selectedFileIds.length > 0 ? (
            <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-sm font-medium text-slate-700">Выбрано: {props.selectedFileIds.length}</span>
              <SelectBox className="min-w-[220px]" value="" onChange={(value) => { if (value) props.onBulkMove(value); }} options={moveOptions} />
              <Button size="sm" variant="danger" onClick={props.onBulkDelete}>Удалить</Button>
            </div>
          ) : (
            <div className="min-w-0 flex-1 text-right text-sm text-slate-400">Выбери материалы чекбоксами, чтобы открыть массовые действия.</div>
          )}
          </div>
        </div>
        {props.loading ? <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center"><div className="text-sm font-medium text-slate-700">Загружаю материалы</div><div className="mt-2 text-sm text-slate-500">Подтягиваю папки, доступы и покрытие клиентского бота.</div></div> : props.files.length === 0 ? <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center"><div className="text-sm font-medium text-slate-700">Материалов пока нет</div><div className="mt-2 text-sm text-slate-500">Загрузи файлы или создай папку, чтобы собрать новую структуру базы знаний.</div></div> : <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">{props.files.map((file) => props.viewMode === "compact" ? <div key={file.id} draggable onDragStart={(event) => { props.onDragStartFile(file.id); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(file.id)); }} onDragEnd={props.onDragEndFile} className={`transition ${props.selectedFileId === file.id ? "bg-sky-50" : "bg-white hover:bg-slate-50"}`}><div className="flex items-center gap-3 px-4 py-3"><input type="checkbox" checked={props.selectedFileIds.includes(file.id)} onChange={() => props.onToggleSelectedFile(file.id)} className="h-4 w-4 rounded border-slate-300 accent-sky-600" /><button type="button" onClick={() => props.onSelectFile(file.id)} className="grid min-w-0 flex-1 grid-cols-[minmax(0,1.8fr)_auto] items-center gap-3 text-left"><div className="min-w-0"><div className="truncate text-sm font-semibold text-slate-900">{file.filename}</div><div className="mt-0.5 truncate text-xs text-slate-500">{buildFolderPath(file.folder_id ?? null, props.folderMap)} · {file.uploaded_by_name || "Не указан"}</div></div><div className="flex items-center gap-2"><Badge tone={statusTone(file.status)}>{statusLabel(file.status)}</Badge>{renderVisibilityChip(file)}</div></button><button type="button" onClick={() => props.onPreviewFile(file.id)} className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:text-slate-700" aria-label="Открыть предпросмотр файла"><Eye className="h-4 w-4" /></button></div></div> : <div key={file.id} draggable onDragStart={(event) => { props.onDragStartFile(file.id); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(file.id)); }} onDragEnd={props.onDragEndFile} className={`transition ${props.selectedFileId === file.id ? "bg-sky-50/60" : "bg-white hover:bg-slate-50"}`}><div className="flex items-start gap-3 px-4 py-3"><input type="checkbox" checked={props.selectedFileIds.includes(file.id)} onChange={() => props.onToggleSelectedFile(file.id)} className="mt-1 h-4 w-4 rounded border-slate-300 accent-sky-600" /><button type="button" onClick={() => props.onSelectFile(file.id)} className="grid min-w-0 flex-1 grid-cols-[minmax(0,1.8fr)_auto] items-start gap-4 text-left"><div className="min-w-0"><div className="truncate text-[15px] font-semibold text-slate-900">{file.filename}</div><div className="mt-1 truncate text-sm text-slate-500">{buildFolderPath(file.folder_id ?? null, props.folderMap)}</div><div className="mt-2 text-xs text-slate-400">{fileTypeLabel(file)} · {file.uploaded_by_name || "Не указан"}{typeof file.query_count === "number" ? ` · ${file.query_count} запросов` : ""}</div></div><div className="flex flex-wrap items-center justify-end gap-2"><Badge tone={statusTone(file.status)}>{statusLabel(file.status)}</Badge>{renderVisibilityChip(file)}<span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500">{hasExplicitFileRules(file) ? "Исключение" : "Наследует"}</span></div></button><button type="button" onClick={() => props.onPreviewFile(file.id)} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:text-slate-700" aria-label="Открыть предпросмотр файла"><Eye className="h-4 w-4" /></button></div></div>)}</div>}
      </PanelBody>
    </Panel>
  );
}

function FolderOverview(props: { folder: KbFolder; folderMap: Map<number, KbFolder>; access: KbAclItem[]; coverage: KbAccessSummary; loading: boolean; groups: KbAccountGroup[] }) {
  return <div className="space-y-4"><OverviewLabel title="Обзор папки" /><div className="space-y-3"><div><div className="text-xl font-semibold text-slate-950">{props.folder.name}</div><div className="mt-1 text-sm text-slate-500">{buildFolderPath(props.folder.id, props.folderMap)}</div></div><AccessBadges target={props.folder} /><div className="border-t border-slate-200 pt-3"><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Сводка политики</div><div className="mt-2 text-sm font-medium text-slate-900">{folderPolicySummary(props.access, props.groups)}</div><div className="mt-2 text-sm leading-6 text-slate-500">{props.access.length ? "Папка задаёт доступ для всей ветки. Новые файлы наследуют эти правила, пока на них не создадут отдельное исключение." : "На папке нет собственных правил. Сейчас действует базовый доступ аккаунта."}</div></div><CoverageMiniList summary={props.coverage} loading={props.loading} /></div></div>;
}

function FileOverview(props: { file: KbFile; folderMap: Map<number, KbFolder>; access: KbAclItem[]; effectiveStaff: string; effectiveClient: string; loading: boolean; groups: KbAccountGroup[] }) {
  return <div className="space-y-4"><OverviewLabel title="Обзор файла" /><div className="space-y-3"><div><div className="text-xl font-semibold text-slate-950">{props.file.filename}</div><div className="mt-1 text-sm text-slate-500">{buildFolderPath(props.file.folder_id ?? null, props.folderMap)}</div></div><AccessBadges target={props.file} /><div className="border-t border-slate-200 pt-3"><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Режим файла</div><div className="mt-2 text-sm font-medium text-slate-900">{props.access.length ? "На файле задано исключение" : "Файл наследует политику папки"}</div><div className="mt-2 text-sm leading-6 text-slate-500">{props.access.length ? folderPolicySummary(props.access, props.groups) : "Рекомендуемый режим. Файл использует те же правила доступа, что и папка."}</div></div><div className="border-t border-slate-200 pt-3"><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Эффективный доступ</div>{props.loading ? <div className="mt-3 text-sm text-slate-500">Пересчитываю права...</div> : <div className="mt-3 flex flex-wrap gap-2"><Badge tone={effectiveAccessTone(props.effectiveStaff)}>Сотрудники: {effectiveAccessLabel(props.effectiveStaff)}</Badge><Badge tone={effectiveAccessTone(props.effectiveClient)}>Клиенты: {effectiveAccessLabel(props.effectiveClient)}</Badge></div>}</div></div></div>;
}

function FolderAccessShell(props: {
  folder: KbFolder;
  access: KbAclDraftItem[];
  groups: KbAccountGroup[];
  loading: boolean;
  staffGroups: KbAccountGroup[];
  clientGroups: KbAccountGroup[];
  templateStaffGroupId: number;
  templateClientGroupId: number;
  onTemplateStaffGroupIdChange: (value: number) => void;
  onTemplateClientGroupIdChange: (value: number) => void;
  onApplyTemplate: (template: KbTemplate) => void;
  onSave: () => void;
  saving: boolean;
  message: string;
}) {
  return (
    <div className="space-y-4">
      <OverviewLabel title="Доступ к папке" />
      <div className="space-y-4">
        <div className="rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-4"><div className="text-sm font-medium text-slate-900">Папка управляет доступом для всей ветки</div><div className="mt-2 text-sm leading-6 text-slate-500">Выбери готовый сценарий. Новые материалы в этой папке будут наследовать политику автоматически, пока ты не создашь отдельное исключение на файле.</div></div>
        <PolicyCards
          onPick={props.onApplyTemplate}
          activeSummary={folderPolicySummary(props.access, props.groups)}
        />
        {props.staffGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Группа сотрудников</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateStaffGroupId || props.staffGroups[0].id)}
                onChange={(value) => props.onTemplateStaffGroupIdChange(Number(value))}
                options={props.staffGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        {props.clientGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Клиентская группа</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateClientGroupId || props.clientGroups[0].id)}
                onChange={(value) => props.onTemplateClientGroupIdChange(Number(value))}
                options={props.clientGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        <ImpactCard text={props.loading ? "Загружаю текущую политику..." : folderPolicySummary(props.access, props.groups)} />
        {props.message ? <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">{props.message}</div> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3">
          <Button variant="primary" onClick={props.onSave} disabled={props.saving}>Сохранить политику</Button>
          <Button variant="secondary" onClick={() => props.onApplyTemplate("inherit")} disabled={props.saving}>Сбросить</Button>
        </div>
      </div>
    </div>
  );
}

function FileAccessShell(props: {
  file: KbFile;
  folderMap: Map<number, KbFolder>;
  access: KbAclDraftItem[];
  groups: KbAccountGroup[];
  loading: boolean;
  staffGroups: KbAccountGroup[];
  clientGroups: KbAccountGroup[];
  templateStaffGroupId: number;
  templateClientGroupId: number;
  onTemplateStaffGroupIdChange: (value: number) => void;
  onTemplateClientGroupIdChange: (value: number) => void;
  onApplyTemplate: (template: KbTemplate) => void;
  onSave: () => void;
  saving: boolean;
  message: string;
}) {
  return (
    <div className="space-y-4">
      <OverviewLabel title="Доступ к файлу" />
      <div className="space-y-4">
        <div className="rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-4">
          <div className="text-sm font-medium text-slate-900">{props.access.length ? "На файле уже есть исключение" : "Файл наследует правила папки"}</div>
          <div className="mt-2 text-sm leading-6 text-slate-500">Папка: {buildFolderPath(props.file.folder_id ?? null, props.folderMap)}</div>
          <div className="mt-2 text-sm leading-6 text-slate-500">{props.access.length ? "Этот файл уже выбивается из общей политики папки. Меняй правило только если файл действительно должен жить отдельно." : "Рекомендуемый режим. Старайся оставлять файл в наследовании, если нет отдельной причины задавать исключение."}</div>
        </div>
        <PolicyCards
          onPick={props.onApplyTemplate}
          includeInherit
          activeSummary={props.access.length ? folderPolicySummary(props.access, props.groups) : "Наследование от папки"}
        />
        {props.staffGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Группа сотрудников</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateStaffGroupId || props.staffGroups[0].id)}
                onChange={(value) => props.onTemplateStaffGroupIdChange(Number(value))}
                options={props.staffGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        {props.clientGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Клиентская группа</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateClientGroupId || props.clientGroups[0].id)}
                onChange={(value) => props.onTemplateClientGroupIdChange(Number(value))}
                options={props.clientGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        <ImpactCard text={props.loading ? "Загружаю исключение..." : props.access.length ? folderPolicySummary(props.access, props.groups) : "Файл останется в режиме наследования."} />
        {props.message ? <div className="text-sm text-slate-600">{props.message}</div> : null}
        <div className="flex items-center gap-3 border-t border-slate-200 pt-3">
          <Button variant="primary" onClick={props.onSave} disabled={props.saving}>Сохранить исключение</Button>
          <Button variant="secondary" onClick={() => props.onApplyTemplate("inherit")} disabled={props.saving}>Вернуть наследование</Button>
        </div>
      </div>
    </div>
  );
}

function BulkAccessShell(props: {
  selectedCount: number;
  draft: KbAclDraftItem[];
  groups: KbAccountGroup[];
  staffGroups: KbAccountGroup[];
  clientGroups: KbAccountGroup[];
  templateStaffGroupId: number;
  templateClientGroupId: number;
  onTemplateStaffGroupIdChange: (value: number) => void;
  onTemplateClientGroupIdChange: (value: number) => void;
  onApplyTemplate: (template: KbTemplate) => void;
  onSave: () => void;
  saving: boolean;
  message: string;
}) {
  return (
    <div className="space-y-4">
      <OverviewLabel title="Массовый доступ" />
      <div className="space-y-4">
        <div className="rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-4"><div className="text-sm font-medium text-slate-900">Массовое изменение доступа</div><div className="mt-2 text-sm leading-6 text-slate-500">Изменения применятся ко всем выбранным файлам: {props.selectedCount}. Используй этот режим, когда нужно быстро привести материалы к одной политике.</div></div>
        <PolicyCards onPick={props.onApplyTemplate} includeInherit activeSummary={props.draft.length ? folderPolicySummary(props.draft, props.groups) : "Наследование от папок"} />
        {props.staffGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Группа сотрудников</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateStaffGroupId || props.staffGroups[0].id)}
                onChange={(value) => props.onTemplateStaffGroupIdChange(Number(value))}
                options={props.staffGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        {props.clientGroups.length ? (
          <div className="border-t border-slate-200 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Клиентская группа</div>
            <div className="mt-2">
              <SelectBox
                value={String(props.templateClientGroupId || props.clientGroups[0].id)}
                onChange={(value) => props.onTemplateClientGroupIdChange(Number(value))}
                options={props.clientGroups.map((group) => ({ value: String(group.id), label: group.name }))}
              />
            </div>
          </div>
        ) : null}
        <ImpactCard text={props.draft.length ? folderPolicySummary(props.draft, props.groups) : "Файлы будут использовать наследование от своих папок."} />
        {props.message ? <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">{props.message}</div> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3">
          <Button variant="primary" onClick={props.onSave} disabled={props.saving}>Применить ко всем</Button>
          <Button variant="secondary" onClick={() => props.onApplyTemplate("inherit")} disabled={props.saving}>Сбросить</Button>
        </div>
      </div>
    </div>
  );
}

function PolicyCards(props: { onPick: (template: KbTemplate) => void; activeSummary?: string; includeInherit?: boolean }) {
  const cards = [
    ...(props.includeInherit ? ([["inherit", "Наследовать", "Файл или папка будут использовать базовые правила без собственных исключений."]] as const) : []),
    ["staff", "Общие материалы", "Все сотрудники могут искать и открывать материалы в этой ветке."],
    ["group", "Только отдел", "Доступ получает только выбранная группа сотрудников."],
    ["clients", "Только клиенты", "Материалы открываются всем клиентам через клиентский бот."],
    ["client_group", "Только клиентская группа", "Доступ получает одна выбранная группа клиентов."],
    ["staff_clients", "Сотрудники и клиенты", "Материалы доступны обеим аудиториям."],
  ] as const;
  return (
    <div className="space-y-3">
      {props.activeSummary ? <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">Сейчас: <span className="font-medium text-slate-900">{props.activeSummary}</span></div> : null}
      {cards.map(([value, title, body]) => (
        <button key={value} type="button" onClick={() => props.onPick(value as KbTemplate)} className="block w-full rounded-[20px] border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-sky-300 hover:bg-sky-50">
          <div className="text-sm font-medium text-slate-900">{title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">{body}</div>
        </button>
      ))}
    </div>
  );
}

function ImpactCard(props: { text: string }) {
  return <div className="rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-4"><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">Влияние</div><div className="mt-2 text-sm leading-6 text-amber-900">{props.text || "Изменение повлияет на поиск и клиентский бот сразу после сохранения."}</div></div>;
}

function EmptyInspector() {
  return <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-5 py-10"><div className="text-sm font-medium text-slate-700">Выбери папку или файл</div><div className="mt-2 text-sm leading-6 text-slate-500">Здесь появятся свойства, доступ и влияние на клиентский бот.</div></div>;
}

function OverviewLabel(props: { title: string }) {
  return <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{props.title}</div>;
}

function CoverageMiniList(props: { summary: KbAccessSummary; loading: boolean }) {
  return <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4"><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Покрытие клиентского бота</div>{props.loading ? <div className="mt-3 text-sm text-slate-500">Загружаю покрытие...</div> : <div className="mt-3 grid gap-3 md:grid-cols-2"><MiniStat title="Готово" value={props.summary.total_ready_files} /><MiniStat title="Всем клиентам" value={props.summary.open_all_clients} /><MiniStat title="Клиентским группам" value={props.summary.open_client_groups} /><MiniStat title="Закрыто" value={props.summary.closed_for_clients} /></div>}</div>;
}

function MiniStat(props: { title: string; value: number }) {
  return <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3"><div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">{props.title}</div><div className="mt-2 text-xl font-semibold text-slate-950">{props.value}</div></div>;
}

function SelectBox(props: { value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }>; className?: string }) {
  return <select value={props.value} onChange={(event) => props.onChange(event.target.value)} className={`min-w-[132px] rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-700 outline-none transition hover:border-slate-300 ${props.className || ""}`}>{props.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>;
}
function AccessBadges(props: { target: { access_badges?: { staff?: string; client?: string } } }) {
  const staff = accessBadgeMeta("staff", props.target.access_badges?.staff);
  const client = accessBadgeMeta("client", props.target.access_badges?.client);
  return <><Badge tone={staff.tone}>{staff.label}</Badge><Badge tone={client.tone}>{client.label}</Badge></>;
}

function renderVisibilityChip(file: KbFile) {
  const client = String(file.access_badges?.client || "client_closed");
  if (client === "client_all") return <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">Открыт клиентам</span>;
  if (client === "client_groups") return <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">Группы клиентов</span>;
  return <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">Без клиентов</span>;
}

function CompactAccessBadges(props: { target: { access_badges?: { staff?: string; client?: string } }; selected?: boolean; onClick?: (event: MouseEvent<HTMLButtonElement>) => void }) {
  const client = accessBadgeMeta("client", props.target.access_badges?.client);
  return (
    <>
      <button type="button" onClick={props.onClick} className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${props.selected ? "border-sky-200 bg-white text-sky-700" : compactTone(client.tone)}`}>{client.shortLabel}</button>
    </>
  );
}

function FolderDialog(props: { state: FolderDialogState; folderMap: Map<number, KbFolder>; onOpenChange: (open: boolean) => void; onNameChange: (name: string) => void; onSubmit: () => void }) {
  const title = !props.state.open ? "" : props.state.mode === "create" ? "Новая папка" : "Переименовать папку";
  const parentPath = !props.state.open || props.state.mode !== "create" ? "" : props.state.parentId != null ? buildFolderPath(props.state.parentId, props.folderMap) : "Корень базы знаний";
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-semibold text-slate-950">{title}</Dialog.Title>
              {props.state.open && props.state.mode === "create" ? <Dialog.Description className="mt-2 text-sm text-slate-500">Родительская папка: {parentPath}</Dialog.Description> : null}
            </div>
            <Dialog.Close asChild><button type="button" className="rounded-xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50"><X className="h-4 w-4" /></button></Dialog.Close>
          </div>
          <div className="mt-5">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Название</div>
            <input
              value={props.state.open ? props.state.name : ""}
              onChange={(event) => props.onNameChange(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-sky-300"
              placeholder="Например, Продажи / Скрипты"
            />
          </div>
          <div className="mt-6 flex items-center gap-3">
            <Button variant="primary" onClick={props.onSubmit}>Сохранить</Button>
            <Button variant="secondary" onClick={() => props.onOpenChange(false)}>Отмена</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ConfirmDialog(props: { state: DeleteDialogState; confirmLabel: string; onOpenChange: (open: boolean) => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <Dialog.Title className="text-xl font-semibold text-slate-950">{props.state.open ? props.state.title : ""}</Dialog.Title>
          <Dialog.Description className="mt-3 text-sm leading-6 text-slate-500">{props.state.open ? props.state.body : ""}</Dialog.Description>
          <div className="mt-6 flex items-center gap-3">
            <Button variant="danger" onClick={props.onConfirm}>{props.confirmLabel}</Button>
            <Button variant="secondary" onClick={() => props.onOpenChange(false)}>Отмена</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function MoveConfirmDialog(props: { state: MoveDialogState; onOpenChange: (open: boolean) => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <Dialog.Title className="text-xl font-semibold text-slate-950">{props.state.open ? props.state.title : ""}</Dialog.Title>
          <Dialog.Description className="mt-3 text-sm leading-6 text-slate-500">{props.state.open ? props.state.body : ""}</Dialog.Description>
          <div className="mt-6 flex items-center gap-3">
            <Button variant="primary" onClick={props.onConfirm}>Переместить</Button>
            <Button variant="secondary" onClick={() => props.onOpenChange(false)}>Отмена</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function UploadMethodDialog(props: {
  state: UploadDialogState;
  onOpenChange: (open: boolean) => void;
  onPickFile: () => void;
  onPickUrl: () => void;
  onBack: () => void;
  onUrlChange: (value: string) => void;
  onSubmitUrl: () => void;
}) {
  return (
    <Dialog.Root open={props.state.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(620px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-semibold text-slate-950">Как добавить материал</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm leading-6 text-slate-500">
                Загрузи файл с компьютера или добавь ссылку на документ, видео или другую поддерживаемую страницу.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button type="button" className="rounded-xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50"><X className="h-4 w-4" /></button>
            </Dialog.Close>
          </div>
          {props.state.mode === "choose" ? (
            <div className="mt-6 grid gap-3 md:grid-cols-2">
              <button type="button" onClick={props.onPickFile} className="rounded-[24px] border border-slate-200 bg-white px-5 py-5 text-left transition hover:border-sky-300 hover:bg-sky-50">
                <div className="text-sm font-semibold text-slate-900">С компьютера</div>
                <div className="mt-2 text-sm leading-6 text-slate-500">Документы, таблицы, презентации, аудио и видео загружаются напрямую в базу знаний.</div>
              </button>
              <button type="button" onClick={props.onPickUrl} className="rounded-[24px] border border-slate-200 bg-white px-5 py-5 text-left transition hover:border-sky-300 hover:bg-sky-50">
                <div className="text-sm font-semibold text-slate-900">По ссылке</div>
                <div className="mt-2 text-sm leading-6 text-slate-500">Подходит для Google Docs, видео и других поддерживаемых страниц, которые нужно добавить как источник.</div>
              </button>
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Ссылка</div>
                <input
                  value={props.state.url}
                  onChange={(event) => props.onUrlChange(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-sky-300"
                  placeholder="https://docs.google.com/... или https://youtube.com/..."
                />
                <div className="mt-2 text-sm text-slate-500">После добавления материал появится в базе знаний, когда закончится обработка.</div>
              </div>
              {props.state.message ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{props.state.message}</div> : null}
              <div className="flex items-center gap-3">
                <Button variant="primary" onClick={props.onSubmitUrl} disabled={props.state.saving}>{props.state.saving ? "Добавляю..." : "Добавить ссылку"}</Button>
                <Button variant="secondary" onClick={props.onBack} disabled={props.state.saving}>Назад</Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function OnboardingDialog(props: { open: boolean; step: number; onOpenChange: (open: boolean) => void; onNext: () => void; onPrev: () => void }) {
  const step = ONBOARDING_STEPS[props.step];
  return (
    <Dialog.Root open={props.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/45 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 grid w-[min(960px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 gap-0 overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-[0_24px_90px_rgba(15,23,42,0.28)] md:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-6 p-8">
            <div className="flex items-center justify-between"><div><div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Шаг {props.step + 1} из {ONBOARDING_STEPS.length}</div><Dialog.Title className="mt-3 text-[28px] font-semibold leading-tight text-slate-950">{step.title}</Dialog.Title></div><Dialog.Close asChild><button className="rounded-xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50" type="button"><X className="h-4 w-4" /></button></Dialog.Close></div>
            <Dialog.Description className="text-[15px] leading-7 text-slate-600">{step.body}</Dialog.Description>
            <div className="flex items-center gap-3"><Button variant="secondary" onClick={() => props.onOpenChange(false)}>Напомнить позже</Button><div className="ml-auto flex items-center gap-3"><Button variant="ghost" onClick={props.onPrev} disabled={props.step === 0}>Назад</Button><Button variant="primary" onClick={props.onNext} disabled={props.step === ONBOARDING_STEPS.length - 1}>Дальше</Button></div></div>
          </div>
          <div className="border-l border-slate-200 bg-[linear-gradient(180deg,#f8fbff_0%,#eef5ff_100%)] p-8"><div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_10px_40px_rgba(15,23,42,0.08)]"><div className="flex items-center gap-2 text-sm font-medium text-slate-900"><PlayCircle className="h-4 w-4 text-sky-600" /> {step.mediaTitle}</div><div className="mt-4 flex aspect-[16/10] items-center justify-center rounded-[24px] border border-dashed border-slate-200 bg-slate-50 text-center text-sm text-slate-400">Слот под GIF или короткое видео</div><div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">Здесь можно показывать короткий сценарий: открытие папки, смену политики, влияние на клиентский бот.</div></div></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function KnowledgeInfoDialog(props: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog.Root open={props.open} onOpenChange={props.onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/30 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(720px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.20)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Справка</div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">Как устроена база знаний</div>
            </div>
            <Dialog.Close asChild>
              <button type="button" className="rounded-full border border-slate-200 p-2 text-slate-500 transition hover:border-slate-300 hover:text-slate-700"><X className="h-4 w-4" /></button>
            </Dialog.Close>
          </div>
          <div className="mt-5 space-y-4 text-sm leading-7 text-slate-600">
            <div>
              <div className="font-medium text-slate-900">Папки задают доступ</div>
              <div className="mt-1">Права лучше настраивать на папке. Новые файлы внутри папки автоматически наследуют её политику.</div>
            </div>
            <div>
              <div className="font-medium text-slate-900">Покрытие клиентского бота</div>
              <div className="mt-1">Показывает, сколько материалов бот может использовать для клиентов: всем клиентам, только клиентским группам или никому.</div>
            </div>
            <div>
              <div className="font-medium text-slate-900">Исключения на файлах</div>
              <div className="mt-1">Если файл должен жить не по правилам папки, для него создаётся отдельное исключение. Используй это редко.</div>
            </div>
            <div className="rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Легенда бейджей</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="emerald">Открыт клиентам</Badge>
                <Badge tone="sky">Группы клиентов</Badge>
                <Badge tone="neutral">Без клиентов</Badge>
                <Badge tone="emerald">Готово</Badge>
                <Badge tone="amber">Исключение</Badge>
                <Badge tone="neutral">Наследует</Badge>
              </div>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function PreviewDialog(props: { file: KbFile | null; inlineUrl: string | null; downloadUrl: string | null; loading: boolean; onClose: () => void; onRetry: () => void }) {
  if (!props.file) return null;
  const ext = fileExt(props.file.filename);
  const baseSrc = props.inlineUrl || "";
  const sourceKind = String(props.file.source_type || "").toLowerCase();
  const isExternal = ["youtube", "rutube", "vk"].includes(sourceKind) && !!String(props.file.source_url || "").trim();
  const externalEmbedUrl = buildExternalEmbedUrl(props.file.source_url);
  const officeSrc = buildOfficeViewerUrl(baseSrc);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6" onClick={props.onClose}>
      <div className="flex h-[85vh] w-[92vw] max-w-6xl flex-col rounded-2xl bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0 truncate text-sm font-semibold text-slate-900">{props.file.filename}</div>
          <div className="flex items-center gap-2">
            {props.downloadUrl ? <a className="rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-700" href={props.downloadUrl} target="_blank" rel="noreferrer">Скачать</a> : null}
            <button className="rounded-lg border border-slate-200 px-3 py-1 text-sm" onClick={props.onClose}>Закрыть</button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-slate-50 p-3">
          {props.loading ? <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Загрузка файла...</div> : null}
          {!props.loading && isExternal ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
              {externalEmbedUrl ? <iframe title={props.file.filename || "external-video"} src={externalEmbedUrl} className="h-[64vh] w-full rounded-xl border border-slate-200 bg-white" allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen /> : <div>Встроенный плеер недоступен для этого источника.</div>}
              {props.file.source_url ? <a className="mt-3 inline-block rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-700" href={props.file.source_url} target="_blank" rel="noreferrer">Открыть источник</a> : null}
            </div>
          ) : null}
          {!props.loading && !isExternal && !baseSrc ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
              Не удалось получить файл для предпросмотра.
              <button className="ml-3 rounded-lg border border-slate-200 px-3 py-1 text-sm" onClick={props.onRetry}>Повторить</button>
            </div>
          ) : null}
          {!props.loading && !!baseSrc && ext === ".pdf" ? <iframe title={props.file.filename} src={baseSrc} className="h-full min-h-[70vh] w-full rounded-xl border border-slate-200 bg-white" /> : null}
          {!props.loading && !!baseSrc && [".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext) ? <img src={baseSrc} alt={props.file.filename} className="mx-auto max-h-full max-w-full rounded-xl border border-slate-200 bg-white" /> : null}
          {!props.loading && !!baseSrc && [".mp4", ".mov", ".avi", ".mkv", ".webm"].includes(ext) ? <video key={baseSrc} src={baseSrc} controls autoPlay className="h-full min-h-[70vh] w-full rounded-xl border border-slate-200 bg-black" /> : null}
          {!props.loading && !!baseSrc && [".mp3", ".ogg", ".wav", ".m4a", ".aac"].includes(ext) ? <div className="rounded-xl border border-slate-200 bg-white p-6"><audio key={baseSrc} src={baseSrc} controls autoPlay className="w-full" /></div> : null}
          {!props.loading && !!baseSrc && [".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".rtf"].includes(ext) ? (officeSrc ? <iframe title={props.file.filename} src={officeSrc} className="h-full min-h-[70vh] w-full rounded-xl border border-slate-200 bg-white" /> : <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Не удалось сформировать предпросмотр Office-документа. Используй скачивание.</div>) : null}
          {!props.loading && !!baseSrc && [".txt", ".csv", ".md", ".epub", ".fb2", ".html", ".htm", ".json", ".xml", ".yaml", ".yml", ".ini", ".toml", ".log"].includes(ext) ? <iframe title={props.file.filename} src={baseSrc} className="h-full min-h-[70vh] w-full rounded-xl border border-slate-200 bg-white" /> : null}
          {!props.loading && !!baseSrc && !isInlinePreviewable(props.file.filename) ? <div className="rounded-xl border border-slate-200 bg-white p-6"><div className="text-sm text-slate-600">Для этого типа файла предпросмотр недоступен.</div>{props.downloadUrl ? <a className="mt-3 inline-block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700" href={props.downloadUrl} target="_blank" rel="noreferrer">Скачать файл</a> : null}</div> : null}
        </div>
      </div>
    </div>
  );
}
