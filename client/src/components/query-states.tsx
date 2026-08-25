import { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw, Loader2, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Loading skeleton presets
// ---------------------------------------------------------------------------

export function KPICardSkeleton() {
  return (
    <Card className="border-l-4 border-l-muted">
      <CardContent className="p-4">
        <Skeleton className="h-3 w-20 mb-2" />
        <Skeleton className="h-7 w-24 mb-1" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function CardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICardSkeleton />
        <KPICardSkeleton />
        <KPICardSkeleton />
        <KPICardSkeleton />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Skeleton className="h-6 w-48" />
          <CardListSkeleton count={3} />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <CardListSkeleton count={2} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error state with retry
// ---------------------------------------------------------------------------

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <Card className={cn("border-destructive/30", className)}>
      <CardContent className="p-6 flex flex-col items-center text-center gap-3">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {message || "Something went wrong loading this data."}
        </p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Computing state (async cache warming)
// ---------------------------------------------------------------------------

interface ComputingStateProps {
  message?: string;
  className?: string;
}

export function ComputingState({ message, className }: ComputingStateProps) {
  return (
    <Card className={cn("border-blue-200 dark:border-blue-900", className)}>
      <CardContent className="p-6 flex flex-col items-center text-center gap-3">
        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
        <p className="text-sm text-muted-foreground">
          {message || "Computing dashboard data. This takes about 30 seconds on first load."}
        </p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, message, icon, action, className }: EmptyStateProps) {
  return (
    <Card className={cn("border-dashed", className)}>
      <CardContent className="p-8 flex flex-col items-center text-center gap-3">
        {icon || <Inbox className="h-8 w-8 text-muted-foreground" />}
        <p className="text-sm font-medium text-foreground">{title}</p>
        {message && <p className="text-xs text-muted-foreground">{message}</p>}
        {action}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Smart query wrapper — handles loading, error, computing, and empty states
// ---------------------------------------------------------------------------

interface QueryStateProps<T> {
  query: ReturnType<typeof useQuery<T>>;
  children: (data: T) => ReactNode;
  loadingComponent?: ReactNode;
  errorComponent?: ReactNode;
  emptyCheck?: (data: T) => boolean;
  emptyComponent?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

export function QueryState<T>({
  query,
  children,
  loadingComponent,
  errorComponent,
  emptyCheck,
  emptyComponent,
  className,
}: QueryStateProps<T>) {
  // Check for "computing" status in the response
  const isComputing = query.data && typeof query.data === "object" && "status" in query.data && (query.data as any).status === "computing";

  if (query.isLoading || isComputing) {
    return <>{loadingComponent || <DashboardSkeleton />}</>;
  }

  if (query.isError) {
    return (
      <>
        {errorComponent || (
          <ErrorState
            message={`Failed to load: ${(query.error as Error)?.message || "unknown error"}`}
            onRetry={() => query.refetch()}
            className={className}
          />
        )}
      </>
    );
  }

  if (emptyCheck && query.data && emptyCheck(query.data)) {
    return <>{emptyComponent || <EmptyState title="No data available" />}</>;
  }

  if (query.data) {
    return <>{children(query.data)}</>;
  }

  return <>{loadingComponent || <DashboardSkeleton />}</>;
}

// ---------------------------------------------------------------------------
// Last refreshed timestamp
// ---------------------------------------------------------------------------

export function LastRefreshed({ timestamp, className }: { timestamp?: number; className?: string }) {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  const ago = Math.round((Date.now() - timestamp) / 1000);
  const label = ago < 60 ? `${ago}s ago` : ago < 3600 ? `${Math.round(ago / 60)}m ago` : `${Math.round(ago / 3600)}h ago`;
  return (
    <span className={cn("text-xs text-muted-foreground flex items-center gap-1", className)}>
      <RefreshCw className="h-3 w-3" />
      Updated {label}
    </span>
  );
}
