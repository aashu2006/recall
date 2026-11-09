"use server";

import { revalidatePath } from "next/cache";
import { signAudio } from "@/lib/audio";

// Calls to the FastAPI backend. BACKEND_URL and CRON_SECRET are read on the server only,
// so the secret never reaches the browser.

export type ActionResult<T = undefined> = { ok: true; data: T } | { ok: false; error: string };

async function backend(path: string, body?: unknown): Promise<Response> {
  const base = process.env.BACKEND_URL;
  const secret = process.env.CRON_SECRET;
  if (!base || !secret) throw new Error("BACKEND_URL and CRON_SECRET must be set (see .env.local.example)");
  return fetch(`${base.replace(/\/+$/, "")}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${secret}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
}

/** FastAPI errors carry {detail}; the briefing preview carries {error}. */
async function readJson(res: Response): Promise<Record<string, unknown>> {
  return ((await res.json().catch(() => null)) ?? {}) as Record<string, unknown>;
}

function errorText(res: Response, json: Record<string, unknown>): string {
  const msg = [json.detail, json.error].find((v) => typeof v === "string") as string | undefined;
  return msg ?? `Backend answered ${res.status}.`;
}

function failure(e: unknown): { ok: false; error: string } {
  if (e instanceof Error && e.name === "TimeoutError") return { ok: false, error: "The backend took too long to answer." };
  return { ok: false, error: e instanceof Error ? e.message : "Couldn't reach the backend." };
}

/** The owner's answer to a pending confirmation: an order id, "new" or "no". Returns the backend's reply text. */
export async function resolvePending(id: number, choice: string): Promise<ActionResult<string | null>> {
  if (!Number.isInteger(id) || id <= 0 || !/^(\d+|new|no)$/.test(choice)) return { ok: false, error: "Invalid option." };
  try {
    const res = await backend(`/pending/${id}/resolve`, { choice });
    const json = await readJson(res);
    revalidatePath("/pending");
    revalidatePath("/");
    // 500 with a message: the backend reopened the item because saving failed.
    if (!res.ok) return { ok: false, error: typeof json.message === "string" ? json.message : errorText(res, json) };
    return { ok: true, data: typeof json.message === "string" ? json.message : null };
  } catch (e) {
    return failure(e);
  }
}

export interface BriefingPreview {
  text: string;
  /** Signed URL of the voiced briefing, null if Timbre or storage failed. */
  audio: string | null;
  /** Set when the text was built but the audio was not. */
  error: string | null;
}

/** Builds today's morning briefing without sending it on WhatsApp: text plus the spoken audio. */
export async function previewBriefing(): Promise<ActionResult<BriefingPreview>> {
  try {
    const res = await backend("/briefing/preview");
    const json = await readJson(res);
    const text = typeof json.text === "string" ? json.text : null;
    if (text === null) return { ok: false, error: errorText(res, json) };
    const path = typeof json.path === "string" ? json.path : null;
    const audio = path ? ((await signAudio([path])).get(path) ?? null) : null;
    revalidatePath("/outbox");
    return { ok: true, data: { text, audio, error: res.ok ? null : errorText(res, json) } };
  } catch (e) {
    return failure(e);
  }
}
