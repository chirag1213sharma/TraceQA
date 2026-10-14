import type { LucideIcon } from "lucide-react";

interface FeaturePlaceholderProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function FeaturePlaceholder({
  icon: Icon,
  title,
  description,
}: FeaturePlaceholderProps) {
  return (
    <section className="relative isolate overflow-hidden rounded-xl border bg-card px-6 py-16 text-center shadow-sm sm:px-12">
      <div
        className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,var(--color-primary),transparent_42%)] opacity-[0.06]"
        aria-hidden="true"
      />
      <span className="mx-auto flex size-12 items-center justify-center rounded-xl border bg-background text-primary shadow-sm">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <h2 className="mt-5 text-lg font-semibold tracking-tight">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
        {description}
      </p>
      <span className="mt-6 inline-flex rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
        Phase 4 integration
      </span>
    </section>
  );
}
