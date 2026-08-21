import { useQuery } from "@tanstack/react-query";
import { AlertCircle, GitBranch, TrendingUp, DollarSign, Target } from "lucide-react";
import { API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { FunnelChart, DonutBreakdown, MetricBarList } from "@/components/charts";
import { fmtCurrency } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function PipelinePage() {
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
  if (error || !cc) return <ErrorState message="Failed to load pipeline data" />;

  const charts = cc.charts;
  const opps = charts.raw_opportunities || [];
  const funnel = charts.pipeline_funnel || [];
  const productMix = charts.product_mix || [];
  const stuckAging = charts.stuck_aging || [];

  // Compute KPIs from raw opportunities
  const activePipeline = opps.filter(o => !["closed_won", "closed_lost"].includes(o.stage)).reduce((s, o) => s + o.estimated_value, 0);
  const wonDeals = opps.filter(o => o.stage === "closed_won");
  const wonValue = wonDeals.reduce((s, o) => s + o.estimated_value, 0);
  const avgDealSize = opps.length > 0 ? opps.reduce((s, o) => s + o.estimated_value, 0) / opps.length : 0;
  const closeRate = opps.length > 0 ? Math.round((wonDeals.length / opps.length) * 100) : 0;

  // Conversion rates from charts
  const conversionRates = charts.conversion_rates || [];
  const byStage: Record<string, number> = {};
  funnel.forEach(f => { byStage[f.stage] = f.count; });

  return (
    <div className="space-y-6">
      <SectionHeader title="Pipeline" subtitle="Focus on moving leads through the funnel to close deals" />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard label="Active Pipeline" value={fmtCurrency(activePipeline)} accent="info" icon={DollarSign} />
        <KPICard label="Close Rate" value={`${closeRate}%`} accent="success" icon={Target} />
        <KPICard label="Won Value" value={fmtCurrency(wonValue)} accent="success" sub={`${wonDeals.length} deals`} icon={TrendingUp} />
        <KPICard label="Avg Deal Size" value={fmtCurrency(avgDealSize)} accent="primary" icon={GitBranch} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <SectionHeader title="Pipeline Funnel" />
          <Card>
            <CardContent className="p-4">
              <FunnelChart data={funnel} height={240} />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Product Mix" />
          <Card>
            <CardContent className="p-4">
              <DonutBreakdown data={productMix} height={240} />
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <SectionHeader title="Conversion Rates" />
          <Card>
            <CardContent className="p-4">
              <MetricBarList
                data={conversionRates.map(c => ({
                  label: c.stage,
                  count: Math.round(c.rate * 100),
                  color: c.rate > 0.8 ? "#059669" : c.rate > 0.5 ? "#0d7490" : "#d97706",
                }))}
                height={200}
                formatValue={(v) => `${v}%`}
              />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Lost Reasons" />
          <Card>
            <CardContent className="p-4">
              {(charts.lost_reasons || []).length > 0 ? (
                <MetricBarList
                  data={(charts.lost_reasons || []).map(l => ({ label: l.reason, count: l.count, color: "#dc2626" }))}
                  height={200}
                />
              ) : (
                <div className="flex items-center justify-center h-[200px] text-sm text-muted-foreground">
                  No lost deals recorded
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Stuck Opportunities */}
      {stuckAging.length > 0 && (
        <div>
          <SectionHeader title="Stuck Opportunities (Aging)" />
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Opp ID</th>
                      <th className="text-left px-4 py-2 font-medium">Stage</th>
                      <th className="text-right px-4 py-2 font-medium">Days in Stage</th>
                      <th className="text-left px-4 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stuckAging.map((s, i) => (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 font-mono text-xs">{s.opp_id}</td>
                        <td className="px-4 py-2.5 capitalize">{s.stage.replace(/_/g, " ")}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{s.days}</td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            s.days > 14
                              ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                              : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                          }`}>
                            {s.days > 14 ? "Critical" : "Stuck"}
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

      {/* Conversion Table */}
      <div>
        <SectionHeader title="Conversion Table" />
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
                    return (
                      <tr key={i} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5 capitalize">{c.stage}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{byStage[c.stage.toLowerCase().replace(/\s/g, "_")] || 0}</td>
                        <td className="px-4 py-2.5 text-right font-mono">{rate}%</td>
                        <td className="px-4 py-2.5">
                          <div className="h-2 w-full max-w-[120px] rounded-full bg-muted overflow-hidden">
                            <div
                              className={`h-full rounded-full ${rate > 80 ? "bg-green-500" : rate > 50 ? "bg-primary" : "bg-amber-500"}`}
                              style={{ width: `${rate}%` }}
                            />
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

      {/* All Opportunities */}
      <div>
        <SectionHeader title="All Opportunities" />
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Opp ID</th>
                    <th className="text-left px-4 py-2 font-medium">Product</th>
                    <th className="text-left px-4 py-2 font-medium">Stage</th>
                    <th className="text-right px-4 py-2 font-medium">Est. Value</th>
                    <th className="text-left px-4 py-2 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {opps.map((opp, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5 font-mono text-xs">{opp.opp_id}</td>
                      <td className="px-4 py-2.5">{opp.product_type}</td>
                      <td className="px-4 py-2.5 capitalize">{opp.stage.replace(/_/g, " ")}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{fmtCurrency(opp.estimated_value)}</td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">{opp.created_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function LoadingState() { return <div className="space-y-4"><div className="h-8 w-64 bg-muted rounded animate-pulse" /><div className="h-32 bg-muted rounded-lg animate-pulse" /></div>; }
function ErrorState({ message }: { message: string }) { return <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300"><AlertCircle className="h-5 w-5" />{message}</div>; }
