import type { ReactNode } from "react";

export function KbV2Main(props: { header: ReactNode; coverage: ReactNode; files: ReactNode }) {
  return (
    <div className="space-y-4">
      {props.header}
      {props.coverage}
      {props.files}
    </div>
  );
}
