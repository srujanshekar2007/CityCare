# Supabase project setup

1. Create a dedicated Supabase project for CityCare.
2. Copy the project URL and public anon/publishable key to `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env`.
3. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and the **server-only** `SUPABASE_SERVICE_ROLE_KEY` for API and seed scripts. Keep service-role credentials out of browser bundles and source control.
4. Apply `supabase/migrations/202611230001_initial_schema.sql` to this empty project.
5. Set Auth site URL and allowed local/production redirect URLs. Enable email/password sign-in.
6. Run `node scripts/provision-demo.mjs` from the project root with server values available in environment.
7. Sign in separately with each role and confirm the corresponding profile role. Review storage and RLS using separate user sessions before exposing the project.

The migration is an initial schema, not a reviewed production security certification. Review Supabase SQL output and policies against the project's needs before launch. Never apply it to an unrelated project. The sample records contain fictional civic locations and are intended for a dedicated demo environment.
