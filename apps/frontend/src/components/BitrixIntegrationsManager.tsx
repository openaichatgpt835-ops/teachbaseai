import { useEffect, useState } from "react";
import { fetchWeb } from "../pages/web/auth";

type BitrixIntegrationItem = {
  id: number;
  status: string;
  external_key: string;
  portal_id?: number | null;
  portal_domain?: string | null;
  is_primary?: boolean;
};

export function BitrixIntegrationsManager({ accountId }: { accountId: number }) {
  const [items, setItems] = useState<BitrixIntegrationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [status, setStatus] = useState("");

  const load = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/integrations/bitrix`);
      const data = await res.json().catch(() => null);
      if (res.ok && data?.items) {
        setItems(data.items);
        setStatus("");
      } else {
        setStatus(data?.detail || "Не удалось загрузить интеграции");
      }
    } catch {
      setStatus("Не удалось загрузить интеграции");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [accountId]);

  const makePrimary = async (integrationId: number) => {
    setSavingId(integrationId);
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/integrations/bitrix/${integrationId}/make-primary`, {
        method: "POST",
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.items) {
        setItems(data.items);
        setStatus("Основной портал обновлён");
      } else {
        setStatus(data?.detail || "Не удалось обновить основной портал");
      }
    } catch {
      setStatus("Не удалось обновить основной портал");
    } finally {
      setSavingId(null);
    }
  };

  const disconnect = async (integrationId: number) => {
    setSavingId(integrationId);
    try {
      const res = await fetchWeb(`/api/v2/web/accounts/${accountId}/integrations/bitrix/${integrationId}`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.items) {
        setItems(data.items);
        setStatus("Интеграция отключена");
      } else {
        setStatus(data?.detail || "Не удалось отключить интеграцию");
      }
    } catch {
      setStatus("Не удалось отключить интеграцию");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="mt-6 rounded-2xl border border-slate-100 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">Порталы Bitrix24 в аккаунте</div>
          <div className="mt-1 text-xs text-slate-500">
            Здесь можно выбрать основной портал для web-bridge и отключить лишнюю интеграцию.
          </div>
        </div>
        <button
          type="button"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Обновление..." : "Обновить"}
        </button>
      </div>

      <div className="mt-4 space-y-3">
        {items.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
            У аккаунта пока нет подключённых порталов Bitrix24.
          </div>
        )}

        {items.map((item) => (
          <div key={item.id} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  {item.portal_domain || item.external_key}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  portal_id: {item.portal_id || "—"} · status: {item.status}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {item.is_primary ? (
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                    Основной
                  </span>
                ) : (
                  <button
                    type="button"
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    onClick={() => makePrimary(item.id)}
                    disabled={savingId === item.id || item.status !== "active"}
                  >
                    Сделать основным
                  </button>
                )}
                <button
                  type="button"
                  className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                  onClick={() => disconnect(item.id)}
                  disabled={savingId === item.id || item.status !== "active"}
                >
                  Отключить
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {status && <div className="mt-3 text-xs text-slate-500">{status}</div>}
    </div>
  );
}
