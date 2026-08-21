// ============================================
// Agency OS — API Types (Phase 2)
// Typed interfaces for the FastAPI backend responses
// ============================================

export type AgentStatus = 'active' | 'error' | 'warning' | 'offline';

export interface AgentInfo {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: Record<string, number | string>;
}

export interface SummaryKPIs {
  revenue_mtd: number;
  revenue_forecast: number;
  pipeline_value: number;
  new_leads: number;
  conversion_rate: number;
  active_clients: number;
  client_lifetime_value: number;
  referral_opportunities: number;
  revenue_goal: number;
  goal_progress: number;
  revenue_gap: number;
}

export interface SummaryResponse {
  scan_date: string;
  kpis: SummaryKPIs;
  data_source: string;
  action_count: number;
  agents_online: number;
  status: string;
}

// Executive / Strategic Analysis
export interface ExecutiveKPIs {
  health_score: number;
  health_grade: string;
  total_priorities: number;
  total_escalations: number;
  critical_escalations: number;
  forecast_confidence: string;
  ai_activities_24h: number;
}

export interface Priority {
  priority: number;
  category: string;
  title: string;
  urgency: string;
}

export interface Escalation {
  title: string;
  severity: string;
  category: string;
  description: string;
  recommended_action?: string;
}

export interface ExecutiveData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: ExecutiveKPIs;
  briefing: {
    leads: number;
    hot_leads: number;
    open_tasks: number;
    pipeline_value: number;
  };
  priorities: Priority[];
  escalations?: Escalation[];
  health_breakdown?: Record<string, number>;
}

// Lead Scoring
export interface LeadScoringKPIs {
  total_leads: number;
  average_score: number;
  hot_leads: number;
  warm_leads: number;
  nurture_leads: number;
  cold_leads: number;
  leads_at_risk: number;
  total_pipeline_value: number;
}

export interface ScoredOpportunity {
  opp_id: string;
  contact_name: string;
  product_type: string;
  stage: string;
  estimated_value: number;
  weighted_value: number;
  expected_close: string;
  score: number;
}

export interface LeadScoringData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: LeadScoringKPIs;
  tier_distribution: Record<string, number>;
  top_10_opportunities: ScoredOpportunity[];
}

// CLV Intelligence
export interface CLVKPIs {
  total_clients: number;
  average_clv: number;
  estimated_total_clv: number;
  total_clv: number;
  total_historical_revenue: number;
  highest_value_client: string;
  total_referral_revenue: number;
  retention_rate: number;
}

export interface CLVSegment {
  count: number;
  client_count: number;
  total_value: number;
  total_clv: number;
}

export interface CallPriority {
  display_name: string;
  client_name: string;
  name: string;
  reason: string;
  reasoning: string;
  recommended_action: string;
  priority: string;
}

export interface CLVClient {
  contact_id: string;
  name: string;
  email: string;
  phone: string;
  client_since: string;
  total_revenue: number;
  transaction_count: number;
  last_activity: string;
  clv: number;
  avg_transaction: number;
  annual_rate: number;
  value_tier: string;
  score: number;
  health?: number;
}

export interface CLVData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: CLVKPIs;
  client_records_count: number;
  segments: Record<string, CLVSegment>;
  call_priorities: CallPriority[];
  clients: CLVClient[];
  leaderboard?: CLVClient[];
  quadrants?: Record<string, CLVClient[]>;
  concentration?: {
    revenue_concentration: { top_3_pct: number };
    referral_concentration: { top_3_pct: number };
  };
}

// Revenue Forecasting
export interface RevenueKPIs {
  actual_revenue: number;
  committed_revenue: number;
  weighted_pipeline: number;
  unweighted_pipeline: number;
  revenue_gap: number;
  revenue_at_risk: number;
}

export interface RevenueCategory {
  total_value: number;
  count: number;
}

export interface RevenueData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: RevenueKPIs;
  categories: Record<string, RevenueCategory>;
  forecasts: {
    end_of_month: number;
    next_month: number;
    next_quarter: number;
  };
}

// What Changed (fixed: uses movement_score/movement_grade)
export interface WhatChangedKPIs {
  movement_score: number;
  movement_grade: string;
  total_changes: number;
  positive_exceptions: number;
  negative_exceptions: number;
  improving_trends: number;
  declining_trends: number;
  missed_opportunities: number;
  ai_insights: number;
}

export interface ChangeRecord {
  category: string;
  type: string;
  severity: string;
  description: string;
  count: number;
  period: string;
}

export interface WhatChangedData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: WhatChangedKPIs;
  top_5_changes: ChangeRecord[];
  movement_score?: { score: number; grade: string };
}

// Action Queue
export interface ActionItem {
  priority: number;
  phase: number;
  agent: string;
  type: string;
  severity: string;
  title: string;
  description: string;
  contact: string;
  contact_id: string;
  action: string;
  status: string;
}

// Referral Intelligence
export interface ReferralKPIs {
  total_sources: number;
  average_score: number;
  advocates: number;
  high_potential: number;
  nurture: number;
  dormant: number;
  total_opportunities: number;
  total_gaps: number;
  active_campaigns: number;
}

export interface ReferralSource {
  source_id?: string;
  name: string;
  score: number;
  tier?: string;
  referrals_count?: number;
  conversion_rate?: number;
  revenue_influenced?: number;
  last_contact?: string;
  status?: string;
}

export interface ReferralOpportunity {
  title: string;
  source?: string;
  score?: number;
  potential_value?: number;
  description?: string;
  recommended_action?: string;
}

export interface ReferralCampaign {
  name: string;
  status: string;
  sent: number;
  opened: number;
  clicked: number;
  converted: number;
}

export interface ReferralIntelligenceData {
  agent_name: string;
  phase: number;
  port: number;
  endpoints: number;
  status: AgentStatus;
  kpis: ReferralKPIs;
  top_opportunities: ReferralOpportunity[];
  tier_distribution: Record<string, number>;
  scored_sources?: ReferralSource[];
  leaderboard?: ReferralSource[];
  rising_sources?: ReferralSource[];
  dormant_sources?: ReferralSource[];
  funnel?: Record<string, number>;
  attribution?: Record<string, number>;
  partner_opportunities?: ReferralOpportunity[];
  gaps?: Array<{ title: string; description: string; severity: string }>;
  campaigns?: ReferralCampaign[];
  briefing?: { message: string };
}

// Pipeline (from charts.raw_opportunities)
export interface RawOpportunity {
  opp_id: string;
  product_type: string;
  stage: string;
  estimated_value: number;
  created_date: string;
}

export interface FunnelStage {
  stage: string;
  label: string;
  count: number;
}

export interface ConversionRate {
  stage: string;
  rate: number;
}

export interface StuckAging {
  opp_id: string;
  stage: string;
  days: number;
}

export interface ProductMixItem {
  label: string;
  count: number;
}

// Charts
export interface ChartData {
  pipeline_funnel?: FunnelStage[];
  conversion_rates?: ConversionRate[];
  lost_reasons?: Array<{ reason: string; count: number }>;
  product_mix?: ProductMixItem[];
  stuck_aging?: StuckAging[];
  actions_by_priority?: Array<{ label: string; count: number }>;
  actions_by_agent?: Array<{ label: string; count: number }>;
  actions_by_type?: Array<{ label: string; count: number }>;
  actions_by_severity?: Array<{ label: string; count: number }>;
  crm_issue_severity?: Array<{ label: string; count: number; color: string }>;
  data_quality_gauge?: number;
  duplicates_by_confidence?: Array<{ label: string; count: number }>;
  tag_field_health?: Array<{ label: string; count: number; color: string }>;
  task_issues?: Array<{ label: string; count: number }>;
  appt_issues?: Array<{ label: string; count: number }>;
  content_by_month?: Array<{ label: string; count: number }>;
  touchpoints_by_month?: Array<{ label: string; count: number }>;
  events_by_month?: Array<{ label: string; count: number }>;
  events_by_type?: Array<{ label: string; count: number }>;
  agent_health?: Array<{ phase: number; name: string; score: number; label: string; status: string }>;
  raw_actions?: ActionItem[];
  raw_opportunities?: RawOpportunity[];
}

// Command Center (the main aggregated response)
export interface CommandCenterData {
  scan_date: string;
  agents: AgentInfo[];
  executive: ExecutiveData;
  what_changed: WhatChangedData;
  lead_scoring: LeadScoringData;
  referral_intelligence: ReferralIntelligenceData;
  revenue_forecasting: RevenueData;
  clv_intelligence: CLVData;
  pipeline: Record<string, unknown>;
  compliance: Record<string, unknown>;
  action_queue: ActionItem[];
  charts: ChartData;
  summary: {
    total_scripts: number;
    total_endpoints: number;
    api_ports: string;
    monthly_cost: string;
    hours_saved_weekly: string;
    phases_built: number;
  };
}
