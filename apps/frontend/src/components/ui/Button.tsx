import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl border text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "border-sky-600 bg-sky-600 text-white hover:bg-sky-700 hover:border-sky-700",
        secondary: "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
        ghost: "border-transparent bg-transparent text-slate-600 hover:bg-slate-100",
        danger: "border-rose-200 bg-white text-rose-600 hover:bg-rose-50",
      },
      size: {
        sm: "px-3 py-2 text-xs",
        md: "px-4 py-2.5",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
);

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>
>(function Button({ className, variant, size, ...props }, ref) {
  return <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
});
