import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearWebUser, getWebPortalInfo, getWebUser } from "./auth";

const UI_MODE_KEY = "tb_web_ui_mode";

function getUiMode(): "legacy" | "new" {
  const raw = localStorage.getItem(UI_MODE_KEY);
  return raw === "new" ? "new" : "legacy";
}

function setUiMode(mode: "legacy" | "new") {
  localStorage.setItem(UI_MODE_KEY, mode);
}

export function WebLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = getWebUser();
  const { portalId, portalToken } = getWebPortalInfo();
  const [demoUntil, setDemoUntil] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aiRopOpen, setAiRopOpen] = useState(false);
  const uiMode = getUiMode();
  const userLabel = useMemo(() => user?.email || "Пользователь", [user]);

  useEffect(() => {
    if (!user || !portalId || !portalToken) {
      navigate("/login");
      return;
    }
    if (uiMode === "legacy") {
      window.location.href = "/iframe/?mode=web";
      return;
    }
  }, [user, portalId, portalToken, uiMode, navigate]);

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
        if (res.ok) {
          setDemoUntil(data?.demo_until || null);
        }
      } catch {
        // ignore
      }
    };
    loadStatus();
  }, [portalId, portalToken]);

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
    if (Number.isNaN(dt.getTime())) return `Тариф: до ${demoUntil}`;
    const days = Math.max(0, Math.ceil((dt.getTime() - Date.now()) / 86400000));
    return `Тариф: осталось ${days} дн.`;
  })();

  const onLogout = () => {
    clearWebUser();
    navigate("/login");
  };

  const switchToLegacy = () => {
    setUiMode("legacy");
    window.location.href = "/iframe/?mode=web";
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-slate-100 px-4 py-6">
        <div className="text-lg font-semibold text-slate-900">Teachbase AI</div>
        <nav className="mt-6 space-y-1 text-sm">
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/overview") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/overview" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>Обзор</Link>
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/kb") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/kb" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>База знаний</Link>
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/sources") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/sources" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>Источники данных</Link>
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/users") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/users" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>Пользователи и доступы</Link>
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/analytics") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/analytics" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>Аналитика</Link>
          <button
            type="button"
            className={`w-full text-left rounded-xl px-3 py-2 ${location.pathname.includes("/settings") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => {
              setAiRopOpen(false);
              setSettingsOpen((prev) => !prev);
              navigate("/app/settings");
            }}
          >
            Настройки
          </button>
          <div
            className="overflow-hidden pl-3 transition-all duration-300"
            style={{ maxHeight: settingsOpen ? 120 : 0, opacity: settingsOpen ? 1 : 0.4 }}
          >
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname === "/app/settings" ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/settings"
            >
              Основные
            </Link>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/settings/integrations") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/settings/integrations"
            >
              Интеграции
            </Link>
          </div>
          <button
            className={`w-full text-left rounded-xl px-3 py-2 ${location.pathname.includes("/ai-rop") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => {
              setSettingsOpen(false);
              setAiRopOpen((prev) => !prev);
              navigate("/app/ai-rop");
            }}
          >
            AI РОП
          </button>
          <div
            className="ml-4 mt-1 space-y-1 overflow-hidden transition-all"
            style={{ maxHeight: aiRopOpen ? 140 : 0, opacity: aiRopOpen ? 1 : 0.4 }}
          >
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname === "/app/ai-rop" ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/ai-rop"
            >
              Основные
            </Link>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/access") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/ai-rop/access"
            >
              Доступ
            </Link>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/trainer") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/ai-rop/trainer"
            >
              AI Тренер
            </Link>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname.includes("/ai-rop/analyst") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/app/ai-rop/analyst"
            >
              AI Аналитик
            </Link>
          </div>
          <Link className={`block rounded-xl px-3 py-2 ${location.pathname.includes("/flow") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`} to="/app/flow" onClick={() => { setSettingsOpen(false); setAiRopOpen(false); }}>Конструктор</Link>
        </nav>
      </aside>

      <div className="ml-64">
        <header className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-100">
          <div className="w-full px-8 py-4 flex items-center justify-between">
            <div className="text-sm text-slate-500">Web‑кабинет</div>
            <div className="flex items-center gap-3">
              {demoLeftLabel && (
                <div className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs text-sky-700 font-semibold">
                  {demoLeftLabel}
                </div>
              )}
              <div className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                {userLabel}
              </div>
              <button
                className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
                onClick={switchToLegacy}
              >
                Старый дизайн
              </button>
              <button
                className="rounded-full bg-sky-600 px-3 py-1 text-xs text-white"
                onClick={onLogout}
              >
                Выйти
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
