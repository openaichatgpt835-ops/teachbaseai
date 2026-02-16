
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";
import { Select } from "../../components/Select";
import "../../flow.css";

type FlowNode = { id: string; type: string; title?: string; config?: any; x?: number; y?: number };
type FlowEdge = { id: string; from: string; to: string; condition?: any };
type FlowDraft = {
  version: number;
  settings: { mood: string; custom_prompt: string; use_history: boolean };
  nodes: FlowNode[];
  edges: FlowEdge[];
};

type FlowChatMsg = { role: "user" | "bot"; text: string; trace?: string };

const NODE_WIDTH = 170;
const NODE_HEIGHT = 78;

function displayName(type: string) {
  const map: Record<string, string> = {
    start: "Start",
    ask: "Question",
    branch: "Intent",
    kb_answer: "RAG Search",
    message: "Answer Composer",
    prompt: "Answer Composer (style)",
    webhook: "Action",
    bitrix_lead: "Action",
    bitrix_deal: "Action",
    handoff: "CTA / Handoff",
  };
  return map[type] || type;
}

function nodeIconPath(type: string) {
  switch (type) {
    case "start":
      return "M5 12h14M12 5l7 7-7 7";
    case "ask":
      return "M4 6h16v8H7l-3 4V6Z";
    case "branch":
      return "M6 6h12M6 12h12M6 18h6";
    case "kb_answer":
      return "M6 4h9a4 4 0 0 1 4 4v12H9a3 3 0 0 0-3 3V4Z";
    case "message":
      return "M4 5h16v10H7l-3 4V5Z";
    case "webhook":
      return "M12 3v6M6 9l6 6 6-6M6 21h12";
    case "bitrix_lead":
      return "M4 8h8v8H4zM14 6h6v12h-6z";
    case "bitrix_deal":
      return "M5 6h14v12H5zM8 9h8M8 13h6";
    case "handoff":
      return "M6 12h6l3 3 3-3h-2a3 3 0 0 0-6 0H6Z";
    default:
      return "M5 12h14";
  }
}

function nodeStyle(node: FlowNode) {
  return {
    left: `${node.x ?? 100}px`,
    top: `${node.y ?? 100}px`,
    width: `${NODE_WIDTH}px`,
    height: `${NODE_HEIGHT}px`,
  };
}

function nodeOutPoint(node: FlowNode) {
  return {
    x: (node.x ?? 100) + NODE_WIDTH,
    y: (node.y ?? 100) + NODE_HEIGHT / 2,
  };
}

function nodeInPoint(node: FlowNode) {
  return {
    x: node.x ?? 100,
    y: (node.y ?? 100) + NODE_HEIGHT / 2,
  };
}

function bezierPath(x1: number, y1: number, x2: number, y2: number) {
  const dx = Math.max(60, Math.abs(x2 - x1) * 0.5);
  const c1x = x1 + dx;
  const c2x = x2 - dx;
  return `M ${x1} ${y1} C ${c1x} ${y1} ${c2x} ${y2} ${x2} ${y2}`;
}

function ensureNodeConfig(node: FlowNode) {
  if (!node.config) node.config = {};
  if (node.type === "branch") {
    if (!Array.isArray(node.config.meanings)) node.config.meanings = [];
  }
  if (node.type === "webhook" && typeof node.config.payload !== "string") {
    node.config.payload = node.config.payload ? JSON.stringify(node.config.payload, null, 2) : "";
  }
  if ((node.type === "bitrix_lead" || node.type === "bitrix_deal") && typeof node.config.fields !== "string") {
    node.config.fields = node.config.fields ? JSON.stringify(node.config.fields, null, 2) : "";
  }
}

function newNodeId() {
  return `n_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
}
export function WebFlowPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const [flowDraft, setFlowDraft] = useState<FlowDraft>({
    version: 1,
    settings: { mood: "нейтральный", custom_prompt: "", use_history: true },
    nodes: [],
    edges: [],
  });
  const [flowMessage, setFlowMessage] = useState("");
  const [flowSaving, setFlowSaving] = useState(false);
  const [flowPublishing, setFlowPublishing] = useState(false);
  const [flowTesting, setFlowTesting] = useState(false);
  const [flowScale, setFlowScale] = useState(1);
  const [flowPan, setFlowPan] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [hoverEdgeId, setHoverEdgeId] = useState<string | null>(null);
  const [connectingFrom, setConnectingFrom] = useState<{ id: string; x: number; y: number } | null>(null);
  const [connectPreview, setConnectPreview] = useState<{ x: number; y: number } | null>(null);
  const [flowTestInput, setFlowTestInput] = useState("");
  const [flowTestState, setFlowTestState] = useState<Record<string, any> | null>(null);
  const [flowChatLog, setFlowChatLog] = useState<FlowChatMsg[]>([]);

  const draggingNodeId = useRef<string | null>(null);
  const dragStart = useRef<{ x: number; y: number; nodeX: number; nodeY: number } | null>(null);
  const isPanning = useRef(false);
  const panStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const headers = useMemo(
    () => ({
      Authorization: `Bearer ${portalToken}`,
      "X-Requested-With": "XMLHttpRequest",
      Accept: "application/json",
      "Content-Type": "application/json",
    }),
    [portalToken]
  );

  const selectedNode = useMemo(
    () => flowDraft.nodes.find((n) => n.id === selectedNodeId) || null,
    [flowDraft.nodes, selectedNodeId]
  );

  const flowStageStyle = useMemo(
    () => ({ transform: `translate(${flowPan.x}px, ${flowPan.y}px) scale(${flowScale})` }),
    [flowPan, flowScale]
  );

  const connectPreviewPath = useMemo(() => {
    if (!connectingFrom || !connectPreview) return "";
    return bezierPath(connectingFrom.x, connectingFrom.y, connectPreview.x, connectPreview.y);
  }, [connectingFrom, connectPreview]);

  const toFlowPoint = useCallback(
    (evt: MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      const x = (evt.clientX - rect.left - flowPan.x) / flowScale;
      const y = (evt.clientY - rect.top - flowPan.y) / flowScale;
      return { x, y };
    },
    [flowPan, flowScale]
  );

  const edgePath = useCallback(
    (edge: FlowEdge) => {
      const from = flowDraft.nodes.find((n) => n.id === edge.from);
      const to = flowDraft.nodes.find((n) => n.id === edge.to);
      if (!from || !to) return "";
      const p1 = nodeOutPoint(from);
      const p2 = nodeInPoint(to);
      return bezierPath(p1.x, p1.y, p2.x, p2.y);
    },
    [flowDraft.nodes]
  );
  const loadFlow = useCallback(async () => {
    if (!portalId || !portalToken) return;
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/botflow/client`);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setFlowMessage(data?.error || "Не удалось загрузить сценарий");
      return;
    }
    const draft = data?.draft;
    if (draft) {
      setFlowDraft({
        version: draft.version || 1,
        settings: {
          mood: draft.settings?.mood || "нейтральный",
          custom_prompt: draft.settings?.custom_prompt || "",
          use_history: draft.settings?.use_history !== false,
        },
        nodes: draft.nodes || [],
        edges: (draft.edges || []).map((e: any) => ({ ...e, id: e.id || newNodeId() })),
      });
    } else {
      setFlowDraft({
        version: 1,
        settings: { mood: "нейтральный", custom_prompt: "", use_history: true },
        nodes: [
          { id: "start", type: "start", title: "Start", x: 120, y: 120, config: {} },
          { id: "kb", type: "kb_answer", title: "RAG Search", x: 380, y: 120, config: { pre_prompt: "" } },
        ],
        edges: [{ id: newNodeId(), from: "start", to: "kb" }],
      });
    }
  }, [headers, portalId, portalToken]);

  useEffect(() => {
    loadFlow();
  }, [loadFlow]);

  useEffect(() => {
    const onKeydown = (evt: KeyboardEvent) => {
      if (evt.key !== "Delete" && evt.key !== "Backspace") return;
      if (selectedEdgeId) {
        setFlowDraft((prev) => ({ ...prev, edges: prev.edges.filter((e) => e.id !== selectedEdgeId) }));
        setSelectedEdgeId(null);
        return;
      }
      if (selectedNodeId) {
        setFlowDraft((prev) => ({
          ...prev,
          nodes: prev.nodes.filter((n) => n.id !== selectedNodeId),
          edges: prev.edges.filter((e) => e.from !== selectedNodeId && e.to !== selectedNodeId),
        }));
        setSelectedNodeId(null);
      }
    };
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, [selectedEdgeId, selectedNodeId]);

  useEffect(() => {
    const onMove = (evt: MouseEvent) => {
      if (draggingNodeId.current && dragStart.current) {
        const nodeId = draggingNodeId.current;
        setFlowDraft((prev) => {
          const nextNodes = prev.nodes.map((n) => {
            if (n.id !== nodeId) return n;
            const p = toFlowPoint(evt);
            return { ...n, x: dragStart.current!.nodeX + (p.x - dragStart.current!.x), y: dragStart.current!.nodeY + (p.y - dragStart.current!.y) };
          });
          return { ...prev, nodes: nextNodes };
        });
      }
      if (isPanning.current && panStart.current) {
        setFlowPan({
          x: panStart.current.panX + (evt.clientX - panStart.current.x),
          y: panStart.current.panY + (evt.clientY - panStart.current.y),
        });
      }
      if (connectingFrom) {
        const p = toFlowPoint(evt);
        setConnectPreview({ x: p.x, y: p.y });
      }
    };
    const onUp = () => {
      draggingNodeId.current = null;
      dragStart.current = null;
      isPanning.current = false;
      panStart.current = null;
      if (connectingFrom) {
        setConnectPreview(null);
        setConnectingFrom(null);
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [connectingFrom, toFlowPoint]);
  const addFlowNode = (type: string) => {
    setFlowDraft((prev) => {
      const idx = prev.nodes.length;
      const node: FlowNode = {
        id: newNodeId(),
        type,
        title: displayName(type),
        x: 120 + (idx % 4) * 220,
        y: 120 + Math.floor(idx / 4) * 150,
        config: {},
      };
      if (type === "ask") node.config = { question: "Чем могу помочь?", var: "answer" };
      if (type === "message") node.config = { text: "Спасибо за интерес!" };
      if (type === "branch") node.config = { meanings: [] };
      if (type === "kb_answer") node.config = { pre_prompt: "" };
      if (type === "webhook") node.config = { url: "", payload: "" };
      if (type === "bitrix_lead" || type === "bitrix_deal") node.config = { fields: "" };
      if (type === "handoff") node.config = { text: "Передаю менеджеру." };
      return { ...prev, nodes: [...prev.nodes, node] };
    });
  };

  const addFlowNodeAfter = (node: FlowNode) => {
    const next: FlowNode = {
      id: newNodeId(),
      type: "message",
      title: "Answer",
      x: (node.x ?? 100) + 260,
      y: node.y ?? 100,
      config: { text: "..." },
    };
    setFlowDraft((prev) => ({
      ...prev,
      nodes: [...prev.nodes, next],
      edges: [...prev.edges, { id: newNodeId(), from: node.id, to: next.id }],
    }));
    setSelectedNodeId(next.id);
  };

  const onNodeMouseDown = (node: FlowNode, evt: React.MouseEvent) => {
    if (evt.button !== 0) return;
    ensureNodeConfig(node);
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
    draggingNodeId.current = node.id;
    const p = toFlowPoint(evt.nativeEvent);
    dragStart.current = { x: p.x, y: p.y, nodeX: node.x ?? 100, nodeY: node.y ?? 100 };
  };

  const onCanvasMouseDown = (evt: React.MouseEvent) => {
    if (evt.button !== 0) return;
    if ((evt.target as HTMLElement).closest(".tb-flow-node")) return;
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    isPanning.current = true;
    panStart.current = { x: evt.clientX, y: evt.clientY, panX: flowPan.x, panY: flowPan.y };
  };

  const onPortMouseDown = (node: FlowNode, evt: React.MouseEvent) => {
    const p = nodeOutPoint(node);
    setConnectingFrom({ id: node.id, x: p.x, y: p.y });
    const pt = toFlowPoint(evt.nativeEvent);
    setConnectPreview({ x: pt.x, y: pt.y });
  };

  const onPortMouseUp = (node: FlowNode) => {
    if (!connectingFrom) return;
    if (connectingFrom.id === node.id) return;
    setFlowDraft((prev) => ({
      ...prev,
      edges: [...prev.edges, { id: newNodeId(), from: connectingFrom.id, to: node.id }],
    }));
    setConnectingFrom(null);
    setConnectPreview(null);
  };

  const removeSelectedNode = () => {
    if (!selectedNodeId) return;
    setFlowDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.filter((n) => n.id !== selectedNodeId),
      edges: prev.edges.filter((e) => e.from !== selectedNodeId && e.to !== selectedNodeId),
    }));
    setSelectedNodeId(null);
  };

  const removeEdge = (edgeId: string) => {
    setFlowDraft((prev) => ({ ...prev, edges: prev.edges.filter((e) => e.id !== edgeId) }));
    if (selectedEdgeId === edgeId) setSelectedEdgeId(null);
  };

  const addMeaning = () => {
    if (!selectedNode) return;
    ensureNodeConfig(selectedNode);
    const meanings = Array.isArray(selectedNode.config.meanings) ? selectedNode.config.meanings : [];
    const next = [...meanings, { id: "", title: "", phrases: "", sensitivity: 0.5 }];
    updateNodeConfig(selectedNode.id, { meanings: next });
  };

  const removeMeaning = (idx: number) => {
    if (!selectedNode) return;
    const meanings = Array.isArray(selectedNode.config.meanings) ? selectedNode.config.meanings : [];
    const next = meanings.filter((_: any, i: number) => i !== idx);
    updateNodeConfig(selectedNode.id, { meanings: next });
  };

  const updateNodeConfig = (id: string, patch: any) => {
    setFlowDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.map((n) => {
        if (n.id !== id) return n;
        const config = { ...(n.config || {}), ...patch };
        return { ...n, config };
      }),
    }));
  };

  const updateNode = (id: string, patch: Partial<FlowNode>) => {
    setFlowDraft((prev) => ({
      ...prev,
      nodes: prev.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)),
    }));
  };

  const saveFlowDraft = async () => {
    if (!portalId || !portalToken) return;
    setFlowSaving(true);
    setFlowMessage("");
    const payload = JSON.parse(JSON.stringify(flowDraft));
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/botflow/client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_json: payload }),
    });
    const data = await res.json().catch(() => null);
    setFlowSaving(false);
    setFlowMessage(res.ok ? "Сохранено" : (data?.error || "Ошибка"));
  };

  const publishFlow = async () => {
    if (!portalId || !portalToken) return;
    setFlowPublishing(true);
    setFlowMessage("");
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/botflow/client/publish`, {
      method: "POST",
    });
    const data = await res.json().catch(() => null);
    setFlowPublishing(false);
    setFlowMessage(res.ok ? "Опубликовано" : (data?.error || "Ошибка"));
  };

  const runFlowTest = async () => {
    if (!portalId || !portalToken || !flowTestInput.trim()) return;
    setFlowTesting(true);
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/botflow/client/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: flowTestInput, draft_json: flowDraft, state_json: flowTestState }),
    });
    const data = await res.json().catch(() => null);
    setFlowTesting(false);
    if (!res.ok) {
      setFlowChatLog((prev) => [...prev, { role: "bot", text: data?.error || "Ошибка теста" }]);
      return;
    }
    setFlowChatLog((prev) => [
      ...prev,
      { role: "user", text: flowTestInput },
      { role: "bot", text: data?.text || "", trace: (data?.trace || []).map((t: any) => t.type || t.event).filter(Boolean).join(" → ") },
    ]);
    setFlowTestState(data?.state || null);
    setFlowTestInput("");
  };

  const resetFlowTest = () => {
    setFlowTestState(null);
    setFlowChatLog([]);
  };
  return (
    <div className="tb-flow">
      <div className="tb-flow-toolbar">
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("start")}>Start</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("ask")}>Question</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("branch")}>Intent</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("kb_answer")}>RAG Search</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("message")}>Answer</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("webhook")}>Webhook</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("bitrix_lead")}>Bitrix Lead</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("bitrix_deal")}>Bitrix Deal</button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={() => addFlowNode("handoff")}>CTA / Handoff</button>
        <div className="tb-flow-zoom">
          <button className="rounded-md border border-slate-200 bg-white px-2" onClick={() => setFlowScale((s) => Math.max(0.2, Math.round((s - 0.1) * 10) / 10))}>−</button>
          <span className="text-xs text-slate-500">{Math.round(flowScale * 100)}%</span>
          <button className="rounded-md border border-slate-200 bg-white px-2" onClick={() => setFlowScale((s) => Math.min(3, Math.round((s + 0.1) * 10) / 10))}>+</button>
        </div>
        <button className="rounded-lg bg-sky-600 px-3 py-1 text-sm font-semibold text-white" onClick={saveFlowDraft} disabled={flowSaving}>
          {flowSaving ? "Сохраняю..." : "Сохранить"}
        </button>
        <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={publishFlow} disabled={flowPublishing}>
          {flowPublishing ? "Публикую..." : "Опубликовать"}
        </button>
        {flowMessage && <span className="text-xs text-slate-500">{flowMessage}</span>}
      </div>

      <div className="tb-flow-settings">
        <div className="space-y-1">
          <label className="text-xs text-slate-600">Настроение</label>
          <Select
            value={flowDraft.settings.mood}
            options={[
              { value: "нейтральный", label: "Нейтральный" },
              { value: "дружелюбный", label: "Дружелюбный" },
              { value: "продающий", label: "Продающий" },
              { value: "строгий", label: "Строгий" },
            ]}
            onChange={(val: string) => setFlowDraft((prev) => ({ ...prev, settings: { ...prev.settings, mood: val } }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-600">Кастомный промпт</label>
          <input
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
            placeholder="Например: отвечай кратко и по делу"
            value={flowDraft.settings.custom_prompt}
            onChange={(e) => setFlowDraft((prev) => ({ ...prev, settings: { ...prev.settings, custom_prompt: e.target.value } }))}
          />
          <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={flowDraft.settings.use_history}
              onChange={(e) => setFlowDraft((prev) => ({ ...prev, settings: { ...prev.settings, use_history: e.target.checked } }))}
            />
            Учитывать контекст диалога
          </label>
        </div>
      </div>

      <div className="tb-flow-layout">
        <div>
          <div
            ref={canvasRef}
            className="tb-flow-canvas"
            style={{ ["--flow-scale" as any]: flowScale }}
            onMouseDown={onCanvasMouseDown}
          >
            <div className="tb-flow-zoom-stage" style={flowStageStyle}>
              <svg className="tb-flow-lines">
                {flowDraft.edges.map((edge) => (
                  <g key={edge.id}>
                    <path
                      className={`tb-flow-edge-halo${selectedEdgeId === edge.id ? " is-selected" : ""}${hoverEdgeId === edge.id ? " is-hover" : ""}`}
                      d={edgePath(edge)}
                    />
                    <path
                      className={`tb-flow-edge-line${selectedEdgeId === edge.id ? " is-selected" : ""}${hoverEdgeId === edge.id ? " is-hover" : ""}`}
                      d={edgePath(edge)}
                    />
                    <path
                      className="tb-flow-edge-hit"
                      d={edgePath(edge)}
                      onMouseEnter={() => setHoverEdgeId(edge.id)}
                      onMouseLeave={() => setHoverEdgeId(null)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedEdgeId(edge.id);
                        setSelectedNodeId(null);
                      }}
                    />
                  </g>
                ))}
                {connectPreview && <path className="tb-flow-edge-line" d={connectPreviewPath} />}
              </svg>
              {flowDraft.nodes.map((node) => (
                <div
                  key={node.id}
                  className={`tb-flow-node${selectedNodeId === node.id ? " is-selected" : ""}`}
                  style={nodeStyle(node)}
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    onNodeMouseDown(node, e);
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    ensureNodeConfig(node);
                    setSelectedNodeId(node.id);
                    setSelectedEdgeId(null);
                  }}
                >
                  <div className="tb-flow-node-header">
                    <span className="tb-flow-node-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none">
                        <path d={nodeIconPath(node.type)} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                    <div className="tb-flow-node-title">{node.title || displayName(node.type)}</div>
                    <div className="tb-flow-node-type">{displayName(node.type)}</div>
                  </div>
                  <div className="tb-flow-node-ports tb-flow-node-ports-in">
                    <div
                      className="tb-flow-port tb-flow-port-in"
                      onMouseUp={(e) => {
                        e.stopPropagation();
                        onPortMouseUp(node);
                      }}
                    ></div>
                  </div>
                  <div className="tb-flow-node-ports tb-flow-node-ports-out">
                    <div
                      className="tb-flow-port tb-flow-port-out"
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        onPortMouseDown(node, e);
                      }}
                    ></div>
                  </div>
                  <div className="tb-flow-port-stub">
                    <div className="tb-flow-port-line"></div>
                    <button className="tb-flow-plus" onClick={(e) => {
                      e.stopPropagation();
                      addFlowNodeAfter(node);
                    }}>+</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="tb-flow-chat">
            <div className="tb-flow-chat-log">
              {flowChatLog.map((msg, idx) => (
                <div key={idx} className={`tb-flow-chat-msg${msg.role === "user" ? " is-user" : ""}`}>
                  <div>{msg.text}</div>
                  {msg.trace && <div className="tb-flow-chat-trace">{msg.trace}</div>}
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <div>
                <label className="text-xs text-slate-600">Тестовое сообщение</label>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                  placeholder="Введите сообщение клиента"
                  value={flowTestInput}
                  onChange={(e) => setFlowTestInput(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <button className="rounded-lg bg-sky-600 px-3 py-1 text-sm font-semibold text-white" onClick={runFlowTest} disabled={flowTesting}>
                  {flowTesting ? "Тестирую..." : "Тестовый прогон"}
                </button>
                <button className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm" onClick={resetFlowTest}>
                  Сбросить контекст
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="tb-flow-panel">
          {selectedNode ? (
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Параметры узла</h3>
              <div className="mt-3 space-y-3">
                <div>
                  <label className="text-xs text-slate-600">Название</label>
                  <input
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                    value={selectedNode.title || ""}
                    onChange={(e) => updateNode(selectedNode.id, { title: e.target.value })}
                  />
                </div>

                {selectedNode.type === "ask" && (
                  <>
                    <div>
                      <label className="text-xs text-slate-600">Вопрос</label>
                      <textarea
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                        rows={3}
                        value={selectedNode.config?.question || ""}
                        onChange={(e) => updateNodeConfig(selectedNode.id, { question: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-600">Сохранять в переменную</label>
                      <input
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                        placeholder="например: phone"
                        value={selectedNode.config?.var || ""}
                        onChange={(e) => updateNodeConfig(selectedNode.id, { var: e.target.value })}
                      />
                    </div>
                  </>
                )}

                {selectedNode.type === "message" && (
                  <div>
                    <label className="text-xs text-slate-600">Текст</label>
                    <textarea
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                      rows={4}
                      value={selectedNode.config?.text || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { text: e.target.value })}
                    />
                  </div>
                )}

                {selectedNode.type === "branch" && (
                  <div>
                    <label className="text-xs text-slate-600">Смыслы</label>
                    {(selectedNode.config?.meanings || []).map((m: any, idx: number) => (
                      <div key={idx} className="tb-flow-cond">
                        <input
                          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                          placeholder="Название смысла"
                          value={m.title || ""}
                          onChange={(e) => {
                            const next = [...selectedNode.config.meanings];
                            next[idx] = { ...next[idx], title: e.target.value };
                            updateNodeConfig(selectedNode.id, { meanings: next });
                          }}
                        />
                        <textarea
                          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                          rows={2}
                          placeholder="Фразы через запятую"
                          value={m.phrases || ""}
                          onChange={(e) => {
                            const next = [...selectedNode.config.meanings];
                            next[idx] = { ...next[idx], phrases: e.target.value };
                            updateNodeConfig(selectedNode.id, { meanings: next });
                          }}
                        />
                        <div className="tb-flow-cond-row">
                          <input
                            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                            placeholder="id"
                            value={m.id || ""}
                            onChange={(e) => {
                              const next = [...selectedNode.config.meanings];
                              next[idx] = { ...next[idx], id: e.target.value };
                              updateNodeConfig(selectedNode.id, { meanings: next });
                            }}
                          />
                          <input
                            type="number"
                            step={0.1}
                            min={0}
                            max={1}
                            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                            value={m.sensitivity ?? 0.5}
                            onChange={(e) => {
                              const next = [...selectedNode.config.meanings];
                              next[idx] = { ...next[idx], sensitivity: Number(e.target.value) };
                              updateNodeConfig(selectedNode.id, { meanings: next });
                            }}
                          />
                          <button className="tb-mini tb-mini-danger" onClick={() => removeMeaning(idx)}>Удалить</button>
                        </div>
                      </div>
                    ))}
                    <button className="tb-mini" onClick={addMeaning}>Добавить смысл</button>
                  </div>
                )}

                {selectedNode.type === "kb_answer" && (
                  <div>
                    <label className="text-xs text-slate-600">Дополнительный промпт</label>
                    <textarea
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                      rows={3}
                      value={selectedNode.config?.pre_prompt || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { pre_prompt: e.target.value })}
                    />
                  </div>
                )}

                {selectedNode.type === "webhook" && (
                  <>
                    <div>
                      <label className="text-xs text-slate-600">URL</label>
                      <input
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                        placeholder="https://..."
                        value={selectedNode.config?.url || ""}
                        onChange={(e) => updateNodeConfig(selectedNode.id, { url: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-600">Payload (JSON)</label>
                      <textarea
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                        rows={4}
                        value={selectedNode.config?.payload || ""}
                        onChange={(e) => updateNodeConfig(selectedNode.id, { payload: e.target.value })}
                      />
                    </div>
                  </>
                )}

                {(selectedNode.type === "bitrix_lead" || selectedNode.type === "bitrix_deal") && (
                  <div>
                    <label className="text-xs text-slate-600">Fields (JSON)</label>
                    <textarea
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                      rows={4}
                      value={selectedNode.config?.fields || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { fields: e.target.value })}
                    />
                  </div>
                )}

                {selectedNode.type === "handoff" && (
                  <div>
                    <label className="text-xs text-slate-600">Текст</label>
                    <textarea
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
                      rows={3}
                      value={selectedNode.config?.text || ""}
                      onChange={(e) => updateNodeConfig(selectedNode.id, { text: e.target.value })}
                    />
                  </div>
                )}

                <div className="tb-flow-node-actions">
                  <button className="tb-mini tb-mini-danger" onClick={removeSelectedNode}>Удалить узел</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500">Выберите узел для редактирования.</div>
          )}

          <div className="mt-4 rounded-xl border border-slate-100 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">Связи</h3>
            <div className="mt-2">
              {flowDraft.edges.map((edge) => (
                <div key={edge.id} className="tb-flow-edge">
                  <div className="text-xs text-slate-500">{edge.from}</div>
                  <div className="text-xs text-slate-500">→ {edge.to}</div>
                  <button className="tb-mini tb-mini-danger" onClick={() => removeEdge(edge.id)}>Удалить</button>
                </div>
              ))}
              {flowDraft.edges.length === 0 && <div className="text-sm text-slate-500">Связей пока нет.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
