-- 003: log of outbound WhatsApp messages. The backend counts today's rows (Asia/Kolkata)
-- before every send to enforce WA_DAILY_SEND_CAP, so the cap survives Render restarts.

create table wa_sends (
  id             bigint generated always as identity primary key,
  to_phone       text not null,
  kind           text not null,          -- text, buttons, audio
  wa_message_id  text,                   -- id returned by the Cloud API
  created_at     timestamptz not null default now()
);

create index wa_sends_created_at_idx on wa_sends (created_at);

alter table wa_sends enable row level security;
