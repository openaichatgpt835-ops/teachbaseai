import type { ReactNode } from "react";

export function KbV2Layout(props: { sidebar: ReactNode; main: ReactNode; inspector: ReactNode }) {
  return (
    <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_360px]">
      <aside>{props.sidebar}</aside>
      <main className="min-w-0">{props.main}</main>
      <aside>{props.inspector}</aside>
    </div>
  );
}
