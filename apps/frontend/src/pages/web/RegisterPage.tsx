import { useState } from "react";
import { Link } from "react-router-dom";

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [company, setCompany] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!email || !password) {
      setError("Укажите email и пароль.");
      return;
    }
    if (password.length < 6) {
      setError("Пароль должен быть не короче 6 символов.");
      return;
    }
    if (password !== confirm) {
      setError("Пароли не совпадают.");
      return;
    }
    try {
      const res = await fetch("/v1/web/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, company }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || "Ошибка регистрации.");
        return;
      }
      setSuccess("Письмо отправлено. Подтвердите email, чтобы войти в кабинет.");
    } catch {
      setError("Сервис временно недоступен.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-indigo-50">
      <div className="max-w-6xl mx-auto px-6 py-12 grid gap-10 lg:grid-cols-2 items-center">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-1 text-xs font-semibold text-sky-700 shadow">
            Teachbase AI — Web-кабинет
          </div>
          <h1 className="text-4xl font-semibold text-slate-900">Запустите свой AI-кабинет</h1>
          <p className="text-slate-600">
            Регистрация без Bitrix24. Получите доступ к базе знаний, конструкторам и настройкам ботов.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
              <div className="text-sm font-semibold text-slate-900">База знаний</div>
              <div className="text-xs text-slate-500 mt-1">Файлы, URL-источники, индексация.</div>
            </div>
            <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
              <div className="text-sm font-semibold text-slate-900">Конструктор бота</div>
              <div className="text-xs text-slate-500 mt-1">Готовые сценарии и тестовый прогон.</div>
            </div>
            <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
              <div className="text-sm font-semibold text-slate-900">Интеграции</div>
              <div className="text-xs text-slate-500 mt-1">Bitrix24, webhook и будущие каналы.</div>
            </div>
            <div className="rounded-2xl bg-white p-4 shadow-sm border border-slate-100">
              <div className="text-sm font-semibold text-slate-900">Оплата</div>
              <div className="text-xs text-slate-500 mt-1">Гибкие тарифы и контроль расходов.</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-lg border border-slate-100 p-8">
          <h2 className="text-xl font-semibold text-slate-900">Регистрация</h2>
          <p className="text-xs text-slate-500 mt-1">Подтвердите email для доступа в кабинет.</p>
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
              <label className="text-xs text-slate-600">Компания</label>
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Название компании"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
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
              <div>
                <label className="text-xs text-slate-600">Повтор пароля</label>
                <input
                  type="password"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Повторите пароль"
                />
              </div>
            </div>
            {error && (
              <div className="rounded-xl bg-rose-50 text-rose-700 text-xs px-3 py-2">{error}</div>
            )}
            {success && (
              <div className="rounded-xl bg-emerald-50 text-emerald-700 text-xs px-3 py-2">{success}</div>
            )}
            <button className="w-full rounded-xl bg-sky-600 text-white py-2 text-sm font-semibold hover:bg-sky-700">
              Создать аккаунт
            </button>
          </form>
          <div className="mt-4 text-xs text-slate-500">
            Уже есть аккаунт?{" "}
            <Link to="/login" className="text-sky-600 font-semibold">
              Войти
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
