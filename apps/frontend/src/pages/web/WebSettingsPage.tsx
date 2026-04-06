import { useEffect, useState, type ReactNode } from "react";
import { PageIntro } from "../../components/PageIntro";
import { Select } from "../../components/Select";
import { UpgradeNoticeBar } from "../../components/LockedSection";
import { UPGRADE_COPY } from "../../shared/upgradeCopy";
import { appStateCopy } from "../../../../shared/ui/stateCopy";
import { fetchPortal, getWebPortalInfo } from "./auth";

type KbSettings = {
  embedding_model: string;
  chat_model: string;
  prompt_preset: string;
  system_prompt_extra: string;
  show_sources: boolean;
  sources_format: "detailed" | "short" | "none";
  media_transcription_enabled: boolean;
  speaker_diarization_enabled: boolean;
  media_transcription_available?: boolean;
  media_transcription_reason?: string;
  speaker_diarization_available?: boolean;
  speaker_diarization_reason?: string;
  model_selection_available?: boolean;
  model_selection_reason?: string;
  advanced_tuning_available?: boolean;
  advanced_tuning_reason?: string;
  billing_policy?: {
    account_id?: number | null;
    plan_code?: string | null;
    plan_name?: string | null;
    source?: string | null;
  };
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

const ANSWER_STYLE_OPTIONS = [
  { value: "concise", label: "Кратко" },
  { value: "balanced", label: "Сбалансированно" },
  { value: "detailed", label: "Развернуто" },
];

function normalizeAnswerStyle(value: string | undefined | null): string {
  const v = String(value || "").trim().toLowerCase();
  if (v === "concise" || v === "balanced" || v === "detailed") return v;
  return "balanced";
}

type SettingsCacheState = {
  kbSettings: KbSettings;
  embedModels: string[];
  chatModels: string[];
};

const defaultSettings: KbSettings = {
  embedding_model: "",
  chat_model: "",
  prompt_preset: "balanced",
  system_prompt_extra: "",
  show_sources: true,
  sources_format: "detailed",
  media_transcription_enabled: true,
  speaker_diarization_enabled: false,
  media_transcription_available: true,
  media_transcription_reason: "",
  collections_multi_assign: true,
  model_selection_available: true,
  model_selection_reason: "",
  advanced_tuning_available: true,
  advanced_tuning_reason: "",
  billing_policy: undefined,
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

const settingsCache = new Map<number, SettingsCacheState>();

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
  const cached = portalId ? settingsCache.get(portalId) : null;
  const [kbSettings, setKbSettings] = useState<KbSettings>(cached?.kbSettings || defaultSettings);
  const [embedModels, setEmbedModels] = useState<string[]>(cached?.embedModels || []);
  const [chatModels, setChatModels] = useState<string[]>(cached?.chatModels || []);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [loadingSettings, setLoadingSettings] = useState(!cached);
  const currentPlanName = kbSettings.billing_policy?.plan_name || "текущий тариф";
  const stateCopy = appStateCopy();

  useEffect(() => {
    if (!portalId || !portalToken) return;
    const cachedState = settingsCache.get(portalId);
    if (cachedState) {
      setKbSettings(cachedState.kbSettings);
      setEmbedModels(cachedState.embedModels);
      setChatModels(cachedState.chatModels);
      setLoadingSettings(false);
    }

    const loadModels = async () => {
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/kb/models`);
        const data = await res.json().catch(() => null);
        if (res.ok && data?.items) {
          const names = data.items.map((m: any) => String(m.id || m.name || m.model || "")).filter(Boolean);
          const nextEmbed = names.filter((n: string) => n.toLowerCase().includes("embed"));
          const nextChat = names.filter((n: string) => !n.toLowerCase().includes("embed"));
          setEmbedModels(nextEmbed);
          setChatModels(nextChat);
          const prev = settingsCache.get(portalId) || { kbSettings: cachedState?.kbSettings || defaultSettings, embedModels: [], chatModels: [] };
          settingsCache.set(portalId, { ...prev, embedModels: nextEmbed, chatModels: nextChat });
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
            prompt_preset: normalizeAnswerStyle(data.prompt_preset),
            system_prompt_extra: data.system_prompt_extra || "",
            show_sources: data.show_sources !== false,
            sources_format: data.sources_format || "detailed",
            media_transcription_enabled: data.media_transcription_enabled !== false,
            media_transcription_available: data.media_transcription_available !== false,
            media_transcription_reason: data.media_transcription_reason || "",
            speaker_diarization_enabled: !!data.speaker_diarization_enabled,
            speaker_diarization_available: data.speaker_diarization_available !== false,
            speaker_diarization_reason: data.speaker_diarization_reason || "",
            model_selection_available: data.model_selection_available !== false,
            model_selection_reason: data.model_selection_reason || "",
            advanced_tuning_available: data.advanced_tuning_available !== false,
            advanced_tuning_reason: data.advanced_tuning_reason || "",
            billing_policy: data.billing_policy || undefined,
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
          if (!next.show_sources) next.sources_format = "none";
          setKbSettings(next);
          const prev = settingsCache.get(portalId) || { kbSettings: defaultSettings, embedModels: cachedState?.embedModels || [], chatModels: cachedState?.chatModels || [] };
          settingsCache.set(portalId, { ...prev, kbSettings: next });
        }
      } finally {
        setLoadingSettings(false);
      }
    };

    loadModels();
    loadSettings();
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!portalId) return;
    const prev = settingsCache.get(portalId) || { kbSettings: defaultSettings, embedModels: [], chatModels: [] };
    settingsCache.set(portalId, { ...prev, kbSettings, embedModels, chatModels });
  }, [portalId, kbSettings, embedModels, chatModels]);

  const saveSettings = async () => {
    if (!portalId || !portalToken) return;
    setSettingsMessage(stateCopy.savingLabel);
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
      setSettingsMessage(res.ok ? stateCopy.savedLabel : (data?.error || stateCopy.genericError));
    } catch {
      setSettingsMessage(stateCopy.genericError);
    }
  };

  return (
    <div className="space-y-6">
      <PageIntro
        moduleId="settings"
        fallbackTitle="Настройки"
        fallbackDescription="Настройте модель, выдачу и интеграции ботов."
      />

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">База знаний</h2>
          {loadingSettings && <span className="text-xs text-slate-500">{stateCopy.loadingLabel}</span>}
        </div>
        {kbSettings.billing_policy?.plan_name && (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
            Текущий тариф: <span className="font-semibold text-slate-900">{kbSettings.billing_policy.plan_name}</span>
            {kbSettings.billing_policy.plan_code ? ` (${kbSettings.billing_policy.plan_code})` : ""}
          </div>
        )}
        <div className="mt-4 space-y-4">
          {kbSettings.model_selection_available ? (
            <>
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
            </>
          ) : (
            <div className="space-y-4">
              <UpgradeNoticeBar {...UPGRADE_COPY.modelSelection} planName={currentPlanName} compact />
              <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 opacity-70">
                <Field label="Embedding-модель" help="Модель для поиска по базе знаний. Обычно не требуется менять.">
                  <Select
                    value={kbSettings.embedding_model}
                    placeholder="—"
                    options={[{ value: "", label: "—" }, ...embedModels.map((m) => ({ value: m, label: m }))]}
                    disabled
                    onChange={() => null}
                  />
                </Field>

                <Field label="Chat-модель" help="Основная модель, которая формирует ответ по найденным фрагментам.">
                  <Select
                    value={kbSettings.chat_model}
                    placeholder="—"
                    options={[{ value: "", label: "—" }, ...chatModels.map((m) => ({ value: m, label: m }))]}
                    disabled
                    onChange={() => null}
                  />
                </Field>
              </div>
            </div>
          )}

          <Field label="Стиль ответа" help="Управляет подачей ответа: компактно, сбалансированно или более развернуто.">
            <Select
              value={kbSettings.prompt_preset}
              options={ANSWER_STYLE_OPTIONS}
              onChange={(val: string) => setKbSettings((prev) => ({ ...prev, prompt_preset: val }))}
            />
          </Field>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
                checked={kbSettings.media_transcription_enabled}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, media_transcription_enabled: e.target.checked }))}
                disabled={!kbSettings.media_transcription_available}
              />
              Включить опцию транскрибации медиа
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
                checked={kbSettings.speaker_diarization_enabled}
                onChange={(e) => setKbSettings((prev) => ({ ...prev, speaker_diarization_enabled: e.target.checked }))}
                disabled={!kbSettings.media_transcription_enabled || !kbSettings.speaker_diarization_available}
              />
              Разделять по спикерам (диаризация)
            </label>
            <div className="text-xs text-slate-500 md:col-span-2">
              Статус транскрибации: {kbSettings.media_transcription_available ? "доступна" : "недоступна"}
              {kbSettings.media_transcription_reason ? ` (${kbSettings.media_transcription_reason})` : ""}
              <br />
              Статус диаризации: {kbSettings.speaker_diarization_available ? "доступна" : "недоступна"}
              {kbSettings.speaker_diarization_reason ? ` (${kbSettings.speaker_diarization_reason})` : ""}
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
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
              disabled={!kbSettings.advanced_tuning_available}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, system_prompt_extra: e.target.value }))}
            />
          </Field>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
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
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
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
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
              checked={kbSettings.strict_mode}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, strict_mode: e.target.checked }))}
            />
            Строгий режим (только по базе знаний)
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
              checked={kbSettings.allow_general}
              onChange={(e) => setKbSettings((prev) => ({ ...prev, allow_general: e.target.checked }))}
            />
            Разрешить общий ответ, если база знаний пуста
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
                className="h-4 w-4 rounded border-slate-300 accent-sky-600"
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

      {kbSettings.advanced_tuning_available ? (
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
      ) : (
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-semibold text-slate-900">Продвинутые параметры</div>
          <div className="mt-4 space-y-4">
            <UpgradeNoticeBar {...UPGRADE_COPY.advancedTuning} planName={currentPlanName} />
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 opacity-70">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Температура" help="Чем выше, тем более креативные ответы. Обычно 0.2–0.5.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.temperature} disabled onChange={() => null} />
                  </Field>
                  <Field label="Макс. токенов" help="Ограничение длины ответа.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.max_tokens} disabled onChange={() => null} />
                  </Field>
                  <Field label="Top-P" help="Альтернатива температуре для управления случайностью.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.top_p} disabled onChange={() => null} />
                  </Field>
                  <Field label="Штраф за повторение тем" help="Снижает повторяемость тем в ответах.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.presence_penalty} disabled onChange={() => null} />
                  </Field>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Top-K фрагментов" help="Сколько фрагментов базы знаний передавать в модель.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.retrieval_top_k} disabled onChange={() => null} />
                  </Field>
                  <Field label="Макс. размер контекста из базы" help="Ограничение объёма найденных фрагментов.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.retrieval_max_chars} disabled onChange={() => null} />
                  </Field>
                  <Field label="Усиление лексики" help="Усиливает точное совпадение ключевых слов.">
                    <input type="number" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" value={kbSettings.lex_boost} disabled onChange={() => null} />
                  </Field>
                </div>
              </div>
            </div>
        </div>
      )}
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
