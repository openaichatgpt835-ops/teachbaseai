import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium", {
  variants: {
    tone: {
      neutral: "border-slate-200 bg-slate-50 text-slate-600",
      sky: "border-sky-200 bg-sky-50 text-sky-700",
      emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
      amber: "border-amber-200 bg-amber-50 text-amber-700",
      rose: "border-rose-200 bg-rose-50 text-rose-700",
      fuchsia: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
    },
  },
  defaultVariants: {
    tone: "neutral",
  },
});

export function Badge({
  className,
  tone,
  ...props
}: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
