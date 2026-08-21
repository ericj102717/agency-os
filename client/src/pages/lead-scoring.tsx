import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/queryClient";
import { Star, Flame, TrendingUp, Coffee, Snowflake, AlertCircle } from "lucide-react";
import { KPICard, SectionHeader, Card, CardContent, SeverityBadge } from "@/components/ui-widgets";
import { fmtCurrency, fmtScore, scoreColor } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function LeadScoringPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load lead scoring data" />;

  const ls = cc.lead_scoring;
  const kpis = ls.kpis;
  const opps = ls.top_10_opportunities;
  const tiers = ls.tier_distribution;

  const tierMeta: Record<string, { icon: typeof Flame; color: string; bg: string }> = {
    HOT: { icon: Flame, color: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950" },
    WARM: { icon: TrendingUp, color: "text-orange-600 dark:text-orange-400", bg: "bg-orange-50 dark:bg-orange-950" },
    NURTURE: { icon: Coffee, color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950" },
    COLD: { icon: Snowflake, color: "text-slate-500 dark:text-slate-400", bg: "bg-slate-50 dark:bg-slate-900" },
  };

  return (
    <div className="space-y-6">
      <SectionHeader title="Lead Scoring & Priorities" subtitle="AI-scored leads ranked by conversion probability" />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <KPICard label="Total Leads" value={kpis.total_leads} accent="primary" />
        <KPICard label="Avg Score" value={fmtScore(kpis.average_score)} accent="info" />
        <KPICard label="Hot Leads" value={kpis.hot_leads} accent="error" />
        <KPICard label="Warm Leads" value={kpis.warm_leads} accent="warning" />
        <KPICard label="Nurture" value={kpis.nurture_leads} accent="info" />
        <KPICard label="Pipeline Value" value={fmtCurrency(kpis.total_pipeline_value)} accent="success" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Tier Distribution */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-3">Tier Distribution</h3>
            <div className="space-y-3">
              {Object.entries(tiers).map(([tier, count]) => {
                const meta = tierMeta[tier] ?? tierMeta.NURTURE;
                const pct = kpis.total_leads > 0 ? (count / kpis.total_leads) * 100 : 0;
                return (
                  <div key={tier}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <meta.icon className={`h-4 w-4 ${meta.color}`} />
                        <span className="text-sm font-medium">{tier}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">{count} ({Math.round(pct)}%)</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${meta.bg.replace("50", "400").replace("950", "500")}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            {kpis.leads_at_risk > 0 && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-950/50 px-3 py-2 text-xs text-red-700 dark:text-red-300">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {kpis.leads_at_risk} leads at risk — no activity in 3+ days
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Opportunities Table */}
        <div className="lg:col-span-2">
          <SectionHeader title="Top 10 Opportunities by Score" />
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs text-muted-foreground">
                      <th className="text-left font-medium px-4 py-2.5">Contact</th>
                      <th className="text-left font-medium px-4 py-2.5">Product</th>
                      <th className="text-left font-medium px-4 py-2.5">Stage</th>
                      <th className="text-right font-medium px-4 py-2.5">Value</th>
                      <th className="text-right font-medium px-4 py-2.5">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opps.map((opp, i) => (
                      <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/50">
                        <td className="px-4 py-2.5 font-medium text-foreground">{opp.contact_name}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{opp.product_type}</td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs capitalize text-muted-foreground">{opp.stage}</span>
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">{fmtCurrency(opp.estimated_value)}</td>
                        <td className="px-4 py-2.5 text-right">
                          <span className={`font-bold tabular-nums ${scoreColor(opp.score)}`}>
                            {fmtScore(opp.score)}
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
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 bg-muted rounded animate-pulse" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-24 bg-muted rounded-lg animate-pulse" />
        ))}
      </div>
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
