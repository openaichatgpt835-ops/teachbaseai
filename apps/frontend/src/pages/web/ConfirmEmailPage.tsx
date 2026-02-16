import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

export function ConfirmEmailPage() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("Подтверждаем email...");

  useEffect(() => {
    const token = params.get("token") || "";
    if (!token) {
      setStatus("error");
      setMessage("Отсутствует токен подтверждения.");
      return;
    }
    const run = async () => {
      try {
        const res = await fetch(`/v1/web/auth/confirm?token=${encodeURIComponent(token)}`);
        const data = await res.json().catch(() => null);
        if (!res.ok) {
          setStatus("error");
          setMessage(data?.detail || "Не удалось подтвердить email.");
          return;
        }
        setStatus("ok");
        setMessage("Email подтверждён. Можно входить в кабинет.");
      } catch {
        setStatus("error");
        setMessage("Сервис временно недоступен.");
      }
    };
    run();
  }, [params]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-indigo-50 flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-lg border border-slate-100 p-8 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Подтверждение email</h1>
        <p className={`mt-4 text-sm ${status === "error" ? "text-rose-600" : "text-slate-600"}`}>
          {message}
        </p>
        <div className="mt-6">
          <Link
            to="/login"
            className="inline-flex items-center justify-center rounded-xl bg-sky-600 text-white px-4 py-2 text-sm font-semibold hover:bg-sky-700"
          >
            Перейти к входу
          </Link>
        </div>
      </div>
    </div>
  );
}
