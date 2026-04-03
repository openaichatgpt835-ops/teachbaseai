import { cn } from "./cn";

export type SegmentedOption = {
  value: string;
  label: string;
};

export function SegmentedControl(props: {
  value: string;
  options: SegmentedOption[];
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1", props.className)}>
      {props.options.map((option) => {
        const active = option.value === props.value;
        return (
          <button
            key={option.value}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs transition-colors",
              active ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
            )}
            onClick={() => props.onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
