import { useState } from "react";
import { Link } from "react-router-dom";

export function WebForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!email.trim()) {
      setError("Укажите email.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/v1/web/auth/password/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || "Не удалось отправить письмо.");
        return;
      }
      setInfo("Если аккаунт с таким email существует, мы отправили ссылку для сброса пароля.");
    } catch {
      setError("Сервис временно недоступен.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-sky-50 flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-lg border border-slate-100 p-8">
        <h1 className="text-2xl font-semibold text-slate-900">Восстановление пароля</h1>
        <p className="text-xs text-slate-500 mt-1">Введите email, и мы отправим ссылку для смены пароля.</p>
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
          {error && <div className="rounded-xl bg-rose-50 text-rose-700 text-xs px-3 py-2">{error}</div>}
          {info && <div className="rounded-xl bg-emerald-50 text-emerald-700 text-xs px-3 py-2">{info}</div>}
          <button className="w-full rounded-xl bg-sky-600 text-white py-2 text-sm font-semibold hover:bg-sky-700" disabled={busy}>
            {busy ? "Отправка..." : "Отправить ссылку"}
          </button>
        </form>
        <div className="mt-4 text-xs text-slate-500">
          <Link to="/login" className="text-sky-600 font-semibold">Вернуться ко входу</Link>
        </div>
      </div>
    </div>
  );
}
