import type { ReactNode } from "react";
import { SECTION_SHELL } from "../../../shared/ui/sectionShell";

type Props = {
  title: ReactNode;
  description: ReactNode;
  className?: string;
};

export function EmptyStateBlock({ title, description, className = "" }: Props) {
  return (
    <div
      className={className}
      style={{
        borderRadius: SECTION_SHELL.emptyRadiusPx,
        border: `1px dashed ${SECTION_SHELL.emptyBorderColor}`,
        background: SECTION_SHELL.emptyBackground,
        padding: 16,
      }}
    >
      <div style={{ color: SECTION_SHELL.emptyTitleColor }} className="text-sm font-medium">
        {title}
      </div>
      <div style={{ color: SECTION_SHELL.emptyTextColor }} className="mt-1 text-sm">
        {description}
      </div>
    </div>
  );
}
