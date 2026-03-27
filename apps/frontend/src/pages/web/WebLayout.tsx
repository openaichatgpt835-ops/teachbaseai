import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { coreModulesByGroup, coreModuleLabel } from "../../../../shared/ui/modules";
import {
  clearWebUser,
  getActiveAccountId,
  getWebAccounts,
  getWebPortalInfo,
  getWebSessionToken,
  getWebUser,
  setActiveAccountId,
  switchWebAccount,
  type WebAccount,
} from "./auth";

const LABELS = {
  user: "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c",
  account: "\u0410\u043a\u043a\u0430\u0443\u043d\u0442",
  tariffUntil: "\u0422\u0430\u0440\u0438\u0444: \u0434\u043e",
  tariffLeft: "\u0422\u0430\u0440\u0438\u0444: \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c",
  daysShort: "\u0434\u043d.",
  billing: "\u0422\u0430\u0440\u0438\u0444\u044b \u0438 \u043e\u043f\u043b\u0430\u0442\u0430",
  settings: "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438",
  basics: "\u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435",
  aiRop: "AI \u0420\u041e\u041f",
  access: "\u0414\u043e\u0441\u0442\u0443\u043f",
  trainer: "AI \u0422\u0440\u0435\u043d\u0435\u0440",
  analyst: "AI \u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a",
  webCabinet: "Web-\u043a\u0430\u0431\u0438\u043d\u0435\u0442",
  project: "\u041f\u0440\u043e\u0435\u043a\u0442",
  logout: "\u0412\u044b\u0439\u0442\u0438",
} as const;

const primaryModules = coreModulesByGroup("web", "primary");
const settingsModules = coreModulesByGroup("web", "settings");

const userFacingPathMatch = (pathname: string, modulePath?: string) => {
  if (!modulePath) return false;
  if (modulePath === "/app/settings") return pathname === modulePath;
  return pathname === modulePath || pathname.startsWith(`${modulePath}/`);
};

export function WebLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = getWebUser();
  const { portalId, portalToken } = getWebPortalInfo();
  const [accounts, setAccounts] = useState<WebAccount[]>(() => getWebAccounts());
  const [activeAccountId, setActiveAccountIdState] = useState<number>(() => getActiveAccountId());
  const [switchingAccount, setSwitchingAccount] = useState(false);
  const [demoUntil, setDemoUntil] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aiRopOpen, setAiRopOpen] = useState(false);
  const userLabel = useMemo(() => user?.email || LABELS.user, [user]);
  const activeAccount = useMemo(
    () => accounts.find((item) => Number(item.id) === Number(activeAccountId)) || null,
    [accounts, activeAccountId],
  );
  const activeAccountLabel = useMemo(() => {
    if (!activeAccount) return "";
    const base = activeAccount.name || `${LABELS.account} ${activeAccount.id}`;
    return activeAccount.account_no ? `${base} ? ?${activeAccount.account_no}` : base;
  }, [activeAccount]);

  useEffect(() => {
    if (!user || !portalId || !portalToken) {
      navigate("/login");
    }
  }, [user, portalId, portalToken, navigate]);

  useEffect(() => {
    const loadStatus = async () => {
      if (!portalId || !portalToken) return;
      try {
        const res = await fetch(`/api/v1/bitrix/portals/${portalId}/web/status`, {
          headers: {
            Authorization: `Bearer ${portalToken}`,
            "X-Requested-With": "XMLHttpRequest",
            Accept: "application/json",
          },
        });
        const data = await res.json().catch(() => null);
        if (res.ok) setDemoUntil(data?.demo_until || null);
      } catch {
        // ignore
      }
    };
    void loadStatus();
  }, [portalId, portalToken]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const syncSession = async () => {
      const sessionToken = getWebSessionToken();
      if (!sessionToken) return;
      try {
        const res = await fetch("/api/v1/web/auth/me", {
          headers: {
            Authorization: `Bearer ${sessionToken}`,
            Accept: "application/json",
          },
        });
        const data = await res.json().catch(() => null);
        if (!res.ok || cancelled) return;
        const nextAccounts = Array.isArray(data?.accounts) ? (data.accounts as WebAccount[]) : [];
        setAccounts(nextAccounts);
        const nextActiveId = Number(data?.active_account_id || 0) || 0;
        setActiveAccountId(nextActiveId || null);
        setActiveAccountIdState(nextActiveId);
      } catch {
        // ignore
      }
    };
    void syncSession();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    setSettingsOpen(location.pathname.includes("/settings"));
    setAiRopOpen(location.pathname.includes("/ai-rop"));
  }, [location.pathname]);

  if (!user || !portalId || !portalToken) {
    return <Navigate to="/login" replace />;
  }

  const demoLeftLabel = (() => {
    if (!demoUntil) return "";
    const dt = new Date(demoUntil);
    if (Number.isNaN(dt.getTime())) return `${LABELS.tariffUntil} ${demoUntil}`;
    const days = Math.max(0, Math.ceil((dt.getTime() - Date.now()) / 86400000));
    return `${LABELS.tariffLeft} ${days} ${LABELS.daysShort}`;
  })();

  const onLogout = () => {
    clearWebUser();
    navigate("/login");
  };

  const onSwitchAccount = async (nextAccountId: number) => {
    if (!nextAccountId || nextAccountId === activeAccountId || switchingAccount) return;
    setSwitchingAccount(true);
    const ok = await switchWebAccount(nextAccountId);
    if (ok) {
      setAccounts(getWebAccounts());
      const currentId = getActiveAccountId();
      setActiveAccountIdState(currentId);
      window.location.reload();
      return;
    }
    setSwitchingAccount(false);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-slate-100 px-4 py-6">
        <div className="text-lg font-semibold text-slate-900">Teachbase AI</div>
        <nav className="mt-6 space-y-1 text-sm">
          {primaryModules.map((item) => {
            const isActive = userFacingPathMatch(location.pathname, item.webPath);
            const label = coreModuleLabel(item.id, item.label);
            return (
              <Link
                key={item.id}
                className={`block rounded-xl px-3 py-2 ${isActive ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
                to={item.webPath || "/app/overview"}
                onClick={() => {
                  setSettingsOpen(false);
                  setAiRopOpen(false);
                }}
              >
                {label}
              </Link>
            );
          })}
          <Link
            className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/billing") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
            to="/app/billing"
            onClick={() => {
              setSettingsOpen(false);
              setAiRopOpen(false);
            }}
          >
            {LABELS.billing}
          </Link>
          <button
            type="button"
            className={`w-full text-left rounded-xl px-3 py-2 ${location.pathname.includes("/settings") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => {
              setAiRopOpen(false);
              setSettingsOpen((prev) => !prev);
              navigate("/app/settings");
            }}
          >
            {coreModuleLabel("settings", LABELS.settings)}
          </button>
          <div className="overflow-hidden pl-3 transition-all duration-300" style={{ maxHeight: settingsOpen ? 120 : 0, opacity: settingsOpen ? 1 : 0.4 }}>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname === "/app/settings" ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/settings"
            >
              {LABELS.basics}
            </Link>
            {settingsModules.map((item) => (
              <Link
                key={item.id}
                className={`block rounded-lg px-3 py-2 text-xs ${userFacingPathMatch(location.pathname, item.webPath) ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
                to={item.webPath || "/app/settings"}
              >
                {item.label}
              </Link>
            ))}
          </div>
          <button
            className={`w-full text-left rounded-xl px-3 py-2 ${location.pathname.includes("/ai-rop") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => {
              setSettingsOpen(false);
              setAiRopOpen((prev) => !prev);
              navigate("/app/ai-rop");
            }}
          >
            {LABELS.aiRop}
          </button>
          <div className="ml-4 mt-1 space-y-1 overflow-hidden transition-all" style={{ maxHeight: aiRopOpen ? 140 : 0, opacity: aiRopOpen ? 1 : 0.4 }}>
            <Link className={`block rounded-lg px-3 py-2 text-xs ${location.pathname === "/app/ai-rop" ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`} to="/app/ai-rop">{LABELS.basics}</Link>
            <Link className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/access") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`} to="/app/ai-rop/access">{LABELS.access}</Link>
            <Link className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/trainer") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`} to="/app/ai-rop/trainer">{LABELS.trainer}</Link>
            <Link className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/analyst") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`} to="/app/ai-rop/analyst">{LABELS.analyst}</Link>
          </div>
        </nav>
      </aside>

      <div className="ml-64">
        <header className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-100">
          <div className="w-full px-8 py-4 flex items-center justify-between">
            <div className="text-sm text-slate-500">{LABELS.webCabinet}</div>
            <div className="flex items-center gap-3">
              {accounts.length > 0 && (
                <div className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                  <span className="text-slate-500">{LABELS.project}</span>
                  <select
                    className="bg-transparent font-semibold outline-none"
                    value={activeAccountId || ""}
                    onChange={(e) => void onSwitchAccount(Number(e.target.value))}
                    disabled={switchingAccount}
                  >
                    {accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name || `${LABELS.account} ${account.id}`}
                        {account.account_no ? ` ? ?${account.account_no}` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {demoLeftLabel && (
                <div className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs text-sky-700 font-semibold">
                  {demoLeftLabel}
                </div>
              )}
              {activeAccountLabel && (
                <div className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                  {activeAccountLabel}
                </div>
              )}
              <div className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">{userLabel}</div>
              <button className="rounded-full bg-sky-600 px-3 py-1 text-xs text-white" onClick={onLogout}>
                {LABELS.logout}
              </button>
            </div>
          </div>
        </header>
        <main className="w-full px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
