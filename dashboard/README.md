# Dashboard

Not set up yet. Famous will scaffold this: Next.js on Vercel, reads Supabase directly.

Supabase is read only from Next.js server-side code (server components, route handlers) using the service key, never from the browser. RLS is on with no policies, so the anon key can't read anything.
