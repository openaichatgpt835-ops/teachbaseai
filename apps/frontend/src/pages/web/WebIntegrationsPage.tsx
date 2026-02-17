import { useEffect, useState } from "react";
import { fetchPortal, getWebPortalInfo } from "./auth";

type TelegramConfig = {
  enabled: boolean;
  allow_uploads: boolean;
  token_masked: string;
  webhook_url: string;
};

type IntegrationsCacheState = {
  integrationTab: "telegram" | "bitrix" | "amocrm";
  staffConfig: TelegramConfig;
  clientConfig: TelegramConfig;
  bitrixMasked: string;
};

const refreshErrorMap: Record<string, string> = {
  missing_refresh_token: "нет refresh_token",
  missing_client_credentials: "не заданы креды",
  bitrix_refresh_failed: "ошибка Bitrix refresh",
  missing_auth: "нет сохранённых токенов",
};

const integrationsCache = new Map<number, IntegrationsCacheState>();

export function WebIntegrationsPage() {
  const { portalId, portalToken } = getWebPortalInfo();
  const cached = portalId ? integrationsCache.get(portalId) : null;
  const [integrationTab, setIntegrationTab] = useState<"telegram" | "bitrix" | "amocrm">(cached?.integrationTab || "telegram");
  const [staffConfig, setStaffConfig] = useState<TelegramConfig>(cached?.staffConfig || {
    enabled: false,
    allow_uploads: false,
    token_masked: "",
    webhook_url: "",
  });
  const [clientConfig, setClientConfig] = useState<TelegramConfig>(cached?.clientConfig || {
    enabled: false,
    allow_uploads: false,
    token_masked: "",
    webhook_url: "",
  });
  const [staffToken, setStaffToken] = useState("");
  const [clientToken, setClientToken] = useState("");
  const [staffStatus, setStaffStatus] = useState("");
  const [clientStatus, setClientStatus] = useState("");

  const [bitrixClientId, setBitrixClientId] = useState("");
  const [bitrixClientSecret, setBitrixClientSecret] = useState("");
  const [bitrixStatus, setBitrixStatus] = useState("");
  const [bitrixMasked, setBitrixMasked] = useState(cached?.bitrixMasked || "");

  useEffect(() => {
    if (!portalId || !portalToken) return;
    const state = integrationsCache.get(portalId);
    if (state) {
      setIntegrationTab(state.integrationTab);
      setStaffConfig(state.staffConfig);
      setClientConfig(state.clientConfig);
      setBitrixMasked(state.bitrixMasked);
    }
    const loadTelegram = async (kind: "staff" | "client") => {
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/telegram/${kind}`);
        const data = await res.json().catch(() => null);
        if (res.ok && data) {
          const cfg = {
            enabled: !!data.enabled,
            allow_uploads: !!data.allow_uploads,
            token_masked: data.token_masked || "",
            webhook_url: data.webhook_url || "",
          };
          if (kind === "staff") setStaffConfig(cfg);
          else setClientConfig(cfg);
        }
      } catch {
        // ignore
      }
    };
    const loadBitrixMask = async () => {
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/bitrix/credentials`);
        const data = await res.json().catch(() => null);
        if (res.ok && data?.client_id_masked) {
          setBitrixMasked(String(data.client_id_masked));
        }
      } catch {
        // ignore
      }
    };
    loadTelegram("staff");
    loadTelegram("client");
    loadBitrixMask();
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!portalId) return;
    integrationsCache.set(portalId, { integrationTab, staffConfig, clientConfig, bitrixMasked });
  }, [portalId, integrationTab, staffConfig, clientConfig, bitrixMasked]);

  const saveTelegram = async (kind: "staff" | "client") => {
    if (!portalId || !portalToken) return;
    const payload =
      kind === "staff"
        ? { bot_token: staffToken || null, enabled: staffConfig.enabled, allow_uploads: staffConfig.allow_uploads }
        : { bot_token: clientToken || null, enabled: clientConfig.enabled, allow_uploads: clientConfig.allow_uploads };
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/telegram/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    const ok = res.ok;
    if (kind === "staff") {
      setStaffStatus(ok ? "Сохранено" : (data?.detail || data?.error || "Ошибка"));
      if (ok) {
        setStaffToken("");
        setStaffConfig((prev) => ({
          ...prev,
          token_masked: data?.token_masked || prev.token_masked,
          webhook_url: data?.webhook_url || prev.webhook_url,
        }));
      }
    } else {
      setClientStatus(ok ? "Сохранено" : (data?.detail || data?.error || "Ошибка"));
      if (ok) {
        setClientToken("");
        setClientConfig((prev) => ({
          ...prev,
          token_masked: data?.token_masked || prev.token_masked,
          webhook_url: data?.webhook_url || prev.webhook_url,
        }));
      }
    }
  };

  const saveBitrixCreds = async () => {
    if (!portalId || !portalToken) return;
    setBitrixStatus("Сохранение...");
    const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/bitrix/credentials`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: bitrixClientId, client_secret: bitrixClientSecret }),
    });
    const data = await res.json().catch(() => null);
    if (res.ok) {
      setBitrixMasked(data?.client_id_masked || "");
      setBitrixClientId("");
      setBitrixClientSecret("");
      if (data?.refreshed) {
        setBitrixStatus("Сохранено и токен обновлён");
      } else if (data?.refresh_error) {
        const msg = refreshErrorMap[data.refresh_error] || data.refresh_error;
        setBitrixStatus(`Креды сохранены, но токен не обновлён: ${msg}`);
      } else {
        setBitrixStatus("Сохранено");
      }
    } else {
      setBitrixStatus(data?.error || "Ошибка");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Интеграции</h1>
        <p className="text-sm text-slate-500 mt-1">Подключайте внешние каналы и настраивайте доступы.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { key: "telegram", label: "Телеграм" },
          { key: "bitrix", label: "Битрикс" },
          { key: "amocrm", label: "AmoCRM" },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
              integrationTab === tab.key
                ? "bg-sky-600 text-white shadow-sm"
                : "border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
            onClick={() => setIntegrationTab(tab.key as typeof integrationTab)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">
          {integrationTab === "telegram" && "Телеграм"}
          {integrationTab === "bitrix" && "Битрикс"}
          {integrationTab === "amocrm" && "AmoCRM"}
        </div>

        {integrationTab === "telegram" && (
          <div className="mt-4 grid gap-6 md:grid-cols-2">
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={staffConfig.enabled}
                  onChange={(e) => setStaffConfig((prev) => ({ ...prev, enabled: e.target.checked }))}
                />
                Бот для сотрудников (RAG: staff)
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={staffConfig.allow_uploads}
                  onChange={(e) => setStaffConfig((prev) => ({ ...prev, allow_uploads: e.target.checked }))}
                />
                Разрешить загрузку файлов
              </label>
              {staffConfig.token_masked && <div className="text-xs text-slate-500">Токен: {staffConfig.token_masked}</div>}
              {staffConfig.webhook_url && <div className="text-xs text-slate-500">Webhook: {staffConfig.webhook_url}</div>}
              <input
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                placeholder="Bot token"
                value={staffToken}
                onChange={(e) => setStaffToken(e.target.value)}
                autoComplete="off"
                name="tg-staff-token"
              />
              <div className="flex items-center gap-3">
                <button
                  className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                  onClick={() => saveTelegram("staff")}
                >
                  Сохранить
                </button>
                {staffStatus && <div className="text-xs text-slate-500">{staffStatus}</div>}
              </div>
            </div>

            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={clientConfig.enabled}
                  onChange={(e) => setClientConfig((prev) => ({ ...prev, enabled: e.target.checked }))}
                />
                Бот для клиентов (RAG: client)
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={clientConfig.allow_uploads}
                  onChange={(e) => setClientConfig((prev) => ({ ...prev, allow_uploads: e.target.checked }))}
                />
                Разрешить загрузку файлов
              </label>
              {clientConfig.token_masked && <div className="text-xs text-slate-500">Токен: {clientConfig.token_masked}</div>}
              {clientConfig.webhook_url && <div className="text-xs text-slate-500">Webhook: {clientConfig.webhook_url}</div>}
              <input
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                placeholder="Bot token"
                value={clientToken}
                onChange={(e) => setClientToken(e.target.value)}
                autoComplete="off"
                name="tg-client-token"
              />
              <div className="flex items-center gap-3">
                <button
                  className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                  onClick={() => saveTelegram("client")}
                >
                  Сохранить
                </button>
                {clientStatus && <div className="text-xs text-slate-500">{clientStatus}</div>}
              </div>
            </div>
          </div>
        )}

        {integrationTab === "bitrix" && (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs text-slate-600">Client ID</label>
              <input
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={bitrixClientId}
                onChange={(e) => setBitrixClientId(e.target.value)}
                placeholder={bitrixMasked ? `Сохранён: ${bitrixMasked}` : "client_id"}
                autoComplete="off"
                name="bitrix-client-id"
              />
              <label className="text-xs text-slate-600">Client Secret</label>
              <input
                type="password"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={bitrixClientSecret}
                onChange={(e) => setBitrixClientSecret(e.target.value)}
                placeholder={bitrixMasked ? "Секрет сохранён" : "client_secret"}
                autoComplete="new-password"
                name="bitrix-client-secret"
              />
              {bitrixMasked && (
                <div className="text-xs text-slate-500">Креды сохранены. Чтобы обновить — введите новые значения и нажмите «Сохранить».</div>
              )}
              <div className="flex items-center gap-3">
                <button
                  className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                  onClick={saveBitrixCreds}
                >
                  Сохранить
                </button>
                {bitrixStatus && <div className="text-xs text-slate-500">{bitrixStatus}</div>}
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {bitrixMasked ? (
                <div>
                  <div className="font-semibold text-slate-800">Интеграция подключена</div>
                  <div className="mt-2">Сохранённый client_id: {bitrixMasked}</div>
                  <div className="mt-2 text-xs text-slate-500">При необходимости замените креды — мы перезапишем их после сохранения.</div>
                </div>
              ) : (
                <div>
                  <div className="font-semibold text-slate-800">Подключите интеграцию Bitrix24</div>
                  <div className="mt-2">Вставьте client_id и client_secret из локального приложения Bitrix24.</div>
                  <div className="mt-2 text-xs text-slate-500">После сохранения появится статус, что креды подключены.</div>
                </div>
              )}
            </div>
          </div>
        )}

        {integrationTab === "amocrm" && (
          <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Настройки интеграции AmoCRM добавим позже.
          </div>
        )}
      </div>
    </div>
  );
}
