import type { ReactNode } from "react";
import { cn } from "./cn";

export function WorkspaceSplit(props: {
  sidebar: ReactNode;
  main: ReactNode;
  inspector?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_380px]", props.className)}>
      <aside>{props.sidebar}</aside>
      <main className="min-w-0">{props.main}</main>
      {props.inspector ? <aside>{props.inspector}</aside> : null}
    </div>
  );
}
