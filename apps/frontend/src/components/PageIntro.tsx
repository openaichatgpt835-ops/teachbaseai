import { coreModuleMeta } from "../../../shared/ui/modules";

type Props = {
  moduleId: string;
  fallbackTitle: string;
  fallbackDescription: string;
};

export function PageIntro({ moduleId, fallbackTitle, fallbackDescription }: Props) {
  const meta = coreModuleMeta(moduleId, {
    label: fallbackTitle,
    description: fallbackDescription,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">{meta.label}</h1>
      <p className="mt-1 text-sm text-slate-500">{meta.description}</p>
    </div>
  );
}
