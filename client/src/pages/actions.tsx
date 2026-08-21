import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckSquare,
  Plus,
  Clock,
  CheckCircle2,
  XCircle,
  AlarmClock,
  AlertCircle,
  X,
  History,
  ChevronRight,
} from "lucide-react";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import { Card, CardContent, SectionHeader } from "@/components/ui-widgets";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ActionStatus =
  | "new"
  | "approved"
  | "in_progress"
  | "waiting"
  | "snoozed"
  | "done"
  | "dismissed";

type Priority = "high" | "medium" | "low";

interface ActionItem {
  id: string;
  title: string;
  description: string | null;
  priority: Priority;
  status: ActionStatus;
  action_type: string | null;
  entity_type: string | null;
  entity_name: string | null;
  due_at: string | null;
  snoozed_until: string | null;
  completed_at: string | null;
  notes: string | null;
  outcome: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

interface ActionEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  outcome: string | null;
  created_at: string;
}

interface ActionsResponse {
  actions: ActionItem[];
  counts: Record<string, number>;
  status: string;
}

interface ActionDetailResponse {
  action: ActionItem;
  events: ActionEvent[];
  status: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLUMN_CONFIG: { status: ActionStatus; label: string; color: string }[] = [
  { status: "new", label: "New", color: "border-blue-500" },
  { status: "approved", label: "Approved", color: "border-violet-500" },
  { status: "in_progress", label: "In Progress", color: "border-amber-500" },
  { status: "waiting", label: "Waiting", color: "border-cyan-500" },
];

const CLOSED_STATUSES: { status: ActionStatus; label: string; icon: typeof CheckCircle2 }[] = [
  { status: "snoozed", label: "Snoozed", icon: AlarmClock },
  { status: "done", label: "Done", icon: CheckCircle2 },
  { status: "dismissed", label: "Dismissed", icon: XCircle },
];

const STATUS_LABELS: Record<ActionStatus, string> = {
  new: "New",
  approved: "Approved",
  in_progress: "In Progress",
  waiting: "Waiting",
  snoozed: "Snoozed",
  done: "Done",
  dismissed: "Dismissed",
};

const ALL_STATUSES: ActionStatus[] = [
  "new",
  "approved",
  "in_progress",
  "waiting",
  "snoozed",
  "done",
  "dismissed",
];

const PRIORITY_COLORS: Record<Priority, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
};

const ALL_PRIORITIES: Priority[] = ["high", "medium", "low"];

// ---------------------------------------------------------------------------
// Action Card (used in board columns)
// ---------------------------------------------------------------------------

function ActionCard({
  action,
  onClick,
}: {
  action: ActionItem;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-lg border border-border bg-card p-3 transition-shadow hover:shadow-md"
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className={cn(
            "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
            PRIORITY_COLORS[action.priority]
          )}
        >
          {action.priority}
        </span>
        {action.entity_name && (
          <span className="text-[10px] text-muted-foreground truncate">
            {action.entity_name}
          </span>
        )}
      </div>
      <div className="text-sm font-medium text-foreground line-clamp-2">
        {action.title}
      </div>
      {action.description && (
        <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
          {action.description}
        </div>
      )}
      {action.due_at && (
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground mt-2">
          <Clock className="h-3 w-3" />
          {new Date(action.due_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Drawer
// ---------------------------------------------------------------------------

function ActionDetailDrawer({
  actionId,
  open,
  onClose,
}: {
  actionId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [outcome, setOutcome] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState<Priority>("medium");

  const { data: detail } = useQuery<ActionDetailResponse>({
    queryKey: ["/api/action-center", actionId],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/api/action-center/${actionId}`
      );
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!actionId && open,
    staleTime: 10_000,
  });

  const action = detail?.action;
  const events = detail?.events ?? [];

  // Sync local state when action loads
  useMemo(() => {
    if (action) {
      setNotes(action.notes || "");
      setOutcome(action.outcome || "");
    }
  }, [action?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateMutation = useMutation({
    mutationFn: async (updates: Record<string, unknown>) => {
      return mutationFetch(`/api/action-center/${actionId}`, {
        method: "PATCH",
        body: updates,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/action-center"] });
    },
  });

  const handleStatusChange = (newStatus: string) => {
    updateMutation.mutate({ status: newStatus });
  };

  const handleSaveNotes = () => {
    if (notes !== (action?.notes || "")) {
      updateMutation.mutate({ notes });
    }
    if (outcome !== (action?.outcome || "")) {
      updateMutation.mutate({ outcome });
    }
  };

  const handleCreateAction = async () => {
    if (!newTitle.trim()) return;
    await mutationFetch("/api/action-center", {
      method: "POST",
      body: {
        title: newTitle,
        priority: newPriority,
        source: "manual",
      },
    });
    setNewTitle("");
    setShowCreateForm(false);
    queryClient.invalidateQueries({ queryKey: ["/api/action-center"] });
  };

  if (!action) {
    return (
      <Sheet open={open} onOpenChange={onClose}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Loading...</SheetTitle>
          </SheetHeader>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
                PRIORITY_COLORS[action.priority]
              )}
            >
              {action.priority}
            </span>
            <Badge variant="outline" className="text-[10px]">
              {STATUS_LABELS[action.status as ActionStatus]}
            </Badge>
          </div>
          <SheetTitle className="text-base">{action.title}</SheetTitle>
        </SheetHeader>

        <div className="px-4 pb-6 space-y-4">
          {/* Description */}
          {action.description && (
            <div>
              <p className="text-sm text-muted-foreground">
                {action.description}
              </p>
            </div>
          )}

          {/* Entity */}
          {action.entity_name && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Related to:</span>
              <span className="font-medium">{action.entity_name}</span>
            </div>
          )}

          {/* Status changer */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              Status
            </label>
            <Select
              value={action.status}
              onValueChange={handleStatusChange}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ALL_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Quick action buttons */}
          <div className="flex flex-wrap gap-2">
            {action.status !== "done" && (
              <Button
                size="sm"
                variant="default"
                onClick={() => handleStatusChange("done")}
                disabled={updateMutation.isPending}
              >
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                Mark Done
              </Button>
            )}
            {action.status !== "in_progress" && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleStatusChange("in_progress")}
                disabled={updateMutation.isPending}
              >
                Start Work
              </Button>
            )}
            {action.status !== "snoozed" && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleStatusChange("snoozed")}
                disabled={updateMutation.isPending}
              >
                <AlarmClock className="h-3.5 w-3.5 mr-1" />
                Snooze
              </Button>
            )}
            {action.status !== "dismissed" && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleStatusChange("dismissed")}
                disabled={updateMutation.isPending}
              >
                <XCircle className="h-3.5 w-3.5 mr-1" />
                Dismiss
              </Button>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              Notes
            </label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes about this action..."
              className="min-h-[80px]"
            />
          </div>

          {/* Outcome */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              Outcome
            </label>
            <Textarea
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="Log the outcome when complete..."
              className="min-h-[60px]"
            />
          </div>

          {(notes !== (action.notes || "") ||
            outcome !== (action.outcome || "")) && (
            <Button
              size="sm"
              onClick={handleSaveNotes}
              disabled={updateMutation.isPending}
            >
              Save Notes & Outcome
            </Button>
          )}

          {/* Event History */}
          {events.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-2">
                <History className="h-3.5 w-3.5" />
                History
              </div>
              <div className="space-y-2">
                {events.map((e, i) => (
                  <div
                    key={e.id}
                    className="flex items-start gap-2 text-xs"
                  >
                    <div className="flex items-center justify-center w-5 h-5 rounded-full bg-muted shrink-0 mt-0.5">
                      {i === events.length - 1 ? (
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                      ) : (
                        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1">
                      <span className="font-medium">
                        {e.event_type === "created" && "Created"}
                        {e.event_type === "status_changed" &&
                          `Status: ${e.from_status || "?"} → ${e.to_status || "?"}`}
                        {e.event_type === "note_added" && "Note added"}
                        {e.event_type === "outcome_logged" && "Outcome logged"}
                      </span>
                      {e.note && (
                        <div className="text-muted-foreground">{e.note}</div>
                      )}
                      <div className="text-[10px] text-muted-foreground">
                        {new Date(e.created_at).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Create new action */}
          {showCreateForm ? (
            <div className="border-t border-border pt-4 space-y-2">
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Action title..."
                onKeyDown={(e) => e.key === "Enter" && handleCreateAction()}
              />
              <Select
                value={newPriority}
                onValueChange={(v) => setNewPriority(v as Priority)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleCreateAction}>
                  Create
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setShowCreateForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Main Actions Page
// ---------------------------------------------------------------------------

export function ActionsPage() {
  const [filter, setFilter] = useState<
    "active" | "snoozed" | "done" | "dismissed" | "all"
  >("active");
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const includeClosed =
    filter === "all" || filter === "snoozed" || filter === "done" || filter === "dismissed";
  const statusFilter =
    filter === "snoozed"
      ? "snoozed"
      : filter === "done"
      ? "done"
      : filter === "dismissed"
      ? "dismissed"
      : undefined;

  const { data } = useQuery<ActionsResponse>({
    queryKey: ["/api/action-center", { filter }],
    queryFn: async () => {
      const params = new URLSearchParams({
        include_closed: String(includeClosed),
        limit: "100",
      });
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(
        `${API_BASE}/api/action-center?${params}`
      );
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 30_000,
  });

  const actions = data?.actions ?? [];
  const counts = data?.counts ?? {};

  const openAction = (id: string) => {
    setSelectedActionId(id);
    setDrawerOpen(true);
  };

  // Group actions by status for board view
  const grouped = useMemo(() => {
    const result: Record<string, ActionItem[]> = {};
    for (const s of ALL_STATUSES) result[s] = [];
    for (const a of actions) {
      if (result[a.status]) result[a.status].push(a);
    }
    return result;
  }, [actions]);

  const openCount =
    (counts.new || 0) +
    (counts.approved || 0) +
    (counts.in_progress || 0) +
    (counts.waiting || 0);
  const inProgressCount = counts.in_progress || 0;
  const snoozedCount = counts.snoozed || 0;
  const doneCount = counts.done || 0;

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Open Actions</div>
            <div className="text-2xl font-bold text-foreground mt-1">
              {openCount}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">In Progress</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {inProgressCount}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Snoozed</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {snoozedCount}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Completed</div>
            <div className="text-2xl font-bold text-green-600 mt-1">
              {doneCount}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 border-b border-border pb-1">
        {(
          [
            { key: "active", label: "Active" },
            { key: "snoozed", label: "Snoozed" },
            { key: "done", label: "Done" },
            { key: "dismissed", label: "Dismissed" },
            { key: "all", label: "All" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-t-lg transition-colors",
              filter === tab.key
                ? "text-primary border-b-2 border-primary -mb-1"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Board (active) or List (closed/all) */}
      {filter === "active" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {COLUMN_CONFIG.map((col) => (
            <div key={col.status} className="space-y-3">
              <div
                className={cn(
                  "flex items-center justify-between border-l-4 pl-2 py-1",
                  col.color
                )}
              >
                <span className="text-sm font-semibold">{col.label}</span>
                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                  {grouped[col.status]?.length || 0}
                </span>
              </div>
              <div className="space-y-2 min-h-[100px]">
                {grouped[col.status]?.map((action) => (
                  <ActionCard
                    key={action.id}
                    action={action}
                    onClick={() => openAction(action.id)}
                  />
                ))}
                {grouped[col.status]?.length === 0 && (
                  <div className="text-xs text-muted-foreground text-center py-4 border border-dashed border-border rounded-lg">
                    No items
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {actions.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center">
                <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  No {filter === "all" ? "" : filter} actions found.
                </p>
              </CardContent>
            </Card>
          ) : (
            actions.map((action) => (
              <ActionCard
                key={action.id}
                action={action}
                onClick={() => openAction(action.id)}
              />
            ))
          )}
        </div>
      )}

      {/* Detail Drawer */}
      <ActionDetailDrawer
        actionId={selectedActionId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
