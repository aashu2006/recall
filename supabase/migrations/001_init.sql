-- 001_init: core tables for Recall. See docs/PRD.md "Data model".
-- RLS is on for every table with no policies: only the service key (backend and
-- dashboard server-side code) can read or write. The anon key sees nothing.

create table clients (
  id          bigint generated always as identity primary key,
  name        text not null,
  phone       text unique,
  aliases     text[] not null default '{}',  -- "Sharma ji", "Sharma Steels"
  created_at  timestamptz not null default now()
);

create table calls (
  id                bigint generated always as identity primary key,
  client_id         bigint references clients (id),  -- null until the sender is matched
  wa_message_id     text unique,                     -- WhatsApp retries webhooks; drop duplicates before downloading
  from_phone        text,
  audio_url         text,
  audio_hash        text not null,                   -- SHA-256 of the audio; reuse transcript, never re-transcribe
  duration_seconds  numeric,
  transcript        text,
  segments          jsonb,                           -- [{start, end, text}], seconds from start of audio
  created_at        timestamptz not null default now()
);

create index calls_audio_hash_idx on calls (audio_hash);

create table orders (
  id             bigint generated always as identity primary key,
  client_id      bigint not null references clients (id),
  item           text not null,
  spec           text,                              -- e.g. "3mm MS"
  quantity       numeric,
  unit           text,                              -- pcs, kg, mm, ton, ...
  rate           numeric,                           -- per unit
  delivery_date  date,
  status         text not null default 'open' check (status in ('open', 'delivered', 'cancelled')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index orders_client_id_idx on orders (client_id);

-- Append-only history. Every insert or update of orders writes a row here in the same
-- transaction. A new order is recorded with field = 'created'.
create table order_changes (
  id          bigint generated always as identity primary key,
  order_id    bigint not null references orders (id),
  call_id     bigint references calls (id),         -- null for manual edits by the owner
  field       text not null,
  old_value   text,
  new_value   text,
  clip_start  numeric,                              -- seconds into the call audio
  clip_end    numeric,
  confidence  real,
  created_at  timestamptz not null default now()
);

create index order_changes_order_id_idx on order_changes (order_id);

create table pending_confirmations (
  id              bigint generated always as identity primary key,
  call_id         bigint references calls (id),
  client_id       bigint references clients (id),
  extracted_json  jsonb not null,
  question        text not null,
  options         jsonb,                            -- candidate order ids for the owner's buttons
  status          text not null default 'pending' check (status in ('pending', 'confirmed', 'rejected', 'expired')),
  resolved_at     timestamptz,
  created_at      timestamptz not null default now()
);

create index pending_confirmations_status_idx on pending_confirmations (status);

create table reminders (
  id          bigint generated always as identity primary key,
  order_id    bigint not null references orders (id),
  due_at      timestamptz not null,
  sent        boolean not null default false,
  created_at  timestamptz not null default now()
);

create index reminders_due_idx on reminders (sent, due_at);

alter table clients enable row level security;
alter table calls enable row level security;
alter table orders enable row level security;
alter table order_changes enable row level security;
alter table pending_confirmations enable row level security;
alter table reminders enable row level security;

-- Private bucket for voice notes and proof clips. Served via signed URLs.
insert into storage.buckets (id, name, public)
values ('audio', 'audio', false)
on conflict (id) do nothing;
