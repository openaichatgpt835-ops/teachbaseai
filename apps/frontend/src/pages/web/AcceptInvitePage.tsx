import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = useMemo(() => (params.get("token") || "").trim(), [params]);
  const [login, setLogin] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!token) {
      setError("Токен приглашения не найден.");
      return;
    }
    if (!login.trim() || !password.trim()) {
      setError("Укажите логин и пароль.");
      return;
    }
    if (password.trim().length < 6) {
      setError("Пароль должен быть не короче 6 символов.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/v2/web/invites/${encodeURIComponent(token)}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login: login.trim(),
          password: password.trim(),
          display_name: displayName.trim() || null,
          email: email.trim() || null,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || data?.message || "Не удалось принять приглашение.");
        return;
      }
      setSuccess("Приглашение принято. Теперь вы можете войти в веб-кабинет.");
    } catch {
      setError("Сервис временно недоступен.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-indigo-50">
      <div className="mx-auto grid max-w-5xl items-center gap-8 px-6 py-12 lg:grid-cols-2">
        <div className="space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-1 text-xs font-semibold text-sky-700 shadow">
            Teachbase AI — Приглашение
          </div>
          <h1 className="text-4xl font-semibold text-slate-900">Вас пригласили в аккаунт</h1>
          <p className="text-slate-600">
            Подтвердите доступ: задайте логин/пароль и завершите подключение к рабочему пространству.
          </p>
        </div>

        <div className="rounded-3xl border border-slate-100 bg-white p-8 shadow-lg">
          <h2 className="text-xl font-semibold text-slate-900">Принять приглашение</h2>
          <p className="mt-1 text-xs text-slate-500">После успешного подтверждения используйте обычный вход.</p>
          <form className="mt-6 space-y-4" onSubmit={onSubmit}>
            <div>
              <label className="text-xs text-slate-600">Логин</label>
              <input
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                placeholder="login"
              />
            </div>
            <div>
              <label className="text-xs text-slate-600">Email (опционально)</label>
              <input
                type="email"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="text-xs text-slate-600">Имя (опционально)</label>
              <input
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Ваше имя"
              />
            </div>
            <div>
              <label className="text-xs text-slate-600">Пароль</label>
              <input
                type="password"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Минимум 6 символов"
              />
            </div>

            {error && <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>}
            {success && <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{success}</div>}

            <button
              className="w-full rounded-xl bg-sky-600 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50"
              disabled={loading}
            >
              {loading ? "Подтверждаю..." : "Принять приглашение"}
            </button>
          </form>

          <div className="mt-4 text-xs text-slate-500">
            Уже есть доступ?{" "}
            <Link to="/login" className="font-semibold text-sky-600">
              Войти
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
