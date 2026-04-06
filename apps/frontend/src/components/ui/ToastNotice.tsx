import { useEffect } from "react";
import { X } from "lucide-react";

type ToastTone = "info" | "error";

export function ToastNotice(props: {
  message: string;
  tone?: ToastTone;
  onClose: () => void;
  durationMs?: number;
}) {
  const tone = props.tone || "info";

  useEffect(() => {
    if (!props.message) return;
    const timer = window.setTimeout(() => props.onClose(), props.durationMs ?? 3200);
    return () => window.clearTimeout(timer);
  }, [props.message, props.onClose, props.durationMs]);

  if (!props.message) return null;

  const toneClass =
    tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : "border-slate-200 bg-white text-slate-700";

  return (
    <div className={`pointer-events-auto flex max-w-[420px] items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-[0_12px_30px_rgba(15,23,42,0.12)] ${toneClass}`}>
      <div className="min-w-0 flex-1 leading-6">{props.message}</div>
      <button
        type="button"
        className="text-slate-400 transition hover:text-slate-700"
        onClick={props.onClose}
        aria-label="Закрыть уведомление"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
