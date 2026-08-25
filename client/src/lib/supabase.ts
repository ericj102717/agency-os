import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Supabase client — uses env vars set at build time
// For Vercel: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
// For pplx.app: falls back to inline values from build
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string || "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string || "";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return null;
  }
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}

export function isAuthEnabled(): boolean {
  return !!SUPABASE_URL && !!SUPABASE_ANON_KEY;
}
