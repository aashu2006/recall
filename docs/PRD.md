# Recall PRD

Akshat Patil and Famous Raj Bhat

## Overview

Recall turns a factory's phone calls and WhatsApp voice notes into a live order book. Clients keep talking the way they already do. After every call, orders, quantity and rate changes, delivery dates and follow-ups show up on a dashboard on their own.  
Built for the Great Indian AI Internship Challenge on Gnani AI's Prisma and Timbre. Submission deadline is 10 Nov 2026.

## Problem

In MSMEs and small factories, most business is done on phone calls, but almost none of it gets written down. A client places an order, bumps the quantity, pushes the rate down, and fixes a delivery date, all in a two-minute call. Later nobody is sure what was actually promised.  
What this leads to:

* Missed or late deliveries because a date was never noted  
* Wrong billing because a rate change was forgotten  
* Disputes where it's the owner's word against the client's  
* The owner carrying the whole order book in his head

Existing tools don't fit. Call recorders give hours of audio nobody listens to again. Order or ERP apps need someone to type everything in, which doesn't happen on a busy shop floor.

## Users

| User | Who they are | What they need |
| :---- | :---- | :---- |
| Factory owner (primary) | Runs a small fabrication, machining or manufacturing unit, takes most client calls himself | One place that shows every order, change and deadline without typing anything |
| Client | Dealers, contractors and companies who order by phone or WhatsApp | Keep ordering the same way, get a clear confirmation of what was agreed |
| Staff (later) | Supervisor or accounts person | Know what to make and deliver today |

All of them speak Hinglish or a local language, mostly on phone audio with machine noise in the background.

## Goals and non-goals

### Goals

* Turn a Hinglish call or voice note into correct, structured order entries without the owner typing  
* Match updates to the right past order instead of creating duplicates  
* Never silently guess: confirm with the owner when unsure  
* Keep everything on WhatsApp so nobody installs a new app  
* Run the whole build and demo on free tiers, zero spend

### Non-goals (for this build)

* Billing, invoicing or GST  
* Inventory and production planning  
* Outbound calling to clients  
* Handling real customer data (demo uses synthetic calls only)

## Features

| Feature | What it does | Priority |
| :---- | :---- | :---- |
| Voice note to order book | Client sends a WhatsApp voice note, system pulls out orders, quantities, rates, dates and follow-ups | Core |
| Order matching | Decides if something is a new order or an update to an old one, and which one | Core |
| Owner confirmation | Low-confidence items go to the owner on WhatsApp with Yes / Edit buttons | Core |
| Audio proof | Every order and change links to the exact clip where the client said it | Core |
| Dashboard | Orders, change history, upcoming deliveries, playable proof clips | Core |
| Client confirmation | Client gets a short WhatsApp summary of what was agreed | Core |
| Morning briefing | Owner gets a voice note with today's deliveries and pending items | Core |
| Voice Q&A | Owner asks "kal kya deliver karna hai?" and gets a voice reply | Nice to have |
| Overcommit warning | Flags a promised date that is already full | Nice to have |
| Live WhatsApp calls | Transcribe actual WhatsApp calls, not just voice notes | Stretch |

## User flows

**Example voice note from a client**  
*"Bhaiya wo 200 bracket wala order hai na, usko 300 kar do. Aur ek naya chahiye, 3mm MS sheet ke 50 piece, Friday tak."*  
What happens next

1. Voice note reaches Recall's WhatsApp number  
2. Prisma transcribes it with segment timestamps  
3. LLM pulls out two items: an update (brackets 200 to 300\) and a new order (50 pcs, 3mm MS sheet, Friday)  
4. Matcher finds the client's open bracket order and links the update to it  
5. Both items are confident, so they go straight to the order book with their audio clips  
6. Client gets a WhatsApp summary of both items  
7. Thursday morning, the owner's briefing says the sheet order is due tomorrow

**When the system isn't sure**  
If the client has two open bracket orders, the matcher can't pick one. The owner gets a WhatsApp message: "Brackets 200 to 300: order #12 or #15?" with buttons. Nothing is saved until he taps.

## System design

Flow: Client voice note → WhatsApp Cloud API → FastAPI backend (webhook on Render) → Prisma STT (segment timestamps) → LLM extraction (Groq, JSON output) → Order matcher (new or update?) → Sure?

* **Yes:** goes straight to the order book (Postgres + audio clips)  
* **No:** owner confirms on WhatsApp buttons, then it goes to the order book

From the order book: the dashboard (Next.js on Vercel) shows everything, and Evon builds the day's summary each night, which Timbre turns into the owner's voice briefing.  
A voice note goes through Prisma, then the LLM pulls out structured items, and the matcher decides if each one is new or an update. Only confident items go straight to the order book. The rest wait for the owner's tap. The webhook returns 200 instantly and does all of this in a background task, so slow steps never block WhatsApp.

## Gnani models

| Model | Used for | Notes |
| :---- | :---- | :---- |
| Prisma v2.5 (STT) | Transcribing voice notes and calls | REST for clips up to 30 s (voice notes are split with Silero VAD into chunks, our own chunk offsets power the audio proof clips). Batch for long calls, gives segment start/end times and speaker labels. Supports Hinglish and 8 kHz phone audio |
| Timbre v2.5 (TTS) | Morning briefing, voice Q&A replies, confirmations | Outputs OGG/Opus, which WhatsApp plays directly as a voice note. Has Hinglish voices |
| Evon v3.3 (LLM) | Nightly summary of the day's orders and changes | Not on the API yet. Run a 4-bit version on Kaggle's free GPUs as a scheduled job |

Live extraction runs on Groq (Gemini as fallback) because it needs to be fast and always on. All LLMs sit behind one client so we can swap with one setting.

## Tech stack (all free tier)

| Layer | Choice | Free limit to watch |
| :---- | :---- | :---- |
| Messaging | WhatsApp Cloud API, Meta test number | Up to 5 verified recipients, no SIM or card needed |
| Speech | Gnani Prisma + Timbre | 5,000 programme credits |
| Live LLM | Groq, Gemini Flash-Lite as fallback | Daily request and token caps, never add a card |
| Nightly LLM | Evon on Kaggle 2x T4 | About 30 GPU hours a week |
| Backend | FastAPI on Render | Sleeps after 15 min idle, about 1 min to wake |
| Database + audio | Supabase Postgres + Storage | 500 MB DB, 1 GB files, pauses after a week idle |
| Dashboard | Next.js on Vercel | Hobby tier |
| Scheduler | GitHub Actions cron | Can run a few minutes late |
| Audio tools | ffmpeg, Silero VAD | Local, free |

Rule for the team: no credit card on any service. If a signup asks for one, we skip it.

## Data model

| Table | Key fields | Why it exists |
| :---- | :---- | :---- |
| clients | id, name, phone, aliases | Match "Sharma ji" and "Sharma Steels" to one client |
| calls | id, client\_id, audio\_url, audio\_hash, transcript, segments, created\_at | One row per voice note or call. Hash stops us transcribing the same file twice |
| orders | id, client\_id, item, spec, quantity, rate, delivery\_date, status | The current state of each order |
| order\_changes | id, order\_id, call\_id, field, old\_value, new\_value, clip\_start, clip\_end, confidence | Append-only history. Every change points to the call and the exact clip |
| pending\_confirmations | id, call\_id, extracted\_json, question, status | Items waiting for the owner's tap |
| reminders | id, order\_id, due\_at, sent | Delivery reminders and briefing items |

Orders are never edited without a matching row in order\_changes, so the audit trail is always complete.

## Evaluation

We build a test set of 20 to 30 synthetic calls once and run every change against it.  
**How the test set is made:** scripts written with the LLM (fake names and numbers), voiced with two Timbre Hinglish voices, then mixed with factory and traffic noise and squeezed to 8 kHz phone quality using ffmpeg. Noise mixing is local, so it costs no credits.  
**Cases covered:** simple new order, quantity change, rate change, date change, two items in one call, an ambiguous update, a noisy call.  
What we measure:

* Transcription error rate (WER) on clean vs noisy audio  
* Extraction accuracy: item, quantity, rate and date all correct  
* Matching accuracy: update linked to the right order  
* Confirmation rate: how often the system asks the owner  
* Time from voice note received to order on dashboard

Targets get set after the first run, once we know the baseline. The final numbers go in the demo and the write-up.

## Risks and mitigations

| Risk | Mitigation |
| :---- | :---- |
| Gnani credits run out faster than expected (rate is not published) | Measure on day 1 with one 30 s clip. Cache transcripts by audio hash, trim silence first, pre-render fixed Timbre phrases, mock APIs in tests |
| Morning briefing needs a paid WhatsApp template if the owner was silent for 24 h | Evening message ends with a one-tap reply that keeps the free window open |
| Service replies stop after 1,000 a month without a card | Hard daily send cap in code |
| Render cold start makes the first webhook fail | Return 200 instantly, process in background, ping every 10 min during demos |
| Evon won't run on free T4 GPUs | Keep Evon to the nightly summary only. Live extraction stays on Groq |
| Free LLM quota too small | Groq primary, Gemini Flash-Lite fallback, model name in one setting |
| Supabase pauses before judging (after 10 Nov) | Daily ping from GitHub Actions |
| WhatsApp live calling is hard to set up | Voice notes are the core. Live calls only if time is left |

## Timeline and team split

11 days to the deadline, so voice notes first and everything else after.

1. **30 Oct to 1 Nov:** Prisma + Timbre test and credit check, WhatsApp test number live, webhook echoes transcripts back, repo and DB set up  
2. **2 to 4 Nov:** extraction, order matching, owner confirmations, audio proof clips  
3. **5 to 6 Nov:** dashboard, client confirmation, morning briefing  
4. **7 Nov:** run the eval set, Evon nightly summary on Kaggle  
5. **8 to 9 Nov:** demo video (60 s cut too), write-up, final posts  
6. **10 Nov:** submit

| Person | Owns |
| :---- | :---- |
| Akshat | Prisma pipeline, extraction, order matching, eval set, Evon |
| Famous | Database, WhatsApp integration, dashboard, briefing and reminders |