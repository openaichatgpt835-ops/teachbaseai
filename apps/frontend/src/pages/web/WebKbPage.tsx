
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";
import { useLocation } from "react-router-dom";

type KbFile = {
  id: number;
  filename: string;
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
};

type KbCollection = { id: number; name: string; color?: string; file_count?: number };
type KbSmartFolder = { id: number; name: string; system_tag?: string; rules?: any };
type KbTopic = { id: string; name: string; count: number; file_ids: number[] };
type SearchMatch = {
  file_id: number;
  filename?: string;
  snippet?: string;
  chunk_index?: number | null;
  page_num?: number | null;
  start_ms?: number | null;
};
type Filter = { kind: "all" | "collection" | "smart" | "topic"; id?: number | string };
type KbPageCacheState = {
  kbFiles: KbFile[];
  kbCollections: KbCollection[];
  kbCollectionFiles: Record<number, number[]>;
  kbSmartFolders: KbSmartFolder[];
  kbTopics: KbTopic[];
  kbTopicSuggestions: { id: string; name: string; count: number }[];
  kbFilter: Filter;
  smartFoldersOpen: boolean;
  kbSort: "new" | "name" | "status";
  kbTypeFilter: string;
  kbPeopleFilter: string;
  kbLocationFilter: string;
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
  const [kbCollections, setKbCollections] = useState<KbCollection[]>(cached?.kbCollections || []);
  const [kbCollectionFiles, setKbCollectionFiles] = useState<Record<number, number[]>>(cached?.kbCollectionFiles || {});
  const [kbSmartFolders, setKbSmartFolders] = useState<KbSmartFolder[]>(cached?.kbSmartFolders || []);
  const [kbTopics, setKbTopics] = useState<KbTopic[]>(cached?.kbTopics || []);
  const [kbTopicSuggestions, setKbTopicSuggestions] = useState<{ id: string; name: string; count: number }[]>(cached?.kbTopicSuggestions || []);
  const [kbTopicsThreshold, setKbTopicsThreshold] = useState<number>(5);
  const [kbTopicsLoadError, setKbTopicsLoadError] = useState("");
  const [kbFilter, setKbFilter] = useState<Filter>(cached?.kbFilter || { kind: "all" });
  const [newCollectionName, setNewCollectionName] = useState("");
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
  const [kbLocationFilter, setKbLocationFilter] = useState(cached?.kbLocationFilter || "all");
  const [kbViewMode, setKbViewMode] = useState<"table" | "grid">(cached?.kbViewMode || "table");

  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [dragOverCollectionId, setDragOverCollectionId] = useState<number | null>(null);
  const [draggedFileId, setDraggedFileId] = useState<number | null>(null);
  const [openFileMenuId, setOpenFileMenuId] = useState<number | null>(null);
  const [contextMenu, setContextMenu] = useState<{ id: number; x: number; y: number } | null>(null);
  const [focusedRowId, setFocusedRowId] = useState<number | null>(null);
  const [lastSelectedId, setLastSelectedId] = useState<number | null>(null);
  const [dragSelectBox, setDragSelectBox] = useState<{ x: number; y: number; w: number; h: number; active: boolean } | null>(null);
  const [kbUploadMessage, setKbUploadMessage] = useState("");
  const [focusApplied, setFocusApplied] = useState(false);
  const [previewFileId, setPreviewFileId] = useState<number | null>(null);
  const [previewStartMs, setPreviewStartMs] = useState<number | null>(null);
  const [previewPage, setPreviewPage] = useState<number | null>(null);
  const [previewInlineUrl, setPreviewInlineUrl] = useState<string | null>(null);
  const [previewDownloadUrl, setPreviewDownloadUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const loadFiles = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files`);
    const data = await res.json().catch(() => null);
    if (res.ok && Array.isArray(data?.items)) setKbFiles(data.items);
  };

  const loadCollections = async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/collections`);
    const data = await res.json().catch(() => null);
    if (res.ok && Array.isArray(data?.items)) {
      setKbCollections(data.items);
      const mapping: Record<number, number[]> = {};
      for (const c of data.items) {
        const filesRes = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/collections/${c.id}/files`);
        const filesData = await filesRes.json().catch(() => null);
        mapping[c.id] = Array.isArray(filesData?.file_ids)
          ? filesData.file_ids.map((x: any) => Number(x)).filter((x: number) => Number.isFinite(x))
          : [];
      }
      setKbCollectionFiles(mapping);
    }
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

  useEffect(() => {
    if (portalId) {
      const state = kbPageCache.get(portalId);
      if (state) {
        setKbFiles(state.kbFiles || []);
        setKbCollections(state.kbCollections || []);
        setKbCollectionFiles(state.kbCollectionFiles || {});
        setKbSmartFolders(state.kbSmartFolders || []);
        setKbTopics(state.kbTopics || []);
        setKbTopicSuggestions(state.kbTopicSuggestions || []);
        setKbFilter(state.kbFilter || { kind: "all" });
        setSmartFoldersOpen(state.smartFoldersOpen ?? true);
        setKbSort(state.kbSort || "new");
        setKbTypeFilter(state.kbTypeFilter || "all");
        setKbPeopleFilter(state.kbPeopleFilter || "all");
        setKbLocationFilter(state.kbLocationFilter || "all");
        setKbViewMode(state.kbViewMode || "table");
      }
    }
    loadFiles();
    loadCollections();
    loadSmartFolders();
    loadTopics();
  }, [portalId, portalToken]);

  useEffect(() => {
    setFocusApplied(false);
  }, [location.search]);

  useEffect(() => {
    if (!portalId) return;
    kbPageCache.set(portalId, {
      kbFiles,
      kbCollections,
      kbCollectionFiles,
      kbSmartFolders,
      kbTopics,
      kbTopicSuggestions,
      kbFilter,
      smartFoldersOpen,
      kbSort,
      kbTypeFilter,
      kbPeopleFilter,
      kbLocationFilter,
      kbViewMode,
    });
  }, [
    portalId,
    kbFiles,
    kbCollections,
    kbCollectionFiles,
    kbSmartFolders,
    kbTopics,
    kbTopicSuggestions,
    kbFilter,
    smartFoldersOpen,
    kbSort,
    kbTypeFilter,
    kbPeopleFilter,
    kbLocationFilter,
    kbViewMode,
  ]);

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
    if (kbLocationFilter !== "all") {
      const ids = kbCollectionFiles[Number(kbLocationFilter)] || [];
      items = items.filter((x) => ids.includes(x.id));
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
    if (kbFilter.kind === "collection" && kbFilter.id) {
      const ids = kbCollectionFiles[Number(kbFilter.id)] || [];
      items = items.filter((x) => ids.includes(x.id));
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
  }, [kbFiles, kbSearch, kbSearchResults, kbTypeFilter, kbPeopleFilter, kbLocationFilter, kbFilter, kbCollectionFiles, kbTopics, kbSmartFolders, selectedFileIds]);

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
      if (kbFilter.kind === "collection" && kbFilter.id) scopeParams.set("collection_ids", String(kbFilter.id));
      if (kbFilter.kind === "smart" && kbFilter.id) scopeParams.set("smart_folder_ids", String(kbFilter.id));
      if (kbFilter.kind === "topic" && kbFilter.id) scopeParams.set("topic_ids", String(kbFilter.id));
      if (kbLocationFilter !== "all") scopeParams.set("collection_ids", kbLocationFilter);
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: q,
        scope: selectedFileIds.length > 0
          ? { file_ids: selectedFileIds }
          : {
              collection_ids: kbFilter.kind === "collection" && kbFilter.id ? [Number(kbFilter.id)] : (kbLocationFilter !== "all" ? [Number(kbLocationFilter)] : undefined),
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
    setSmartSearchAnswer(data?.answer || "");
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
    if (kind === "collection" && id) setKbLocationFilter(String(id));
    if (kind !== "collection") setKbLocationFilter("all");
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

  const createCollection = async () => {
    if (!portalId || !portalToken) return;
    const name = newCollectionName.trim();
    if (!name) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color: null }),
    });
    if (res.ok) {
      setNewCollectionName("");
      await loadCollections();
    }
  };

  const onDragEnterCollection = (id: number) => setDragOverCollectionId(id);
  const onDragLeaveCollection = (id: number) => setDragOverCollectionId((prev) => (prev === id ? null : prev));

  const onDropToCollection = async (collectionId: number, evt: React.DragEvent) => {
    evt.preventDefault();
    setDragOverCollectionId(null);
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
    for (const fileId of ids) {
      await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/collections/${collectionId}/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId }),
      });
    }
    await loadCollections();
  };

  const fileCollections = (fileId: number) => {
    const out: { id: number; name: string; color?: string }[] = [];
    kbCollections.forEach((c) => {
      const ids = kbCollectionFiles[c.id] || [];
      if (ids.includes(fileId)) out.push({ id: c.id, name: c.name, color: c.color });
    });
    return out;
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
    await loadCollections();
    await loadTopics();
  };

  const bulkReindexFiles = async () => {
    for (const id of selectedFileIds) await reindexFile(id);
    setSelectedFileIds([]);
  };

  const bulkDeleteFiles = async () => {
    for (const id of selectedFileIds) await deleteFile(id);
    setSelectedFileIds([]);
  };

  const bulkMoveToCollection = async (evt: React.ChangeEvent<HTMLSelectElement>) => {
    const value = evt.target.value;
    if (!value) return;
    const collectionId = Number(value);
    for (const id of selectedFileIds) {
      await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/collections/${collectionId}/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: id }),
      });
    }
    await loadCollections();
    setSelectedFileIds([]);
    evt.target.value = "";
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
      await loadCollections();
      await loadTopics();
      return;
    }
    setKbUploadMessage(okCount > 0 ? `Файлы загружены: ${okCount}` : "Ошибка загрузки");
    await loadFiles();
    await loadCollections();
    await loadTopics();
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

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
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
          } ${dragOverCollectionId === 0 ? "ring-2 ring-sky-200" : ""}`}
          onClick={() => selectKbFilter("all")}
          onDragEnter={() => onDragEnterCollection(0)}
          onDragLeave={() => onDragLeaveCollection(0)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => onDropToCollection(0, e)}
        >
          Все файлы
        </button>

        <div className="mt-5">
          <div className="text-xs uppercase tracking-wide text-slate-400">Папки</div>
          <div className="mt-2 space-y-1">
            {kbCollections.map((c) => (
              <button
                key={c.id}
                className={`w-full flex items-center justify-between rounded-xl px-3 py-2 text-sm ${
                  kbFilter.kind === "collection" && kbFilter.id === c.id
                    ? "bg-sky-50 text-sky-700"
                    : "text-slate-600 hover:bg-slate-50"
                } ${dragOverCollectionId === c.id ? "ring-2 ring-sky-200" : ""}`}
                onClick={() => selectKbFilter("collection", c.id)}
                onDragEnter={() => onDragEnterCollection(c.id)}
                onDragLeave={() => onDragLeaveCollection(c.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropToCollection(c.id, e)}
              >
                <span className="flex items-center gap-2">
                  {c.name}
                </span>
                <span className="text-xs text-slate-400">{c.file_count || kbCollectionFiles[c.id]?.length || 0}</span>
              </button>
            ))}
            {kbCollections.length === 0 && <div className="text-xs text-slate-400">Папок пока нет.</div>}
          </div>
          <div className="mt-3 space-y-2">
            <input
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="Новая папка"
              value={newCollectionName}
              onChange={(e) => setNewCollectionName(e.target.value)}
            />
            <button className="w-full rounded-xl bg-sky-600 px-3 py-2 text-sm font-semibold text-white" onClick={createCollection}>
              Создать
            </button>
            <div className="text-xs text-slate-400">Подпапки пока не поддерживаются.</div>
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
          <h2 className="text-lg font-semibold text-slate-900">Добро пожаловать в базу знаний</h2>
          <p className="text-sm text-slate-500 mt-1">Управляйте документами и доступами в едином пространстве.</p>
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
            <select className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbLocationFilter} onChange={(e) => setKbLocationFilter(e.target.value)}>
              <option value="all">Местоположение: все</option>
              {kbCollections.map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
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
                  <div>{fileCollections(f.id)[0]?.name || "Корень"}</div>
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
                  <select className="shrink-0 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" onChange={bulkMoveToCollection}>
                    <option value="">Переместить в папку</option>
                    {kbCollections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <button className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm" onClick={bulkReindexFiles}>Переиндексировать</button>
                  <button className="shrink-0 rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-600" onClick={bulkDeleteFiles}>Удалить</button>
                  <button className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm" onClick={() => setSelectedFileIds([])}>Снять выделение</button>
                </div>
              ) : (
                <div className="text-sm font-semibold text-slate-900">Файлы</div>
              )}
            </div>
          </div>

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
                      setFocusedRowId(f.id);
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
                    </label>
                    <div className="truncate text-slate-600">{fileOwnerLabel(f)}</div>
                    <div className="truncate text-slate-600">{fileCollections(f.id)[0]?.name || "Корень"}</div>
                    <div className="text-[11px] rounded-full px-2 py-0.5 bg-slate-100 text-slate-600 w-fit">{fileStatusLabel(f.status)}</div>
                    <div className="relative flex items-center justify-end gap-2">
                      <button className="opacity-0 group-hover:opacity-100 text-xs text-slate-500 hover:text-slate-900" title="Поделиться">
                        Поделиться
                      </button>
                      <button
                        className="opacity-0 group-hover:opacity-100 text-xs text-slate-500 hover:text-slate-900"
                        title="Переместить"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFocusedRowId(f.id);
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
                    <button className="text-slate-400" onClick={(e) => { e.stopPropagation(); toggleFileMenu(f.id); }}>⋮</button>
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
                  <div className="mt-1 text-xs text-slate-500">{fileOwnerLabel(f)}</div>
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
    </div>
  );
}
