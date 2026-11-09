import "server-only";
import { AUDIO_BUCKET, db } from "./supabase";

const SIGNED_URL_TTL_S = 60 * 60;

/**
 * calls.audio_url may hold a bare object path in the audio bucket ("calls/abc.ogg") or a
 * full Supabase Storage URL. Returns the object path, or null if it is not in our bucket
 * (e.g. a WhatsApp media URL, which needs a token and can't be played in the browser).
 */
export function storagePath(audioUrl: string | null): string | null {
  if (!audioUrl) return null;
  const m = audioUrl.match(/\/storage\/v1\/object\/(?:public|sign|authenticated)\/([^/]+)\/([^?#]+)/);
  if (m) return m[1] === AUDIO_BUCKET ? decodeURIComponent(m[2]) : null;
  if (/^[a-z]+:\/\//i.test(audioUrl)) return null;
  return audioUrl.replace(/^\/+/, "");
}

/** Signed URLs for many audio_url values in one request. Keyed by the original audio_url. */
export async function signAudio(audioUrls: (string | null)[]): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  const byPath = new Map<string, string[]>();
  for (const u of audioUrls) {
    const p = storagePath(u);
    if (u && p) byPath.set(p, [...(byPath.get(p) ?? []), u]);
  }
  if (byPath.size === 0) return out;

  const { data, error } = await db()
    .storage.from(AUDIO_BUCKET)
    .createSignedUrls([...byPath.keys()], SIGNED_URL_TTL_S);
  if (error) {
    console.error("signing audio failed:", error.message);
    return out;
  }
  for (const s of data ?? []) {
    if (!s.path || !s.signedUrl || s.error) continue;
    for (const u of byPath.get(s.path) ?? []) out.set(u, s.signedUrl);
  }
  return out;
}
