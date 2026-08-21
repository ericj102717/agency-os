import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/queryClient";
import { Activity, AlertCircle, TrendingUp, Zap, ArrowRight } from "lucide-react";
import { KPICard, SectionHeader, Card, CardContent, SeverityBadge } from "@/components/ui-widgets";
import { fmtScore, gradeColor, scoreColor } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function StrategicAnalysisPage() {
  const { data: cc, isLoading, error } = useQuery<CommandCenterData>({
    queryKey: ["/api/command-center"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/command-center`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 60_000,
  });

  if (isLoading) return <LoadingState />;
  if (error || !cc) return <ErrorState message="Failed to load strategic analysis data" />;

  const exec = cc.executive;
  const k = exec.kpis;
  const priorities = exec.priorities || [];
  const escalations = (exec as any).escalations || [];
  const briefing = exec.briefing;

  const healthColor = scoreColor(k.health_score);

  return (
    <div className="space-y-6">
      <SectionHeader title="Strategic Analysis" subtitle="Executive summary and business health overview" />

      {/* Health Score Banner */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Business Health Score</div>
              <div className="flex items-baseline gap-2">
                <span className={`text-5xl font-bold ${healthColor}`}>{fmtScore(k.health_score)}</span>
                <span className="text-lg text-muted-foreground">/100</span>
                <span className={`text-xl font-bold ${gradeColor(k.health_grade)} ml-2`}>Grade {k.health_grade}</span>
              </div>
              <div className="text-sm text-muted-foreground mt-2">
                Forecast confidence: <strong>{k.forecast_confidence}</strong>
              </div>
            </div>
            <div className="hidden sm:flex flex-col items-end gap-1">
              <div className="text-xs text-muted-foreground">AI Activities (24h)</div>
              <div className="text-2xl font-bold text-foreground">{k.ai_activities_24h}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Total Priorities" value={k.total_priorities} accent="warning" />
        <KPICard label="Total Escalations" value={k.total_escalations} accent="error" />
        <KPICard label="Critical Escalations" value={k.critical_escalations} accent="error" />
        <KPICard label="Pipeline Value" value={`$${(briefing.pipeline_value / 1000).toFixed(0)}K`} accent="info" />
      </div>

      {/* Briefing Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xs text-muted-foreground mb-1">Total Leads</div>
            <div className="text-xl font-bold tabular-nums">{briefing.leads}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xs text-muted-foreground mb-1">Hot Leads</div>
            <div className="text-xl font-bold tabular-nums text-red-600 dark:text-red-400">{briefing.hot_leads}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xs text-muted-foreground mb-1">Open Tasks</div>
            <div className="text-xl font-bold tabular-nums">{briefing.open_tasks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-xs text-muted-foreground mb-1">Pipeline Value</div>
            <div className="text-xl font-bold tabular-nums">${(briefing.pipeline_value / 1000).toFixed(0)}K</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Priorities */}
        <div>
          <SectionHeader title="Top Priorities" />
          <Card>
            <CardContent className="p-4 space-y-3">
              {priorities.length === 0 ? (
                <p className="text-sm text-muted-foreground">No priorities identified.</p>
              ) : (
                priorities.map((p, i) => (
                  <div key={i} className="flex items-start gap-3 border-b border-border pb-3 last:border-0 last:pb-0">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
                      {p.priority}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <SeverityBadge severity={p.urgency} />
                        <span className="text-xs text-muted-foreground capitalize">{p.category}</span>
                      </div>
                      <div className="text-sm font-medium text-foreground">{p.title}</div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Escalations */}
        <div>
          <SectionHeader title="Escalations" />
          <Card>
            <CardContent className="p-4 space-y-3">
              {escalations.length === 0 ? (
                <p className="text-sm text-muted-foreground">No escalations.</p>
              ) : (
                escalations.slice(0, 8).map((e: any, i: number) => (
                  <div key={i} className="border-b border-border pb-3 last:border-0 last:pb-0">
                    <div className="flex items-center gap-2 mb-1">
                      <SeverityBadge severity={e.severity} />
                      <span className="text-xs text-muted-foreground capitalize">{e.category}</span>
                    </div>
                    <div className="text-sm font-medium text-foreground">{e.title}</div>
                    {e.description && (
                      <div className="text-xs text-muted-foreground mt-1">{e.description}</div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
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
