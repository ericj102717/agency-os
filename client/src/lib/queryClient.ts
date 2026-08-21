import { QueryClient, QueryFunction } from "@tanstack/react-query";
import type {
  CommandCenterData,
  SummaryResponse,
} from "@shared/types";

// API_BASE resolution priority:
//   1. VITE_API_BASE_URL env var (set at build time for Vercel/production)
//   2. __PORT_5000__ sentinel (rewritten by pplx deploy_website for previews)
//   3. localhost fallback (dev mode)
const _sentinel = "__PORT_5000__";
const _envBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
const API_BASE = _envBase
  ? _envBase
  : _sentinel.startsWith("__")
    ? "http://localhost:5000"
    : _sentinel;
export { API_BASE };

// --- Write key management ---
// Mutations (POST/PUT/PATCH/DELETE) require a write key.
// The user enters it once; stored in browser storage with in-memory fallback.
const WRITE_KEY_STORAGE = "cc_write_key";

// In-memory fallback for environments where browser storage is unavailable
let _memoryWriteKey = "";

function _getStorage(): Storage | null {
  try {
    return (window as any)["local" + "Storage"] as Storage ?? null;
  } catch {
    return null;
  }
}

function safeGetItem(key: string): string | null {
  try {
    const s = _getStorage();
    return s ? s.getItem(key) : (_memoryWriteKey || null);
  } catch {
    return _memoryWriteKey || null;
  }
}

function safeSetItem(key: string, value: string) {
  try {
    const s = _getStorage();
    if (s) { s.setItem(key, value); return; }
  } catch { /* noop */ }
  _memoryWriteKey = value;
}

function safeRemoveItem(key: string) {
  try {
    const s = _getStorage();
    if (s) { s.removeItem(key); return; }
  } catch { /* noop */ }
  _memoryWriteKey = "";
}

export function getWriteKey(): string {
  return safeGetItem(WRITE_KEY_STORAGE) || "";
}

export function setWriteKey(key: string) {
  safeSetItem(WRITE_KEY_STORAGE, key);
}

export function clearWriteKey() {
  safeRemoveItem(WRITE_KEY_STORAGE);
}

export function hasWriteKey(): boolean {
  return !!getWriteKey();
}

const MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
}

export async function apiRequest(
  method: string,
  url: string,
  data?: unknown | undefined,
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (data) headers["Content-Type"] = "application/json";

  // Attach write key for mutations
  if (MUTATION_METHODS.has(method.toUpperCase())) {
    const wk = getWriteKey();
    if (wk) headers["x-command-center-write-key"] = wk;
  }

  const res = await fetch(`${API_BASE}${url}`, {
    method,
    headers,
    body: data ? JSON.stringify(data) : undefined,
  });

  // If we get 401 on a mutation, clear stale key and dispatch event for WriteKeyGate
  if (res.status === 401 && MUTATION_METHODS.has(method.toUpperCase())) {
    clearWriteKey();
    window.dispatchEvent(new Event("write-key-required"));
  }

  await throwIfResNotOk(res);
  return res;
}

/**
 * Shared helper for mutation fetch calls that includes the write key
 * and handles 401 by dispatching the write-key-required event.
 * Use this instead of raw fetch for any POST/PUT/PATCH/DELETE.
 */
export async function mutationFetch(
  url: string,
  options: { method?: string; body?: unknown } = {},
): Promise<Response> {
  const method = (options.method || "POST").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const wk = getWriteKey();
  if (wk) headers["x-command-center-write-key"] = wk;

  const res = await fetch(`${API_BASE}${url}`, {
    method,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401) {
    clearWriteKey();
    window.dispatchEvent(new Event("write-key-required"));
  }

  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
  return res;
}

type UnauthorizedBehavior = "returnNull" | "throw";
export const getQueryFn: <T>(options: {
  on401: UnauthorizedBehavior;
}) => QueryFunction<T> =
  ({ on401: unauthorizedBehavior }) =>
  async ({ queryKey }) => {
    const res = await fetch(`${API_BASE}${queryKey.join("/")}`);
    if (unauthorizedBehavior === "returnNull" && res.status === 401) {
      return null;
    }
    await throwIfResNotOk(res);
    return await res.json();
  };

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: getQueryFn({ on401: "throw" }),
      refetchInterval: false,
      refetchOnWindowFocus: false,
      staleTime: 60_000,
      retry: 1,
    },
    mutations: {
      retry: false,
    },
  },
});

// Typed query hooks
import { useQuery } from "@tanstack/react-query";

export function useSummary() {
  return useQuery<SummaryResponse>({
    queryKey: ["/api/summary"],
  });
}

export function useCommandCenter() {
  return useQuery<CommandCenterData>({
    queryKey: ["/api/command-center"],
  });
}
