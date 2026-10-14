import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const styles: Record<string, string> = {
  pass: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  passed: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  fail: "border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-400",
  failed: "border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-400",
  skip: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  skipped: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  low: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  high: "border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-400",
  critical: "border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-400",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("capitalize", styles[value.toLowerCase()])}
    >
      {value}
    </Badge>
  );
}

