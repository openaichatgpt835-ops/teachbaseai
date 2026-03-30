import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useOutletContext } from "react-router-dom";
import { coreModulesByGroup, coreModuleLabel } from "../../../../shared/ui/modules";
import type { EmbeddedBitrixContext } from "./EmbeddedBitrixGate";

const LABELS = {
  portal: "\u041f\u043e\u0440\u0442\u0430\u043b",
  account: "\u0410\u043a\u043a\u0430\u0443\u043d\u0442",
  openCabinet: "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u0430\u0431\u0438\u043d\u0435\u0442",
  billing: "\u0422\u0430\u0440\u0438\u0444\u044b \u0438 \u043e\u043f\u043b\u0430\u0442\u0430",
  users: "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438 Bitrix24",
  basics: "\u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435",
  telegram: "\u0422\u0435\u043b\u0435\u0433\u0440\u0430\u043c",
  webCabinet: "Web-\u043a\u0430\u0431\u0438\u043d\u0435\u0442",
  demoUntil: "\u0414\u0435\u043c\u043e \u0434\u043e",
} as const;

const EMBEDDED_PRIMARY = new Set(["overview", "chat", "kb", "sources", "users", "settings"]);

function resolveCabinetPath(pathname: string) {
  if (pathname.startsWith("/embedded/bitrix/chat")) return "/app/chat";
  if (pathname.startsWith("/embedded/bitrix/kb")) return "/app/kb";
  if (pathname.startsWith("/embedded/bitrix/sources")) return "/app/sources";
  if (pathname.startsWith("/embedded/bitrix/users")) return "/app/users";
  if (pathname.startsWith("/embedded/bitrix/settings/telegram")) return "/app/settings/integrations";
  if (pathname.startsWith("/embedded/bitrix/settings")) return "/app/settings";
  if (pathname.startsWith("/embedded/bitrix/billing")) return "/app/billing";
  return "/app/overview";
}

function isActive(pathname: string, route: string | undefined) {
  if (!route) return false;
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function EmbeddedBitrixLayout() {
  const location = useLocation();
  const ctx = useOutletContext<EmbeddedBitrixContext>();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const cabinetHref = resolveCabinetPath(location.pathname);

  if (!ctx?.portalId || !ctx?.portalDomain) {
    return <Navigate to="/embedded/bitrix" replace />;
  }

  const primaryModules = coreModulesByGroup("iframe", "primary", { isWebMode: true }).filter((item) => EMBEDDED_PRIMARY.has(item.id));

  useEffect(() => {
    setSettingsOpen(location.pathname.includes("/settings"));
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 w-64 border-r border-slate-100 bg-white px-4 py-6">
        <div className="text-lg font-semibold text-slate-900">Teachbase AI</div>
        <div className="mt-2 text-xs text-slate-500">Bitrix24 embedded</div>
        <nav className="mt-6 space-y-1 text-sm">
          {primaryModules.map((item) =>
            item.id === "settings" ? (
              <button
                key={item.id}
                type="button"
                className={`w-full text-left rounded-xl px-3 py-2 ${location.pathname.includes("/settings") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
                onClick={() => setSettingsOpen((prev) => !prev)}
              >
                {coreModuleLabel(item.id, item.label)}
              </button>
            ) : (
              <Link
                key={item.id}
                to={item.webPath?.replace("/app", "/embedded/bitrix") || "/embedded/bitrix/overview"}
                className={`block rounded-xl px-3 py-2 ${isActive(location.pathname, item.webPath?.replace("/app", "/embedded/bitrix")) ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
              >
                {coreModuleLabel(item.id, item.id === "users" ? LABELS.users : item.label)}
              </Link>
            ),
          )}
          <div
            className="overflow-hidden pl-3 transition-all duration-300"
            style={{ maxHeight: settingsOpen ? 120 : 0, opacity: settingsOpen ? 1 : 0.4 }}
          >
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${location.pathname === "/embedded/bitrix/settings" ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/embedded/bitrix/settings"
            >
              {LABELS.basics}
            </Link>
            <Link
              className={`block rounded-lg px-3 py-2 text-xs ${isActive(location.pathname, "/embedded/bitrix/settings/telegram") ? "text-sky-700" : "text-slate-500 hover:bg-slate-50"}`}
              to="/embedded/bitrix/settings/telegram"
            >
              {LABELS.telegram}
            </Link>
          </div>
          <Link
            to="/embedded/bitrix/billing"
            className={`block rounded-xl px-3 py-2 ${isActive(location.pathname, "/embedded/bitrix/billing") ? "bg-sky-50 text-sky-700" : "text-slate-600 hover:bg-slate-50"}`}
          >
            {LABELS.billing}
          </Link>
        </nav>
      </aside>

      <div className="ml-64">
        <header className="sticky top-0 z-10 border-b border-slate-100 bg-white/90 backdrop-blur">
          <div className="flex items-center justify-between px-8 py-4">
            <div className="text-sm text-slate-500">{LABELS.webCabinet}</div>
            <div className="flex items-center gap-3">
              <div className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                {LABELS.portal}: {ctx.portalDomain}
              </div>
              {ctx.accountName && (
                <div className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                  {LABELS.account}: {ctx.accountName}
                  {ctx.accountNo ? ` · №${ctx.accountNo}` : ""}
                </div>
              )}
              {ctx.demoUntil && (
                <div className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
                  {LABELS.demoUntil} {ctx.demoUntil}
                </div>
              )}
              <a
                href={cabinetHref}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-sky-600 px-3 py-1 text-xs text-white"
              >
                {LABELS.openCabinet}
              </a>
            </div>
          </div>
        </header>
        <main className="px-8 py-8">
          <Outlet context={ctx} />
        </main>
      </div>
    </div>
  );
}

