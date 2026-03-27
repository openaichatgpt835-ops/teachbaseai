import { useEffect, useState } from "react";
import { UpgradeNoticeBar } from "../../components/LockedSection";
import { UPGRADE_COPY } from "../../shared/upgradeCopy";
import { appStateCopy } from "../../../../shared/ui/stateCopy";
import { fetchPortal, getWebPortalInfo } from "../web/auth";

type TelegramConfig = {
  enabled: boolean;
  allow_uploads: boolean;
  token_masked: string;
  webhook_url: string;
};

type BillingPolicy = {
  plan_name?: string;
};

type FeatureGate = {
  allowed?: boolean;
};

type PortalBillingState = {
  billing_policy?: BillingPolicy;
  feature_gates?: {
    client_bot?: FeatureGate;
  };
};

const LABELS = {
  title: "Телеграм",
  subtitle: "Настройка Telegram-ботов для текущего портала Bitrix24.",
  save: "Сохранить",
  staffTitle: "Бот для сотрудников",
  clientTitle: "Бот для клиентов",
  uploads: "Разрешить загрузку файлов",
  token: "Bot token",
  savedToken: "Токен",
  webhook: "Webhook",
} as const;

export function EmbeddedTelegramPage() {
  const { portalId } = getWebPortalInfo();
  const [staffConfig, setStaffConfig] = useState<TelegramConfig>({
    enabled: false,
    allow_uploads: false,
    token_masked: "",
    webhook_url: "",
  });
  const [clientConfig, setClientConfig] = useState<TelegramConfig>({
    enabled: false,
    allow_uploads: false,
    token_masked: "",
    webhook_url: "",
  });
  const [staffToken, setStaffToken] = useState("");
  const [clientToken, setClientToken] = useState("");
  const [staffStatus, setStaffStatus] = useState("");
  const [clientStatus, setClientStatus] = useState("");
  const [portalBilling, setPortalBilling] = useState<PortalBillingState>({});
  const stateCopy = appStateCopy();

  useEffect(() => {
    if (!portalId) return;

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

    const loadBilling = async () => {
      try {
        const res = await fetchPortal(`/api/v1/bitrix/portals/${portalId}/billing/policy`);
        const data = await res.json().catch(() => null);
        if (res.ok && data) {
          setPortalBilling(data);
        }
      } catch {
        // ignore
      }
    };

    void loadTelegram("staff");
    void loadTelegram("client");
    void loadBilling();
  }, [portalId]);

  const saveTelegram = async (kind: "staff" | "client") => {
    if (!portalId) return;
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
      setStaffStatus(ok ? stateCopy.savedLabel : (data?.detail || data?.error || stateCopy.genericError));
      if (ok) {
        setStaffToken("");
        setStaffConfig((prev) => ({
          ...prev,
          token_masked: data?.token_masked || prev.token_masked,
          webhook_url: data?.webhook_url || prev.webhook_url,
        }));
      }
      return;
    }

    setClientStatus(ok ? stateCopy.savedLabel : (data?.detail || data?.error || stateCopy.genericError));
    if (ok) {
      setClientToken("");
      setClientConfig((prev) => ({
        ...prev,
        token_masked: data?.token_masked || prev.token_masked,
        webhook_url: data?.webhook_url || prev.webhook_url,
      }));
    }
  };

  const clientBotAllowed = !!(portalBilling.feature_gates?.client_bot?.allowed ?? true);
  const planName = portalBilling.billing_policy?.plan_name || "текущий тариф";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{LABELS.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{LABELS.subtitle}</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-semibold text-slate-900">{LABELS.staffTitle}</div>
          <div className="mt-4 space-y-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={staffConfig.enabled}
                onChange={(e) => setStaffConfig((prev) => ({ ...prev, enabled: e.target.checked }))}
              />
              Включить
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={staffConfig.allow_uploads}
                onChange={(e) => setStaffConfig((prev) => ({ ...prev, allow_uploads: e.target.checked }))}
              />
              {LABELS.uploads}
            </label>
            {staffConfig.token_masked && <div className="text-xs text-slate-500">{LABELS.savedToken}: {staffConfig.token_masked}</div>}
            {staffConfig.webhook_url && <div className="text-xs text-slate-500">{LABELS.webhook}: {staffConfig.webhook_url}</div>}
            <input
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder={LABELS.token}
              value={staffToken}
              onChange={(e) => setStaffToken(e.target.value)}
              autoComplete="off"
              name="embedded-tg-staff-token"
            />
            <div className="flex items-center gap-3">
              <button
                className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                onClick={() => void saveTelegram("staff")}
              >
                {LABELS.save}
              </button>
              {staffStatus && <div className="text-xs text-slate-500">{staffStatus}</div>}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-semibold text-slate-900">{LABELS.clientTitle}</div>
          <div className="mt-4 space-y-3">
            {clientBotAllowed ? (
              <>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={clientConfig.enabled}
                    onChange={(e) => setClientConfig((prev) => ({ ...prev, enabled: e.target.checked }))}
                  />
                  Включить
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={clientConfig.allow_uploads}
                    onChange={(e) => setClientConfig((prev) => ({ ...prev, allow_uploads: e.target.checked }))}
                  />
                  {LABELS.uploads}
                </label>
                {clientConfig.token_masked && <div className="text-xs text-slate-500">{LABELS.savedToken}: {clientConfig.token_masked}</div>}
                {clientConfig.webhook_url && <div className="text-xs text-slate-500">{LABELS.webhook}: {clientConfig.webhook_url}</div>}
                <input
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                  placeholder={LABELS.token}
                  value={clientToken}
                  onChange={(e) => setClientToken(e.target.value)}
                  autoComplete="off"
                  name="embedded-tg-client-token"
                />
                <div className="flex items-center gap-3">
                  <button
                    className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                    onClick={() => void saveTelegram("client")}
                  >
                    {LABELS.save}
                  </button>
                  {clientStatus && <div className="text-xs text-slate-500">{clientStatus}</div>}
                </div>
              </>
            ) : (
              <>
                <UpgradeNoticeBar {...UPGRADE_COPY.telegramClient} planName={planName} compact />
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 opacity-70">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={clientConfig.enabled} disabled onChange={() => null} />
                    Включить
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={clientConfig.allow_uploads} disabled onChange={() => null} />
                    {LABELS.uploads}
                  </label>
                  <input
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                    placeholder={LABELS.token}
                    value={clientToken}
                    disabled
                    onChange={() => null}
                  />
                  <button className="rounded-xl bg-slate-300 px-4 py-2 text-sm font-semibold text-white" disabled>
                    {LABELS.save}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
