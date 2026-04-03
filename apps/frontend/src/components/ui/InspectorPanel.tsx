import type { ReactNode } from "react";
import { Panel, PanelBody, PanelHeader } from "./Panel";
import { SegmentedControl, type SegmentedOption } from "./SegmentedControl";

export function InspectorPanel(props: {
  title: ReactNode;
  subtitle?: ReactNode;
  mode?: string;
  modes?: SegmentedOption[];
  onModeChange?: (value: string) => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Panel tone="elevated">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <PanelHeader title={props.title} subtitle={props.subtitle} />
        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          {props.modes && props.mode && props.onModeChange ? (
            <SegmentedControl value={props.mode} options={props.modes} onChange={props.onModeChange} />
          ) : null}
          {props.actions}
        </div>
      </div>
      <PanelBody>{props.children}</PanelBody>
    </Panel>
  );
}
