import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { fetchPortal, getWebPortalInfo, getWebUser } from "./auth";

type ChatSource = {
  file_id?: number | null;
  filename?: string;
  mime_type?: string;
  source_type?: string;
  source_url?: string;
  page_num?: number | null;
  start_ms?: number | null;
  end_ms?: number | null;
  chunk_index?: number | null;
  text?: string;
};

type ChatMsg = {
  role: "user" | "assistant";
  text: string;
  ts: number;
  sources?: ChatSource[];
};

type FileChunk = {
  id: number;
  chunk_index: number;
  text: string;
  start_ms?: number | null;
  end_ms?: number | null;
  page_num?: number | null;
};

function chatStorageKey(portalId: number) {
  const email = (getWebUser()?.email || "").trim().toLowerCase() || "anonymous";
  return `tb_web_chat_history:${portalId}:${email}`;
}

function chatScrollKey(portalId: number) {
  const email = (getWebUser()?.email || "").trim().toLowerCase() || "anonymous";
  return `tb_web_chat_scroll:${portalId}:${email}`;
}

function fileExt(name: string | undefined) {
  const n = (name || "").toLowerCase();
  if (!n.includes(".")) return "";
  return `.${n.split(".").pop() || ""}`;
}

function fmtMs(ms?: number | null) {
  const total = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function buildTimedExternalUrl(source: ChatSource): string {
  const url = (source.source_url || "").trim();
  if (!url) return "";
  const sec = source.start_ms ? Math.max(0, Math.floor(Number(source.start_ms) / 1000)) : 0;
  if (sec <= 0) return url;
  try {
    const u = new URL(url);
    const h = u.hostname.toLowerCase();
    if (h.includes("youtube.com") || h.includes("youtu.be")) {
      if (u.hostname.toLowerCase().includes("youtu.be")) u.searchParams.set("t", String(sec));
      else u.searchParams.set("start", String(sec));
      return u.toString();
    }
    if (h.includes("rutube") || h.includes("vk.com") || h.includes("vkvideo")) {
      u.searchParams.set("t", String(sec));
      return u.toString();
    }
    u.searchParams.set("t", String(sec));
    return u.toString();
  } catch {
    return url;
  }
}

function buildExternalEmbedUrl(source: ChatSource): string {
  const raw = (source.source_url || "").trim();
  if (!raw) return "";
  const sec = source.start_ms ? Math.max(0, Math.floor(Number(source.start_ms) / 1000)) : 0;
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

function _tokens(text: string): string[] {
  return (text || "")
    .toLowerCase()
    .replace(/[^a-zа-я0-9ё\s]/gi, " ")
    .split(/\s+/)
    .filter((t) => t.length >= 4);
}

function _lineRefIndexes(line: string, sources: ChatSource[]): number[] {
  const lt = new Set(_tokens(line));
  if (!lt.size || !sources.length) return [];
  const scored = sources
    .map((s, idx) => {
      const st = _tokens(s.text || s.filename || "");
      let score = 0;
      for (const t of st) if (lt.has(t)) score += 1;
      return { idx, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || a.idx - b.idx)
    .slice(0, 3)
    .map((x) => x.idx);
  return scored;
}

function lineRefsMap(answer: string, sources: ChatSource[]): Map<number, number[]> {
  const lines = String(answer || "").split("\n");
  const hasList = lines.some((l) => /^\s*(\d+[\)\.]|[-*•])\s+/.test(l.trim()));
  const out = new Map<number, number[]>();
  let fallback = 0;
  lines.forEach((line, i) => {
    const t = line.trim();
    if (!t) return;
    const eligible = hasList ? /^\s*(\d+[\)\.]|[-*•])\s+/.test(t) : true;
    if (!eligible) return;
    let refs = _lineRefIndexes(t, sources);
    if (!refs.length && sources.length) {
      refs = [fallback % sources.length];
      fallback += 1;
    }
    out.set(i, refs);
  });
  return out;
}

export function WebChatPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [previewSource, setPreviewSource] = useState<ChatSource | null>(null);
  const [previewChunks, setPreviewChunks] = useState<FileChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [selectedChunkIdx, setSelectedChunkIdx] = useState<number | null>(null);
  const [pdfPage, setPdfPage] = useState<number | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const listRef = useRef<HTMLDivElement | null>(null);
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const chunkRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  const scrollToBottomPersist = () => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (!listRef.current) return;
        listRef.current.scrollTop = listRef.current.scrollHeight;
        if (portalId) localStorage.setItem(chatScrollKey(portalId), String(listRef.current.scrollTop));
      });
    });
  };

  useEffect(() => {
    if (!portalId) return;
    try {
      const raw = localStorage.getItem(chatStorageKey(portalId));
      const parsed = raw ? JSON.parse(raw) : [];
      setMessages(Array.isArray(parsed) ? parsed : []);
    } catch {
      setMessages([]);
    }
  }, [portalId]);

  useEffect(() => {
    if (!previewSource) return;
    if (selectedChunkIdx == null) return;
    window.setTimeout(() => {
      const el = chunkRefs.current.get(selectedChunkIdx);
      el?.scrollIntoView({ block: "center" });
    }, 0);
  }, [previewSource, previewChunks, selectedChunkIdx]);

  useEffect(() => {
    if (!portalId) return;
    try {
      localStorage.setItem(chatStorageKey(portalId), JSON.stringify(messages.slice(-200)));
    } catch {
      // ignore
    }
  }, [portalId, messages]);

  useEffect(() => {
    if (!portalId) return;
    window.setTimeout(() => {
      if (!listRef.current) return;
      const raw = localStorage.getItem(chatScrollKey(portalId));
      const pos = raw != null ? Number(raw) : NaN;
      if (Number.isFinite(pos)) listRef.current.scrollTop = pos;
      else listRef.current.scrollTop = listRef.current.scrollHeight;
    }, 0);
  }, [portalId]);

  const canSend = useMemo(() => !!portalId && !!portalToken && !!input.trim() && !sending, [portalId, portalToken, input, sending]);

  const pushMessage = (msg: ChatMsg) => {
    setMessages((prev) => {
      const next = [...prev, msg];
      scrollToBottomPersist();
      return next;
    });
  };

  const onSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!canSend || !portalId) return;
    const q = input.trim();
    setInput("");
    setError("");
    pushMessage({ role: "user", text: q, ts: Date.now() });
    setSending(true);
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Api-Schema": "v2" },
        body: JSON.stringify({ query: q, sources_format: "none" }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const err = data?.error || data?.detail || "Ошибка запроса";
        setError(err);
        pushMessage({ role: "assistant", text: `Не удалось выполнить запрос: ${err}`, ts: Date.now() });
        return;
      }
      const payload = data?.data || data || {};
      pushMessage({
        role: "assistant",
        text: String(payload?.answer || "Пустой ответ"),
        ts: Date.now(),
        sources: Array.isArray(payload?.sources) ? payload.sources : [],
      });
    } finally {
      setSending(false);
      scrollToBottomPersist();
    }
  };

  const onInputKeyDown = (evt: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (evt.key !== "Enter") return;
    if (evt.shiftKey) return;
    evt.preventDefault();
    if (!canSend) return;
    void onSubmit(evt as unknown as FormEvent);
  };

  const closePreview = () => {
    setPreviewSource(null);
    setPreviewUrl(null);
    setDownloadUrl(null);
    setPreviewChunks([]);
    setSelectedChunkIdx(null);
    setPdfPage(null);
    chunkRefs.current.clear();
  };

  const openSourcePreview = async (src: ChatSource) => {
    setPreviewSource(src);
    setPreviewChunks([]);
    setSelectedChunkIdx(src.chunk_index ?? null);
    setPdfPage(src.page_num ?? null);
    setPreviewUrl(null);
    setDownloadUrl(null);

    if (!portalId || !src.file_id) return;

    const sourceKind = (src.source_type || "").toLowerCase();
    const externalPreferred = ["youtube", "rutube", "vk"].includes(sourceKind) && !!(src.source_url || "").trim();
    if (!externalPreferred) {
      setPreviewLoading(true);
      try {
        const pr = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${src.file_id}/signed-url?inline=1`);
        const pd = await pr.json().catch(() => null);
        if (pr.ok && pd?.url) setPreviewUrl(String(pd.url));

        const dr = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${src.file_id}/signed-url?inline=0`);
        const dd = await dr.json().catch(() => null);
        if (dr.ok && dd?.url) setDownloadUrl(String(dd.url));
      } finally {
        setPreviewLoading(false);
      }
    }

    setChunksLoading(true);
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${src.file_id}/chunks?limit=2000`);
      const data = await res.json().catch(() => null);
      if (res.ok && Array.isArray(data?.items)) {
        const items = data.items as FileChunk[];
        setPreviewChunks(items);
        if (!src.page_num) {
          const fromChunk = items.find((x) => x.chunk_index === (src.chunk_index ?? -1)) || items[0];
          if (fromChunk?.page_num) setPdfPage(fromChunk.page_num);
        }
      }
    } finally {
      setChunksLoading(false);
    }
  };

  const renderPreview = () => {
    if (!previewSource || !portalId) return null;
    const src = previewSource;
    const ext = fileExt(src.filename);
    const externalUrl = buildTimedExternalUrl(src);
    const externalEmbedUrl = buildExternalEmbedUrl(src);
    const sourceKind = (src.source_type || "").toLowerCase();
    const isExternal = (["youtube", "rutube", "vk"].includes(sourceKind) && !!externalUrl) || (!src.file_id && !!externalUrl);

    const startSec = src.start_ms ? Math.max(0, Math.floor(Number(src.start_ms) / 1000)) : 0;
    const base = previewUrl || "";
    const mediaSrc = startSec > 0 ? `${base}#t=${startSec}` : base;
    const pdfSrc = `${base}${pdfPage ? `#page=${pdfPage}` : ""}`;

    const mime = (src.mime_type || "").toLowerCase();
    const isVideo = [".mp4", ".mov", ".avi", ".mkv", ".webm"].includes(ext) || mime.startsWith("video/");
    const isAudio = [".mp3", ".ogg", ".wav", ".m4a", ".aac"].includes(ext) || mime.startsWith("audio/");
    const isPdf = ext === ".pdf" || mime.includes("pdf");
    const isImage = [".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext) || mime.startsWith("image/");

    const onPickChunk = (ch: FileChunk) => {
      setSelectedChunkIdx(ch.chunk_index);
      if (ch.page_num) setPdfPage(ch.page_num);
      if (mediaRef.current && ch.start_ms != null) {
        mediaRef.current.currentTime = Number(ch.start_ms) / 1000;
        void mediaRef.current.play().catch(() => {});
      }
    };

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6">
        <div className="flex h-[86vh] w-[94vw] max-w-7xl flex-col rounded-2xl bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="truncate text-sm font-semibold text-slate-900">{src.filename || "Источник"}</div>
            <div className="flex items-center gap-2">
              {downloadUrl && (
                <a className="rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-700" href={downloadUrl} target="_blank" rel="noreferrer">
                  Скачать
                </a>
              )}
              <button className="rounded-lg border border-slate-200 px-3 py-1 text-sm" onClick={closePreview}>Закрыть</button>
            </div>
          </div>
          <div className="grid flex-1 grid-cols-[1.2fr_0.8fr] gap-0 overflow-hidden">
            <div className="overflow-auto bg-slate-50 p-3">
              {previewLoading ? (
                <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Загрузка файла...</div>
              ) : isExternal ? (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                  {externalEmbedUrl ? (
                    <iframe
                      title={src.filename || "external-video"}
                      src={externalEmbedUrl}
                      className="h-[64vh] w-full rounded-xl border border-slate-200 bg-white"
                      allow="autoplay; encrypted-media; picture-in-picture"
                      allowFullScreen
                    />
                  ) : (
                    <div className="text-sm text-slate-700">Встроенный плеер недоступен для этого источника. Можно открыть внешнюю ссылку с таймкодом.</div>
                  )}
                  <a className="inline-block rounded-lg bg-sky-600 px-3 py-2 text-sm text-white" href={externalUrl} target="_blank" rel="noreferrer">Открыть источник</a>
                </div>
              ) : !base ? (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-sm text-slate-700">Не удалось получить URL предпросмотра. Повтори попытку.</div>
                  <button className="rounded-lg border border-slate-200 px-3 py-2 text-sm" onClick={() => openSourcePreview(src)}>Повторить</button>
                  {downloadUrl && <a className="inline-block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700" href={downloadUrl}>Скачать</a>}
                </div>
              ) : isVideo ? (
                <video ref={(n) => (mediaRef.current = n)} key={mediaSrc} src={mediaSrc} controls autoPlay className="h-full w-full rounded-xl border border-slate-200 bg-black" />
              ) : isAudio ? (
                <div className="rounded-xl border border-slate-200 bg-white p-6">
                  <audio ref={(n) => (mediaRef.current = n)} key={mediaSrc} src={mediaSrc} controls autoPlay className="w-full" />
                </div>
              ) : isPdf ? (
                <iframe title={src.filename || "pdf"} src={pdfSrc} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
              ) : isImage ? (
                <img src={base} alt={src.filename || "image"} className="mx-auto max-h-full max-w-full rounded-xl border border-slate-200 bg-white" />
              ) : (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-sm text-slate-700">Для этого типа файла пока показываем контекст справа. Viewer doc/xls/ppt добавляю отдельной задачей.</div>
                  {downloadUrl && <a className="inline-block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700" href={downloadUrl}>Скачать</a>}
                </div>
              )}
            </div>
            <div className="border-l border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-800">Контекст / транскрибация</div>
              <div className="h-[calc(86vh-94px)] overflow-auto p-3">
                {chunksLoading && <div className="text-sm text-slate-500">Загрузка контекста...</div>}
                {!chunksLoading && previewChunks.length === 0 && <div className="text-sm text-slate-500">Контекст пока недоступен.</div>}
                <div className="space-y-2">
                  {previewChunks.map((ch) => (
                    <button
                      key={ch.id}
                      ref={(n) => {
                        if (!n) {
                          chunkRefs.current.delete(ch.chunk_index);
                          return;
                        }
                        chunkRefs.current.set(ch.chunk_index, n);
                      }}
                      type="button"
                      className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${selectedChunkIdx === ch.chunk_index ? "border-yellow-300 bg-yellow-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
                      onClick={() => onPickChunk(ch)}
                    >
                      <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                        <span>#{ch.chunk_index + 1}</span>
                        {ch.page_num ? <span>стр. {ch.page_num}</span> : null}
                        {ch.start_ms != null ? <span>{fmtMs(ch.start_ms)}</span> : null}
                      </div>
                      <div className="line-clamp-5 whitespace-pre-wrap text-slate-700">{ch.text}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Чат</h1>
        <p className="mt-1 text-slate-500">Диалог с моделью по базе знаний портала.</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div
          ref={listRef}
          className="h-[56vh] overflow-y-auto rounded-xl border border-slate-100 bg-slate-50 p-4"
          onScroll={() => {
            if (!portalId || !listRef.current) return;
            localStorage.setItem(chatScrollKey(portalId), String(listRef.current.scrollTop));
          }}
        >
          {!messages.length ? (
            <div className="text-sm text-slate-500">Задайте первый вопрос.</div>
          ) : (
            <div className="space-y-3">
              {messages.map((m, idx) => (
                <div key={`${m.ts}-${idx}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  {(() => {
                    const refsByLine = m.role === "assistant" && m.sources?.length ? lineRefsMap(m.text, m.sources || []) : null;
                    return (
                  <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${m.role === "user" ? "bg-sky-600 text-white" : "border border-slate-200 bg-white text-slate-800"}`}>
                    {m.role !== "assistant" || !m.sources?.length ? (
                      m.text
                    ) : (
                      <div className="space-y-1">
                        {String(m.text || "").split("\n").map((line, lineIdx) => {
                          const refs = refsByLine?.get(lineIdx) || [];
                          if (!line) return <div key={`${m.ts}-line-${lineIdx}`} className="h-4" />;
                          return (
                            <div key={`${m.ts}-line-${lineIdx}`} className="whitespace-pre-wrap">
                              <span>{line}</span>
                              {refs.map((srcIdx) => (
                                <button
                                  key={`${m.ts}-${lineIdx}-${srcIdx}`}
                                  type="button"
                                  className="ml-1 text-sky-700 underline"
                                  onClick={() => {
                                    const s = m.sources?.[srcIdx];
                                    if (s) void openSourcePreview(s);
                                  }}
                                >
                                  [{srcIdx + 1}]
                                </button>
                              ))}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {m.role === "assistant" && !!m.sources?.length && (
                      <div className="mt-3 border-t border-slate-200 pt-2 text-xs text-slate-600">
                        <div className="mb-1 font-semibold text-slate-700">Источники</div>
                        <div className="space-y-1">
                          {m.sources.map((s, sIdx) => (
                            <button key={`${m.ts}-${sIdx}`} type="button" className="block text-left text-sky-700 underline" onClick={() => openSourcePreview(s)}>
                              {(sIdx + 1).toString()}. {s.filename || "Файл"}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                    );
                  })()}
                </div>
              ))}
            </div>
          )}
        </div>

        <form className="mt-4 flex items-end gap-3" onSubmit={onSubmit}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onInputKeyDown}
            rows={3}
            placeholder="Введите вопрос..."
            className="min-h-[92px] flex-1 resize-y rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-sky-400"
          />
          <button type="submit" disabled={!canSend} className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
            {sending ? "Отправка..." : "Отправить"}
          </button>
        </form>
        {error && <div className="mt-2 text-sm text-rose-600">{error}</div>}
      </div>
      {renderPreview()}
    </div>
  );
}
