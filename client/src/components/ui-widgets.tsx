import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { severityBadge } from "@/lib/format";
import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "primary" | "success" | "warning" | "error" | "info";
  icon?: LucideIcon;
}

const accentClasses: Record<string, string> = {
  primary: "border-l-primary",
  success: "border-l-green-500",
  warning: "border-l-yellow-500",
  error: "border-l-red-500",
  info: "border-l-blue-500",
};

export function KPICard({ label, value, sub, accent = "primary", icon: Icon }: KPICardProps) {
  return (
    <Card className={cn("border-l-4", accentClasses[accent])}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="text-xs font-medium text-muted-foreground mb-1">{label}</div>
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
        </div>
        <div className="text-2xl font-bold text-foreground tabular-nums">{value}</div>
        {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = severityBadge(severity);
  return <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold", cls)}>{severity.toUpperCase()}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const color =
    status === "active" ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300"
    : status === "error" ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
    : status === "warning" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300"
    : "bg-muted text-muted-foreground";
  return <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold", color)}>{status.toUpperCase()}</span>;
}

export { Card, CardHeader, CardTitle, CardContent };
