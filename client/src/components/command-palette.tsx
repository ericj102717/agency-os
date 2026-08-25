import { useState, useEffect, useRef, useMemo } from "react";
import { useLocation } from "wouter";
import {
  Search,
  Home,
  CheckSquare,
  Users,
  Target,
  TrendingUp,
  BarChart3,
  GitBranch,
  AlertTriangle,
  Briefcase,
  Megaphone,
  GraduationCap,
  Settings,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface CommandItem {
  label: string;
  path: string;
  icon: typeof Home;
  group: string;
  keywords: string[];
}

const COMMANDS: CommandItem[] = [
  { label: "Home Dashboard", path: "/", icon: Home, group: "Home", keywords: ["home", "dashboard", "overview"] },
  { label: "Action Center", path: "/actions", icon: CheckSquare, group: "Home", keywords: ["actions", "tasks", "queue", "todo"] },
  { label: "All Leads", path: "/leads", icon: Target, group: "Leads", keywords: ["leads", "contacts", "prospects"] },
  { label: "Lead Scoring", path: "/lead-scoring", icon: Target, group: "Leads", keywords: ["scoring", "lead score", "prioritize"] },
  { label: "Pipeline", path: "/pipeline", icon: GitBranch, group: "Leads", keywords: ["pipeline", "deals", "opportunities"] },
  { label: "Client Health", path: "/client-health", icon: Users, group: "Customers", keywords: ["clients", "health", "customers"] },
  { label: "Client Activity", path: "/client-activity", icon: Briefcase, group: "Customers", keywords: ["activity", "timeline", "client activity"] },
  { label: "CLV Intelligence", path: "/clv", icon: Users, group: "Customers", keywords: ["clv", "lifetime value", "client value"] },
  { label: "Revenue Forecast", path: "/revenue-forecast", icon: TrendingUp, group: "Revenue", keywords: ["revenue", "forecast", "projections"] },
  { label: "Strategic Analysis", path: "/executive", icon: BarChart3, group: "Insights", keywords: ["executive", "strategy", "analysis"] },
  { label: "What Changed", path: "/what-changed", icon: AlertTriangle, group: "Insights", keywords: ["changes", "what changed", "diff"] },
  { label: "Referral Opportunities", path: "/referral-intel", icon: Users, group: "Insights", keywords: ["referral", "opportunities", "introductions"] },
  { label: "Marketing Posts", path: "/marketing-posts", icon: Megaphone, group: "Marketing", keywords: ["marketing", "posts", "social"] },
  { label: "Training Mode", path: "/training", icon: GraduationCap, group: "Learning", keywords: ["training", "learn", "courses"] },
  { label: "Settings", path: "/settings", icon: Settings, group: "Settings", keywords: ["settings", "config", "preferences"] },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const [, navigate] = useLocation();

  // Keyboard shortcut: Cmd/Ctrl + K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const filtered = useMemo(() => {
    if (!query) return COMMANDS;
    const q = query.toLowerCase();
    return COMMANDS.filter(c =>
      c.label.toLowerCase().includes(q) ||
      c.keywords.some(k => k.includes(q))
    );
  }, [query]);

  const execute = (item: CommandItem) => {
    navigate(item.path);
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selectedIndex]) execute(filtered[selectedIndex]);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 px-3 py-2 rounded-lg bg-background border border-border shadow-lg text-sm text-muted-foreground hover:bg-muted transition-colors"
        title="Search (Cmd+K)"
      >
        <Search className="h-4 w-4" />
        <span className="hidden sm:inline">Search</span>
        <kbd className="hidden sm:inline px-1.5 py-0.5 text-xs rounded border border-border bg-muted">⌘K</kbd>
      </button>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg mx-4 rounded-xl bg-background border border-border shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Search pages, leads, clients, actions..."
            className="border-0 px-0 focus-visible:ring-0"
          />
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No results for "{query}"
            </div>
          )}
          {filtered.map((item, i) => (
            <button
              key={item.path}
              onClick={() => execute(item)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                i === selectedIndex ? "bg-accent text-accent-foreground" : "hover:bg-muted"
              )}
            >
              <item.icon className="h-4 w-4 text-muted-foreground" />
              <span className="flex-1 text-left">{item.label}</span>
              <span className="text-xs text-muted-foreground">{item.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
