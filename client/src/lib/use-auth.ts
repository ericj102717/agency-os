import { useEffect, useState, useCallback } from "react";
import { getSupabase, isAuthEnabled } from "@/lib/supabase";
import type { User } from "@supabase/supabase-js";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: isAuthEnabled(),
    error: null,
  });

  const supabase = getSupabase();

  useEffect(() => {
    if (!supabase) {
      setState({ user: null, loading: false, error: null });
      return;
    }

    // Check existing session
    supabase.auth.getSession().then(({ data, error }) => {
      if (error) {
        setState({ user: null, loading: false, error: error.message });
      } else {
        setState({ user: data.session?.user ?? null, loading: false, error: null });
      }
    });

    // Listen for auth changes
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ user: session?.user ?? null, loading: false, error: null });
    });

    return () => listener.subscription.unsubscribe();
  }, [supabase]);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) return { error: "Auth not configured" };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: error.message };
    return { error: null };
  }, [supabase]);

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) return { error: "Auth not configured" };
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) return { error: error.message };
    return { error: null };
  }, [supabase]);

  const signOut = useCallback(async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
  }, [supabase]);

  return {
    user: state.user,
    loading: state.loading,
    error: state.error,
    isAuthEnabled: isAuthEnabled(),
    signIn,
    signUp,
    signOut,
  };
}
