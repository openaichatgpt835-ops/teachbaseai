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
        <div className="min-w-0 flex-1">
          <PanelHeader title={props.title} subtitle={props.subtitle} />
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:max-w-full xl:justify-end">
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
