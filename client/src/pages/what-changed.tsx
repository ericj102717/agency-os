import { useQuery } from "@tanstack/react-query";
import { AlertCircle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent, SeverityBadge } from "@/components/ui-widgets";
import { fmtScore, gradeColor, scoreColor } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

const severityIcons: Record<string, typeof TrendingUp> = {
  high: TrendingUp,
  medium: AlertCircle,
  low: Minus,
  informational: Minus,
  warning: TrendingDown,
  critical: AlertCircle,
};

export function WhatChangedPage() {
  const { data: cc, isLoading, error } = useQuery<CommandCenterData>({
    queryKey: [`${API_BASE}/api/command-center`],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/command-center`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 60_000,
  });

  if (isLoading) return <LoadingState />;
  if (error || !cc) return <ErrorState message="Failed to load change detection data" />;

  const wc = cc.what_changed;
  const k = wc.kpis;
  const changes = wc.top_5_changes || [];
  const score = k.movement_score ?? wc.movement_score?.score ?? 0;
  const grade = k.movement_grade ?? wc.movement_score?.grade ?? "—";

  return (
    <div className="space-y-6">
      <SectionHeader title="What Changed?" subtitle="Recent business changes and exception detection" />

      {/* Health Score Banner */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Movement Score</div>
              <div className="flex items-baseline gap-2">
                <span className={`text-4xl font-bold ${scoreColor(score)}`}>{fmtScore(score)}</span>
                <span className="text-sm text-muted-foreground">/100</span>
                <span className={`text-lg font-bold ${gradeColor(grade)} ml-2`}>Grade {grade}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Total Changes" value={k.total_changes} accent="info" />
        <KPICard label="Positive Exceptions" value={k.positive_exceptions} accent="success" />
        <KPICard label="Negative Exceptions" value={k.negative_exceptions} accent="warning" />
        <KPICard label="Missed Opportunities" value={k.missed_opportunities} accent="error" />
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Improving Trends" value={k.improving_trends} accent="success" />
        <KPICard label="Declining Trends" value={k.declining_trends} accent="error" />
        <KPICard label="AI Insights" value={k.ai_insights} accent="info" />
        <KPICard label="Movement Score" value={fmtScore(score)} accent="primary" />
      </div>

      {/* Top Changes */}
      <div>
        <SectionHeader title="Top 5 Changes" />
        <div className="space-y-3">
          {changes.length === 0 ? (
            <Card>
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">No changes detected.</p>
              </CardContent>
            </Card>
          ) : (
            changes.map((change, i) => {
              const Icon = severityIcons[change.severity] ?? AlertCircle;
              return (
                <Card key={i}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <SeverityBadge severity={change.severity} />
                          <span className="text-xs text-muted-foreground capitalize">
                            {change.category} — {change.type.replace(/_/g, " ")}
                          </span>
                        </div>
                        <div className="text-sm font-medium text-foreground">{change.description}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {change.count} item{change.count !== 1 ? "s" : ""} — {change.period}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 bg-muted rounded animate-pulse" />
      <div className="h-32 bg-muted rounded-lg animate-pulse" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300">
      <AlertCircle className="h-5 w-5" />
      {message}
    </div>
  );
}
