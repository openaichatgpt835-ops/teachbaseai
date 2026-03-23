import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

type UpgradeDrawerButtonProps = {
  title: string;
  description: string;
  planName?: string | null;
};

export function UpgradeDrawerButton({ title, description, planName }: UpgradeDrawerButtonProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
      >
        Подробнее
      </button>
      {open && (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/35"
            aria-label="Закрыть окно апгрейда"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 top-auto flex md:inset-y-0 md:right-0 md:left-auto md:w-[440px]">
            <div className="mt-auto w-full rounded-t-3xl border border-slate-200 bg-white shadow-2xl md:mt-0 md:rounded-none md:rounded-l-3xl">
              <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">Апгрейд тарифа</div>
                  <h3 className="mt-1 text-lg font-semibold text-slate-900">{title}</h3>
                </div>
                <button type="button" className="text-sm text-slate-500 hover:text-slate-700" onClick={() => setOpen(false)}>
                  Закрыть
                </button>
              </div>
              <div className="space-y-4 px-5 py-5 text-sm text-slate-600">
                <p className="leading-6">{description}</p>
                {planName ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    Текущий тариф: <span className="font-semibold text-slate-900">{planName}</span>
                  </div>
                ) : null}
                <div className="rounded-2xl border border-sky-100 bg-sky-50 px-4 py-3 text-slate-700">
                  Снять ограничение можно через апгрейд тарифа или персональный override для аккаунта.
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    to="/app/billing"
                    onClick={() => setOpen(false)}
                    className="inline-flex items-center justify-center rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                  >
                    Посмотреть тарифы
                  </Link>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    onClick={() => setOpen(false)}
                  >
                    Позже
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

type LockedSectionProps = {
  title: string;
  summary: string;
  planName?: string | null;
  children: ReactNode;
  className?: string;
};

export function LockedSection({ title, summary, planName, children, className = "" }: LockedSectionProps) {
  return (
    <div className={`relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/80 ${className}`.trim()}>
      <div aria-hidden="true" className="pointer-events-none select-none blur-[3px] opacity-45">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center p-3 md:p-4">
        <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white/96 p-4 text-slate-700 shadow-xl backdrop-blur">
          <div className="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            Раздел недоступен
          </div>
          <h3 className="mt-3 text-base font-semibold text-slate-900">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{summary}</p>
          {planName ? (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Текущий тариф: <span className="font-semibold text-slate-800">{planName}</span>
            </div>
          ) : null}
          <div className="mt-4">
            <Link
              to="/app/billing"
              className="inline-flex items-center justify-center rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
            >
              Тарифы и оплата
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

type UpgradeInlineNoticeProps = {
  title: string;
  text: string;
  description: string;
  planName?: string | null;
};

export function UpgradeInlineNotice({ title, text, description, planName }: UpgradeInlineNoticeProps) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900 md:flex-row md:items-start md:justify-between">
      <div className="leading-6">{text}</div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link
          to="/app/billing"
          className="inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-sm font-semibold text-sky-700 ring-1 ring-inset ring-sky-200 hover:bg-sky-50"
        >
          Тарифы и оплата
        </Link>
        <UpgradeDrawerButton title={title} description={description} planName={planName} />
      </div>
    </div>
  );
}
