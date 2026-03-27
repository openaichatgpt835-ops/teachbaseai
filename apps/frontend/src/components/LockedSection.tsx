import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  UPGRADE_BADGE_HIGHER_PLAN,
  UPGRADE_BADGE_LOCKED,
  UPGRADE_CTA_PRIMARY,
  UPGRADE_CTA_SECONDARY,
  UPGRADE_DRAWER_CLOSE,
  UPGRADE_DRAWER_HINT,
  UPGRADE_DRAWER_TITLE,
  UPGRADE_PLAN_LABEL,
} from "../shared/upgradeCopy";

type UpgradeDrawerButtonProps = {
  title: string;
  description: string;
  planName?: string | null;
};

function useBillingPath() {
  const location = useLocation();
  return useMemo(() => (location.pathname.startsWith("/embedded/bitrix") ? "/embedded/bitrix/billing" : "/app/billing"), [location.pathname]);
}

export function UpgradeDrawerButton({ title, description, planName }: UpgradeDrawerButtonProps) {
  const [open, setOpen] = useState(false);
  const billingPath = useBillingPath();

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
        {UPGRADE_CTA_SECONDARY}
      </button>
      {open && (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/35"
            aria-label={UPGRADE_DRAWER_CLOSE}
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 top-auto flex md:inset-y-0 md:left-auto md:right-0 md:w-[440px]">
            <div className="mt-auto w-full rounded-t-3xl border border-slate-200 bg-white shadow-2xl md:mt-0 md:rounded-l-3xl md:rounded-r-none md:rounded-t-none">
              <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">{UPGRADE_DRAWER_TITLE}</div>
                  <h3 className="mt-1 text-lg font-semibold text-slate-900">{title}</h3>
                </div>
                <button type="button" className="text-sm text-slate-500 hover:text-slate-700" onClick={() => setOpen(false)}>
                  {UPGRADE_DRAWER_CLOSE}
                </button>
              </div>
              <div className="space-y-4 px-5 py-5 text-sm text-slate-600">
                <p className="leading-6">{description}</p>
                {planName ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    {UPGRADE_PLAN_LABEL}: <span className="font-semibold text-slate-900">{planName}</span>
                  </div>
                ) : null}
                <div className="rounded-2xl border border-sky-100 bg-sky-50 px-4 py-3 text-slate-700">
                  {UPGRADE_DRAWER_HINT}
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    to={billingPath}
                    onClick={() => setOpen(false)}
                    className="inline-flex items-center justify-center rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
                  >
                    {UPGRADE_CTA_PRIMARY}
                  </Link>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    onClick={() => setOpen(false)}
                  >
                    {UPGRADE_DRAWER_CLOSE}
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

type UpgradeNoticeBarProps = {
  title: string;
  text: string;
  description?: string;
  planName?: string | null;
  compact?: boolean;
};

export function UpgradeNoticeBar({ title, text, description, planName, compact = false }: UpgradeNoticeBarProps) {
  const billingPath = useBillingPath();
  return (
    <div
      className={[
        "rounded-2xl border border-amber-200 bg-amber-50 text-amber-950",
        compact ? "px-3 py-3" : "px-4 py-4",
      ].join(" ")}
    >
      <div className={compact ? "flex flex-col gap-2" : "flex flex-col gap-3 md:flex-row md:items-start md:justify-between"}>
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">{UPGRADE_BADGE_LOCKED}</div>
          <div className="mt-1 text-sm font-semibold text-slate-900">{title}</div>
          <div className={compact ? "mt-1 text-xs leading-5 text-slate-700" : "mt-1 text-sm leading-6 text-slate-700"}>{text}</div>
          {planName ? <div className="mt-2 text-xs font-medium text-slate-500">{UPGRADE_PLAN_LABEL}: {planName}</div> : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to={billingPath}
            className="inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-sm font-semibold text-sky-700 ring-1 ring-inset ring-sky-200 hover:bg-sky-50"
          >
            {UPGRADE_CTA_PRIMARY}
          </Link>
          {description ? <UpgradeDrawerButton title={title} description={description} planName={planName} /> : null}
        </div>
      </div>
    </div>
  );
}

type UpgradeFeatureCardProps = {
  title: string;
  text: string;
  bullets?: string[];
  description?: string;
  planName?: string | null;
  children?: ReactNode;
};

export function UpgradeFeatureCard({ title, text, bullets = [], description, planName, children }: UpgradeFeatureCardProps) {
  const billingPath = useBillingPath();
  return (
    <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-5 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">{UPGRADE_BADGE_HIGHER_PLAN}</div>
      <h3 className="mt-2 text-lg font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">{text}</p>
      {bullets.length ? (
        <ul className="mt-4 space-y-2 text-sm text-slate-700">
          {bullets.map((bullet) => (
            <li key={bullet} className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 rounded-full bg-sky-500" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {children ? <div className="mt-4 rounded-2xl border border-slate-200/70 bg-white/70 p-4">{children}</div> : null}
      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          to={billingPath}
          className="inline-flex items-center justify-center rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700"
        >
          {UPGRADE_CTA_PRIMARY}
        </Link>
        {description ? <UpgradeDrawerButton title={title} description={description} planName={planName} /> : null}
      </div>
      {planName ? <div className="mt-3 text-xs font-medium text-slate-500">{UPGRADE_PLAN_LABEL}: {planName}</div> : null}
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
  return <UpgradeNoticeBar title={title} text={text} description={description} planName={planName} />;
}
