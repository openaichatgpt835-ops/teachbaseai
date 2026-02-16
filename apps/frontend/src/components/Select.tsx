import { useEffect, useMemo, useRef, useState } from "react";

type Option = { value: string; label: string };

type SelectProps = {
  value: string;
  options: Option[];
  placeholder?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
};

export function Select({ value, options, placeholder, onChange, disabled, className }: SelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const currentLabel = useMemo(() => {
    const opt = options.find((o) => o.value === value);
    return opt?.label || placeholder || "—";
  }, [options, placeholder, value]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (evt: MouseEvent) => {
      if (!rootRef.current?.contains(evt.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (evt: KeyboardEvent) => {
      if (evt.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative ${className || ""}`}>
      <button
        type="button"
        className={`flex w-full items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm transition focus:outline-none focus:ring-2 focus:ring-sky-200 ${
          disabled ? "cursor-not-allowed opacity-60" : "hover:border-slate-300"
        }`}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <span className="truncate text-slate-900">{currentLabel}</span>
        <span className="text-slate-400">▾</span>
      </button>
      {open && !disabled && (
        <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          <div className="max-h-64 overflow-auto py-1">
            {options.map((opt) => {
              const active = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition ${
                    active ? "bg-sky-50 text-sky-700" : "text-slate-700 hover:bg-slate-50"
                  }`}
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                >
                  <span className="truncate">{opt.label}</span>
                  {active && <span className="text-sky-600">✓</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
