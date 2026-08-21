import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Phone,
  MessageSquare,
  Mail,
  FileText,
  Calendar,
  Clock,
  MapPin,
  Plus,
  PhoneCall,
  PhoneIncoming,
  PhoneMissed,
  ArrowRight,
  CheckCircle2,
  X,
  User,
  CalendarDays,
  RefreshCw,
  Trash2,
  Link2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import { Card, CardContent } from "@/components/ui-widgets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
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

type Channel = "call" | "text" | "email" | "note";
type Direction = "inbound" | "outbound" | "internal";
type EventType = "appointment" | "follow_up" | "estimate" | "call" | "meeting" | "other";

interface Communication {
  id: string;
  contact_id: string | null;
  contact_name: string | null;
  channel: Channel;
  direction: Direction;
  subject: string | null;
  body: string | null;
  summary: string | null;
  status: string;
  occurred_at: string;
  duration_seconds: number | null;
}

interface CalendarEvent {
  id: string;
  contact_id: string | null;
  contact_name: string | null;
  title: string;
  description: string | null;
  location: string | null;
  event_type: EventType;
  status: string;
  start_at: string;
  end_at: string | null;
  all_day: number;
}

interface TimelineItem {
  id: string;
  timeline_type: "communication" | "calendar";
  contact_name: string | null;
  subject?: string | null;
  title?: string | null;
  body?: string | null;
  description?: string | null;
  channel?: Channel;
  event_type?: EventType;
  direction?: Direction;
  status: string;
  occurred_at?: string;
  start_at?: string;
  location?: string | null;
  sort_date: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHANNEL_CONFIG: Record<Channel, { icon: typeof Phone; color: string; label: string }> = {
  call: { icon: PhoneCall, color: "text-blue-600 bg-blue-100 dark:bg-blue-950 dark:text-blue-300", label: "Call" },
  text: { icon: MessageSquare, color: "text-green-600 bg-green-100 dark:bg-green-950 dark:text-green-300", label: "Text" },
  email: { icon: Mail, color: "text-purple-600 bg-purple-100 dark:bg-purple-950 dark:text-purple-300", label: "Email" },
  note: { icon: FileText, color: "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-300", label: "Note" },
};

const DIRECTION_ICON: Record<Direction, typeof Phone> = {
  inbound: PhoneIncoming,
  outbound: PhoneCall,
  internal: FileText,
};

const EVENT_TYPE_CONFIG: Record<EventType, { icon: typeof Calendar; color: string; label: string }> = {
  appointment: { icon: Calendar, color: "text-violet-600 bg-violet-100 dark:bg-violet-950 dark:text-violet-300", label: "Appointment" },
  follow_up: { icon: Phone, color: "text-amber-600 bg-amber-100 dark:bg-amber-950 dark:text-amber-300", label: "Follow-up" },
  estimate: { icon: FileText, color: "text-cyan-600 bg-cyan-100 dark:bg-cyan-950 dark:text-cyan-300", label: "Estimate" },
  call: { icon: PhoneCall, color: "text-blue-600 bg-blue-100 dark:bg-blue-950 dark:text-blue-300", label: "Call" },
  meeting: { icon: User, color: "text-pink-600 bg-pink-100 dark:bg-pink-950 dark:text-pink-300", label: "Meeting" },
  other: { icon: CalendarDays, color: "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-300", label: "Other" },
};

const ALL_CHANNELS: Channel[] = ["call", "text", "email", "note"];
const ALL_EVENT_TYPES: EventType[] = ["appointment", "follow_up", "estimate", "call", "meeting"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return sec > 0 ? `${min}m ${sec}s` : `${min}m`;
}

function isUpcoming(iso: string): boolean {
  return new Date(iso) > new Date();
}

// ---------------------------------------------------------------------------
// Log Communication Modal
// ---------------------------------------------------------------------------

function LogCommForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState<Channel>("call");
  const [direction, setDirection] = useState<Direction>("outbound");
  const [contactName, setContactName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [duration, setDuration] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      return mutationFetch("/api/communications", {
        method: "POST",
        body: {
          channel,
          direction,
          contact_name: contactName || undefined,
          subject: subject || undefined,
          body: body || undefined,
          duration_seconds: duration ? parseInt(duration) : undefined,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/communications"] });
      queryClient.invalidateQueries({ queryKey: ["/api/client-activity/timeline"] });
      onClose();
    },
  });

  return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Log Communication</SheetTitle>
        </SheetHeader>
        <div className="px-4 pb-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Channel</label>
              <Select value={channel} onValueChange={(v) => setChannel(v as Channel)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ALL_CHANNELS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {CHANNEL_CONFIG[c].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Direction</label>
              <Select value={direction} onValueChange={(v) => setDirection(v as Direction)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="inbound">Inbound</SelectItem>
                  <SelectItem value="outbound">Outbound</SelectItem>
                  <SelectItem value="internal">Internal</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Contact Name</label>
            <Input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="e.g., John Smith" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Subject</label>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Brief subject line" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Details</label>
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="What was discussed?" className="min-h-[100px]" />
          </div>
          {channel === "call" && (
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Duration (seconds)</label>
              <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="300" />
            </div>
          )}
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !body.trim()}>
            {mutation.isPending ? "Saving..." : "Log Communication"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Schedule Event Modal
// ---------------------------------------------------------------------------

function ScheduleEventForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [contactName, setContactName] = useState("");
  const [eventType, setEventType] = useState<EventType>("appointment");
  const [startAt, setStartAt] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      return mutationFetch("/api/calendar/events", {
        method: "POST",
        body: {
          title,
          contact_name: contactName || undefined,
          event_type: eventType,
          start_at: new Date(startAt).toISOString(),
          location: location || undefined,
          description: description || undefined,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/calendar/events"] });
      queryClient.invalidateQueries({ queryKey: ["/api/client-activity/timeline"] });
      onClose();
    },
  });

  return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Schedule Event</SheetTitle>
        </SheetHeader>
        <div className="px-4 pb-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g., Roof estimate - John Smith" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Type</label>
              <Select value={eventType} onValueChange={(v) => setEventType(v as EventType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ALL_EVENT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{EVENT_TYPE_CONFIG[t].label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">When</label>
              <Input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Contact Name</label>
            <Input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="e.g., John Smith" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Location</label>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g., 123 Main St, Aurora, CO" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Description</label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Event details..." className="min-h-[80px]" />
          </div>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !title.trim() || !startAt}>
            {mutation.isPending ? "Saving..." : "Schedule Event"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Timeline Item
// ---------------------------------------------------------------------------

function TimelineRow({ item }: { item: TimelineItem }) {
  const isComm = item.timeline_type === "communication";
  const iconConfig = isComm
    ? CHANNEL_CONFIG[item.channel || "note"]
    : EVENT_TYPE_CONFIG[item.event_type || "appointment"];
  const Icon = iconConfig.icon;
  const dateStr = isComm ? item.occurred_at : item.start_at;
  const title = isComm ? item.subject || "Communication logged" : item.title || "Event";
  const body = isComm ? item.body : item.description;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className={cn("flex items-center justify-center w-9 h-9 rounded-full shrink-0", iconConfig.color)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">{title}</span>
          {!isComm && isUpcoming(item.start_at || "") && (
            <Badge variant="outline" className="text-[9px] py-0 px-1 shrink-0">Upcoming</Badge>
          )}
        </div>
        {item.contact_name && (
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <User className="h-3 w-3" />
            {item.contact_name}
          </div>
        )}
        {body && (
          <div className="text-xs text-muted-foreground mt-1 line-clamp-3 sm:line-clamp-2">{body}</div>
        )}
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-1">
          <span className="flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" />
            {fmtDateTime(dateStr || item.sort_date)}
          </span>
          {item.location && (
            <span className="flex items-center gap-0.5 truncate">
              <MapPin className="h-2.5 w-2.5 shrink-0" />
              <span className="truncate">{item.location}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Communication Row
// ---------------------------------------------------------------------------

function CommRow({ comm }: { comm: Communication }) {
  const cfg = CHANNEL_CONFIG[comm.channel];
  const Icon = cfg.icon;
  const DirIcon = DIRECTION_ICON[comm.direction];

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className={cn("flex items-center justify-center w-9 h-9 rounded-full shrink-0", cfg.color)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">{comm.subject || cfg.label}</span>
          <DirIcon className="h-3 w-3 text-muted-foreground shrink-0" />
        </div>
        {comm.contact_name && (
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <User className="h-3 w-3" />
            {comm.contact_name}
          </div>
        )}
        {comm.body && (
          <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{comm.body}</div>
        )}
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-1">
          <span className="flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" />
            {fmtDateTime(comm.occurred_at)}
          </span>
          {comm.duration_seconds && <span>{fmtDuration(comm.duration_seconds)}</span>}
          {comm.status === "follow_up_needed" && (
            <Badge variant="outline" className="text-[9px] py-0 px-1 text-amber-600 border-amber-300">Follow-up</Badge>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Calendar Event Row
// ---------------------------------------------------------------------------

function EventRow({ event }: { event: CalendarEvent }) {
  const cfg = EVENT_TYPE_CONFIG[event.event_type];
  const Icon = cfg.icon;
  const upcoming = isUpcoming(event.start_at);

  return (
    <Card className={cn("transition-shadow hover:shadow-md", upcoming && "border-l-4 border-l-primary")}>
      <CardContent className="p-3">
        <div className="flex items-start gap-3">
          <div className={cn("flex items-center justify-center w-9 h-9 rounded-full shrink-0", cfg.color)}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-sm font-medium text-foreground">{event.title}</span>
              {upcoming && <Badge variant="outline" className="text-[9px] py-0 px-1">Upcoming</Badge>}
            </div>
            {event.contact_name && (
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <User className="h-3 w-3" />
                {event.contact_name}
              </div>
            )}
            {event.description && (
              <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{event.description}</div>
            )}
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-1">
              <span className="flex items-center gap-0.5">
                <Clock className="h-2.5 w-2.5" />
                {fmtDateTime(event.start_at)}
              </span>
              {event.location && (
                <span className="flex items-center gap-0.5">
                  <MapPin className="h-2.5 w-2.5" />
                  {event.location}
                </span>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Provider Connection Card
// ---------------------------------------------------------------------------

interface ProviderStatus {
  configured: boolean;
  connected: boolean;
  email: string;
  connected_at: string;
  last_synced_at: string;
}

function ProviderCard({
  provider,
  label,
  icon: Icon,
  color,
  status,
  onConnect,
  onDisconnect,
  onSync,
  syncing,
}: {
  provider: string;
  label: string;
  icon: typeof Calendar;
  color: string;
  status: ProviderStatus;
  onConnect: () => void;
  onDisconnect: () => void;
  onSync: () => void;
  syncing: boolean;
}) {
  if (!status.configured) {
    return (
      <Card>
        <CardContent className="p-4 sm:p-5">
          <div className="flex items-center gap-3">
            <div className={cn("flex items-center justify-center w-10 h-10 sm:w-11 sm:h-11 rounded-lg shrink-0", color)}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-foreground">{label}</h3>
                <Badge variant="outline" className="text-[9px] text-muted-foreground shrink-0">Not configured</Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                OAuth credentials not set. Configure in server settings to enable calendar sync.
              </p>
            </div>
            <Button size="sm" disabled className="opacity-50 cursor-not-allowed shrink-0">
              <Link2 className="h-3.5 w-3.5 mr-1.5" />
              Connect
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!status.connected) {
    return (
      <Card>
        <CardContent className="p-4 sm:p-5">
          <div className="flex items-center gap-3">
            <div className={cn("flex items-center justify-center w-10 h-10 sm:w-11 sm:h-11 rounded-lg shrink-0", color)}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-foreground">{label}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Not connected</p>
            </div>
            <Button size="sm" onClick={onConnect} className="shrink-0">
              <Link2 className="h-3.5 w-3.5 mr-1.5" />
              Connect
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-center gap-3">
          <div className={cn("flex items-center justify-center w-10 h-10 sm:w-11 sm:h-11 rounded-lg shrink-0", color)}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">{label}</h3>
              <Badge variant="outline" className="text-[9px] text-green-600 border-green-300">Connected</Badge>
            </div>
            {status.email && (
              <p className="text-xs text-muted-foreground mt-0.5 truncate">{status.email}</p>
            )}
            {status.last_synced_at && (
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Last synced {fmtDateTime(status.last_synced_at)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <Button
              size="sm"
              variant="secondary"
              onClick={onSync}
              disabled={syncing}
            >
              {syncing ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              )}
              Sync
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onDisconnect}
              className="text-muted-foreground hover:text-red-600"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function ClientActivityPage() {
  const [tab, setTab] = useState<"timeline" | "communications" | "calendar" | "connect">("timeline");
  const [commFilter, setCommFilter] = useState<Channel | "all">("all");
  const [showLogForm, setShowLogForm] = useState(false);
  const [showEventForm, setShowEventForm] = useState(false);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);
  const [oauthMessage, setOauthMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const queryClient = useQueryClient();

  const { data: timelineData } = useQuery<{ timeline: TimelineItem[]; count: number }>({
    queryKey: ["/api/client-activity/timeline"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/client-activity/timeline?limit=50`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 30_000,
  });

  const { data: commData } = useQuery<{ communications: Communication[]; count: number }>({
    queryKey: ["/api/communications", commFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (commFilter !== "all") params.set("channel", commFilter);
      const res = await fetch(`${API_BASE}/api/communications?${params}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 30_000,
  });

  const { data: calData } = useQuery<{ events: CalendarEvent[]; count: number }>({
    queryKey: ["/api/calendar/events"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/calendar/events?limit=50`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 30_000,
  });

  const { data: connData, refetch: refetchConnections } = useQuery<{ connections: { google: ProviderStatus; outlook: ProviderStatus } }>({
    queryKey: ["/api/calendar/connections"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/calendar/connections`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 10_000,
  });

  const timeline = timelineData?.timeline ?? [];
  const communications = commData?.communications ?? [];
  const events = calData?.events ?? [];
  const connections = connData?.connections;

  const upcomingEvents = useMemo(() => events.filter(e => isUpcoming(e.start_at)), [events]);
  const followUpComms = communications.filter(c => c.status === "follow_up_needed");

  // Check URL for OAuth callback params
  useMemo(() => {
    const hash = window.location.hash;
    const params = new URLSearchParams(hash.split("?")[1] || "");
    if (params.get("oauth_success")) {
      setOauthMessage({ type: "success", text: `${params.get("oauth_success")} calendar connected successfully` });
      setTab("connect");
      refetchConnections();
      // Clean URL
      window.history.replaceState(null, "", "#/client-activity");
    } else if (params.get("oauth_error")) {
      setOauthMessage({ type: "error", text: `Failed to connect ${params.get("provider") || "calendar"}: ${params.get("oauth_error")}` });
      setTab("connect");
      window.history.replaceState(null, "", "#/client-activity");
    }
  }, [refetchConnections]);

  const handleConnect = async (provider: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/calendar/oauth/${provider}/start`);
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (e) {
      setOauthMessage({ type: "error", text: `Failed to start ${provider} OAuth: ${e}` });
    }
  };

  const handleDisconnect = async (provider: string) => {
    try {
      await mutationFetch(`/api/calendar/connections/${provider}`, { method: "DELETE" });
      refetchConnections();
      setOauthMessage({ type: "success", text: `${provider} calendar disconnected` });
    } catch (e) {
      setOauthMessage({ type: "error", text: `Failed to disconnect: ${e}` });
    }
  };

  const handleSync = async (provider: string) => {
    setSyncingProvider(provider);
    try {
      await mutationFetch(`/api/calendar/sync/${provider}`, { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["/api/calendar/events"] });
      queryClient.invalidateQueries({ queryKey: ["/api/client-activity/timeline"] });
      refetchConnections();
      setOauthMessage({ type: "success", text: `${provider} calendar synced` });
    } catch (e) {
      setOauthMessage({ type: "error", text: `Sync failed: ${e}` });
    } finally {
      setSyncingProvider(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Total Communications</div>
            <div className="text-2xl font-bold text-foreground mt-1">{communications.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Follow-ups Needed</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">{followUpComms.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Upcoming Events</div>
            <div className="text-2xl font-bold text-violet-600 mt-1">{upcomingEvents.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Timeline Items</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">{timeline.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={() => setShowLogForm(true)}>
          <Phone className="h-3.5 w-3.5 mr-1.5" />
          Log Communication
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setShowEventForm(true)}>
          <Calendar className="h-3.5 w-3.5 mr-1.5" />
          Schedule Event
        </Button>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-border pb-1 overflow-x-auto scrollbar-thin w-full" style={{ scrollbarWidth: 'thin', WebkitOverflowScrolling: 'touch' }}>
        {([
          { key: "timeline", label: "Timeline", short: "Feed" },
          { key: "communications", label: "Communications", short: "Comms" },
          { key: "calendar", label: "Calendar", short: "Events" },
          { key: "connect", label: "Connect Calendar", short: "Connect" },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap flex-shrink-0",
              tab === t.key
                ? "text-primary border-b-2 border-primary -mb-1"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <span className="hidden sm:inline">{t.label}</span>
            <span className="sm:hidden">{t.short}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === "timeline" && (
        <Card>
          <CardContent className="p-4">
            {timeline.length === 0 ? (
              <div className="text-center py-8">
                <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">No activity yet. Log a communication or schedule an event to get started.</p>
              </div>
            ) : (
              timeline.map((item) => <TimelineRow key={item.id} item={item} />)
            )}
          </CardContent>
        </Card>
      )}

      {tab === "communications" && (
        <div className="space-y-3">
          {/* Channel filter */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCommFilter("all")}
              className={cn(
                "px-2.5 py-1 text-xs font-medium rounded-md transition-colors",
                commFilter === "all" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              All
            </button>
            {ALL_CHANNELS.map((c) => (
              <button
                key={c}
                onClick={() => setCommFilter(c)}
                className={cn(
                  "px-2.5 py-1 text-xs font-medium rounded-md transition-colors capitalize",
                  commFilter === c ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {CHANNEL_CONFIG[c].label}
              </button>
            ))}
          </div>
          <Card>
            <CardContent className="p-4">
              {communications.length === 0 ? (
                <div className="text-center py-8">
                  <Mail className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">No communications logged yet.</p>
                </div>
              ) : (
                communications.map((c) => <CommRow key={c.id} comm={c} />)
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "calendar" && (
        <div className="space-y-3">
          {events.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center">
                <Calendar className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">No events scheduled. Click "Schedule Event" to add one.</p>
              </CardContent>
            </Card>
          ) : (
            events.map((e) => <EventRow key={e.id} event={e} />)
          )}
        </div>
      )}

      {tab === "connect" && (
        <div className="space-y-4">
          {/* OAuth callback message */}
          {oauthMessage && (
            <div className={cn(
              "flex items-center gap-2 p-3 rounded-lg text-sm",
              oauthMessage.type === "success"
                ? "bg-green-50 dark:bg-green-950/50 text-green-700 dark:text-green-300"
                : "bg-red-50 dark:bg-red-950/50 text-red-700 dark:text-red-300"
            )}>
              {oauthMessage.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 shrink-0" />
              )}
              <span className="flex-1">{oauthMessage.text}</span>
              <button onClick={() => setOauthMessage(null)} className="shrink-0">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <Card>
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-violet-100 dark:bg-violet-950 shrink-0">
                  <Calendar className="h-6 w-6 text-violet-600 dark:text-violet-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Calendar Integration</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    Connect your Google Calendar or Outlook to sync appointments automatically.
                    Events from your external calendar appear in the Calendar tab and Timeline.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Google Calendar */}
          <ProviderCard
            provider="google"
            label="Google Calendar"
            icon={Calendar}
            color="text-blue-600 bg-blue-100 dark:bg-blue-950 dark:text-blue-300"
            status={connections?.google || { configured: false, connected: false, email: "", connected_at: "", last_synced_at: "" }}
            onConnect={() => handleConnect("google")}
            onDisconnect={() => handleDisconnect("google")}
            onSync={() => handleSync("google")}
            syncing={syncingProvider === "google"}
          />

          {/* Outlook */}
          <ProviderCard
            provider="outlook"
            label="Outlook"
            icon={Mail}
            color="text-blue-700 bg-blue-100 dark:bg-blue-950 dark:text-blue-300"
            status={connections?.outlook || { configured: false, connected: false, email: "", connected_at: "", last_synced_at: "" }}
            onConnect={() => handleConnect("outlook")}
            onDisconnect={() => handleDisconnect("outlook")}
            onSync={() => handleSync("outlook")}
            syncing={syncingProvider === "outlook"}
          />

          {/* How it works */}
          <Card>
            <CardContent className="p-6">
              <h3 className="text-sm font-semibold text-foreground mb-2">How it works</h3>
              <div className="space-y-2">
                {[
                  "Click Connect to authorize access via Google or Microsoft OAuth",
                  "Events from your external calendar sync into Mission Control",
                  "Click Sync anytime to pull the latest events",
                  "Disconnect anytime — your tokens are deleted immediately",
                ].map((step, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary font-bold text-[10px] shrink-0">
                      {i + 1}
                    </div>
                    {step}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Modals */}
      {showLogForm && <LogCommForm onClose={() => setShowLogForm(false)} />}
      {showEventForm && <ScheduleEventForm onClose={() => setShowEventForm(false)} />}
    </div>
  );
}
