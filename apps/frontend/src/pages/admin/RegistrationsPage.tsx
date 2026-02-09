import { useEffect, useState } from "react";
import { api } from "../../api/client";

type MailboxSettings = {
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_password: string;
  smtp_secure: string;
  from_email: string;
  from_name: string;
};

type MailSettings = {
  registration: MailboxSettings;
  onboarding: MailboxSettings;
  invoices: MailboxSettings;
};

type TemplateItem = {
  subject: string;
  html: string;
  text: string;
  delay_days?: number | null;
};

type MailTemplates = {
  registration: TemplateItem;
  registration_confirmed: TemplateItem;
  onboarding: TemplateItem[];
};

type Stats = {
  registrations_total: number;
  registrations_confirmed: number;
  web_hits: number;
  iframe_hits: number;
  ai_requests: number;
  ret3: number;
};

type PortalStatRow = {
  portal_id: number | null;
  domain: string;
  count: number;
};

type SeriesPoint = {
  date: string;
  count: number;
};

const emptyBox: MailboxSettings = {
  smtp_host: "",
  smtp_port: "587",
  smtp_user: "",
  smtp_password: "",
  smtp_secure: "tls",
  from_email: "",
  from_name: "",
};

export function RegistrationsPage() {
  const [settings, setSettings] = useState<MailSettings>({
    registration: { ...emptyBox },
    onboarding: { ...emptyBox },
    invoices: { ...emptyBox },
  });
  const [templates, setTemplates] = useState<MailTemplates>({
    registration: { subject: "", html: "", text: "" },
    registration_confirmed: { subject: "", html: "", text: "" },
    onboarding: [],
  });
  const [stats, setStats] = useState<Stats | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [testEmail, setTestEmail] = useState("lagutinaleks@gmail.com");
  const [testMailbox, setTestMailbox] = useState("registration");
  const [testTemplate, setTestTemplate] = useState("registration");
  const [testOnboardingIndex, setTestOnboardingIndex] = useState(0);
  const [sendingTest, setSendingTest] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTitle, setDetailTitle] = useState("");
  const [detailRows, setDetailRows] = useState<PortalStatRow[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [period, setPeriod] = useState<"week" | "month" | "year">("month");
  const [selectedMetric, setSelectedMetric] = useState<string>("registrations_total");
  const [selectedPortal, setSelectedPortal] = useState<PortalStatRow | null>(null);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [seriesLoading, setSeriesLoading] = useState(false);

  useEffect(() => {
    api.get("/v1/admin/registrations/settings").then((data) => {
      setSettings(data as MailSettings);
    });
    api.get("/v1/admin/registrations/templates").then((data) => {
      setTemplates(data as MailTemplates);
    });
    api.get("/v1/admin/registrations/stats").then((data) => {
      setStats(data as Stats);
    });
  }, []);

  const onSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      await api.put("/v1/admin/registrations/settings", settings);
      await api.put("/v1/admin/registrations/templates", templates);
      setMessage("Сохранено");
    } catch {
      setMessage("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    setSendingTest(true);
    setMessage("");
    try {
      await api.post("/v1/admin/registrations/test-email", {
        to: testEmail,
        mailbox: testMailbox,
        template: testTemplate,
        onboarding_index: testOnboardingIndex,
      });
      setMessage("Тестовое письмо отправлено");
    } catch {
      setMessage("Ошибка отправки");
    } finally {
      setSendingTest(false);
    }
  };

  const openDetail = async (metric: string, title: string) => {
    setDetailOpen(true);
    setDetailTitle(title);
    setDetailRows([]);
    setDetailLoading(true);
    setSelectedMetric(metric);
    setSelectedPortal(null);
    try {
      const data = await api.get(`/v1/admin/registrations/stats/portals?metric=${metric}`);
      setDetailRows((data as { items?: PortalStatRow[] })?.items || []);
    } finally {
      setDetailLoading(false);
    }
  };

  const loadSeries = async (metric: string, periodValue: string, portalId?: number | null) => {
    setSeriesLoading(true);
    try {
      const portalQuery = portalId != null ? `&portal_id=${portalId}` : "";
      const data = await api.get(
        `/v1/admin/registrations/stats/timeseries?metric=${metric}&period=${periodValue}${portalQuery}`
      );
      setSeries((data as { items?: SeriesPoint[] })?.items || []);
    } finally {
      setSeriesLoading(false);
    }
  };

  useEffect(() => {
    loadSeries(selectedMetric, period, selectedPortal?.portal_id ?? null);
  }, [period, selectedMetric, selectedPortal]);

  const renderBox = (title: string, key: keyof MailSettings) => {
    const box = settings[key];
    return (
      <div className="bg-white shadow rounded p-4">
        <h2 className="text-lg font-semibold mb-3">{title}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-sm">
            SMTP host
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.smtp_host}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], smtp_host: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            SMTP port
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.smtp_port}
              placeholder="25:465:587"
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], smtp_port: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            SMTP user
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.smtp_user}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], smtp_user: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            SMTP password
            <input
              type="password"
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.smtp_password}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], smtp_password: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            Secure
            <select
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.smtp_secure}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], smtp_secure: e.target.value } }))}
            >
              <option value="tls">TLS</option>
              <option value="ssl">SSL</option>
              <option value="none">None</option>
            </select>
          </label>
          <label className="text-sm">
            From email
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.from_email}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], from_email: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            From name
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={box.from_name}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: { ...s[key], from_name: e.target.value } }))}
            />
          </label>
        </div>
      </div>
    );
  };

  const renderPreview = (html: string) => (
    <div className="border rounded p-3 bg-gray-50">
      <div className="text-xs text-gray-500 mb-2">Превью</div>
      <div dangerouslySetInnerHTML={{ __html: html || "<em>Нет HTML</em>" }} />
    </div>
  );

  const renderTemplate = (title: string, key: keyof MailTemplates) => {
    if (key === "onboarding") return null;
    const tpl = templates[key] as TemplateItem;
    return (
      <details className="bg-white shadow rounded p-4" open={false}>
        <summary className="cursor-pointer text-lg font-semibold">{title}</summary>
        <div className="grid grid-cols-1 gap-3 mt-3">
          <label className="text-sm">
            Тема
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={tpl.subject}
              onChange={(e) => setTemplates((s) => ({ ...s, [key]: { ...s[key], subject: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            HTML
            <textarea
              className="mt-1 w-full border rounded px-2 py-1 font-mono text-xs"
              rows={6}
              value={tpl.html}
              onChange={(e) => setTemplates((s) => ({ ...s, [key]: { ...s[key], html: e.target.value } }))}
            />
          </label>
          <label className="text-sm">
            Текст (plain)
            <textarea
              className="mt-1 w-full border rounded px-2 py-1 text-xs"
              rows={3}
              value={tpl.text}
              onChange={(e) => setTemplates((s) => ({ ...s, [key]: { ...s[key], text: e.target.value } }))}
            />
          </label>
          {renderPreview(tpl.html)}
        </div>
      </details>
    );
  };

  const renderOnboarding = () => {
    const list = templates.onboarding || [];
    return (
      <details className="bg-white shadow rounded p-4" open={false}>
        <summary className="cursor-pointer text-lg font-semibold">Цепочка онбординга</summary>
        <div className="mt-3">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-gray-500">Письма по дням 0/2/5/9/15/28</div>
            <button
              className="text-sm text-blue-600"
              onClick={() =>
                setTemplates((s) => ({
                  ...s,
                  onboarding: [...(s.onboarding || []), { subject: "", html: "", text: "" }],
                }))
              }
            >
              Добавить письмо
            </button>
          </div>
          {list.length === 0 && <div className="text-sm text-gray-500">Писем пока нет.</div>}
          {list.map((tpl, idx) => (
            <details key={idx} className="border rounded p-3 mb-3" open={false}>
              <summary className="cursor-pointer font-semibold text-sm">Письмо #{idx + 1}</summary>
              <div className="mt-3 grid grid-cols-1 gap-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500">ID: {idx}</div>
                  <button
                    className="text-xs text-red-600"
                    onClick={() =>
                      setTemplates((s) => ({
                        ...s,
                        onboarding: s.onboarding.filter((_, i) => i !== idx),
                      }))
                    }
                  >
                    Удалить
                  </button>
                </div>
                <label className="text-sm">
                  Задержка (дней)
                  <input
                    type="number"
                    min={0}
                    className="mt-1 w-full border rounded px-2 py-1"
                    value={tpl.delay_days ?? 0}
                    onChange={(e) =>
                      setTemplates((s) => ({
                        ...s,
                        onboarding: s.onboarding.map((t, i) =>
                          i === idx ? { ...t, delay_days: parseInt(e.target.value, 10) || 0 } : t
                        ),
                      }))
                    }
                  />
                </label>
                <label className="text-sm">
                  Тема
                  <input
                    className="mt-1 w-full border rounded px-2 py-1"
                    value={tpl.subject}
                    onChange={(e) =>
                      setTemplates((s) => ({
                        ...s,
                        onboarding: s.onboarding.map((t, i) =>
                          i === idx ? { ...t, subject: e.target.value } : t
                        ),
                      }))
                    }
                  />
                </label>
                <label className="text-sm">
                  HTML
                  <textarea
                    className="mt-1 w-full border rounded px-2 py-1 font-mono text-xs"
                    rows={5}
                    value={tpl.html}
                    onChange={(e) =>
                      setTemplates((s) => ({
                        ...s,
                        onboarding: s.onboarding.map((t, i) => (i === idx ? { ...t, html: e.target.value } : t)),
                      }))
                    }
                  />
                </label>
                <label className="text-sm">
                  Текст (plain)
                  <textarea
                    className="mt-1 w-full border rounded px-2 py-1 text-xs"
                    rows={3}
                    value={tpl.text}
                    onChange={(e) =>
                      setTemplates((s) => ({
                        ...s,
                        onboarding: s.onboarding.map((t, i) => (i === idx ? { ...t, text: e.target.value } : t)),
                      }))
                    }
                  />
                </label>
                {renderPreview(tpl.html)}
              </div>
            </details>
          ))}
        </div>
      </details>
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Регистрации</h1>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Период:</span>
        {(["week", "month", "year"] as const).map((p) => (
          <button
            key={p}
            className={`px-3 py-1 rounded border ${
              period === p ? "bg-sky-600 text-white border-sky-600" : "bg-white text-gray-700"
            }`}
            onClick={() => setPeriod(p)}
          >
            {p === "week" ? "Неделя" : p === "month" ? "Месяц" : "Год"}
          </button>
        ))}
      </div>

      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("registrations_total", "Регистрации по порталам")}
          >
            <div className="text-sm text-gray-500">Регистрации</div>
            <div className="text-2xl font-semibold">{stats.registrations_total}</div>
          </button>
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("registrations_confirmed", "Подтверждённые по порталам")}
          >
            <div className="text-sm text-gray-500">Подтвержденные</div>
            <div className="text-2xl font-semibold">{stats.registrations_confirmed}</div>
          </button>
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("ret3", "ret3 по порталам")}
          >
            <div className="text-sm text-gray-500">ret3</div>
            <div className="text-2xl font-semibold">{stats.ret3}</div>
          </button>
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("web_hits", "Хиты web по порталам")}
          >
            <div className="text-sm text-gray-500">Хиты web</div>
            <div className="text-2xl font-semibold">{stats.web_hits}</div>
          </button>
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("iframe_hits", "Хиты iframe по порталам")}
          >
            <div className="text-sm text-gray-500">Хиты iframe</div>
            <div className="text-2xl font-semibold">{stats.iframe_hits}</div>
          </button>
          <button
            className="bg-white shadow rounded p-4 text-left hover:shadow-md transition"
            onClick={() => openDetail("ai_requests", "Запросы к ИИ по порталам")}
          >
            <div className="text-sm text-gray-500">Запросы к ИИ</div>
            <div className="text-2xl font-semibold">{stats.ai_requests}</div>
          </button>
        </div>
      )}

      <div className="bg-white shadow rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-sm text-gray-500">График</div>
            <div className="text-lg font-semibold">
              {selectedMetric === "registrations_total" && "Регистрации"}
              {selectedMetric === "registrations_confirmed" && "Подтверждённые"}
              {selectedMetric === "ret3" && "ret3"}
              {selectedMetric === "web_hits" && "Хиты web"}
              {selectedMetric === "iframe_hits" && "Хиты iframe"}
              {selectedMetric === "ai_requests" && "Запросы к ИИ"}
            </div>
            {selectedPortal && (
              <div className="text-xs text-gray-500">Портал: {selectedPortal.domain}</div>
            )}
          </div>
          <button
            className="text-xs text-gray-500"
            onClick={() => setSelectedPortal(null)}
            disabled={!selectedPortal}
          >
            Сбросить портал
          </button>
        </div>
        {seriesLoading ? (
          <div className="text-sm text-gray-500">Загрузка...</div>
        ) : series.length === 0 ? (
          <div className="text-sm text-gray-500">Нет данных.</div>
        ) : (
          <svg viewBox="0 0 600 180" className="w-full h-40">
            <rect x="0" y="0" width="600" height="180" fill="#f8fafc" rx="12" />
            {(() => {
              const padding = 20;
              const max = Math.max(...series.map((s) => s.count), 1);
              const stepX = (600 - padding * 2) / Math.max(series.length - 1, 1);
              const points = series.map((s, i) => {
                const x = padding + i * stepX;
                const y = 160 - (s.count / max) * 120;
                return `${x},${y}`;
              });
              return (
                <>
                  <polyline
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={points.join(" ")}
                  />
                  {series.map((s, i) => {
                    const x = padding + i * stepX;
                    const y = 160 - (s.count / max) * 120;
                    return <circle key={s.date} cx={x} cy={y} r="3" fill="#2563eb" />;
                  })}
                </>
              );
            })()}
          </svg>
        )}
      </div>

      {renderBox("Регистрационные письма", "registration")}
      {renderBox("Онбординг письма", "onboarding")}
      {renderBox("Счета клиентам", "invoices")}

      {renderTemplate("Шаблон: регистрация", "registration")}
      {renderTemplate("Шаблон: регистрация подтверждена", "registration_confirmed")}
      {renderOnboarding()}

      <div className="bg-white shadow rounded p-4">
        <h2 className="text-lg font-semibold mb-3">Тестовое письмо</h2>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <label className="text-sm">
            Email
            <input
              className="mt-1 w-full border rounded px-2 py-1"
              value={testEmail}
              onChange={(e) => setTestEmail(e.target.value)}
            />
          </label>
          <label className="text-sm">
            Ящик
            <select
              className="mt-1 w-full border rounded px-2 py-1"
              value={testMailbox}
              onChange={(e) => setTestMailbox(e.target.value)}
            >
              <option value="registration">registration</option>
              <option value="onboarding">onboarding</option>
              <option value="invoices">invoices</option>
            </select>
          </label>
          <label className="text-sm">
            Шаблон
            <select
              className="mt-1 w-full border rounded px-2 py-1"
              value={testTemplate}
              onChange={(e) => setTestTemplate(e.target.value)}
            >
              <option value="registration">registration</option>
              <option value="registration_confirmed">registration_confirmed</option>
              <option value="onboarding">onboarding</option>
            </select>
          </label>
          <label className="text-sm">
            Onboarding #
            <input
              type="number"
              min={0}
              className="mt-1 w-full border rounded px-2 py-1"
              value={testOnboardingIndex}
              onChange={(e) => setTestOnboardingIndex(parseInt(e.target.value, 10) || 0)}
            />
          </label>
        </div>
        <div className="mt-3">
          <button
            className="bg-sky-600 text-white px-4 py-2 rounded disabled:opacity-50"
            disabled={sendingTest}
            onClick={sendTest}
          >
            {sendingTest ? "Отправка..." : "Отправить тестовое"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
        {message && <span className="text-sm text-gray-600">{message}</span>}
      </div>

      {detailOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full">
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div className="text-lg font-semibold">{detailTitle}</div>
              <button className="text-sm text-gray-500" onClick={() => setDetailOpen(false)}>
                Закрыть
              </button>
            </div>
            <div className="p-5">
              {detailLoading ? (
                <div className="text-sm text-gray-500">Загрузка...</div>
              ) : detailRows.length === 0 ? (
                <div className="text-sm text-gray-500">Нет данных.</div>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="py-2">Портал</th>
                        <th className="py-2">ID</th>
                        <th className="py-2 text-right">Количество</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailRows.map((row) => (
                        <tr
                          key={`${row.domain}-${row.portal_id}`}
                          className="border-b last:border-b-0 hover:bg-slate-50 cursor-pointer"
                          onClick={() => {
                            setSelectedPortal(row);
                            setDetailOpen(false);
                          }}
                        >
                          <td className="py-2">{row.domain}</td>
                          <td className="py-2">{row.portal_id ?? "—"}</td>
                          <td className="py-2 text-right font-semibold">{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
