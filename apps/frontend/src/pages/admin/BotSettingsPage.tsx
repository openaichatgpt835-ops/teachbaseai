import { useEffect, useState } from "react";
import { api, getAuthToken } from "../../api/client";

type Portal = { id: number; domain: string };

type BotSettings = {
  temperature: number;
  max_tokens: number;
  top_p: number | null;
  presence_penalty: number | null;
  frequency_penalty: number | null;
  allow_general: boolean;
  strict_mode: boolean;
  context_messages: number;
  context_chars: number;
  retrieval_top_k: number;
  retrieval_max_chars: number;
  lex_boost: number;
  use_history: boolean;
  use_cache: boolean;
  system_prompt_extra: string;
};

type PortalSettings = Partial<BotSettings>;

const boolOptions = [
  { label: "Наследовать", value: "inherit" },
  { label: "Включить", value: "true" },
  { label: "Выключить", value: "false" },
];

const toBool = (v: string): boolean | null => {
  if (v === "true") return true;
  if (v === "false") return false;
  return null;
};

export function BotSettingsPage() {
  const [portals, setPortals] = useState<Portal[]>([]);
  const [portalId, setPortalId] = useState<number | "">("");
  const [globalSettings, setGlobalSettings] = useState<BotSettings | null>(null);
  const [form, setForm] = useState<BotSettings>({
    temperature: 0.2,
    max_tokens: 700,
    top_p: null,
    presence_penalty: null,
    frequency_penalty: null,
    allow_general: false,
    strict_mode: true,
    context_messages: 6,
    context_chars: 4000,
    retrieval_top_k: 5,
    retrieval_max_chars: 4000,
    lex_boost: 0.12,
    use_history: true,
    use_cache: true,
    system_prompt_extra: "",
  });
  const [portalForm, setPortalForm] = useState<{
    temperature: string;
    max_tokens: string;
    top_p: string;
    presence_penalty: string;
    frequency_penalty: string;
    allow_general: string;
    strict_mode: string;
    context_messages: string;
    context_chars: string;
    retrieval_top_k: string;
    retrieval_max_chars: string;
    lex_boost: string;
    use_history: string;
    use_cache: string;
    system_prompt_extra: string;
  }>({
    temperature: "",
    max_tokens: "",
    top_p: "",
    presence_penalty: "",
    frequency_penalty: "",
    allow_general: "inherit",
    strict_mode: "inherit",
    context_messages: "",
    context_chars: "",
    retrieval_top_k: "",
    retrieval_max_chars: "",
    lex_boost: "",
    use_history: "inherit",
    use_cache: "inherit",
    system_prompt_extra: "",
  });

  useEffect(() => {
    api.get("/v1/admin/portals").then((d) => setPortals(d.items || []));
    api.get("/v1/admin/bot/settings").then((d) => {
      setGlobalSettings(d);
      setForm((f) => ({ ...f, ...d }));
    });
  }, []);

  useEffect(() => {
    if (!portalId) return;
    const t = getAuthToken();
    fetch(`/api/v1/admin/kb/portals/${portalId}/settings`, {
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: PortalSettings | null) => {
        if (!d) return;
        setPortalForm({
          temperature: d.temperature?.toString() || "",
          max_tokens: d.max_tokens?.toString() || "",
          top_p: d.top_p?.toString() || "",
          presence_penalty: d.presence_penalty?.toString() || "",
          frequency_penalty: d.frequency_penalty?.toString() || "",
          allow_general: d.allow_general === true ? "true" : d.allow_general === false ? "false" : "inherit",
          strict_mode: d.strict_mode === true ? "true" : d.strict_mode === false ? "false" : "inherit",
          context_messages: d.context_messages?.toString() || "",
          context_chars: d.context_chars?.toString() || "",
          retrieval_top_k: d.retrieval_top_k?.toString() || "",
          retrieval_max_chars: d.retrieval_max_chars?.toString() || "",
          lex_boost: d.lex_boost?.toString() || "",
          use_history: d.use_history === true ? "true" : d.use_history === false ? "false" : "inherit",
          use_cache: d.use_cache === true ? "true" : d.use_cache === false ? "false" : "inherit",
          system_prompt_extra: d.system_prompt_extra || "",
        });
      })
      .catch(() => null);
  }, [portalId]);

  const saveGlobal = async () => {
    const t = getAuthToken();
    const res = await fetch("/api/v1/admin/bot/settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
      },
      body: JSON.stringify(form),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setGlobalSettings(data);
    setForm((f) => ({ ...f, ...data }));
  };

  const savePortal = async () => {
    if (!portalId) return;
    const fd = new FormData();
    const addNum = (k: string, v: string) => {
      if (v !== "") fd.append(k, v);
    };
    addNum("temperature", portalForm.temperature);
    addNum("max_tokens", portalForm.max_tokens);
    addNum("top_p", portalForm.top_p);
    addNum("presence_penalty", portalForm.presence_penalty);
    addNum("frequency_penalty", portalForm.frequency_penalty);
    const ag = toBool(portalForm.allow_general);
    if (ag !== null) fd.append("allow_general", ag ? "true" : "false");
    const sm = toBool(portalForm.strict_mode);
    if (sm !== null) fd.append("strict_mode", sm ? "true" : "false");
    addNum("context_messages", portalForm.context_messages);
    addNum("context_chars", portalForm.context_chars);
    addNum("retrieval_top_k", portalForm.retrieval_top_k);
    addNum("retrieval_max_chars", portalForm.retrieval_max_chars);
    addNum("lex_boost", portalForm.lex_boost);
    const uh = toBool(portalForm.use_history);
    if (uh !== null) fd.append("use_history", uh ? "true" : "false");
    const uc = toBool(portalForm.use_cache);
    if (uc !== null) fd.append("use_cache", uc ? "true" : "false");
    if (portalForm.system_prompt_extra) fd.append("system_prompt_extra", portalForm.system_prompt_extra);
    const t = getAuthToken();
    const res = await fetch(`/api/v1/admin/kb/portals/${portalId}/settings`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
  };

  const renderNumberInput = (
    label: string,
    value: string,
    set: (v: string) => void,
    placeholder?: string
  ) => (
    <label className="text-sm">
      {label}
      <input
        className="w-full border rounded p-2 mt-1"
        value={value}
        placeholder={placeholder}
        onChange={(e) => set(e.target.value)}
      />
    </label>
  );

  return (
    <div className="space-y-6">
      <div className="bg-white rounded shadow p-6">
        <h1 className="text-xl font-semibold mb-2">Настройки бота</h1>
        <p className="text-sm text-gray-600">
          Управление качеством ответов, контекстом чата и политикой извлечения.
        </p>
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Глобальные настройки (по умолчанию)</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {renderNumberInput("Temperature", String(form.temperature), (v) => setForm((f) => ({ ...f, temperature: Number(v) || 0 })))}
          {renderNumberInput("Max tokens", String(form.max_tokens), (v) => setForm((f) => ({ ...f, max_tokens: Number(v) || 0 })))}
          {renderNumberInput("Top‑P", form.top_p?.toString() || "", (v) => setForm((f) => ({ ...f, top_p: v ? Number(v) : null })))}
          {renderNumberInput("Presence penalty", form.presence_penalty?.toString() || "", (v) => setForm((f) => ({ ...f, presence_penalty: v ? Number(v) : null })))}
          {renderNumberInput("Frequency penalty", form.frequency_penalty?.toString() || "", (v) => setForm((f) => ({ ...f, frequency_penalty: v ? Number(v) : null })))}
          {renderNumberInput("Контекст: сообщений", String(form.context_messages), (v) => setForm((f) => ({ ...f, context_messages: Number(v) || 0 })))}
          {renderNumberInput("Контекст: символов", String(form.context_chars), (v) => setForm((f) => ({ ...f, context_chars: Number(v) || 0 })))}
          {renderNumberInput("Retrieval top‑k", String(form.retrieval_top_k), (v) => setForm((f) => ({ ...f, retrieval_top_k: Number(v) || 0 })))}
          {renderNumberInput("Retrieval max chars", String(form.retrieval_max_chars), (v) => setForm((f) => ({ ...f, retrieval_max_chars: Number(v) || 0 })))}
          {renderNumberInput("Lex boost", String(form.lex_boost), (v) => setForm((f) => ({ ...f, lex_boost: Number(v) || 0 })))}
          <label className="text-sm">
            Разрешить ответы вне базы
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.allow_general ? "true" : "false"}
              onChange={(e) => setForm((f) => ({ ...f, allow_general: e.target.value === "true" }))}
            >
              <option value="false">Нет</option>
              <option value="true">Да</option>
            </select>
          </label>
          <label className="text-sm">
            Строгий режим (только база)
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.strict_mode ? "true" : "false"}
              onChange={(e) => setForm((f) => ({ ...f, strict_mode: e.target.value === "true" }))}
            >
              <option value="true">Да</option>
              <option value="false">Нет</option>
            </select>
          </label>
          <label className="text-sm">
            Использовать историю
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.use_history ? "true" : "false"}
              onChange={(e) => setForm((f) => ({ ...f, use_history: e.target.value === "true" }))}
            >
              <option value="true">Да</option>
              <option value="false">Нет</option>
            </select>
          </label>
          <label className="text-sm">
            Кэш релевантных чанков
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.use_cache ? "true" : "false"}
              onChange={(e) => setForm((f) => ({ ...f, use_cache: e.target.value === "true" }))}
            >
              <option value="true">Да</option>
              <option value="false">Нет</option>
            </select>
          </label>
          <label className="text-sm md:col-span-2">
            Доп. системная инструкция
            <textarea
              className="w-full border rounded p-2 mt-1"
              rows={3}
              value={form.system_prompt_extra}
              onChange={(e) => setForm((f) => ({ ...f, system_prompt_extra: e.target.value }))}
              placeholder="Например: отвечай кратко и без избыточных формальностей."
            />
          </label>
        </div>
        <div className="mt-4">
          <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={saveGlobal}>
            Сохранить глобально
          </button>
        </div>
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Переопределение для портала</h2>
        <div className="flex items-center gap-4 mb-4">
          <select
            className="border rounded p-2"
            value={portalId}
            onChange={(e) => setPortalId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">Выберите портал</option>
            {portals.map((p) => (
              <option key={`portal-${p.id}`} value={p.id}>
                {p.domain} (id {p.id})
              </option>
            ))}
          </select>
          <span className="text-xs text-gray-500">
            Пустые поля — наследование от глобальных настроек.
          </span>
        </div>
        {portalId ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              {renderNumberInput("Temperature", portalForm.temperature, (v) => setPortalForm((f) => ({ ...f, temperature: v })), globalSettings ? String(globalSettings.temperature) : "")}
              {renderNumberInput("Max tokens", portalForm.max_tokens, (v) => setPortalForm((f) => ({ ...f, max_tokens: v })), globalSettings ? String(globalSettings.max_tokens) : "")}
              {renderNumberInput("Top‑P", portalForm.top_p, (v) => setPortalForm((f) => ({ ...f, top_p: v })), globalSettings?.top_p?.toString() || "")}
              {renderNumberInput("Presence penalty", portalForm.presence_penalty, (v) => setPortalForm((f) => ({ ...f, presence_penalty: v })), globalSettings?.presence_penalty?.toString() || "")}
              {renderNumberInput("Frequency penalty", portalForm.frequency_penalty, (v) => setPortalForm((f) => ({ ...f, frequency_penalty: v })), globalSettings?.frequency_penalty?.toString() || "")}
              {renderNumberInput("Контекст: сообщений", portalForm.context_messages, (v) => setPortalForm((f) => ({ ...f, context_messages: v })), globalSettings ? String(globalSettings.context_messages) : "")}
              {renderNumberInput("Контекст: символов", portalForm.context_chars, (v) => setPortalForm((f) => ({ ...f, context_chars: v })), globalSettings ? String(globalSettings.context_chars) : "")}
              {renderNumberInput("Retrieval top‑k", portalForm.retrieval_top_k, (v) => setPortalForm((f) => ({ ...f, retrieval_top_k: v })), globalSettings ? String(globalSettings.retrieval_top_k) : "")}
              {renderNumberInput("Retrieval max chars", portalForm.retrieval_max_chars, (v) => setPortalForm((f) => ({ ...f, retrieval_max_chars: v })), globalSettings ? String(globalSettings.retrieval_max_chars) : "")}
              {renderNumberInput("Lex boost", portalForm.lex_boost, (v) => setPortalForm((f) => ({ ...f, lex_boost: v })), globalSettings ? String(globalSettings.lex_boost) : "")}
              <label className="text-sm">
                Разрешить ответы вне базы
                <select
                  className="w-full border rounded p-2 mt-1"
                  value={portalForm.allow_general}
                  onChange={(e) => setPortalForm((f) => ({ ...f, allow_general: e.target.value }))}
                >
                  {boolOptions.map((o) => (
                    <option key={`ag-${o.value}`} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                Строгий режим (только база)
                <select
                  className="w-full border rounded p-2 mt-1"
                  value={portalForm.strict_mode}
                  onChange={(e) => setPortalForm((f) => ({ ...f, strict_mode: e.target.value }))}
                >
                  {boolOptions.map((o) => (
                    <option key={`sm-${o.value}`} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                Использовать историю
                <select
                  className="w-full border rounded p-2 mt-1"
                  value={portalForm.use_history}
                  onChange={(e) => setPortalForm((f) => ({ ...f, use_history: e.target.value }))}
                >
                  {boolOptions.map((o) => (
                    <option key={`uh-${o.value}`} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                Кэш релевантных чанков
                <select
                  className="w-full border rounded p-2 mt-1"
                  value={portalForm.use_cache}
                  onChange={(e) => setPortalForm((f) => ({ ...f, use_cache: e.target.value }))}
                >
                  {boolOptions.map((o) => (
                    <option key={`uc-${o.value}`} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm md:col-span-2">
                Доп. системная инструкция
                <textarea
                  className="w-full border rounded p-2 mt-1"
                  rows={3}
                  value={portalForm.system_prompt_extra}
                  onChange={(e) => setPortalForm((f) => ({ ...f, system_prompt_extra: e.target.value }))}
                />
              </label>
            </div>
            <div className="mt-4">
              <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={savePortal}>
                Сохранить для портала
              </button>
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-500">Выберите портал, чтобы настроить переопределения.</div>
        )}
      </div>
    </div>
  );
}
