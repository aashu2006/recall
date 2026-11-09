-- 004: wa_sends becomes a full log of every outbound WhatsApp attempt, so replies can be
-- read without WhatsApp (sends fail while the Meta account is unverified).
--
-- kind now says what the message is for: client_summary, owner_question, owner_reply,
-- owner_alert, briefing. The WhatsApp message type (text, buttons, audio) moves to msg_type.
-- status: sent, failed (error holds why, including the daily cap), or preview (briefing
-- rendered but deliberately not sent). Only status = 'sent' rows count for WA_DAILY_SEND_CAP.

alter table wa_sends
  add column msg_type   text,
  add column body       text,
  add column media_path text,             -- object path in the audio bucket, for audio
  add column status     text not null default 'sent',
  add column error      text;

-- Rows from before 004: kind held the message type and every row was a successful send.
update wa_sends set msg_type = kind where msg_type is null;

alter table wa_sends
  add constraint wa_sends_status_check check (status in ('sent', 'failed', 'preview'));

create index wa_sends_status_created_at_idx on wa_sends (status, created_at);
