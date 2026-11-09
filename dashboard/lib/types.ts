// Row shapes from supabase/migrations/001_init.sql.

export type OrderStatus = "open" | "delivered" | "cancelled";

export interface Client {
  id: number;
  name: string;
  phone: string | null;
}

export interface Order {
  id: number;
  client_id: number;
  item: string;
  spec: string | null;
  quantity: number | null;
  unit: string | null;
  rate: number | null;
  delivery_date: string | null; // YYYY-MM-DD
  status: OrderStatus;
  created_at: string;
  updated_at: string;
  clients: Pick<Client, "name"> | null;
}

export interface Call {
  id: number;
  client_id: number | null;
  from_phone: string | null;
  audio_url: string | null;
  duration_seconds: number | null;
  transcript: string | null;
  created_at: string;
  clients: Pick<Client, "name"> | null;
}

export interface OrderChange {
  id: number;
  order_id: number;
  call_id: number | null;
  field: string;
  old_value: string | null;
  new_value: string | null;
  clip_start: number | null;
  clip_end: number | null;
  confidence: number | null;
  created_at: string;
  calls: (Pick<Call, "audio_url"> & { segments?: Segment[] | null }) | null;
}

/** calls.segments: seconds from the start of the audio. */
export interface Segment {
  start: number;
  end: number;
  text: string;
}

export interface PendingConfirmation {
  id: number;
  call_id: number | null;
  client_id: number | null;
  extracted_json: Record<string, unknown>;
  question: string;
  options: unknown;
  status: string;
  created_at: string;
  clients: Pick<Client, "name"> | null;
}

/** wa_sends: every outbound WhatsApp attempt (003_wa_sends.sql, 004_wa_sends_log.sql). */
export interface WaSend {
  id: number;
  to_phone: string;
  /** client_summary, owner_question, owner_reply, owner_alert, briefing (older rows: text, buttons, audio). */
  kind: string;
  msg_type: string | null;
  body: string | null;
  /** Object path in the audio bucket, for voice notes. */
  media_path: string | null;
  status: "sent" | "failed" | "preview" | string;
  error: string | null;
  wa_message_id: string | null;
  created_at: string;
}
