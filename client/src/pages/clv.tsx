import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/queryClient";
import { Phone, Award, TrendingUp, Users, AlertCircle } from "lucide-react";
import { KPICard, SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { fmtCurrency, fmtCurrencyFull, fmtPct, tierColor } from "@/lib/format";
import type { CommandCenterData, CLVClient } from "@shared/types";

const tierNames: Record<string, string> = {
  A: "Strategic Relationships",
  B: "High-Value Clients",
  C: "Core Clients",
  D: "Growth Opportunities",
};

export function CLVPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load CLV intelligence data" />;

  const clv = cc.clv_intelligence;
  const k = clv.kpis;
  const segments = clv.segments || {};
  const calls = clv.call_priorities || [];
  const clients = clv.clients || [];
  const retentionPct = Math.round((k.retention_rate ?? 0.92) * 100);

  return (
    <div className="space-y-6">
      <SectionHeader title="Client Value Intelligence" subtitle="Lifetime value analysis and client segmentation" />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard label="Total Clients" value={k.total_clients} accent="primary" />
        <KPICard label="Historical Revenue" value={fmtCurrency(k.total_historical_revenue)} accent="success" />
        <KPICard label="Est. Total CLV" value={fmtCurrency(k.estimated_total_clv)} accent="primary" />
        <KPICard label="Average CLV" value={fmtCurrency(k.average_clv)} accent="info" />
        <KPICard label="Referral Revenue" value={fmtCurrency(k.total_referral_revenue)} accent="warning" />
        <KPICard label="Retention Rate" value={fmtPct(retentionPct)} accent="success" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Client Segmentation */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" />
              Client Segmentation
            </h3>
            <div className="space-y-3">
              {(["A", "B", "C", "D"] as const).map((tier) => {
                const seg = segments[tier] ?? { count: 0, total_value: 0 };
                return (
                  <div key={tier}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-semibold ${tierColor(tier)}`}>
                        Tier {tier} — {tierNames[tier]}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        <strong>{seg.count}</strong> clients
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Total value: {fmtCurrencyFull(seg.total_value)}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Who Should I Call */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Phone className="h-4 w-4 text-primary" />
              Who Should I Call Today?
            </h3>
            <div className="space-y-2">
              {calls.length === 0 ? (
                <p className="text-sm text-muted-foreground">No call priorities.</p>
              ) : (
                calls.slice(0, 6).map((c, i) => (
                  <div key={i} className="border-b border-border pb-2 last:border-0 last:pb-0">
                    <div className="text-sm font-medium text-foreground">
                      {i + 1}. {c.display_name || c.client_name || c.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">{c.reason}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] font-bold uppercase rounded px-1.5 py-0.5 ${
                        c.priority === "high" ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
                        : c.priority === "medium" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      }`}>
                        {c.priority}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Concentration Risk */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-primary" />
              Concentration Risk
            </h3>
            <div className="space-y-2">
              <div className="text-sm">
                Revenue (top 3):{" "}
                <strong>
                  {fmtPct((clv.concentration?.revenue_concentration?.top_3_pct ?? 0) * 100)}
                </strong>
              </div>
              <div className="text-sm">
                Referrals (top 3):{" "}
                <strong>
                  {fmtPct((clv.concentration?.referral_concentration?.top_3_pct ?? 0) * 100)}
                </strong>
              </div>
              {(clv.concentration?.revenue_concentration?.top_3_pct ?? 0) > 0.3 ? (
                <div className="mt-2 inline-flex items-center rounded bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 px-2 py-0.5 text-[10px] font-bold">
                  CONCENTRATION ALERT
                </div>
              ) : (
                <div className="mt-2 inline-flex items-center rounded bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300 px-2 py-0.5 text-[10px] font-bold">
                  NO ALERT
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Client Leaderboard */}
      <div>
        <SectionHeader title="Client Value Leaderboard" />
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="text-left font-medium px-4 py-2.5">Client</th>
                    <th className="text-right font-medium px-4 py-2.5">Revenue</th>
                    <th className="text-right font-medium px-4 py-2.5">CLV</th>
                    <th className="text-right font-medium px-4 py-2.5">Score</th>
                    <th className="text-left font-medium px-4 py-2.5">Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c: CLVClient, i) => (
                    <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/50">
                      <td className="px-4 py-2.5 font-medium text-foreground">{c.name}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{fmtCurrency(c.total_revenue)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums font-semibold">{fmtCurrency(c.clv)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{Math.round(c.score)}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-bold ${tierColor(c.value_tier)}`}>
                          {c.value_tier}
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
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 bg-muted rounded animate-pulse" />
      <div className="grid grid-cols-6 gap-3">
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
