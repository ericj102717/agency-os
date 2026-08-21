import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/queryClient";
import { TrendingUp, AlertCircle, Calendar, Target } from "lucide-react";
import { KPICard, SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { fmtCurrency, fmtCurrencyFull } from "@/lib/format";
import type { CommandCenterData } from "@shared/types";

export function RevenueForecastPage() {
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
  if (error || !cc) return <ErrorState message="Failed to load revenue forecast data" />;

  const rf = cc.revenue_forecasting;
  const k = rf.kpis;
  const cats = rf.categories;
  const forecasts = rf.forecasts;

  const catLabels: Record<string, string> = {
    actual: "Actual Revenue",
    committed: "Committed",
    weighted_pipeline: "Weighted Pipeline",
    unweighted_pipeline: "Unweighted Pipeline",
  };

  const catColors: Record<string, string> = {
    actual: "bg-green-500",
    committed: "bg-blue-500",
    weighted_pipeline: "bg-yellow-500",
    unweighted_pipeline: "bg-orange-500",
  };

  const totalCat = Object.values(cats).reduce((sum, c) => sum + (c.total_value ?? 0), 0);

  return (
    <div className="space-y-6">
      <SectionHeader title="Revenue Forecast" subtitle="Pipeline projections and gap analysis" />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard label="Actual Revenue" value={fmtCurrency(k.actual_revenue)} accent="success" />
        <KPICard label="Committed" value={fmtCurrency(k.committed_revenue)} accent="info" />
        <KPICard label="Weighted Pipeline" value={fmtCurrency(k.weighted_pipeline)} accent="warning" />
        <KPICard label="Unweighted Pipeline" value={fmtCurrency(k.unweighted_pipeline)} accent="warning" />
        <KPICard label="Revenue at Risk" value={fmtCurrency(k.revenue_at_risk)} accent="error" />
        <KPICard label="Revenue Gap" value={fmtCurrency(k.revenue_gap)} accent="error" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Revenue Categories Bar Chart */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              Revenue Categories
            </h3>
            <div className="space-y-4">
              {Object.entries(cats).map(([key, val]) => {
                const pct = totalCat > 0 ? (val.total_value / totalCat) * 100 : 0;
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">{catLabels[key] ?? key}</span>
                      <span className="text-sm text-muted-foreground">
                        {fmtCurrencyFull(val.total_value)} ({val.count} deals)
                      </span>
                    </div>
                    <div className="h-3 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${catColors[key] ?? "bg-primary"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Forecast Projections */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <Calendar className="h-4 w-4 text-primary" />
              Forecast Projections
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3">
                <span className="text-sm font-medium">End of Month</span>
                <span className="text-lg font-bold tabular-nums text-foreground">
                  {fmtCurrencyFull(forecasts.end_of_month)}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3">
                <span className="text-sm font-medium">Next Month</span>
                <span className="text-lg font-bold tabular-nums text-foreground">
                  {fmtCurrencyFull(forecasts.next_month)}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3">
                <span className="text-sm font-medium">Next Quarter</span>
                <span className="text-lg font-bold tabular-nums text-foreground">
                  {fmtCurrencyFull(forecasts.next_quarter)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Gap Analysis */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            Revenue Gap Analysis
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">Monthly Goal</div>
              <div className="text-xl font-bold tabular-nums">$85,000</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">Current + Pipeline</div>
              <div className="text-xl font-bold tabular-nums text-green-600 dark:text-green-400">
                {fmtCurrencyFull(k.actual_revenue + k.weighted_pipeline)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">Gap to Goal</div>
              <div className="text-xl font-bold tabular-nums text-red-600 dark:text-red-400">
                {fmtCurrencyFull(k.revenue_gap)}
              </div>
            </div>
          </div>
          {k.revenue_gap > 0 && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-yellow-50 dark:bg-yellow-950/50 px-4 py-3 text-sm text-yellow-800 dark:text-yellow-200">
              <AlertCircle className="h-4 w-4 shrink-0" />
              Focus on closing in-progress deals first. The weighted pipeline covers{" "}
              {Math.round((k.weighted_pipeline / k.revenue_gap) * 100)}% of the gap.
            </div>
          )}
        </CardContent>
      </Card>
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
