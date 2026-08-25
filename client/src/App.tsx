import { Switch, Route, Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/lib/theme";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { ActionModals } from "@/components/modals";
import { WriteKeyGate } from "@/components/write-key-gate";
import { CommandPalette } from "@/components/command-palette";
import { useAuth } from "@/lib/use-auth";
import { LoginPage } from "@/pages/login";
import { HomePage } from "@/pages/home";
import { LeadScoringPage } from "@/pages/lead-scoring";
import { CLVPage } from "@/pages/clv";
import { RevenueForecastPage } from "@/pages/revenue-forecast";
import { StrategicAnalysisPage } from "@/pages/strategic-analysis";
import { WhatChangedPage } from "@/pages/what-changed";
import { AllLeadsPage } from "@/pages/all-leads";
import { PipelinePage } from "@/pages/pipeline";
import { ClientHealthPage } from "@/pages/client-health";
import { ReferralOpportunitiesPage } from "@/pages/referral-opportunities";
import { MarketingPostsPage } from "@/pages/marketing-posts";
import { SettingsPage } from "@/pages/settings";
import { TrainingPage } from "@/pages/training";
import { ActionsPage } from "@/pages/actions";
import { ClientActivityPage } from "@/pages/client-activity";
import NotFound from "@/pages/not-found";

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
      <ActionModals />
      <WriteKeyGate />
      <CommandPalette />
    </div>
  );
}

function AppRouter() {
  const { user, loading, isAuthEnabled } = useAuth();

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  // Auth gate — if auth is enabled and user is not signed in, show login
  if (isAuthEnabled && !user) {
    return <LoginPage />;
  }

  return (
    <AppLayout>
      <Switch>
        <Route path="/" component={HomePage} />
        <Route path="/actions" component={ActionsPage} />
        <Route path="/client-activity" component={ClientActivityPage} />
        <Route path="/lead-scoring" component={LeadScoringPage} />
        <Route path="/clv" component={CLVPage} />
        <Route path="/revenue-forecast" component={RevenueForecastPage} />
        <Route path="/executive" component={StrategicAnalysisPage} />
        <Route path="/what-changed" component={WhatChangedPage} />
        <Route path="/leads" component={AllLeadsPage} />
        <Route path="/pipeline" component={PipelinePage} />
        <Route path="/client-health" component={ClientHealthPage} />
        <Route path="/referral-intel" component={ReferralOpportunitiesPage} />
        <Route path="/marketing-posts" component={MarketingPostsPage} />
        <Route path="/settings" component={SettingsPage} />
        <Route path="/training" component={TrainingPage} />
        <Route component={NotFound} />
      </Switch>
    </AppLayout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <Toaster />
          <Router hook={useHashLocation}>
            <AppRouter />
          </Router>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
