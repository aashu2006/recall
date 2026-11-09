import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Service key client. Server components only: the "server-only" import makes the
// build fail if this module ever ends up in a browser bundle.
let client: SupabaseClient | null = null;

export function db(): SupabaseClient {
  if (client) return client;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (see dashboard/.env.local.example)");
  }
  client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}

export const AUDIO_BUCKET = process.env.SUPABASE_AUDIO_BUCKET || "audio";

/** Throw on a Supabase error so the page shows the error boundary instead of empty data. */
// Untyped client (no generated DB types), so the caller names the row shape.
export function must<T>(res: { data: unknown; error: { message: string } | null }): T {
  if (res.error) throw new Error(res.error.message);
  return res.data as T;
}
