import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { AlertTriangle, TrendingUp, Users, Target, GitBranch, ArrowRight, CheckSquare } from "lucide-react";
import { useSummary, useCommandCenter, API_BASE } from "@/lib/queryClient";
import { KPICard, SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { fmtCurrency, fmtPct } from "@/lib/format";
import type { SummaryResponse, CommandCenterData } from "@shared/types";

export function HomePage() {
  const { data: summary } = useQuery<SummaryResponse>({
    queryKey: ["/api/summary"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/summary`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 60_000,
  });

  const { data: cc } = useQuery<CommandCenterData>({
    queryKey: ["/api/command-center"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/command-center`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 60_000,
  });

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const k = summary?.kpis;
  const isDemo = summary?.data_source === "demo";

  const revenueMtd = k?.revenue_mtd ?? 0;
  const revenueGoal = k?.revenue_goal ?? 85000;
  const revenuePct = revenueGoal > 0 ? Math.round((revenueMtd / revenueGoal) * 100) : 0;

  const focusCards: { icon: typeof TrendingUp; title: string; desc: string; link: string; urgency: "high" | "medium" | "low" }[] = [];

  if (revenuePct < 50) {
    focusCards.push({
      icon: TrendingUp,
      title: "Revenue needs attention",
      desc: `You're at ${revenuePct}% of your monthly goal. Focus on closing pipeline opportunities.`,
      link: "/pipeline",
      urgency: "high",
    });
  }
  if ((k?.new_leads ?? 0) > 0) {
    focusCards.push({
      icon: Target,
      title: `${k!.new_leads} new lead${k!.new_leads > 1 ? "s" : ""} to contact`,
      desc: "Contact new leads within 24 hours to maximize conversion rates.",
      link: "/leads",
      urgency: "medium",
    });
  }
  if ((k?.referral_opportunities ?? 0) > 0) {
    focusCards.push({
      icon: Users,
      title: `${k!.referral_opportunities} referral opportunities`,
      desc: "Existing clients can introduce you to new business. Reach out this week.",
      link: "/referral-intel",
      urgency: "medium",
    });
  }
  if (focusCards.length === 0) {
    focusCards.push({
      icon: AlertTriangle,
      title: "Check your business scorecard",
      desc: "Review your business health across key categories.",
      link: "/executive",
      urgency: "low",
    });
  }

  const urgencyStyles = {
    high: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
    medium: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
    low: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  };

  const actions = cc?.action_queue ?? [];

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <div>
        <h2 className="text-xl font-semibold text-foreground">{greeting}. Here's what matters today.</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Recommendations are draft suggestions until you approve them. {isDemo ? "Showing demo data." : ""}
        </p>
      </div>

      {isDemo && (
        <div className="flex items-center gap-2 rounded-lg bg-yellow-50 dark:bg-yellow-950/50 px-4 py-3 text-sm text-yellow-800 dark:text-yellow-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Not enough data yet. Using demo data. Import your contacts and revenue to get personalized recommendations.
        </div>
      )}

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Revenue (This Month)"
          value={fmtCurrency(revenueMtd)}
          sub={`${revenuePct}% of ${fmtCurrency(revenueGoal)} goal`}
          accent="primary"
        />
        <KPICard
          label="Pipeline Value"
          value={fmtCurrency(k?.pipeline_value)}
          sub="Open opportunities"
          accent="info"
        />
        <KPICard
          label="New Leads"
          value={k?.new_leads ?? 0}
          sub="Awaiting follow-up"
          accent="warning"
        />
        <KPICard
          label="Active Clients"
          value={k?.active_clients ?? 0}
          sub="Currently served"
          accent="success"
        />
      </div>

      {/* Today's Focus + Action Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <SectionHeader title="Today's Focus" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {focusCards.slice(0, 4).map((card, i) => (
              <Link key={i} href={card.link}>
                <Card className="cursor-pointer transition-shadow hover:shadow-md">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-bold uppercase ${urgencyStyles[card.urgency]}`}>
                        {card.urgency}
                      </span>
                    </div>
                    <div className="flex items-start gap-2">
                      <card.icon className="h-5 w-5 shrink-0 text-muted-foreground mt-0.5" />
                      <div>
                        <div className="text-sm font-semibold text-foreground">{card.title}</div>
                        <div className="text-xs text-muted-foreground mt-1">{card.desc}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-primary mt-3 font-medium">
                      Take Action <ArrowRight className="h-3 w-3" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        <div>
          <SectionHeader title="Action Queue" />
          <Card>
            <CardContent className="p-4 space-y-3">
              <Link href="/actions" className="block">
                <div className="flex items-center justify-between text-sm text-primary font-medium mb-2">
                  <span className="flex items-center gap-1.5">
                    <CheckSquare className="h-4 w-4" />
                    Open Action Center
                  </span>
                  <ArrowRight className="h-3 w-3" />
                </div>
              </Link>
              {actions.length === 0 ? (
                <p className="text-sm text-muted-foreground">No actions pending.</p>
              ) : (
                actions.slice(0, 5).map((action, i) => (
                  <div key={i} className="border-b border-border pb-3 last:border-0 last:pb-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                        action.severity === "high" ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
                        : action.severity === "warning" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      }`}>
                        {action.severity}
                      </span>
                      <span className="text-xs text-muted-foreground">P{action.priority}</span>
                    </div>
                    <div className="text-sm font-medium text-foreground">{action.title}</div>
                    <div className="text-xs text-muted-foreground mt-1">{action.description}</div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Quick Access */}
      <div>
        <SectionHeader title="Quick Access" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Pipeline", link: "/pipeline", icon: GitBranch },
            { label: "Lead Priorities", link: "/lead-scoring", icon: Target },
            { label: "Client Value", link: "/clv", icon: Users },
            { label: "Revenue Forecast", link: "/revenue-forecast", icon: TrendingUp },
            { label: "Strategic Analysis", link: "/executive", icon: AlertTriangle },
            { label: "What Changed?", link: "/what-changed", icon: AlertTriangle },
          ].map((tile) => (
            <Link key={tile.label} href={tile.link}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <CardContent className="p-4 flex flex-col items-center gap-2 text-center">
                  <tile.icon className="h-6 w-6 text-primary" />
                  <span className="text-xs font-medium text-foreground">{tile.label}</span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
