import { PlayCircle } from "lucide-react";
import { Button } from "./Button";

export function HelpTriggerButton(props: { onClick: () => void; label?: string; className?: string }) {
  return (
    <Button size="sm" variant="secondary" onClick={props.onClick} className={props.className}>
      <PlayCircle className="mr-2 h-4 w-4" />
      {props.label || "Как это работает"}
    </Button>
  );
}
