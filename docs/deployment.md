# Deployment checklist

- Deploy `apps/web` as a Vite static SPA; configure SPA fallback to `index.html`.
- Set frontend `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and API origin.
- Deploy `apps/api` to a Node.js host that runs a persistent Express server; bind `0.0.0.0` and use `PORT`.
- Set API Supabase URL/anon key, service-role key only if the separate provisioning utility runs there, and exact `WEB_ORIGIN`.
- Apply migrations to the intended Supabase project, enable email/password Auth, set allowed redirect URLs, and verify the private evidence bucket.
- Provision demo users only in a dedicated demo environment; test all three accounts and role access.
- Inspect Supabase RLS and Storage policies using distinct citizen, worker, and admin sessions.
- Configure TLS, production-safe logs, backups, and provider-appropriate health checks.
- Review current provider quotas, limits, and pricing before choosing a hosting tier; no free tier is guaranteed to remain free.
