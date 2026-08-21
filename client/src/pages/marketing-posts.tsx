import { useState, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Megaphone,
  RefreshCw,
  Copy,
  Check,
  Save,
  Calendar,
  Edit3,
  Hash,
  AlertCircle,
} from "lucide-react";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import { SectionHeader, Card, CardContent } from "@/components/ui-widgets";

// ---- Types ----

interface ChannelInfo {
  max_chars: number;
  emoji_friendly?: boolean;
  hashtag_limit?: number;
}

interface MarketingConfig {
  status: string;
  company: string;
  industry: string;
  channels: string[];
  channel_info: Record<string, ChannelInfo>;
  tones: string[];
  themes: string[];
  daily_themes: Array<{ day: string; theme: string; focus: string }>;
}

interface MarketingPost {
  id: string;
  date: string;
  day: string;
  theme: string;
  focus: string;
  channel: string;
  tone: string;
  content: string;
  char_count: number;
  max_chars: number;
  status: string;
}

interface PostsResponse {
  status: string;
  company: string;
  industry: string;
  channel: string;
  tone: string;
  generated_at: string;
  week_start: string;
  posts: MarketingPost[];
}

interface CustomizeResponse {
  status: string;
  post_id: string;
  content: string;
  char_count: number;
  max_chars: number;
}

interface PostsQueryParams {
  company: string;
  industry: string;
  tone: string;
  channel: string;
  cta: string;
  offer: string;
  target_date: string;
}

// ---- Page ----

export function MarketingPostsPage() {
  // Config query — loads defaults for company/industry/channel/tone
  const { data: config, isLoading: configLoading, error: configError } = useQuery<MarketingConfig>({
    queryKey: [`${API_BASE}/api/marketing-posts/config`],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/marketing-posts/config`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });

  // Form state — prefilled from config once it arrives
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [channel, setChannel] = useState("facebook");
  const [tone, setTone] = useState("friendly");
  const [cta, setCta] = useState("");
  const [offer, setOffer] = useState("");

  // Seed form from config on first load
  const [seeded, setSeeded] = useState(false);
  if (config && !seeded) {
    setCompany(config.company || "");
    setIndustry(config.industry || "");
    setChannel(config.channels?.[0] || "facebook");
    setTone(config.tones?.[0] || "friendly");
    setSeeded(true);
  }

  // Tracks whether the user has requested a generation (so the posts query is
  // lazy — only fires after "Generate Posts" is clicked).
  const [params, setParams] = useState<PostsQueryParams | null>(null);

  // Editable copies of post content keyed by post id
  const [editedContent, setEditedContent] = useState<Record<string, string>>({});
  // Per-post "edited" flag (set when user saves a customization)
  const [editedFlags, setEditedFlags] = useState<Record<string, boolean>>({});
  // Per-post copied feedback
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const postsQueryKey = params
    ? [
        `${API_BASE}/api/marketing-posts`,
        params.company,
        params.industry,
        params.tone,
        params.channel,
        params.cta,
        params.offer,
        params.target_date,
      ]
    : ["marketing-posts", "idle"];

  const {
    data: postsData,
    isLoading: postsLoading,
    error: postsError,
    refetch: refetchPosts,
    isFetching: postsFetching,
  } = useQuery<PostsResponse>({
    queryKey: postsQueryKey,
    queryFn: async ({ queryKey }) => {
      // queryKey is [baseUrl, company, industry, tone, channel, cta, offer, target_date]
      const [base, qCompany, qIndustry, qTone, qChannel, qCta, qOffer, qDate] = queryKey as [
        string,
        string,
        string,
        string,
        string,
        string,
        string,
        string
      ];
      const search = new URLSearchParams({
        company: qCompany,
        industry: qIndustry,
        tone: qTone,
        channel: qChannel,
        cta: qCta,
        offer: qOffer,
        target_date: qDate,
      });
      const res = await fetch(`${base}?${search.toString()}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    enabled: !!params,
    staleTime: 5 * 60_000,
  });

  // Mutation for the customize endpoint
  const customizeMutation = useMutation<
    CustomizeResponse,
    Error,
    { post_id: string; content: string; company: string; channel: string }
  >({
    mutationFn: async (body) => {
      const res = await mutationFetch("/api/marketing-posts/customize", {
        method: "POST",
        body,
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    onSuccess: (data, variables) => {
      setEditedFlags((prev) => ({ ...prev, [variables.post_id]: true }));
      setEditedContent((prev) => ({ ...prev, [variables.post_id]: data.content }));
    },
  });

  const handleGenerate = useCallback(() => {
    const targetDate = new Date().toISOString().slice(0, 10);
    // Reset edits when regenerating
    setEditedContent({});
    setEditedFlags({});
    setParams({
      company: company || config?.company || "",
      industry: industry || config?.industry || "",
      tone,
      channel,
      cta,
      offer,
      target_date: targetDate,
    });
  }, [company, industry, tone, channel, cta, offer, config]);

  const handleCopy = useCallback(
    async (post: MarketingPost) => {
      const text = editedContent[post.id] ?? post.content;
      try {
        await navigator.clipboard.writeText(text);
        setCopiedId(post.id);
        setTimeout(() => setCopiedId((curr) => (curr === post.id ? null : curr)), 2000);
      } catch {
        // Fallback for environments without clipboard API
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        try {
          document.execCommand("copy");
          setCopiedId(post.id);
          setTimeout(() => setCopiedId((curr) => (curr === post.id ? null : curr)), 2000);
        } finally {
          document.body.removeChild(textarea);
        }
      }
    },
    [editedContent]
  );

  const handleSave = useCallback(
    (post: MarketingPost) => {
      const content = editedContent[post.id] ?? post.content;
      customizeMutation.mutate({
        post_id: post.id,
        content,
        company: company || config?.company || "",
        channel: post.channel,
      });
    },
    [editedContent, company, config, customizeMutation]
  );

  // ---- Render ----

  if (configLoading) return <LoadingState />;
  if (configError || !config) {
    return (
      <ErrorState message="Failed to load marketing post configuration. Please try again." />
    );
  }

  const channels = config.channels || ["facebook", "instagram", "linkedin", "email", "sms", "google"];
  const tones = config.tones || ["professional", "friendly", "educational"];
  const posts = postsData?.posts ?? [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Marketing Posts"
        subtitle="Generate daily marketing content tailored to your business — 7 days at a time"
      />

      {/* Customization Panel */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <Megaphone className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Content Settings</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <FormField label="Company Name">
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Your business name"
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </FormField>
            <FormField label="Industry">
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="Your industry"
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </FormField>
            <FormField label="Channel">
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {channels.map((ch) => (
                  <option key={ch} value={ch}>
                    {ch.charAt(0).toUpperCase() + ch.slice(1)}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Tone">
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {tones.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Call to Action">
              <input
                type="text"
                value={cta}
                onChange={(e) => setCta(e.target.value)}
                placeholder="Call us today to schedule your free estimate!"
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </FormField>
            <FormField label="Offer">
              <input
                type="text"
                value={offer}
                onChange={(e) => setOffer(e.target.value)}
                placeholder="Schedule a free consultation this month..."
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </FormField>
          </div>
          <div className="flex justify-end mt-4">
            <button
              onClick={handleGenerate}
              disabled={postsFetching}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`h-4 w-4 ${postsFetching ? "animate-spin" : ""}`} />
              {postsData ? "Regenerate Posts" : "Generate Posts"}
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Posts section */}
      {postsLoading && <LoadingState label="Generating your 7 days of marketing posts..." />}
      {postsError && (
        <ErrorState message="Failed to generate marketing posts. Please try again." />
      )}

      {!params && !postsLoading && (
        <EmptyState onGenerate={handleGenerate} />
      )}

      {posts.length > 0 && (
        <div>
          <SectionHeader
            title="7-Day Content Calendar"
            subtitle={`${postsData?.channel ? postsData.channel.charAt(0).toUpperCase() + postsData.channel.slice(1) : ""} · ${postsData?.tone ? postsData.tone.charAt(0).toUpperCase() + postsData.tone.slice(1) : ""} tone${postsData?.week_start ? ` · Week of ${postsData.week_start}` : ""}`}
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                editedContent={editedContent[post.id]}
                isEdited={!!editedFlags[post.id]}
                isCopied={copiedId === post.id}
                isSaving={customizeMutation.isPending && customizeMutation.variables?.post_id === post.id}
                onContentChange={(val) =>
                  setEditedContent((prev) => ({ ...prev, [post.id]: val }))
                }
                onCopy={() => handleCopy(post)}
                onSave={() => handleSave(post)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Sub-components ----

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-medium text-muted-foreground mb-1 block">{label}</label>
      {children}
    </div>
  );
}

function PostCard({
  post,
  editedContent,
  isEdited,
  isCopied,
  isSaving,
  onContentChange,
  onCopy,
  onSave,
}: {
  post: MarketingPost;
  editedContent: string | undefined;
  isEdited: boolean;
  isCopied: boolean;
  isSaving: boolean;
  onContentChange: (val: string) => void;
  onCopy: () => void;
  onSave: () => void;
}) {
  const content = editedContent ?? post.content;
  const charCount = content.length;
  const maxChars = post.max_chars;
  const overLimit = charCount > maxChars;

  return (
    <Card className="flex flex-col">
      <CardContent className="p-4 flex flex-col flex-1">
        {/* Header row: day + date */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">{post.day}</span>
            <span className="text-xs text-muted-foreground">{post.date}</span>
          </div>
          <span
            className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold ${
              isEdited
                ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {isEdited ? "EDITED" : (post.status || "draft").toUpperCase()}
          </span>
        </div>

        {/* Theme badge + focus */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 text-primary px-2 py-0.5 text-[11px] font-semibold">
            <Hash className="h-3 w-3" />
            {post.theme}
          </span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">{post.focus}</p>

        {/* Editable textarea */}
        <textarea
          value={content}
          onChange={(e) => onContentChange(e.target.value)}
          rows={8}
          className="w-full flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-primary min-h-[140px]"
          aria-label={`Edit post content for ${post.day} — ${post.theme}`}
        />

        {/* Char count + actions */}
        <div className="flex items-center justify-between gap-2 mt-2">
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={`font-mono ${overLimit ? "text-red-600 dark:text-red-400 font-semibold" : "text-muted-foreground"}`}
            >
              {charCount}
            </span>
            <span className="text-muted-foreground">/</span>
            <span className="text-muted-foreground font-mono">{maxChars}</span>
            {overLimit && (
              <span className="text-red-600 dark:text-red-400 ml-1">over limit</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-background text-xs font-medium hover:bg-muted transition-colors"
              title="Copy to clipboard"
            >
              {isCopied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                  <span className="text-green-600 dark:text-green-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </>
              )}
            </button>
            <button
              onClick={onSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              title="Save edited content"
            >
              {isSaving ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : isEdited ? (
                <Edit3 className="h-3.5 w-3.5" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              {isEdited ? "Saved" : "Save"}
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---- States ----

function LoadingState({ label }: { label?: string }) {
  return (
    <div className="space-y-4">
      {label ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          {label}
        </div>
      ) : (
        <div className="h-8 w-64 bg-muted rounded animate-pulse" />
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-56 bg-muted rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-red-50 dark:bg-red-950/50 px-4 py-6 text-red-700 dark:text-red-300">
      <AlertCircle className="h-5 w-5 shrink-0" />
      {message}
    </div>
  );
}

function EmptyState({ onGenerate }: { onGenerate: () => void }) {
  return (
    <Card>
      <CardContent className="p-8 flex flex-col items-center justify-center text-center">
        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-3">
          <Megaphone className="h-6 w-6 text-primary" />
        </div>
        <h3 className="text-sm font-semibold text-foreground mb-1">No posts yet</h3>
        <p className="text-xs text-muted-foreground mb-4 max-w-sm">
          Configure your content settings above and click "Generate Posts" to create a week of
          tailored marketing content.
        </p>
        <button
          onClick={onGenerate}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Generate Posts
        </button>
      </CardContent>
    </Card>
  );
}
