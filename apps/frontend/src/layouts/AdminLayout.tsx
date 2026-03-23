import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { clearAuthToken, getAuthToken } from "../api/client";

type AdminNavItem = {
  to: string;
  label: string;
  description: string;
};

type AdminNavSection = {
  title: string;
  items: AdminNavItem[];
};

const NAV_SECTIONS: AdminNavSection[] = [
  {
    title: "Operations",
    items: [
      { to: "/admin/operations", label: "Обзор", description: "Health, очереди, ошибки и быстрые переходы" },
      { to: "/admin/system", label: "Система", description: "Очереди, воркеры и runtime" },
      { to: "/admin/errors", label: "Ошибки API", description: "Инциденты и ошибки каналов" },
      { to: "/admin/traces", label: "Трейсы", description: "Trace drill-down и timeline" },
      { to: "/admin/inbound-events", label: "Inbound Events", description: "Входящие события и хранение" },
    ],
  },
  {
    title: "Accounts",
    items: [
      { to: "/admin/accounts", label: "Обзор", description: "Порталы, RBAC и диалоги по аккаунтам" },
      { to: "/admin/portals", label: "Порталы", description: "Bitrix-порталы и интеграции" },
      { to: "/admin/dialogs", label: "Диалоги", description: "Диалоги и сообщения" },
      { to: "/admin/rbac-owners", label: "RBAC аудит", description: "Владельцы и доступы" },
    ],
  },
  {
    title: "Revenue",
    items: [
      { to: "/admin/revenue", label: "Обзор", description: "Pricing, usage и foundation под тарифы" },
    ],
  },
  {
    title: "Product Controls",
    items: [
      { to: "/admin/knowledge-base", label: "База знаний", description: "KB runtime и провайдеры" },
      { to: "/admin/bot-settings", label: "Настройки бота", description: "Бот и runtime settings" },
    ],
  },
  {
    title: "Lifecycle",
    items: [{ to: "/admin/registrations", label: "Регистрации", description: "Онбординг и email flow" }],
  },
];

function getActiveItem(pathname: string): AdminNavItem | null {
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      if (pathname === item.to || pathname.startsWith(`${item.to}/`)) return item;
    }
  }
  return null;
}

export function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!getAuthToken()) navigate("/admin/login");
  }, [navigate]);

  const handleLogout = () => {
    clearAuthToken();
    navigate("/admin/login");
  };

  const activeItem = getActiveItem(location.pathname);
  const compactItems = NAV_SECTIONS.flatMap((section) => section.items);

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-80 shrink-0 border-r border-slate-200 bg-white xl:flex xl:flex-col">
          <div className="border-b border-slate-200 px-6 py-5">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Teachbase AI</div>
            <div className="mt-2 text-xl font-semibold text-slate-900">Admin Console</div>
            <div className="mt-1 text-sm text-slate-500">Операции, аккаунты, выручка и продуктовые контроли.</div>
          </div>
          <nav className="flex-1 overflow-y-auto px-4 py-5">
            <div className="space-y-6">
              {NAV_SECTIONS.map((section) => (
                <div key={section.title}>
                  <div className="px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{section.title}</div>
                  <div className="mt-2 space-y-1">
                    {section.items.map((item) => (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        className={({ isActive }) =>
                          [
                            "block rounded-2xl px-3 py-3 transition",
                            isActive || location.pathname.startsWith(`${item.to}/`)
                              ? "bg-sky-50 text-sky-900 ring-1 ring-sky-100"
                              : "text-slate-700 hover:bg-slate-50",
                          ].join(" ")
                        }
                      >
                        <div className="text-sm font-semibold">{item.label}</div>
                        <div className="mt-1 text-xs text-slate-500">{item.description}</div>
                      </NavLink>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </nav>
          <div className="border-t border-slate-200 px-4 py-4">
            <button
              onClick={handleLogout}
              className="w-full rounded-2xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Выйти
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  {activeItem ? `Admin / ${activeItem.label}` : "Admin"}
                </div>
                <div className="mt-1 truncate text-lg font-semibold text-slate-900">{activeItem?.label || "Admin Console"}</div>
                <div className="mt-1 hidden text-sm text-slate-500 md:block">
                  {activeItem?.description || "Сгруппированная навигация по операционным зонам."}
                </div>
              </div>
              <div className="flex items-center gap-2 xl:hidden">
                {compactItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      [
                        "rounded-xl px-3 py-2 text-xs font-medium transition",
                        isActive || location.pathname.startsWith(`${item.to}/`)
                          ? "bg-sky-600 text-white"
                          : "bg-slate-100 text-slate-700 hover:bg-slate-200",
                      ].join(" ")
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
                <button
                  onClick={handleLogout}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Выйти
                </button>
              </div>
            </div>
          </header>

          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
