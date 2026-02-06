import { useEffect, useState } from "react";
import { api, getAuthToken } from "../../api/client";

type Portal = { id: number; domain: string };
type KBFile = {
  id: number;
  portal_id: number;
  filename: string;
  mime_type?: string;
  size_bytes: number;
  status: string;
  error_message?: string;
  created_at?: string;
};

type CredsStatus = {
  api_base: string;
  model: string;
  embedding_model?: string;
  chat_model?: string;
  scope: string;
  has_client_id: boolean;
  has_auth_key: boolean;
  has_access_token: boolean;
  access_token_expires_at?: number | null;
  client_id_masked?: string;
  auth_key_masked?: string;
  auth_key_input_masked?: string;
  auth_key_input_len?: number;
  auth_key_updated?: boolean;
  auth_key_input_sha12?: string;
  auth_key_sha12?: string;
  auth_key_mismatch?: boolean;
};

type ModelItem = { id?: string; name?: string; model?: string; object?: string };
type PortalKbSettings = { embedding_model?: string; chat_model?: string; api_base?: string; prompt_preset?: string };
type Pricing = { chat_rub_per_1k: number; embed_rub_per_1k: number };

const DEFAULT_API_BASE = "https://gigachat.devices.sberbank.ru/api/v1";

export function KnowledgeBasePage() {
  const [portals, setPortals] = useState<Portal[]>([]);
  const [files, setFiles] = useState<KBFile[]>([]);
  const [portalId, setPortalId] = useState<number | "">("");
  const [loading, setLoading] = useState(false);
  const [creds, setCreds] = useState<CredsStatus | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [portalSettings, setPortalSettings] = useState<PortalKbSettings | null>(null);
  const [tokenError, setTokenError] = useState<string>("");
  const [pricing, setPricing] = useState<Pricing>({ chat_rub_per_1k: 0, embed_rub_per_1k: 0 });
  const [form, setForm] = useState({
    api_base: DEFAULT_API_BASE,
    embedding_model: "",
    chat_model: "",
    model: "",
    client_id: "",
    scope: "GIGACHAT_API_PERS",
    auth_key: "",
  });

  useEffect(() => {
    api.get("/v1/admin/portals").then((d) => {
      setPortals(d.items || []);
    });
    api.get("/v1/admin/kb/credentials").then((d) => {
      setCreds(d);
      setForm((f) => ({
        ...f,
        api_base: d.api_base || DEFAULT_API_BASE,
        embedding_model: d.embedding_model || d.model || "",
        chat_model: d.chat_model || "",
        model: d.model || "",
        scope: d.scope || f.scope,
      }));
    });
    api.get("/v1/admin/billing/pricing").then((d) => {
      if (d) setPricing(d);
    });
    refreshFiles();
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      refreshFiles();
    }, 15000);
    return () => clearInterval(id);
  }, [portalId]);

  useEffect(() => {
    if (!portalId) {
      setPortalSettings(null);
      return;
    }
    const t = getAuthToken();
    fetch(`/api/v1/admin/kb/portals/${portalId}/settings`, {
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setPortalSettings(d);
      })
      .catch(() => null);
  }, [portalId]);

  useEffect(() => {
    if (!creds?.has_auth_key) return;
    const id = setInterval(() => {
      handleRefreshToken().catch(() => null);
    }, 25 * 60 * 1000);
    return () => clearInterval(id);
  }, [creds?.has_auth_key]);

  const refreshFiles = () => {
    const qs = portalId ? `?portal_id=${portalId}` : "";
    api.get(`/v1/admin/kb/files${qs}`).then((d) => setFiles(d.items || []));
  };

  const handleSaveCreds = async () => {
    setTokenError("");
    const fd = new FormData();
    fd.append("api_base", form.api_base || DEFAULT_API_BASE);
    fd.append("embedding_model", form.embedding_model || "");
    fd.append("chat_model", form.chat_model || "");
    fd.append("model", form.embedding_model || form.model || "");
    if (form.client_id) fd.append("client_id", form.client_id);
    if (form.scope) fd.append("scope", form.scope);
    if (form.auth_key) fd.append("auth_key", form.auth_key);
    const t = getAuthToken();
    const res = await fetch("/api/v1/admin/kb/credentials", {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setCreds(data);
    setForm((f) => ({ ...f, auth_key: "" }));
    if (data?.token_error) {
      setTokenError(data.token_error);
    } else if (data?.has_access_token) {
      setTokenError("");
    }
  };

  const handleRefreshToken = async () => {
    setTokenError("");
    const t = getAuthToken();
    const res = await fetch("/api/v1/admin/kb/token/refresh", {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
    });
    if (!res.ok) {
      const msg = await res.text();
      setTokenError(msg || "Ошибка получения токена");
      throw new Error(msg || "token_error");
    }
    await res.json().catch(() => null);
    const updated = await api.get("/v1/admin/kb/credentials");
    setCreds(updated);
  };

  const handleLoadModels = async () => {
    setTokenError("");
    const t = getAuthToken();
    const res = await fetch("/api/v1/admin/kb/models", {
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
    });
    if (!res.ok) {
      const msg = await res.text();
      setTokenError(msg || "Ошибка загрузки моделей");
      return;
    }
    const data = await res.json();
    const items: ModelItem[] = data.items || [];
    const names = items
      .map((m) => m.id || m.model || m.name)
      .filter((v): v is string => !!v);
    setModels(names);
    if (names.length > 0) {
      const emb = names.find((n) => n.toLowerCase().includes("embed")) || names[0];
      const chat = names.find((n) => !n.toLowerCase().includes("embed")) || names[0];
      setForm((f) => ({
        ...f,
        embedding_model: f.embedding_model || emb,
        chat_model: f.chat_model || chat,
      }));
    }
  };

  const handleSavePortalSettings = async () => {
    if (!portalId) return;
    const t = getAuthToken();
    const fd = new FormData();
    if (portalSettings?.embedding_model !== undefined) fd.append("embedding_model", portalSettings.embedding_model || "");
    if (portalSettings?.chat_model !== undefined) fd.append("chat_model", portalSettings.chat_model || "");
    if (portalSettings?.api_base !== undefined) fd.append("api_base", portalSettings.api_base || "");
    if (portalSettings?.prompt_preset !== undefined) fd.append("prompt_preset", portalSettings.prompt_preset || "");
    const res = await fetch(`/api/v1/admin/kb/portals/${portalId}/settings`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : undefined,
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setPortalSettings(data);
  };

  const handleSavePricing = async () => {
    const t = getAuthToken();
    const res = await fetch("/api/v1/admin/billing/pricing", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
      },
      body: JSON.stringify(pricing),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setPricing(data);
  };

  const handleUpload = async (filesList: FileList | null) => {
    if (!filesList || filesList.length === 0) return;
    if (!portalId) return;
    setLoading(true);
    const t = getAuthToken();
    try {
      for (const f of Array.from(filesList)) {
        const fd = new FormData();
        fd.append("portal_id", String(portalId));
        fd.append("file", f);
        const res = await fetch("/api/v1/admin/kb/files/upload", {
          method: "POST",
          headers: t ? { Authorization: `Bearer ${t}` } : undefined,
          body: fd,
        });
        if (!res.ok) {
          await res.text();
        }
      }
    } finally {
      setLoading(false);
      refreshFiles();
    }
  };

  const formatExpires = (v?: number | null) => {
    if (!v) return "—";
    try {
      return new Date(v * 1000).toLocaleString();
    } catch {
      return "—";
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded shadow p-6">
        <h1 className="text-xl font-semibold mb-4">База знаний</h1>
        <p className="text-sm text-gray-600">
          Загрузка файлов и настройки GigaChat. Векторная индексация будет
          добавлена в следующем шаге.
        </p>
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">GigaChat креды</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm">
            API base
            <input
              className="w-full border rounded p-2 mt-1"
              value={form.api_base}
              onChange={(e) => setForm({ ...form, api_base: e.target.value })}
            />
            <div className="text-xs text-gray-500 mt-1">По умолчанию: {DEFAULT_API_BASE}</div>
          </label>
          <label className="text-sm">
            Embedding model
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.embedding_model}
              onChange={(e) => setForm({ ...form, embedding_model: e.target.value })}
            >
              <option value="">Выберите модель</option>
              {form.embedding_model && !models.includes(form.embedding_model) && (
                <option value={form.embedding_model}>{form.embedding_model}</option>
              )}
              {models.map((m) => (
                <option key={`emb-${m}`} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <button className="mt-2 px-3 py-1 border rounded" onClick={handleLoadModels}>
              Загрузить модели
            </button>
          </label>
          <label className="text-sm">
            Chat model
            <select
              className="w-full border rounded p-2 mt-1"
              value={form.chat_model}
              onChange={(e) => setForm({ ...form, chat_model: e.target.value })}
            >
              <option value="">Выберите модель</option>
              {form.chat_model && !models.includes(form.chat_model) && (
                <option value={form.chat_model}>{form.chat_model}</option>
              )}
              {models.map((m) => (
                <option key={`chat-${m}`} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <div className="text-xs text-gray-500 mt-1">Для диалогов нужна чат‑модель (не embeddings).</div>
          </label>
          <label className="text-sm">
            Client ID
            <input
              className="w-full border rounded p-2 mt-1"
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              placeholder={creds?.client_id_masked || ""}
            />
          </label>
          <label className="text-sm">
            Scope
            <input
              className="w-full border rounded p-2 mt-1"
              value={form.scope}
              onChange={(e) => setForm({ ...form, scope: e.target.value })}
            />
          </label>
          <label className="text-sm md:col-span-2">
            Authorization key
            <input
              type="password"
              className="w-full border rounded p-2 mt-1"
              value={form.auth_key}
              onChange={(e) => setForm({ ...form, auth_key: e.target.value })}
              placeholder={creds?.auth_key_masked || ""}
            />
          </label>
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={handleSaveCreds}>
            Сохранить
          </button>
          <button className="px-3 py-2 border rounded" onClick={handleRefreshToken}>
            Обновить токен вручную
          </button>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Токен обновляется автоматически после сохранения и по таймеру.
        </div>
        {creds && (
          <div className="text-sm text-gray-700 mt-3">
            Статус: client_id {creds.has_client_id ? "ok" : "нет"}, auth_key{" "}
            {creds.has_auth_key ? "ok" : "нет"}, token{" "}
            {creds.has_access_token ? "ok" : "нет"}, expires_at {formatExpires(creds.access_token_expires_at)}
            {creds.embedding_model ? `, embed: ${creds.embedding_model}` : ""}
            {creds.chat_model ? `, chat: ${creds.chat_model}` : ""}
            {creds.auth_key_masked ? `, auth_key: ${creds.auth_key_masked}` : ""}
            {typeof creds.auth_key_input_len === "number" ? `, input_len: ${creds.auth_key_input_len}` : ""}
            {creds.auth_key_input_masked ? `, input: ${creds.auth_key_input_masked}` : ""}
            {typeof creds.auth_key_updated === "boolean" ? `, updated: ${creds.auth_key_updated ? "yes" : "no"}` : ""}
            {creds.auth_key_input_sha12 ? `, input_sha12: ${creds.auth_key_input_sha12}` : ""}
            {creds.auth_key_sha12 ? `, stored_sha12: ${creds.auth_key_sha12}` : ""}
            {typeof creds.auth_key_mismatch === "boolean"
              ? `, mismatch: ${creds.auth_key_mismatch ? "yes" : "no"}`
              : ""}
          </div>
        )}
        {tokenError && <div className="text-sm text-red-600 mt-2">{tokenError}</div>}
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Тарифы (рубли)</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm">
            Чат: руб/1000 токенов
            <input
              className="w-full border rounded p-2 mt-1"
              type="number"
              step="0.01"
              value={pricing.chat_rub_per_1k}
              onChange={(e) => setPricing((p) => ({ ...p, chat_rub_per_1k: Number(e.target.value) }))}
            />
          </label>
          <label className="text-sm">
            Эмбеддинги: руб/1000 токенов
            <input
              className="w-full border rounded p-2 mt-1"
              type="number"
              step="0.01"
              value={pricing.embed_rub_per_1k}
              onChange={(e) => setPricing((p) => ({ ...p, embed_rub_per_1k: Number(e.target.value) }))}
            />
          </label>
        </div>
        <div className="mt-3">
          <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={handleSavePricing}>
            Сохранить тарифы
          </button>
        </div>
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Модели для портала</h2>
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
            Настройки применяются только к выбранному порталу.
          </span>
        </div>
        {portalId ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm">
                Embedding model
              <select
                className="w-full border rounded p-2 mt-1"
                value={portalSettings?.embedding_model || ""}
                onChange={(e) =>
                  setPortalSettings((p) => ({ ...(p || {}), embedding_model: e.target.value }))
                }
              >
                <option value="">—</option>
                {portalSettings?.embedding_model &&
                  !models.includes(portalSettings.embedding_model) && (
                    <option value={portalSettings.embedding_model}>{portalSettings.embedding_model}</option>
                  )}
                {models.map((m) => (
                  <option key={`p-emb-${m}`} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              </label>
              <label className="text-sm">
                Chat model
              <select
                className="w-full border rounded p-2 mt-1"
                value={portalSettings?.chat_model || ""}
                onChange={(e) =>
                  setPortalSettings((p) => ({ ...(p || {}), chat_model: e.target.value }))
                }
              >
                <option value="">—</option>
                {portalSettings?.chat_model && !models.includes(portalSettings.chat_model) && (
                  <option value={portalSettings.chat_model}>{portalSettings.chat_model}</option>
                )}
                {models.map((m) => (
                  <option key={`p-chat-${m}`} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              </label>
              <label className="text-sm md:col-span-2">
                API base (опционально)
                <input
                  className="w-full border rounded p-2 mt-1"
                  value={portalSettings?.api_base || ""}
                  onChange={(e) =>
                    setPortalSettings((p) => ({ ...(p || {}), api_base: e.target.value }))
                  }
                />
              </label>
              <label className="text-sm md:col-span-2">
                Пресет ответа
                <select
                  className="w-full border rounded p-2 mt-1"
                  value={portalSettings?.prompt_preset || "auto"}
                  onChange={(e) =>
                    setPortalSettings((p) => ({ ...(p || {}), prompt_preset: e.target.value }))
                  }
                >
                  <option value="auto">Авто (по запросу)</option>
                  <option value="summary">Краткий обзор</option>
                  <option value="faq">FAQ</option>
                  <option value="timeline">Таймлайн</option>
                </select>
              </label>
            </div>
            <div className="flex items-center gap-3 mt-4">
              <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={handleSavePortalSettings}>
                Сохранить для портала
              </button>
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-500">Выберите портал, чтобы настроить модели.</div>
        )}
      </div>

      <div className="bg-white rounded shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Загрузка файлов</h2>
        <div className="flex items-center gap-4">
          <input
            type="file"
            multiple
            onChange={(e) => handleUpload(e.target.files)}
            disabled={!portalId || loading}
          />
          <button className="px-3 py-2 border rounded" onClick={refreshFiles}>
            Обновить список
          </button>
        </div>
        <div className="mt-4 overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">ID</th>
                <th className="p-2">Портал</th>
                <th className="p-2">Файл</th>
                <th className="p-2">Размер</th>
                <th className="p-2">Статус</th>
                <th className="p-2">Ошибка</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id} className="border-b">
                  <td className="p-2">{f.id}</td>
                  <td className="p-2">{f.portal_id}</td>
                  <td className="p-2">{f.filename}</td>
                  <td className="p-2">{f.size_bytes}</td>
                  <td className="p-2">{f.status}</td>
                  <td className="p-2">{f.error_message || ""}</td>
                </tr>
              ))}
              {files.length === 0 && (
                <tr>
                  <td className="p-2 text-gray-500" colSpan={6}>
                    Пока нет файлов
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
