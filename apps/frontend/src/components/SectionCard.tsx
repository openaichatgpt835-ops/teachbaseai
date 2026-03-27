import type { ReactNode } from "react";
import { SECTION_SHELL } from "../../../shared/ui/sectionShell";

type Props = {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function SectionCard({ title, actions, children, className = "" }: Props) {
  return (
    <section
      className={`bg-white ${className}`.trim()}
      style={{
        borderRadius: SECTION_SHELL.cardRadiusPx,
        border: `1px solid ${SECTION_SHELL.cardBorderColor}`,
        boxShadow: SECTION_SHELL.cardShadow,
        padding: SECTION_SHELL.cardPaddingPx,
      }}
    >
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title ? <h2 className="text-sm font-semibold text-slate-900">{title}</h2> : <div />}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
