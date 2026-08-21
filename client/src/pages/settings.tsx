import { useState, useEffect } from "react";
import { Settings, Database, Bell, Users, Zap, Save, Info, Loader2, CheckCircle } from "lucide-react";
import { SectionHeader, Card, CardContent } from "@/components/ui-widgets";
import { useQuery, useMutation } from "@tanstack/react-query";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import type { CommandCenterData } from "@shared/types";
import { cn } from "@/lib/utils";

interface UserPreferences {
  revenue_goal: number;
  demo_mode: boolean;
  auto_refresh: boolean;
  refresh_interval: number;
  notifications: {
    new_leads: boolean;
    revenue_gap: boolean;
    stuck_opps: boolean;
    referral_ops: boolean;
  };
}

const DEFAULT_PREFS: UserPreferences = {
  revenue_goal: 85000,
  demo_mode: true,
  auto_refresh: true,
  refresh_interval: 60,
  notifications: {
    new_leads: true,
    revenue_gap: true,
    stuck_opps: true,
    referral_ops: true,
  },
};

export function SettingsPage() {
  const { data: cc } = useQuery<CommandCenterData>({
    queryKey: [`${API_BASE}/api/command-center`],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/command-center`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 60_000,
  });

  const { data: prefsData, isLoading: prefsLoading } = useQuery<UserPreferences>({
    queryKey: [`${API_BASE}/api/user-preferences`],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/user-preferences`);
      if (!res.ok) throw new Error(`${res.status}`);
      const d = await res.json();
      return d.status === "ok" ? d : DEFAULT_PREFS;
    },
    staleTime: 30_000,
  });

  const [settings, setSettings] = useState<UserPreferences>(DEFAULT_PREFS);
  const [saveResult, setSaveResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    if (prefsData) setSettings(prefsData);
  }, [prefsData]);

  const saveMutation = useMutation({
    mutationFn: async (payload: UserPreferences) => {
      const res = await mutationFetch("/api/user-preferences", { method: "POST", body: payload });
      return res.json();
    },
    onSuccess: (data) => {
      if (data.status === "ok") {
        setSaveResult({ ok: true, message: "Settings saved successfully" });
        setTimeout(() => setSaveResult(null), 2000);
      } else {
        setSaveResult({ ok: false, message: data.error || "Failed to save" });
      }
    },
    onError: () => {
      setSaveResult({ ok: false, message: "Network error — could not reach backend" });
    },
  });

  const summary = cc?.summary ?? {
    total_scripts: 56,
    total_endpoints: 30,
    api_ports: "8088",
    monthly_cost: "$0",
    hours_saved_weekly: "40+",
    phases_built: 12,
  };
  const agents = cc?.agents || [];

  return (
    <div className="space-y-6">
      <SectionHeader title="Settings" subtitle="Configure your Agency OS Command Center" />

      {/* System Info */}
      <div>
        <SectionHeader title="System Information" />
        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Total Scripts</div>
                <div className="font-mono font-bold">{summary.total_scripts || 56}+</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Total Endpoints</div>
                <div className="font-mono font-bold">{summary.total_endpoints || 30}+</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">API Ports</div>
                <div className="font-mono font-bold">{summary.api_ports || "8088"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Phases Built</div>
                <div className="font-mono font-bold">{summary.phases_built || 12}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Monthly Cost</div>
                <div className="font-mono font-bold">{summary.monthly_cost || "$0"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Hours Saved Weekly</div>
                <div className="font-mono font-bold">{summary.hours_saved_weekly || "40+"}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Status */}
      <div>
        <SectionHeader title="Agent Status" />
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Agent</th>
                    <th className="text-right px-4 py-2 font-medium">Phase</th>
                    <th className="text-right px-4 py-2 font-medium">Port</th>
                    <th className="text-right px-4 py-2 font-medium">Endpoints</th>
                    <th className="text-left px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5 font-medium">{agent.agent_name}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{agent.phase}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{agent.port}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{agent.endpoints}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          agent.status === "active"
                            ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                            : agent.status === "error"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                        }`}>
                          {agent.status}
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

      {/* Business Configuration */}
      <div>
        <SectionHeader title="Business Configuration" />
        <Card>
          <CardContent className="p-4 space-y-4">
            <div>
              <label className="text-sm font-medium mb-1 block">Monthly Revenue Goal</label>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">$</span>
                <input
                  type="number"
                  value={settings.revenue_goal}
                  onChange={(e) => setSettings({ ...settings, revenue_goal: Number(e.target.value) })}
                  className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Auto-Refresh Interval (seconds)</label>
              <input
                type="number"
                value={settings.refresh_interval}
                onChange={(e) => setSettings({ ...settings, refresh_interval: Number(e.target.value) })}
                className="w-32 px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Toggles */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <SectionHeader title="Data & Display" />
          <Card>
            <CardContent className="p-4 space-y-3">
              <ToggleRow
                icon={Database}
                label="Demo Mode"
                description="Use sample data when real data is unavailable"
                checked={settings.demo_mode}
                onChange={(v) => setSettings({ ...settings, demo_mode: v })}
              />
              <ToggleRow
                icon={Zap}
                label="Auto-Refresh"
                description="Automatically refresh data at the interval above"
                checked={settings.auto_refresh}
                onChange={(v) => setSettings({ ...settings, auto_refresh: v })}
              />
            </CardContent>
          </Card>
        </div>
        <div>
          <SectionHeader title="Notifications" />
          <Card>
            <CardContent className="p-4 space-y-3">
              <ToggleRow
                icon={Bell}
                label="New Leads"
                description="Alert when new leads arrive"
                checked={settings.notifications.new_leads}
                onChange={(v) => setSettings({ ...settings, notifications: { ...settings.notifications, new_leads: v } })}
              />
              <ToggleRow
                icon={Bell}
                label="Revenue Gap"
                description="Alert when revenue falls behind goal"
                checked={settings.notifications.revenue_gap}
                onChange={(v) => setSettings({ ...settings, notifications: { ...settings.notifications, revenue_gap: v } })}
              />
              <ToggleRow
                icon={Bell}
                label="Stuck Opportunities"
                description="Alert when opportunities stall"
                checked={settings.notifications.stuck_opps}
                onChange={(v) => setSettings({ ...settings, notifications: { ...settings.notifications, stuck_opps: v } })}
              />
              <ToggleRow
                icon={Bell}
                label="Referral Opportunities"
                description="Alert on new referral opportunities"
                checked={settings.notifications.referral_ops}
                onChange={(v) => setSettings({ ...settings, notifications: { ...settings.notifications, referral_ops: v } })}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Save button + status */}
      <div className="flex items-center justify-end gap-3">
        {saveResult && (
          <div className={cn(
            "flex items-center gap-2 text-sm",
            saveResult.ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
          )}>
            {saveResult.ok ? <CheckCircle className="h-4 w-4" /> : <Info className="h-4 w-4" />}
            {saveResult.message}
          </div>
        )}
        <button
          onClick={() => saveMutation.mutate(settings)}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saveMutation.isPending ? "Saving..." : "Save Settings"}
        </button>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 px-4 py-3 text-sm text-blue-700 dark:text-blue-300">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <div>
          Settings are persisted to the database and survive page refreshes. Revenue goal changes also update your dashboard KPIs. Demo mode controls whether sample data is shown when real data is unavailable.
        </div>
      </div>
    </div>
  );
}

function ToggleRow({
  icon: Icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: typeof Bell;
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-start gap-2.5">
        <Icon className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
        <div>
          <div className="text-sm font-medium">{label}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition-colors shrink-0 ${checked ? "bg-primary" : "bg-muted"}`}
      >
        <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${checked ? "translate-x-5" : ""}`} />
      </button>
    </div>
  );
}
