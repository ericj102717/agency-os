import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Users, Heart, Activity, TrendingDown, AlertTriangle } from "lucide-react";
import { API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent, SeverityBadge } from "@/components/ui-widgets";
import { MetricBarList, GaugeChart } from "@/components/charts";
import { fmtCurrency, fmtPct } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function ClientHealthPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load client health data" />;

  const clv = cc.clv_intelligence;
  const k = clv.kpis;
  const charts = cc.charts;
  const clients = clv.clients || [];
  const segments = clv.segments || {};
  const callPriorities = clv.call_priorities || [];

  // Compute health metrics
  const healthyClients = clients.filter(c => (c.health ?? 50) >= 70).length;
  const atRiskClients = clients.filter(c => (c.health ?? 50) < 50).length;
  const avgHealth = clients.length > 0
    ? Math.round(clients.reduce((s, c) => s + (c.health ?? 50), 0) / clients.length)
    : 0;
  const retentionRate = k.retention_rate || 0;

  // CRM data quality
  const dqScore = charts.data_quality_gauge || 100;
  const crmAgent = cc.agents[5] || {};
  const crmK = crmAgent.kpis || {};

  return (
    <div className="space-y-6">
      <SectionHeader title="Client Health" subtitle="Monitor client relationships, health scores, and data quality" />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Total Clients" value={k.total_clients} accent="primary" icon={Users} />
        <KPICard label="Avg Health" value={`${avgHealth}%`} accent={avgHealth >= 70 ? "success" : "warning"} icon={Heart} />
        <KPICard label="At Risk" value={atRiskClients} accent="error" icon={AlertTriangle} />
        <KPICard label="Retention Rate" value={fmtPct(retentionRate)} accent="success" icon={Activity} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Healthy Clients" value={healthyClients} accent="success" />
        <KPICard label="Data Quality" value={`${dqScore}%`} accent={dqScore >= 80 ? "success" : "warning"} />
        <KPICard label="Stuck Opportunities" value={crmK.stuck_opportunities || 0} accent="warning" />
        <KPICard label="Overdue Tasks" value={crmK.overdue_tasks || 0} accent="error" />
      </div>

      {/* Health Score Gauge + CRM Issues */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div>
          <SectionHeader title="Data Quality Score" />
          <Card>
            <CardContent className="p-4 flex flex-col items-center">
              <GaugeChart value={dqScore} height={120} />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Issues by Severity" />
          <Card>
            <CardContent className="p-4">
              <MetricBarList data={charts.crm_issue_severity || []} height={120} />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Tag & Field Health" />
          <Card>
            <CardContent className="p-4">
              <MetricBarList data={charts.tag_field_health || []} height={120} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Client Segments */}
      <div>
        <SectionHeader title="Client Segmentation" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(segments).map(([tier, data]) => {
            const labels: Record<string, string> = {
              A: "Strategic Relationships",
              B: "High-Value Clients",
              C: "Core Clients",
              D: "Growth Opportunities",
            };
            const colors: Record<string, string> = {
              A: "border-green-500 bg-green-50 dark:bg-green-950/30",
              B: "border-blue-500 bg-blue-50 dark:bg-blue-950/30",
              C: "border-amber-500 bg-amber-50 dark:bg-amber-950/30",
              D: "border-slate-400 bg-slate-50 dark:bg-slate-900/30",
            };
            const count = data.client_count || data.count || 0;
            const value = data.total_value || data.total_clv || 0;
            return (
              <Card key={tier} className={`border-l-4 ${colors[tier] || ""}`}>
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground mb-1">Tier {tier}</div>
                  <div className="text-sm font-medium mb-2">{labels[tier] || tier}</div>
                  <div className="text-2xl font-bold">{count}</div>
                  <div className="text-xs text-muted-foreground mt-1">{fmtCurrency(value)} value</div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Who Should I Call Today */}
      {callPriorities.length > 0 && (
        <div>
          <SectionHeader title="Who Should I Call Today?" />
          <div className="space-y-2">
            {callPriorities.map((cp, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-sm">
                        {i + 1}
                      </div>
                      <div>
                        <div className="text-sm font-medium">{cp.display_name || cp.client_name || cp.name}</div>
                        <div className="text-xs text-muted-foreground mt-0.5">{cp.reason || cp.reasoning}</div>
                        {cp.recommended_action && (
                          <div className="text-xs text-primary mt-1">→ {cp.recommended_action}</div>
                        )}
                      </div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      cp.priority === "urgent" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" :
                      cp.priority === "high" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" :
                      "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    }`}>
                      {cp.priority}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Client Leaderboard */}
      {clients.length > 0 && (
        <div>
          <SectionHeader title="Client Leaderboard" />
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Client</th>
                      <th className="text-left px-4 py-2 font-medium">Tier</th>
                      <th className="text-right px-4 py-2 font-medium">Revenue</th>
                      <th className="text-right px-4 py-2 font-medium">CLV</th>
                      <th className="text-right px-4 py-2 font-medium">Score</th>
                      <th className="text-left px-4 py-2 font-medium">Last Activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clients.slice(0, 15).map((c, i) => (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 font-medium">{c.name}</td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            c.value_tier === "A" ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" :
                            c.value_tier === "B" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" :
                            c.value_tier === "C" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" :
                            "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                          }`}>
                            {c.value_tier}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono">{fmtCurrency(c.total_revenue)}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{fmtCurrency(c.clv)}</td>
                        <td className="px-4 py-2.5 text-right font-mono font-bold">{c.score}</td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">{c.last_activity || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function LoadingState() { return <div className="space-y-4"><div className="h-8 w-64 bg-muted rounded animate-pulse" /><div className="h-32 bg-muted rounded-lg animate-pulse" /></div>; }
function ErrorState({ message }: { message: string }) { return <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300"><AlertCircle className="h-5 w-5" />{message}</div>; }
