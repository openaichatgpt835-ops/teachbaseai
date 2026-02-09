import { useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { clearWebUser, getWebUser, getWebPortalInfo } from "./auth";

export function WebAppPage() {
  const navigate = useNavigate();
  const user = getWebUser();
  const { portalId, portalToken } = getWebPortalInfo();
  const userLabel = useMemo(() => user?.email || "Пользователь", [user]);

  useEffect(() => {
    if (!user || !portalId || !portalToken) {
      navigate("/login");
      return;
    }
    window.location.href = "/iframe/?mode=web";
  }, [user, portalId, portalToken, navigate]);

  const onLogout = () => {
    clearWebUser();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-indigo-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-6 py-4 text-sm text-slate-600">
        Перенаправляем в web-кабинет…
        <div className="text-xs text-slate-500 mt-2">{userLabel}</div>
        <button
          className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs"
          onClick={onLogout}
        >
          Выйти
        </button>
      </div>
    </div>
  );
}
