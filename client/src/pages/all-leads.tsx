import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Users, UserPlus, CheckCircle, Mail } from "lucide-react";
import { API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { FunnelChart } from "@/components/charts";
import type { CommandCenterData } from "@shared/types";

export function AllLeadsPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load leads data" />;

  const leadsAgent = cc.agents[0] || {};
  const k = leadsAgent.kpis || {};
  const charts = cc.charts;
  const funnel = charts.pipeline_funnel || [];
  const conversionRates = charts.conversion_rates || [];
  const leadScoring = cc.lead_scoring;
  const topOpps = leadScoring.top_10_opportunities || [];
  const tierDist = leadScoring.tier_distribution || {};

  return (
    <div className="space-y-6">
      <SectionHeader title="All Leads" subtitle="Review your leads below. Contact new leads within 24 hours to maximize conversion." />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Total Contacts" value={k.total_contacts || 0} accent="primary" icon={Users} />
        <KPICard label="Leads" value={k.leads || 0} sub={`${k.new_leads || 0} new`} accent="info" icon={UserPlus} />
        <KPICard label="Prospects" value={k.prospects || 0} sub={`${k.qualified || 0} qualified`} accent="warning" icon={Mail} />
        <KPICard label="Clients" value={k.clients || 0} sub={`${k.closed_won || 0} closed won`} accent="success" icon={CheckCircle} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <SectionHeader title="Pipeline Funnel" />
          <Card>
            <CardContent className="p-4">
              <FunnelChart data={funnel} height={220} />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Conversion Rates" />
          <Card>
            <CardContent className="p-4">
              <div className="space-y-2">
                {conversionRates.map((c, i) => {
                  const rate = Math.round(c.rate * 100);
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-24 text-xs text-muted-foreground capitalize">{c.stage}</div>
                      <div className="flex-1 h-8 rounded-md bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-r flex items-center justify-end pr-2 ${rate > 80 ? "bg-green-500" : rate > 50 ? "bg-primary" : "bg-amber-500"}`}
                          style={{ width: `${Math.max(rate, 3)}%` }}
                        >
                          <span className="text-xs font-semibold text-white">{rate}%</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Tier Distribution */}
      <div>
        <SectionHeader title="Lead Tier Distribution" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(tierDist).map(([tier, count]) => {
            const total = Object.values(tierDist).reduce((a, b) => a + b, 0) || 1;
            const pct = Math.round((count / total) * 100);
            const colors: Record<string, string> = {
              HOT: "bg-red-500", WARM: "bg-amber-500", NURTURE: "bg-blue-500", COLD: "bg-slate-500",
            };
            return (
              <Card key={tier}>
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground mb-1">{tier}</div>
                  <div className="text-2xl font-bold">{count}</div>
                  <div className="text-xs text-muted-foreground">{pct}% of leads</div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div className={`h-full rounded-full ${colors[tier] || "bg-primary"}`} style={{ width: `${pct}%` }} />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Pipeline Conversion Table */}
      <div>
        <SectionHeader title="Pipeline Conversion Table" />
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Stage</th>
                    <th className="text-right px-4 py-2 font-medium">Count</th>
                    <th className="text-right px-4 py-2 font-medium">Conversion</th>
                    <th className="text-left px-4 py-2 font-medium">Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {conversionRates.map((c, i) => {
                    const rate = Math.round(c.rate * 100);
                    const stageCount = funnel.find(f => f.stage === c.stage.toLowerCase().replace(/\s/g, "_"))?.count || 0;
                    return (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 capitalize">{c.stage}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{stageCount}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{rate}%</td>
                        <td className="px-4 py-2.5">
                          <div className="h-2 w-full max-w-[120px] rounded-full bg-muted overflow-hidden">
                            <div className={`h-full rounded-full ${rate > 80 ? "bg-green-500" : rate > 50 ? "bg-primary" : "bg-amber-500"}`} style={{ width: `${rate}%` }} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Opportunities */}
      {topOpps.length > 0 && (
        <div>
          <SectionHeader title="Top 10 Opportunities by Score" />
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Contact</th>
                      <th className="text-left px-4 py-2 font-medium">Product</th>
                      <th className="text-left px-4 py-2 font-medium">Stage</th>
                      <th className="text-right px-4 py-2 font-medium">Value</th>
                      <th className="text-right px-4 py-2 font-medium">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topOpps.map((opp, i) => (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 font-medium">{opp.contact_name}</td>
                        <td className="px-4 py-2.5">{opp.product_type}</td>
                        <td className="px-4 py-2.5 capitalize">{opp.stage.replace(/_/g, " ")}</td>
                        <td className="px-4 py-2.5 text-right font-mono">${(opp.estimated_value || 0).toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-right">
                          <span className={`font-mono font-bold ${opp.score > 80 ? "text-red-500" : opp.score > 50 ? "text-amber-500" : "text-blue-500"}`}>
                            {opp.score}
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
    </div>
  );
}

function LoadingState() { return <div className="space-y-4"><div className="h-8 w-64 bg-muted rounded animate-pulse" /><div className="h-32 bg-muted rounded-lg animate-pulse" /></div>; }
function ErrorState({ message }: { message: string }) { return <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300"><AlertCircle className="h-5 w-5" />{message}</div>; }
