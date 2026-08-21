import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Users, GitBranch, Target, Mail, TrendingUp } from "lucide-react";
import { API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent, SeverityBadge } from "@/components/ui-widgets";
import { DonutBreakdown, MetricBarList } from "@/components/charts";
import { fmtScore } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function ReferralOpportunitiesPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load referral intelligence" />;

  const ri = cc.referral_intelligence;
  const k = ri.kpis;
  const charts = cc.charts;
  const scored = ri.scored_sources || ri.leaderboard || [];
  const campaigns = ri.campaigns || [];
  const gaps = ri.gaps || [];
  const topOpps = ri.top_opportunities || [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Referral Opportunities"
        subtitle="Nurture referral sources to grow referrals — they close at 3x the rate of cold leads"
      />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Referral Sources" value={k.total_sources} accent="primary" icon={Users} />
        <KPICard label="Avg Score" value={fmtScore(k.average_score)} accent="info" icon={Target} />
        <KPICard label="Advocates" value={k.advocates} accent="success" icon={TrendingUp} />
        <KPICard label="Opportunities" value={k.total_opportunities} accent="warning" icon={GitBranch} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Active Campaigns" value={k.active_campaigns} accent="primary" />
        <KPICard label="Total Gaps" value={k.total_gaps} accent="error" />
        <KPICard label="High Potential" value={k.high_potential} accent="info" />
        <KPICard label="Dormant" value={k.dormant} accent="warning" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <SectionHeader title="Actions by Priority" />
          <Card>
            <CardContent className="p-4">
              <DonutBreakdown data={charts.actions_by_priority || []} height={200} />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Actions by Severity" />
          <Card>
            <CardContent className="p-4">
              <MetricBarList
                data={(charts.actions_by_severity || []).map((s) => ({
                  label: s.label,
                  count: s.count,
                  color: s.label === "critical" ? "#dc2626" : s.label === "warning" || s.label === "high" ? "#d97706" : "#0d7490",
                }))}
                height={200}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Top Opportunities */}
      {topOpps.length > 0 && (
        <div>
          <SectionHeader title="Top Referral Opportunities" />
          <div className="space-y-2">
            {topOpps.map((opp, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{opp.title}</div>
                      {opp.description && <div className="text-xs text-muted-foreground mt-1">{opp.description}</div>}
                      {opp.recommended_action && (
                        <div className="text-xs text-primary mt-1">→ {opp.recommended_action}</div>
                      )}
                    </div>
                    {opp.score !== undefined && (
                      <div className="text-sm font-bold text-primary">{fmtScore(opp.score)}</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Scored Sources Table */}
      {scored.length > 0 && (
        <div>
          <SectionHeader title="Source Leaderboard" />
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Source</th>
                      <th className="text-right px-4 py-2 font-medium">Score</th>
                      <th className="text-right px-4 py-2 font-medium">Referrals</th>
                      <th className="text-right px-4 py-2 font-medium">Conversion</th>
                      <th className="text-left px-4 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scored.map((src, i) => (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 font-medium">{src.name}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{fmtScore(src.score)}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{src.referrals_count || 0}</td>
                        <td className="px-4 py-2.5 text-right font-mono">
                          {src.conversion_rate ? `${Math.round(src.conversion_rate * 100)}%` : "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            src.tier === "ADVOCATE" ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" :
                            src.tier === "HIGH_POTENTIAL" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" :
                            "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                          }`}>
                            {src.tier || src.status || "Active"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Campaigns */}
      {campaigns.length > 0 && (
        <div>
          <SectionHeader title="Active Campaigns" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {campaigns.map((c, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-medium">{c.name}</div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">{c.status}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><span className="text-muted-foreground">Sent:</span> <span className="font-mono">{c.sent}</span></div>
                    <div><span className="text-muted-foreground">Opened:</span> <span className="font-mono">{c.opened}</span></div>
                    <div><span className="text-muted-foreground">Clicked:</span> <span className="font-mono">{c.clicked}</span></div>
                    <div><span className="text-muted-foreground">Converted:</span> <span className="font-mono">{c.converted}</span></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Gaps */}
      {gaps.length > 0 && (
        <div>
          <SectionHeader title="Referral Gaps" />
          <div className="space-y-2">
            {gaps.map((gap, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <SeverityBadge severity={gap.severity} />
                    <div>
                      <div className="text-sm font-medium">{gap.title}</div>
                      <div className="text-xs text-muted-foreground mt-1">{gap.description}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LoadingState() {
  return <div className="space-y-4"><div className="h-8 w-64 bg-muted rounded animate-pulse" /><div className="h-32 bg-muted rounded-lg animate-pulse" /></div>;
}
function ErrorState({ message }: { message: string }) {
  return <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300"><AlertCircle className="h-5 w-5" />{message}</div>;
}
