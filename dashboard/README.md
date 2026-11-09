# Recall dashboard

Next.js (App Router) + Tailwind. Read-only view of the order book, deployed on Vercel.

Supabase is read only from server components with the service key, never from the browser.
`lib/supabase.ts` imports `server-only`, so the build fails if it is ever pulled into client code.
RLS is on with no policies, so the anon key can't read anything.

## Pages

| Route | Shows |
| --- | --- |
| `/` | Deliveries today and tomorrow (IST), pending confirmations count, open orders |
| `/orders/[id]` | Order details and change history, each change with old → new and its proof clip |
| `/calls` | Latest 50 calls: client, time, audio, transcript |
| `/pending` | Pending confirmations: question, extracted item, candidate orders |

Every page re-renders on the server every 10 s (`components/AutoRefresh.tsx`). Refresh pauses
while the tab is hidden or any audio is playing.

## Audio

`calls.audio_url` holds an object path in the private `audio` bucket (a full Supabase Storage
URL also works). Pages sign those paths server side (1 h). A change's proof clip is the call
audio played from `clip_start` to `clip_end` (`components/AudioPlayer.tsx`), so no separate
clip files are needed.

## Run

```bash
cp .env.local.example .env.local   # fill SUPABASE_URL, SUPABASE_SERVICE_KEY
npm install
npm run dev                        # http://localhost:3000
npm run build && npm run lint      # production build, typecheck
```

## Deploy (Vercel Hobby)

Import the repo, set **Root Directory** to `dashboard`, and add `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY` and `SUPABASE_AUDIO_BUCKET` as environment variables (not `NEXT_PUBLIC_`).
