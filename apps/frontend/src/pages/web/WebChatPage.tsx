import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { fetchPortal, getWebPortalInfo, getWebUser } from "./auth";

type ChatSource = {
  file_id?: number | null;
  chunk_id?: number | null;
  filename?: string;
  mime_type?: string;
  source_type?: string;
  source_url?: string;
  page_num?: number | null;
  start_ms?: number | null;
  end_ms?: number | null;
  chunk_index?: number | null;
  anchor_kind?: string;
  anchor_value?: string;
  text?: string;
  support_chunk_ids?: number[];
  support_chunk_indexes?: number[];
  anchor_page_display?: number | null;
};

type ChatMsg = {
  role: "user" | "assistant";
  text: string;
  ts: number;
  sources?: ChatSource[];
  line_refs?: Record<string, number[]>;
};

type FileChunk = {
  id: number;
  chunk_index: number;
  text: string;
  start_ms?: number | null;
  end_ms?: number | null;
  page_num?: number | null;
  anchor_kind?: string;
  anchor_value?: string;
};

type PdfJsDoc = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<any>;
  destroy?: () => void;
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

function _tokens(text: string): string[] {
  return (text || "")
    .toLowerCase()
    .replace(/[^a-zа-я0-9ё\s]/gi, " ")
    .split(/\s+/)
    .filter((t) => t.length >= 4);
}

function _tokenOverlapScore(a: string[], b: string[]): number {
  if (!a.length || !b.length) return 0;
  const sa = new Set(a);
  const sb = new Set(b);
  let inter = 0;
  sa.forEach((t) => {
    if (sb.has(t)) inter += 1;
  });
  return inter;
}

function _lineMatchScore(line: string, text: string): number {
  const a = _tokens(line || "");
  const b = _tokens(text || "");
  return _tokenOverlapScore(a, b);
}

function _bestChunkBySourceText(sourceText: string | undefined, chunks: FileChunk[]): FileChunk | null {
  const srcRaw = String(sourceText || "").trim();
  if (!srcRaw || !chunks.length) return null;
  const srcNorm = _norm(srcRaw);
  const srcTok = _tokens(srcRaw);
  let best: { ch: FileChunk; score: number } | null = null;
  for (const ch of chunks) {
    const txt = String(ch.text || "");
    if (!txt) continue;
    const chNorm = _norm(txt);
    const chTok = _tokens(txt);
    let score = 0;
    if (srcNorm && chNorm) {
      if (chNorm === srcNorm) score += 1000;
      else if (chNorm.includes(srcNorm)) score += 700;
      else if (srcNorm.includes(chNorm) && chNorm.length > 120) score += 500;
    }
    score += _tokenOverlapScore(srcTok, chTok) * 8;
    if (score <= 0) continue;
    if (!best || score > best.score) best = { ch, score };
  }
  return best?.ch || null;
}

function _selectAnchorChunk(
  src: ChatSource,
  items: FileChunk[],
  parsedChunkId: number,
  parsedChunk: number,
  anchorKind: string,
  anchorValue: string
): FileChunk | null {
  if (!items.length) return null;
  const fromChunkId = Number.isFinite(parsedChunkId)
    ? items.find((x) => Number(x.id) === Number(parsedChunkId))
    : null;
  const fromChunkIndex = Number.isFinite(parsedChunk)
    ? items.find((x) => x.chunk_index === Number(parsedChunk))
    : null;
  const fromAnchor = items.find(
    (x) => String(x.anchor_kind || "").toLowerCase() === anchorKind && String(x.anchor_value || "") === anchorValue
  );
  if (fromChunkId) return fromChunkId;
  if (fromChunkIndex) return fromChunkIndex;
  if (fromAnchor) return fromAnchor;

  // Span-like fallback: rank by text overlap; then prefer neighbors around anchor chunk index (if any).
  const byText = _bestChunkBySourceText(src.text, items);
  if (!byText) return items[0] || null;
  if (!Number.isFinite(parsedChunk)) return byText;
  const near = items
    .filter((x) => Math.abs(Number(x.chunk_index) - Number(parsedChunk)) <= 2)
    .sort((a, b) => Math.abs(Number(a.chunk_index) - Number(parsedChunk)) - Math.abs(Number(b.chunk_index) - Number(parsedChunk)));
  if (!near.length) return byText;
  const nearBest = _bestChunkBySourceText(src.text, near);
  return nearBest || byText;
}

function _nearestChunkWithPage(chunks: FileChunk[], targetIdx: number | null | undefined): FileChunk | null {
  if (!chunks.length) return null;
  const withPage = chunks.filter((c) => Number(c.page_num || 0) > 0);
  if (!withPage.length) return null;
  if (!Number.isFinite(Number(targetIdx))) return withPage[0];
  const tidx = Number(targetIdx);
  let best: { ch: FileChunk; d: number } | null = null;
  for (const ch of withPage) {
    const d = Math.abs(Number(ch.chunk_index) - tidx);
    if (!best || d < best.d) best = { ch, d };
  }
  return best?.ch || null;
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
  lines.forEach((line, i) => {
    const t = line.trim();
    if (!t) return;
    const eligible = hasList ? /^\s*(\d+[\)\.]|[-*•])\s+/.test(t) : true;
    if (!eligible) return;
    const refs = _lineRefIndexes(t, sources);
    out.set(i, refs);
  });
  return out;
}

function sourceKey(s: ChatSource): string {
  return [
    s.file_id ?? "",
    s.chunk_id ?? "",
    s.chunk_index ?? "",
    s.page_num ?? "",
    s.start_ms ?? "",
    (s.filename || "").trim().toLowerCase(),
  ].join("|");
}

function uniqueSources(sources: ChatSource[] | undefined): ChatSource[] {
  const out: ChatSource[] = [];
  const seen = new Set<string>();
  for (const s of sources || []) {
    const k = sourceKey(s);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(s);
  }
  return out;
}

function _escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function _normalizeNeedle(raw: string | undefined): string {
  const t = String(raw || "").replace(/\s+/g, " ").trim();
  if (!t) return "";
  return t.slice(0, 180);
}

function renderHighlightedText(text: string, rawNeedle: string | undefined) {
  const needle = _normalizeNeedle(rawNeedle);
  if (!needle || needle.length < 12) return text;
  const re = new RegExp(_escapeRegex(needle), "ig");
  const out: any[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const i = m.index;
    if (i > last) out.push(text.slice(last, i));
    out.push(
      <mark key={`${i}-${m[0].length}`} className="rounded bg-yellow-200/80 px-0.5">
        {text.slice(i, i + m[0].length)}
      </mark>
    );
    last = i + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out.length ? out : text;
}

function _norm(s: string): string {
  return (s || "").toLowerCase().replace(/[^a-zа-яё0-9\s]/gi, " ").replace(/\s+/g, " ").trim();
}

function PdfHighlightViewer({
  url,
  page,
  pageDisplayOffset = 0,
  needle,
  onResolvedPage,
}: {
  url: string;
  page: number;
  pageDisplayOffset?: number;
  needle?: string;
  onResolvedPage?: (page: number) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const docRef = useRef<PdfJsDoc | null>(null);
  const renderingRef = useRef<Set<number>>(new Set());
  const lastJumpKeyRef = useRef<string>("");
  const autoHitJumpedRef = useRef(false);
  const pageTextCacheRef = useRef<Map<number, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [numPages, setNumPages] = useState<number>(0);
  const [renderedPages, setRenderedPages] = useState<number[]>([]);
  const [firstHitPage, setFirstHitPage] = useState<number | null>(null);
  const [resolvedPage, setResolvedPage] = useState<number | null>(null);
  const effectivePage = Math.max(1, Number(resolvedPage || page || 1));

  const appendRange = (from: number, to: number) => {
    if (!numPages) return;
    const a = Math.max(1, Math.min(from, numPages));
    const b = Math.max(1, Math.min(to, numPages));
    const [start, end] = a <= b ? [a, b] : [b, a];
    setRenderedPages((prev) => {
      const s = new Set(prev);
      for (let i = start; i <= end; i += 1) s.add(i);
      return Array.from(s).sort((x, y) => x - y);
    });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setRenderedPages([]);
    setFirstHitPage(null);
    setResolvedPage(null);
    autoHitJumpedRef.current = false;
    docRef.current = null;
    renderingRef.current.clear();
    pageTextCacheRef.current.clear();
    const render = async () => {
      try {
        const dynamicImport = new Function("u", "return import(u)");
        const mod: any = await (dynamicImport as any)("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs");
        const workerUrl = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";
        mod.GlobalWorkerOptions.workerSrc = workerUrl;
        const loadingTask = mod.getDocument(url);
        const doc: PdfJsDoc = await loadingTask.promise;
        if (cancelled) return;
        docRef.current = doc;
        setNumPages(doc.numPages || 0);
        const p0 = Math.max(1, Math.min(Number(page || 1), doc.numPages || 1));
        setRenderedPages(() => {
          const from = Math.max(1, p0 - 2);
          const to = Math.min(doc.numPages || 1, p0 + 2);
          const arr: number[] = [];
          for (let i = from; i <= to; i += 1) arr.push(i);
          return arr;
        });
        if (!cancelled) setLoading(false);
      } catch (e: any) {
        if (!cancelled) {
          setError(String(e?.message || "pdf_render_error"));
          setLoading(false);
        }
      }
    };
    void render();
    return () => {
      cancelled = true;
      docRef.current?.destroy?.();
      docRef.current = null;
    };
  }, [url, page]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !numPages) return;
    const onScroll = () => {
      const st = host.scrollTop;
      const h = host.clientHeight;
      const sh = host.scrollHeight;
      if (sh - (st + h) < 500) {
        const maxP = renderedPages.length ? renderedPages[renderedPages.length - 1] : effectivePage;
        appendRange(maxP + 1, maxP + 2);
      }
      if (st < 220) {
        const minP = renderedPages.length ? renderedPages[0] : effectivePage;
        appendRange(minP - 2, minP - 1);
      }
    };
    host.addEventListener("scroll", onScroll, { passive: true });
    return () => host.removeEventListener("scroll", onScroll);
  }, [numPages, renderedPages, effectivePage]);

  useEffect(() => {
    if (!numPages) return;
    appendRange(effectivePage - 2, effectivePage + 2);
  }, [effectivePage, numPages]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const pno = effectivePage;
    const k = `${url}|${pno}`;
    if (lastJumpKeyRef.current === k) return;
    const target = host.querySelector(`[data-page='${pno}']`) as HTMLElement | null;
    if (target) {
      target.scrollIntoView({ block: "start" });
      lastJumpKeyRef.current = k;
    }
  }, [effectivePage, url, renderedPages]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    if (!firstHitPage || autoHitJumpedRef.current) return;
    const target = host.querySelector(`[data-page='${firstHitPage}']`) as HTMLElement | null;
    if (target) {
      target.scrollIntoView({ block: "start" });
      autoHitJumpedRef.current = true;
    }
  }, [firstHitPage, renderedPages]);

  useEffect(() => {
    const doc = docRef.current;
    if (!doc || !renderedPages.length) return;
    let cancelled = false;
    const run = async () => {
      const mod: any = await (new Function("u", "return import(u)") as any)(
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs"
      );
      for (const pno of renderedPages) {
        if (cancelled) return;
        if (renderingRef.current.has(pno)) continue;
        const canvas = document.querySelector(`canvas[data-p='${pno}']`) as HTMLCanvasElement | null;
        const textLayer = document.querySelector(`div[data-t='${pno}']`) as HTMLDivElement | null;
        if (!canvas || !textLayer) continue;
        renderingRef.current.add(pno);
        try {
          const p = await doc.getPage(pno);
          const baseViewport = p.getViewport({ scale: 1 });
          const hostW = Math.max(320, (hostRef.current?.clientWidth || 900) - 36);
          const fitScale = hostW / Math.max(1, baseViewport.width);
          const scale = Math.max(0.55, Math.min(1.0, fitScale));
          const viewport = p.getViewport({ scale });
          const ctx = canvas.getContext("2d");
          if (!ctx) continue;
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = `${Math.floor(viewport.width)}px`;
          canvas.style.height = `${Math.floor(viewport.height)}px`;
          textLayer.innerHTML = "";
          textLayer.style.width = `${Math.floor(viewport.width)}px`;
          textLayer.style.height = `${Math.floor(viewport.height)}px`;
          await p.render({ canvasContext: ctx, viewport }).promise;
          const content = await p.getTextContent();
          const targetPage = effectivePage;
          // Keep highlight strictly bound to anchor page to avoid drifting to neighbor pages.
          const isSearchScope = pno === targetPage;
          const needleNorm = _norm(String(needle || "")).slice(0, 1200);
          const needleSets = isSearchScope
            ? [Array.from(new Set(needleNorm.split(" ").filter((x) => x.length >= 4).slice(0, 40)))]
                .filter((arr) => arr.length > 0)
            : [];
          const items = (content.items || []) as any[];
          const normItems = items.map((it) => _norm(String(it?.str || "")));
          const ranges: Array<[number, number]> = [];
          for (const uniqTokens of needleSets) {
            const needCover = Math.max(2, Math.min(uniqTokens.length, Math.ceil(uniqTokens.length * 0.4)));
            const itemTokens: string[][] = normItems.map((s) => uniqTokens.filter((t) => s.includes(t)));
            let l = 0;
            let covered = 0;
            const freq = new Map<string, number>();
            let best: { l: number; r: number; w: number; covered: number } | null = null;
            for (let r = 0; r < itemTokens.length; r += 1) {
              for (const t of itemTokens[r]) {
                const n = (freq.get(t) || 0) + 1;
                freq.set(t, n);
                if (n === 1) covered += 1;
              }
              while (covered >= needCover && l <= r) {
                const w = r - l;
                if (!best || w < best.w || (w === best.w && covered > best.covered)) {
                  best = { l, r, w, covered };
                }
                for (const t of itemTokens[l]) {
                  const n = (freq.get(t) || 0) - 1;
                  if (n <= 0) {
                    freq.delete(t);
                    covered -= 1;
                  } else {
                    freq.set(t, n);
                  }
                }
                l += 1;
              }
            }
            if (best) {
              ranges.push([best.l, best.r]);
              setFirstHitPage((prev) => prev ?? pno);
            } else {
              const firstIdx = normItems.findIndex((s) => uniqTokens.some((t) => s.includes(t)));
              if (firstIdx >= 0) {
                const endIdx = Math.min(normItems.length - 1, firstIdx + Math.max(8, Math.min(36, uniqTokens.length * 4)));
                ranges.push([firstIdx, endIdx]);
                setFirstHitPage((prev) => prev ?? pno);
              }
            }
          }
          for (let i = 0; i < items.length; i += 1) {
            const item = items[i];
            const str = String(item?.str || "");
            if (!str.trim()) continue;
            const tx = (mod as any).Util.transform(viewport.transform, item.transform);
            const left = tx[4];
            const top = tx[5] - item.height;
            const width = item.width;
            const height = item.height;
            const span = document.createElement("span");
            span.textContent = str;
            span.style.position = "absolute";
            span.style.left = `${left}px`;
            span.style.top = `${top}px`;
            span.style.width = `${width}px`;
            span.style.height = `${height}px`;
            span.style.fontSize = `${height}px`;
            span.style.color = "transparent";
            span.style.userSelect = "text";
            span.style.whiteSpace = "pre";
            const inAnyRange = ranges.some(([a, b]) => i >= a && i <= b);
            if (inAnyRange) {
              span.style.background = "rgba(250, 204, 21, 0.45)";
              span.style.borderRadius = "2px";
            }
            textLayer.appendChild(span);
          }
        } catch {
          // ignore page render error
        } finally {
          renderingRef.current.delete(pno);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [renderedPages, needle, url, effectivePage]);

  useEffect(() => {
    const doc = docRef.current;
    if (!doc || !numPages) return;
    const q = _norm(String(needle || "")).slice(0, 1800);
    const toks = Array.from(new Set(q.split(" ").filter((x) => x.length >= 4))).slice(0, 64);
    if (toks.length < 3) return;
    let cancelled = false;
    const resolve = async () => {
      const getPageText = async (pno: number): Promise<string> => {
        const cached = pageTextCacheRef.current.get(pno);
        if (cached != null) return cached;
        try {
          const p = await doc.getPage(pno);
          const content = await p.getTextContent();
          const text = (content.items || [])
            .map((it: any) => String(it?.str || ""))
            .join(" ");
          const n = _norm(text);
          pageTextCacheRef.current.set(pno, n);
          return n;
        } catch {
          pageTextCacheRef.current.set(pno, "");
          return "";
        }
      };
      let bestPage = 0;
      let bestScore = -1;
      for (let pno = 1; pno <= numPages; pno += 1) {
        if (cancelled) return;
        const txt = await getPageText(pno);
        if (!txt) continue;
        let covered = 0;
        let pairHits = 0;
        for (let i = 0; i < toks.length; i += 1) {
          const t = toks[i];
          if (txt.includes(t)) covered += 1;
          if (i < toks.length - 1) {
            const bi = `${toks[i]} ${toks[i + 1]}`;
            if (bi.length >= 9 && txt.includes(bi)) pairHits += 1;
          }
        }
        const coverage = covered / Math.max(1, toks.length);
        const score = (coverage * 10) + pairHits;
        if (score > bestScore) {
          bestScore = score;
          bestPage = pno;
        }
      }
      if (cancelled || bestPage <= 0) return;
      if (bestScore < 2.4) return;
      setResolvedPage(bestPage);
      onResolvedPage?.(bestPage);
    };
    void resolve();
    return () => {
      cancelled = true;
    };
  }, [url, needle, numPages, onResolvedPage]);

  return (
    <div className="relative h-full w-full rounded-xl border border-slate-200 bg-white">
      {loading && <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-slate-600">Загрузка PDF...</div>}
      {error ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center px-4 text-sm text-rose-600">{error}</div>
      ) : null}
      <div ref={hostRef} className="h-full w-full overflow-auto p-3">
        <div className="mx-auto flex flex-col gap-6">
          {renderedPages.map((pno) => (
            <div key={pno} data-page={pno} className="relative mx-auto rounded-md border border-slate-200 bg-white shadow-sm">
              <div className="absolute left-2 top-2 z-10 rounded bg-white/90 px-1.5 py-0.5 text-[11px] text-slate-600">
                стр. {Math.max(1, pno - Math.max(0, Number(pageDisplayOffset || 0)))}
              </div>
              <canvas data-p={pno} className="block" />
              <div data-t={pno} className="pointer-events-none absolute left-0 top-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
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
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewNeedle, setPreviewNeedle] = useState<string>("");
  const [, setPreviewSupportNeedles] = useState<string[]>([]);
  const [resolvedPreviewPage, setResolvedPreviewPage] = useState<number | null>(null);

  const listRef = useRef<HTMLDivElement | null>(null);
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const chunkRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const leftChunkRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const scrollRestoredRef = useRef(false);

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
    scrollRestoredRef.current = false;
  }, [portalId]);

  useEffect(() => {
    if (!previewSource) return;
    if (selectedChunkIdx == null) return;
    window.setTimeout(() => {
      const el = chunkRefs.current.get(selectedChunkIdx);
      el?.scrollIntoView({ block: "center" });
      const left = leftChunkRefs.current.get(selectedChunkIdx);
      left?.scrollIntoView({ block: "center" });
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
    if (!portalId || scrollRestoredRef.current) return;
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (!listRef.current) return;
        const raw = localStorage.getItem(chatScrollKey(portalId));
        const pos = raw != null ? Number(raw) : NaN;
        // If scroll position is unknown/invalid (or stale "0"), open chat at bottom.
        if (Number.isFinite(pos) && pos > 4) listRef.current.scrollTop = pos;
        else listRef.current.scrollTop = listRef.current.scrollHeight;
        scrollRestoredRef.current = true;
      });
    });
  }, [portalId, messages.length]);

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
        line_refs: payload?.line_refs && typeof payload.line_refs === "object" ? payload.line_refs : {},
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
    setPreviewPdfUrl(null);
    setDownloadUrl(null);
    setPreviewChunks([]);
    setSelectedChunkIdx(null);
    setPdfPage(null);
    setPreviewNeedle("");
    setPreviewSupportNeedles([]);
    setResolvedPreviewPage(null);
    chunkRefs.current.clear();
  };

  const openSourcePreview = async (src: ChatSource, focusText?: string) => {
    setPreviewSource(src);
    setPreviewChunks([]);
    const anchorKind = String(src.anchor_kind || "").toLowerCase();
    const anchorValue = String(src.anchor_value || "");
    const parsedChunkId = Number(src.chunk_id ?? NaN);
    const parsedChunk = Number(src.chunk_index ?? (anchorKind === "chunk_index" ? anchorValue : NaN));
    const parsedPage = Number(src.page_num ?? (anchorKind === "pdf_page" ? anchorValue : NaN));
    const parsedMs = Number(src.start_ms ?? (anchorKind === "media_ms" ? anchorValue : NaN));
    setSelectedChunkIdx(Number.isFinite(parsedChunk) ? parsedChunk : null);
    setPdfPage(Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : null);
    setPreviewUrl(null);
    setPreviewPdfUrl(null);
    setDownloadUrl(null);
    const needleFromAnswer = String(focusText || src.text || "").trim();
    setPreviewNeedle(needleFromAnswer);
    setPreviewSupportNeedles([]);
    setResolvedPreviewPage(null);

    if (!portalId || !src.file_id) return;

    const sourceKind = (src.source_type || "").toLowerCase();
    const externalPreferred = ["youtube", "rutube", "vk"].includes(sourceKind) && !!(src.source_url || "").trim();
    if (!externalPreferred) {
      setPreviewLoading(true);
      try {
        const pr = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${src.file_id}/signed-url?inline=1`);
        const pd = await pr.json().catch(() => null);
        if (pr.ok && pd?.url) setPreviewUrl(String(pd.url));

        const ppr = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/files/${src.file_id}/signed-url?inline=1&rendition=preview_pdf`);
        const ppd = await ppr.json().catch(() => null);
        if (ppr.ok && ppd?.url) setPreviewPdfUrl(String(ppd.url));

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
        const srcForMatch: ChatSource = needleFromAnswer ? { ...src, text: needleFromAnswer } : src;
        const target = _selectAnchorChunk(srcForMatch, items, parsedChunkId, parsedChunk, anchorKind, anchorValue);
        const supportIdxRaw = Array.isArray(src.support_chunk_indexes) ? src.support_chunk_indexes : [];
        const supportIdxSet = new Set<number>();
        for (const x of supportIdxRaw) {
          const n = Number(x);
          if (Number.isFinite(n)) supportIdxSet.add(n);
        }
        // fallback only if backend didn't provide support window
        if (!supportIdxSet.size && target?.chunk_index != null) {
          const t = Number(target.chunk_index);
          supportIdxSet.add(t);
          supportIdxSet.add(t - 1);
          supportIdxSet.add(t + 1);
        }
        let supportRows = items
          .filter((x) => supportIdxSet.has(Number(x.chunk_index)))
          .sort((a, b) => Number(a.chunk_index) - Number(b.chunk_index));
        if (needleFromAnswer) {
          const scored = supportRows
            .map((x) => ({ x, sc: _lineMatchScore(needleFromAnswer, String(x.text || "")) }))
            .sort((p, q) => q.sc - p.sc);
          const positive = scored.filter((z) => z.sc > 0).map((z) => z.x);
          if (positive.length) supportRows = positive;
        }
        const supportNeedles = supportRows
          .map((x) => String(x.text || "").trim())
          .filter((x) => x.length > 0)
          .slice(0, 4);
        setPreviewSupportNeedles(supportNeedles);

        if (target && (selectedChunkIdx == null || !Number.isFinite(parsedChunk))) {
          setSelectedChunkIdx(target.chunk_index);
        }
        if (target?.text) {
          setPreviewNeedle(String(target.text));
        } else if (needleFromAnswer) {
          setPreviewNeedle(needleFromAnswer);
        }
        // Prefer page from resolved target chunk; source-level page_num can be stale/ambiguous.
        if (target?.page_num && Number(target.page_num) > 0) {
          setPdfPage(Number(target.page_num));
        } else {
          const near = _nearestChunkWithPage(items, target?.chunk_index);
          if (near?.page_num && Number(near.page_num) > 0) {
            setPdfPage(Number(near.page_num));
          } else if (Number.isFinite(parsedPage) && parsedPage > 0) {
            setPdfPage(Number(parsedPage));
          }
        }
        if (
          !(target?.page_num && Number(target.page_num) > 0) &&
          !(_nearestChunkWithPage(items, target?.chunk_index)?.page_num)
          && !(Number.isFinite(parsedPage) && parsedPage > 0)
        ) {
          setPdfPage(null);
        }
        if (!(Number.isFinite(parsedMs)) && target?.start_ms != null) {
          src.start_ms = target.start_ms;
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
    const basePreviewPdf = previewPdfUrl || "";
    const mediaSrc = startSec > 0 ? `${base}#t=${startSec}` : base;
    const officeSrc = buildOfficeViewerUrl(base);

    const mime = (src.mime_type || "").toLowerCase();
    const isVideo = [".mp4", ".mov", ".avi", ".mkv", ".webm"].includes(ext) || mime.startsWith("video/");
    const isAudio = [".mp3", ".ogg", ".wav", ".m4a", ".aac"].includes(ext) || mime.startsWith("audio/");
    const isPdf = ext === ".pdf" || mime.includes("pdf");
    const isImage = [".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext) || mime.startsWith("image/");
    const isOffice = [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf"].includes(ext);
    const isTextLike = [".txt", ".csv", ".md", ".epub", ".fb2", ".json", ".xml", ".log"].includes(ext);
    const isChunkTextPreview = [".doc", ".docx", ".epub", ".fb2", ".txt", ".md", ".csv", ".rtf", ".log", ".json", ".xml"].includes(ext);
    const supportsPagedPreview = isOffice || [".epub", ".fb2"].includes(ext);

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
                <PdfHighlightViewer
                  key={`pdfjs-${src.file_id || src.filename || "file"}-${pdfPage || 1}`}
                  url={base}
                  page={Math.max(1, Number(pdfPage || 1))}
                  pageDisplayOffset={0}
                  needle={previewNeedle || src.text}
                  onResolvedPage={(p) => setResolvedPreviewPage(p)}
                />
              ) : supportsPagedPreview && !!basePreviewPdf ? (
                <PdfHighlightViewer
                  key={`pdfjs-preview-${src.file_id || src.filename || "file"}-${pdfPage || 1}`}
                  url={basePreviewPdf}
                  page={Math.max(1, Number(pdfPage || 1))}
                  pageDisplayOffset={0}
                  needle={previewNeedle || src.text}
                  onResolvedPage={(p) => setResolvedPreviewPage(p)}
                />
              ) : isChunkTextPreview ? (
                previewChunks.length > 0 ? (
                  <div className="h-full overflow-auto rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-3 text-xs text-slate-500">Предпросмотр по фрагментам (переход к цитате)</div>
                    <div className="space-y-2">
                      {previewChunks.map((ch) => (
                        <div
                          key={`left-${ch.id}`}
                          ref={(n) => {
                            if (!n) {
                              leftChunkRefs.current.delete(ch.chunk_index);
                              return;
                            }
                            leftChunkRefs.current.set(ch.chunk_index, n);
                          }}
                          className={`rounded-lg border px-3 py-2 text-sm whitespace-pre-wrap ${
                            selectedChunkIdx === ch.chunk_index ? "border-yellow-300 bg-yellow-50" : "border-slate-200 bg-white"
                          }`}
                        >
                          {renderHighlightedText(ch.text || "", previewNeedle || src.text)}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (isOffice && officeSrc) ? (
                  <iframe title={src.filename || "office"} src={officeSrc} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
                ) : (
                  <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                    <div className="text-sm text-slate-700">Фрагменты не найдены. Используйте скачивание файла.</div>
                  </div>
                )
              ) : isImage ? (
                <img src={base} alt={src.filename || "image"} className="mx-auto max-h-full max-w-full rounded-xl border border-slate-200 bg-white" />
              ) : isOffice ? (
                officeSrc ? (
                  <iframe title={src.filename || "office"} src={officeSrc} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
                ) : (
                  <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                    <div className="text-sm text-slate-700">Не удалось открыть предпросмотр Office-документа. Используйте скачивание.</div>
                  </div>
                )
              ) : isTextLike ? (
                <iframe title={src.filename || "text"} src={base} className="h-full w-full rounded-xl border border-slate-200 bg-white" />
              ) : (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-sm text-slate-700">Для этого типа файла используйте скачивание. Контекст доступен справа.</div>
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
                        {(selectedChunkIdx === ch.chunk_index && resolvedPreviewPage)
                          ? <span>стр. {resolvedPreviewPage}</span>
                          : (ch.page_num ? <span>стр. {ch.page_num}</span> : null)}
                        {ch.start_ms != null ? <span>{fmtMs(ch.start_ms)}</span> : null}
                      </div>
                      <div className="line-clamp-5 whitespace-pre-wrap text-slate-700">
                        {ch.text || ""}
                      </div>
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
            if (!portalId || !listRef.current || messages.length === 0) return;
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
                    const hasBackendRefs = !!(m.line_refs && Object.keys(m.line_refs).length);
                    const msgSources = m.role === "assistant" ? (hasBackendRefs ? (m.sources || []) : uniqueSources(m.sources)) : [];
                    const refsByLine =
                      m.role === "assistant" && msgSources.length
                        ? (hasBackendRefs
                            ? new Map<number, number[]>(
                                Object.entries(m.line_refs || {})
                                  .map(([k, v]) => [Number(k), Array.isArray(v) ? v : []] as [number, number[]])
                                  .filter(([k]) => Number.isFinite(k))
                              )
                            : lineRefsMap(m.text, msgSources))
                        : null;
                    const usedSourceIdx = new Set<number>();
                    refsByLine?.forEach((refs) => {
                      refs.forEach((srcIdx) => {
                        if (Number.isInteger(srcIdx) && srcIdx >= 0 && srcIdx < msgSources.length) usedSourceIdx.add(srcIdx);
                      });
                    });
                    const sourceIndexMap = new Map<number, number>();
                    const orderedUsed = Array.from(usedSourceIdx).sort((a, b) => a - b);
                    const renderedSources: ChatSource[] = [];
                    if (orderedUsed.length > 0) {
                      orderedUsed.forEach((origIdx, pos) => {
                        const src = msgSources[origIdx];
                        const next = pos + 1;
                        sourceIndexMap.set(origIdx, next);
                        renderedSources.push(src);
                      });
                    } else {
                      msgSources.forEach((src, idx) => {
                        sourceIndexMap.set(idx, idx + 1);
                        renderedSources.push(src);
                      });
                    }
                    return (
                  <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${m.role === "user" ? "bg-sky-600 text-white" : "border border-slate-200 bg-white text-slate-800"}`}>
                    {m.role !== "assistant" || !msgSources.length ? (
                      m.text
                    ) : (
                      <div className="space-y-1">
                        {String(m.text || "").split("\n").map((line, lineIdx) => {
                          const refs = refsByLine?.get(lineIdx) || [];
                          const mappedRefs = Array.from(
                            new Set(
                              refs.map((srcIdx) => sourceIndexMap.get(srcIdx) || srcIdx + 1)
                            )
                          );
                          if (!line) return <div key={`${m.ts}-line-${lineIdx}`} className="h-4" />;
                          return (
                            <div key={`${m.ts}-line-${lineIdx}`} className="whitespace-pre-wrap">
                              <span>{line}</span>
                              {mappedRefs.map((displayIdx) => (
                                <button
                                  key={`${m.ts}-${lineIdx}-${displayIdx}`}
                                  type="button"
                                className="ml-1 text-sky-700 underline"
                                onClick={() => {
                                    const srcIdx = refs.find((r) => (sourceIndexMap.get(r) || r + 1) === displayIdx);
                                    const s = srcIdx == null ? null : msgSources[srcIdx];
                                    if (s) void openSourcePreview(s, line);
                                  }}
                                >
                                  [{displayIdx}]
                                </button>
                              ))}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {m.role === "assistant" && !!msgSources.length && (
                      <div className="mt-3 border-t border-slate-200 pt-2 text-xs text-slate-600">
                        <div className="mb-1 font-semibold text-slate-700">Источники</div>
                        <div className="space-y-1">
                          {renderedSources.map((s, sIdx) => (
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
