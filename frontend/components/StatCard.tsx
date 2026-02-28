import { classNames } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  accent?: string;
  icon?: React.ReactNode;
}

export default function StatCard({ label, value, sublabel, accent, icon }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 transition-colors hover:border-border-light">
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            {label}
          </span>
          <span
            className={classNames(
              "text-2xl font-bold tracking-tight",
              accent || "text-foreground"
            )}
          >
            {value}
          </span>
          {sublabel && (
            <span className="text-xs text-muted">{sublabel}</span>
          )}
        </div>
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
