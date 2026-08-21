export function fmtCurrency(n: number | undefined | null): string {
  if (n === undefined || n === null || isNaN(n)) return "$0";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function fmtCurrencyFull(n: number | undefined | null): string {
  if (n === undefined || n === null || isNaN(n)) return "$0";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function fmtPct(n: number | undefined | null): string {
  if (n === undefined || n === null || isNaN(n)) return "0%";
  return `${Math.round(n)}%`;
}

export function fmtScore(n: number | undefined | null): string {
  if (n === undefined || n === null || isNaN(n)) return "0";
  return Math.round(n).toString();
}

export function gradeColor(grade: string): string {
  switch (grade) {
    case "A": return "text-green-600 dark:text-green-400";
    case "B": return "text-blue-600 dark:text-blue-400";
    case "C": return "text-yellow-600 dark:text-yellow-400";
    case "D": return "text-orange-600 dark:text-orange-400";
    case "F": return "text-red-600 dark:text-red-400";
    default: return "text-muted-foreground";
  }
}

export function scoreColor(score: number, max = 100): string {
  const pct = (score / max) * 100;
  if (pct >= 80) return "text-green-600 dark:text-green-400";
  if (pct >= 60) return "text-blue-600 dark:text-blue-400";
  if (pct >= 40) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

export function severityBadge(severity: string): string {
  switch (severity.toLowerCase()) {
    case "high":
    case "critical":
      return "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
    case "medium":
    case "warning":
      return "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300";
    case "low":
    case "informational":
      return "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function tierColor(tier: string): string {
  switch (tier.toUpperCase()) {
    case "A":
    case "PLATINUM":
      return "text-purple-600 dark:text-purple-400";
    case "B":
    case "GOLD":
      return "text-yellow-600 dark:text-yellow-400";
    case "C":
    case "SILVER":
      return "text-slate-500 dark:text-slate-400";
    case "D":
    case "BRONZE":
      return "text-orange-600 dark:text-orange-400";
    default:
      return "text-muted-foreground";
  }
}
