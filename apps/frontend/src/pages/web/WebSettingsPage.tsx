import { useEffect, useState, type ReactNode } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";
import { Select } from "../../components/Select";

type KbSettings = {
  embedding_model: string;
  chat_model: string;
  prompt_preset: string;
  system_prompt_extra: string;
  show_sources: boolean;
  sources_format: "detailed" | "short" | "none";
  collections_multi_assign: boolean;
  smart_folder_threshold: number | "";
  allow_general: boolean;
  strict_mode: boolean;
  use_history: boolean;
  use_cache: boolean;
  context_messages: number | "";
  context_chars: number | "";
  retrieval_top_k: number | "";
  retrieval_max_chars: number | "";
  lex_boost: number | "";
  temperature: number | "";
  max_tokens: number | "";
  top_p: number | "";
  presence_penalty: number | "";
  frequency_penalty: number | "";
};

const defaultSettings: KbSettings = {
  embedding_model: "",
  chat_model: "",
  prompt_preset: "auto",
  system_prompt_extra: "",
  show_sources: true,
  sources_format: "detailed",
  collections_multi_assign: true,
  smart_folder_threshold: 5,
  allow_general: false,
  strict_mode: true,
  use_history: true,
  use_cache: true,
  context_messages: 6,
  context_chars: 4000,
  retrieval_top_k: 5,
  retrieval_max_chars: 4000,
  lex_boost: 0.12,
  temperature: 0.2,
  max_tokens: 700,
  top_p: "",
  presence_penalty: "",
  frequency_penalty: "",
};

function toOptionalNumber(v: number | "") {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function toOptionalInt(v: number | "") {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

function HelpTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex items-center">
      <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 text-[10px] font-semibold text-slate-500">?</span>
      <span className="pointer-events-none absolute left-6 top-1/2 hidden -translate-y-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-3 py-1 text-[11px] text-white shadow-lg group-hover:block">
        {text}
      </span>
    </span>
  );
}

export function WebSettingsPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const [kbSettings, setKbSettings] = useState<KbSettings>(defaultSettings);
  const [embedModels, setEmbedModels] = useState<string[]>([]);
  const [chatModels, setChatModels] = useState<string[]>([]);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [loadingSettings, setLoadingSettings] = useState(false);

  useEffect(() => {
    if (!portalId || !portalToken) return;
    const loadModels = async () => {
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/models`);
        const data = await res.json().catch(() => null);
        if (res.ok && data?.items) {
          const names = data.items
            .map((m: any) => String(m.id || m.name || m.model || ""))
            .filter(Boolean);
          setEmbedModels(names.filter((n: string) => n.toLowerCase().includes("embed")));
          setChatModels(names.filter((n: string) => !n.toLowerCase().includes("embed")));
        }
      } catch {
        // ignore
      }
    };

    const loadSettings = async () => {
      setLoadingSettings(true);
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/settings`);
        const data = await res.json().catch(() => null);
        if (res.ok && data) {
          const next: KbSettings = {
            embedding_model: data.embedding_model || "EmbeddingsGigaR",
            chat_model: data.chat_model || "GigaChat-2-Pro",
            prompt_preset: data.prompt_preset || "auto",
            system_prompt_extra: data.system_prompt_extra || "",
            show_sources: data.show_sources !== false,
            sources_format: data.sources_format || "detailed",
            collections_multi_assign: data.collections_multi_assign !== false,
            smart_folder_threshold: data.smart_folder_threshold ?? 5,
            allow_general: !!data.allow_general,
            strict_mode: data.strict_mode !== false,
            use_history: data.use_history !== false,
            use_cache: data.use_cache !== false,
            context_messages: data.context_messages ?? 6,
            context_chars: data.context_chars ?? 4000,
            retrieval_top_k: data.retrieval_top_k ?? 5,
            retrieval_max_chars: data.retrieval_max_chars ?? 4000,
            lex_boost: data.lex_boost ?? 0.12,
            temperature: data.temperature ?? 0.2,
            max_tokens: data.max_tokens ?? 700,
            top_p: data.top_p ?? "",
            presence_penalty: data.presence_penalty ?? "",
            frequency_penalty: data.frequency_penalty ?? "",
          };
          if (!next.show_sources) {
            next.sources_format = "none";
          }
          setKbSettings(next);
        }
      } finally {
        setLoadingSettings(false);
      }
    };

    loadModels();
    loadSettings();
  }, [portalId, portalToken]);

  const saveSettings = async () => {
    if (!portalId || !portalToken) return;
    setSettingsMessage("Сохранение...");
    const payload = {
      ...kbSettings,
      top_p: toOptionalNumber(kbSettings.top_p),
      presence_penalty: toOptionalNumber(kbSettings.presence_penalty),
      frequency_penalty: toOptionalNumber(kbSettings.frequency_penalty),
      temperature: toOptionalNumber(kbSettings.temperature),
      max_tokens: toOptionalInt(kbSettings.max_tokens),
      context_messages: toOptionalInt(kbSettings.context_messages),
      context_chars: toOptionalInt(kbSettings.context_chars),
      retrieval_top_k: toOptionalInt(kbSettings.retrieval_top_k),
      retrieval_max_chars: toOptionalInt(kbSettings.retrieval_max_chars),
      lex_boost: toOptionalNumber(kbSettings.lex_boost),
      show_sources: kbSettings.sources_format === "none" ? false : kbSettings.show_sources,
      collections_multi_assign: kbSettings.collections_multi_assign,
      smart_folder_threshold: toOptionalInt(kbSettings.smart_folder_threshold),
    };
    try {
      const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      setSettingsMessage(res.ok ? "Сохранено" : (data?.error || "Ошибка"));
    } catch {
      setSettingsMessage("Ошибка");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Настройки</h1>
        <p className="text-sm text-slate-500 mt-1">Настройте модель, выдачу и интеграции ботов.</p>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">База знаний</h2>
          {loadingSettings && <span className="text-xs text-slate-500">Загрузка...</span>}
        </div>
        <div className="mt-4 space-y-4">
          <Field label="Embedding-модель" help="Модель для поиска по базе знаний. Обычно не требуется менять.">
            <Select
              value={kbSettings.embedding_model}
              placeholder="—"
              options={[{ value: "", label: "—" }, ...embedModels.map((m) => ({ value: m, label: m }))]}
              onChange={(val: string) => setKbSettings((prev) => ({ ...prev, embedding_model: val }))}
            />
          </Field>

          <Field label="Chat-модель" help="Основная модель, которая формирует ответ по найденным фрагментам.">
            <Select
              value={kbSettings.chat_model}
              placeholder="—"
              options={[{ value: "", label: "—" }, ...chatModels.map((m) => ({ value: m, label: m }))]}
              onChange={(val: string) => setKbSettings((prev) => ({ ...prev, chat_model: val }))}
            />
          </Field>

          <Field label="Пресет ответа" help="Выберите стиль ответа: краткий обзор, FAQ или таймлайн.">
            <Select
              value={kbSettings.prompt_preset}
              options={[
                { value: "auto", label: "Авто" },
                { value: "summary", label: "Краткий обзор" },
                { value: "faq", label: "FAQ" },
                { value: "timeline", label: "Таймлайн" },
              ]}
              onChange={(val: string) => setKbSettings((prev) => ({ ...prev, prompt_preset: val }))}
            />
          </Field>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={kbSettings.collections_multi_assign}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, collections_multi_assign: e.target.checked }))}
              />
              Разрешить файл в нескольких папках
            </label>
            <Field label="Порог для умных папок" help="Когда файлов по теме больше порога, предложим создать умную папку.">
              <input
                type="number"
                min={1}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={kbSettings.smart_folder_threshold}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, smart_folder_threshold: e.target.value === "" ? "" : Number(e.target.value) }))}
              />
            </Field>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Ответы бота</h2>
        <div className="mt-4 space-y-4">
          <Field label="Препромпт" help="Инструкция, которая добавляется в системное сообщение перед каждым ответом.">
            <textarea
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              rows={3}
              placeholder="Например: отвечай кратко и по делу."
              value={kbSettings.system_prompt_extra}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, system_prompt_extra: e.target.value }))}
            />
          </Field>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={kbSettings.show_sources}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, show_sources: e.target.checked }))}
            />
            Показывать источники в ответе
          </label>

          <Field label="Формат источников" help="Короткий список — только названия файлов. Подробный — с фрагментами.">
            <Select
              value={kbSettings.sources_format}
              options={[
                { value: "detailed", label: "Подробный (цитаты)" },
                { value: "short", label: "Короткий список" },
                { value: "none", label: "Не показывать" },
              ]}
              onChange={(val: string) => setKbSettings((prev) => ({ ...prev, sources_format: val as KbSettings["sources_format"] }))}
            />
          </Field>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={kbSettings.use_history}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, use_history: e.target.checked }))}
            />
            Учитывать контекст диалога
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Глубина контекста (сообщений)" help="Сколько последних сообщений учитывать при ответе.">
              <input
                type="number"
                min={0}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={kbSettings.context_messages}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, context_messages: e.target.value === "" ? "" : Number(e.target.value) }))}
              />
            </Field>
            <Field label="Ограничение контекста (символы)" help="Максимальный объём контекста, который отправляется в модель.">
              <input
                type="number"
                min={0}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={kbSettings.context_chars}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, context_chars: e.target.value === "" ? "" : Number(e.target.value) }))}
              />
            </Field>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={kbSettings.strict_mode}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, strict_mode: e.target.checked }))}
            />
            Строгий режим (только по базе знаний)
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={kbSettings.allow_general}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, allow_general: e.target.checked }))}
            />
            Разрешить общий ответ, если база знаний пуста
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={kbSettings.use_cache}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, use_cache: e.target.checked }))}
            />
            Использовать кэш релевантности
          </label>

          <div className="rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-500">
            Бот отвечает только по вашей базе знаний (файлы и URL-источники).
          </div>
        </div>
      </div>

      <details className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <summary className="cursor-pointer text-sm font-semibold text-slate-900">Продвинутые параметры</summary>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field label="Температура" help="Чем выше, тем более креативные ответы. Обычно 0.2–0.5.">
            <input
              type="number"
              step="0.05"
              min={0}
              max={1.5}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.temperature}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, temperature: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Макс. токенов" help="Ограничение длины ответа.">
            <input
              type="number"
              min={0}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.max_tokens}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, max_tokens: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Top-P" help="Альтернатива температуре для управления случайностью.">
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.top_p}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, top_p: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Штраф за повторение тем" help="Снижает повторяемость тем в ответах.">
            <input
              type="number"
              step="0.1"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.presence_penalty}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, presence_penalty: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Штраф за повторение слов" help="Снижает повторяемость слов и фраз.">
            <input
              type="number"
              step="0.1"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.frequency_penalty}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, frequency_penalty: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field label="Top-K фрагментов" help="Сколько фрагментов базы знаний передавать в модель.">
            <input
              type="number"
              min={1}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.retrieval_top_k}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, retrieval_top_k: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Макс. размер контекста из базы" help="Ограничение объёма найденных фрагментов.">
            <input
              type="number"
              min={0}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.retrieval_max_chars}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, retrieval_max_chars: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
          <Field label="Усиление лексики" help="Усиливает точное совпадение ключевых слов.">
            <input
              type="number"
              step="0.01"
              min={0}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={kbSettings.lex_boost}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, lex_boost: e.target.value === "" ? "" : Number(e.target.value) }))}
            />
          </Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
            onClick={saveSettings}
          >
            Сохранить
          </button>
          {settingsMessage && <div className="text-xs text-slate-500">{settingsMessage}</div>}
        </div>
      </details>
    </div>
  );
}

function Field({ label, help, children }: { label: string; help: string; children: ReactNode }) {
  return (
    <div>
      <label className="flex items-center text-xs text-slate-600">
        <span>{label}</span>
        <HelpTip text={help} />
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
