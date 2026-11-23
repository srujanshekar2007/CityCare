<<<<<<< HEAD
# CityCare

CityCare is a civic issue reporting and resolution platform for citizens, one city administrator, and field workers. Citizens report a categorized issue with a description, photographs, and map coordinates. Administrators review reports and assign work; workers submit progress and resolution evidence; an administrator approves closure.

**Tagline:** Your City. Your Voice. A Better Tomorrow.

## Current implementation status

The independent foundation includes the React/TypeScript/Vite web app, Express/TypeScript REST API, original SVG brand assets, initial Supabase schema and row-level security, and setup documentation. With a configured Supabase project, the current app supports email/password sign-in, citizen issue submission with GPS/manual Leaflet location and private photo upload, citizen complaint lists, worker assignment-filtered task lists, and an admin complaint queue with live rows and status counts. Admin charts remain illustrative in preview mode. Full complaint detail and evidence review, worker task actions, notifications UI, zone/worker management screens, CSV reports, and complete analytics are still outstanding.

Supabase credentials were not available during implementation. Demo users have **not** been provisioned or tested, and the app will not authenticate those credentials until a project is configured and the provisioning script is run. The migration has not been applied or tested against a live Supabase project. See [Supabase setup](docs/supabase-setup.md).

## Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, React Router, Lucide, Recharts, Leaflet
- API: Node.js, Express, TypeScript, Zod
- Persistence/auth/storage: Supabase Auth, Postgres, Storage, RLS
- Maps: Leaflet + OpenStreetMap tiles

## Local development

Requirements: Node.js 20.19+ and npm. From the project root:

```sh
cp .env.example .env
npm install
npm run dev
```

Run the API separately with `npm run dev:api`. Add project-specific Supabase values to `.env` first. Never place the service-role key in a `VITE_` variable or commit it. The API health endpoint is `GET /health` on port 4000.

## Environment

`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are public client configuration values. `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are server-side configuration; only the API provisioning utilities may use the service role. `.env.example` contains placeholders.

## Database

Apply `supabase/migrations/202611230001_initial_schema.sql` to a fresh Supabase project using the Supabase CLI or SQL editor. It creates the three allowed roles, categories, complaint workflow tables, history, notifications, audit records, RLS policies, and a private evidence bucket. Details and known implementation limits are in [database and RLS notes](docs/database-and-rls.md).

## Demo accounts

The login page displays the requested demo credentials and explains that provisioning is required. Run `node scripts/provision-demo.mjs` only against a dedicated CityCare Supabase project with server credentials configured. It creates or updates the demo accounts and a small sample dataset; it does not reset or delete project data. Verify each login manually after provisioning. Credentials are documented in [demo provisioning](docs/demo-accounts.md).

## Deploy

The static Vite frontend can be deployed to Vercel or another static host. Deploy the Express API to a Node host such as Render. Configure CORS to the exact frontend origin, set server environment variables, apply migrations, and set Supabase Auth redirect URLs. Hosting plans and free-tier limits change; check provider terms before deployment. A deployment checklist is in [deployment](docs/deployment.md).

## API

Initial endpoints: `GET /health`, `GET /api/me`, `GET /api/complaints`, `POST /api/complaints`, and `PATCH /api/complaints/:id/status`. Authenticated endpoints verify the Supabase JWT, read role from the database, validate request bodies with Zod, and rely on RLS for data access. See [API notes](docs/api.md).

## Brand assets

Original SVG assets live in `assets/brand/` and are copied into the web public directory: wordmark, icon, dark-background wordmark, and favicon. The mark combines a location pin, city skyline, and completion check.

## Future enhancements

Complete citizen reporting with map selection and private image upload, build full admin and worker workflows, connect all dashboard metrics to Supabase queries, add responsive complaint mapping and CSV export, and verify role/ownership policies with a configured project. AI features are intentionally postponed.
=======
# CityCare
>>>>>>> origin/main
