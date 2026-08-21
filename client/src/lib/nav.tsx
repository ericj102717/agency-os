import { Activity } from "lucide-react";
import { CheckSquare } from "lucide-react";
import {
  Home,
  Users,
  Target,
  DollarSign,
  Megaphone,
  BarChart3,
  Settings,
  Star,
  Heart,
  GitBranch,
  TrendingUp,
  Award,
  Activity,
  AlertCircle,
  GraduationCap,
  Share2,
} from "lucide-react";

export interface NavItem {
  label: string;
  path: string;
  icon: typeof Home;
}

export interface NavGroup {
  label: string;
  icon: typeof Home;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: "Home",
    icon: Home,
    items: [
      { label: "Home", path: "/", icon: Home },
      { label: "Actions", path: "/actions", icon: CheckSquare },
    ],
  },
  {
    label: "Leads",
    icon: Target,
    items: [
      { label: "All Leads", path: "/leads", icon: Users },
      { label: "Lead Priorities", path: "/lead-scoring", icon: Star },
      { label: "Pipeline", path: "/pipeline", icon: GitBranch },
    ],
  },
  {
    label: "Customers",
    icon: Users,
    items: [
      { label: "Client Activity", path: "/client-activity", icon: Activity },
      { label: "Client Value", path: "/clv", icon: Award },
      { label: "Client Health", path: "/client-health", icon: Heart },
    ],
  },
  {
    label: "Revenue",
    icon: DollarSign,
    items: [
      { label: "Revenue Forecast", path: "/revenue-forecast", icon: TrendingUp },
    ],
  },
  {
    label: "Marketing",
    icon: Megaphone,
    items: [
      { label: "Marketing Posts", path: "/marketing-posts", icon: Megaphone },
      { label: "Referral Opportunities", path: "/referral-intel", icon: Share2 },
    ],
  },
  {
    label: "Insights",
    icon: BarChart3,
    items: [
      { label: "Strategic Analysis", path: "/executive", icon: Activity },
      { label: "What Changed?", path: "/what-changed", icon: AlertCircle },
    ],
  },
  {
    label: "Learning",
    icon: GraduationCap,
    items: [{ label: "Training Mode", path: "/training", icon: GraduationCap }],
  },
  {
    label: "Settings",
    icon: Settings,
    items: [{ label: "Settings", path: "/settings", icon: Settings }],
  },
];

// Flat map for title lookup
export const pageTitleMap: Record<string, string> = {
  "/": "Home",
  "/actions": "Action Center",
  "/client-activity": "Client Activity",
  "/leads": "All Leads",
  "/lead-scoring": "Lead Priorities",
  "/pipeline": "Pipeline",
  "/clv": "Client Value",
  "/client-health": "Client Health",
  "/revenue-forecast": "Revenue Forecast",
  "/referral-intel": "Referral Opportunities",
  "/marketing-posts": "Marketing Posts",
  "/executive": "Strategic Analysis",
  "/what-changed": "What Changed?",
  "/settings": "Settings",
  "/training": "Training Mode",
};
