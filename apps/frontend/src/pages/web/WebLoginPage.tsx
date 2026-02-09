import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { getWebUser, setWebUser, setWebSession } from "./auth";

export function WebLoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Укажите email и пароль.");
      return;
    }
    try {
      const res = await fetch("/v1/web/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || "Неверный email или пароль.");
        return;
      }
      const existing = getWebUser();
      if (!existing) {
        setWebUser({ email, createdAt: new Date().toISOString() });
      }
      setWebSession(data.session_token, data.portal_id, data.portal_token);
      navigate("/app");
    } catch {
      setError("Сервис временно недоступен.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-sky-50 flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-lg border border-slate-100 p-8">
        <h1 className="text-2xl font-semibold text-slate-900">Вход в кабинет</h1>
        <p className="text-xs text-slate-500 mt-1">Email + пароль. Пока без подтверждения.</p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="text-xs text-slate-600">Email</label>
            <input
              type="email"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="text-xs text-slate-600">Пароль</label>
            <input
              type="password"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Пароль"
            />
          </div>
          {error && (
            <div className="rounded-xl bg-rose-50 text-rose-700 text-xs px-3 py-2">
              {error}
            </div>
          )}
          <button className="w-full rounded-xl bg-sky-600 text-white py-2 text-sm font-semibold hover:bg-sky-700">
            Войти
          </button>
        </form>
        <div className="mt-4 text-xs text-slate-500">
          Нет аккаунта?{" "}
          <Link to="/register" className="text-sky-600 font-semibold">
            Зарегистрироваться
          </Link>
        </div>
      </div>
    </div>
  );
}
