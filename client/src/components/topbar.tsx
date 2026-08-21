import { useState } from "react";
import { RefreshCw, UserPlus, UserCheck, DollarSign, Share2, FileText, MoreHorizontal } from "lucide-react";
import { pageTitleMap } from "@/lib/nav";
import { useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { openModal } from "@/components/modals";

export function Topbar() {
  const [location] = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const title = pageTitleMap[location] || "Agency OS";
  const now = new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

  const actions = [
    { label: "Add Lead", icon: UserPlus, color: "text-blue-600 dark:text-blue-400", onClick: () => openModal("add-lead") },
    { label: "Add Client", icon: UserCheck, color: "text-teal-600 dark:text-teal-400", onClick: () => openModal("add-client") },
    { label: "Log Revenue", icon: DollarSign, color: "text-green-600 dark:text-green-400", onClick: () => openModal("log-revenue") },
    { label: "Add Referral", icon: Share2, color: "text-purple-600 dark:text-purple-400", onClick: () => openModal("add-referral") },
    { label: "Add Note", icon: FileText, color: "text-amber-600 dark:text-amber-400", onClick: () => openModal("add-note") },
  ];

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-2 px-4 lg:px-6 py-3 bg-background/80 backdrop-blur-sm border-b border-border">
      <div className="flex items-center gap-3">
        {/* Spacer for mobile hamburger */}
        <div className="lg:hidden w-8" />
        <h1 className="text-lg font-semibold">{title}</h1>
        <span className="hidden sm:inline text-xs text-muted-foreground ml-2">Updated {now}</span>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="p-2 rounded-lg hover:bg-muted transition-colors"
          aria-label="Refresh"
        >
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
        </button>

        {/* Desktop action buttons */}
        <div className="hidden md:flex items-center gap-1.5">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                onClick={action.onClick}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-muted transition-colors"
              >
                <Icon className={cn("h-3.5 w-3.5", action.color)} />
                <span className="hidden lg:inline">{action.label}</span>
              </button>
            );
          })}
        </div>

        {/* Mobile: Quick Actions menu */}
        <div className="md:hidden relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-muted transition-colors"
          >
            <MoreHorizontal className="h-4 w-4" />
            <span className="text-xs">Actions</span>
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 z-50 w-48 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
                {actions.map((action) => {
                  const Icon = action.icon;
                  return (
                    <button
                      key={action.label}
                      onClick={() => { action.onClick(); setMenuOpen(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-muted transition-colors text-left"
                    >
                      <Icon className={cn("h-4 w-4", action.color)} />
                      {action.label}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
