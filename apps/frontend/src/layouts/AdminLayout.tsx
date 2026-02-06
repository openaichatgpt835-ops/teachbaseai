import { Outlet, Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { clearAuthToken, getAuthToken } from "../api/client";

export function AdminLayout() {
  const navigate = useNavigate();
  useEffect(() => {
    if (!getAuthToken()) navigate("/admin/login");
  }, [navigate]);
  const handleLogout = () => {
    clearAuthToken();
    navigate("/admin/login");
  };
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/admin/portals" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Порталы
              </Link>
              <Link to="/admin/dialogs" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Диалоги
              </Link>
              <Link to="/admin/system" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Система
              </Link>
              <Link to="/admin/traces" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Трейсы Bitrix
              </Link>
              <Link to="/admin/inbound-events" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Inbound events
              </Link>
              <Link to="/admin/knowledge-base" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                База знаний
              </Link>
              <Link to="/admin/bot-settings" className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                Настройки бота
              </Link>
            </div>
            <button
              onClick={handleLogout}
              className="px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Выход
            </button>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
