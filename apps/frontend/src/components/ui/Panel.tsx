import type { HTMLAttributes, ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const panelVariants = cva("rounded-3xl border shadow-sm", {
  variants: {
    tone: {
      default: "border-slate-100 bg-white",
      muted: "border-slate-200 bg-slate-50",
      elevated: "border-slate-200 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.06)]",
    },
    padding: {
      sm: "p-4",
      md: "p-5",
      lg: "p-6",
    },
  },
  defaultVariants: {
    tone: "default",
    padding: "md",
  },
});

export function Panel({
  className,
  tone,
  padding,
  ...props
}: HTMLAttributes<HTMLDivElement> & VariantProps<typeof panelVariants>) {
  return <div className={cn(panelVariants({ tone, padding }), className)} {...props} />;
}

export function PanelHeader(props: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4", props.className)}>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-slate-900">{props.title}</div>
        {props.subtitle ? <div className="mt-1 text-sm text-slate-500">{props.subtitle}</div> : null}
      </div>
      {props.actions ? <div className="shrink-0">{props.actions}</div> : null}
    </div>
  );
}

export function PanelBody(props: { children: ReactNode; className?: string }) {
  return <div className={cn("mt-4", props.className)}>{props.children}</div>;
}
