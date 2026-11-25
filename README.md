# CityCare

CityCare is a civic complaint reporting and resolution platform for citizens, administrators, and field workers. This repository contains a React client, an authenticated Express API, Supabase integration, and an optional standalone Python intelligence service.

## Architecture

- `apps/web`: React 19, TypeScript, Vite, React Router, Recharts, Leaflet and the Supabase publishable client.
- `apps/api`: Express 5 and TypeScript. It verifies Supabase access tokens, reads the user's profile role, and uses a publishable Supabase client with the caller's JWT so database permissions remain enforced by RLS.
- `ml-service`: FastAPI NLP and geospatial analysis. The Express API is the only application integration path to its protected analysis endpoints.
- Supabase: Authentication, PostgreSQL, Storage and Row Level Security.

The Python service is independently deployable. Adding it to the repository does not deploy it to Vercel. If the service is unavailable or not configured, existing complaint submission remains available and intelligence calls return a service-unavailable response.

## Database notes

The checked-in initial migration represents an earlier schema snapshot and is not authoritative for an already configured CityCare project. Existing app code and the project owner's verified live schema information indicate that `workers` uses `id`, `profile_id`, `zone_id`, `specialization`, `availability`, and `created_at`; category and zone activation use `is_active`; and assignments use `worker_id` plus the statuses `assigned`, `accepted`, `in_progress`, `submitted`, `completed`, and `reassigned`. Complaint analytics use the available complaint timestamps, `deadline`, coordinates, category and zone references, and `complaint_updates` history. Verify live foreign keys and RLS in Supabase before applying any migration. This intelligence upgrade does not change database schema, policies, or data.

## Local setup

Requirements: Node.js/npm and Python 3.9 or newer. Configure the existing frontend and API environment files using the examples, then start each service in a separate terminal from the repository root.

```sh
npm install
npm run dev
npm run dev:api
```

The web client defaults to `http://localhost:5173`; Express defaults to `http://localhost:4000`.

### Environment variables

Frontend (`apps/web/.env`):

- `VITE_SUPABASE_URL`: Supabase project URL.
- `VITE_SUPABASE_PUBLISHABLE_KEY`: publishable/anon key. Never put a secret or service-role key in a `VITE_` variable.
- `VITE_API_URL`: Express base URL, normally `http://localhost:4000`.

Express (`apps/api/.env`):

- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`: server-side token validation and caller-scoped RLS queries.
- `PORT`, `WEB_ORIGIN`: API port and exact allowed browser origin.
- `ML_SERVICE_URL`: FastAPI base URL, normally `http://127.0.0.1:8001`.
- `ML_SERVICE_TOKEN`: shared server-to-server bearer secret. Generate a private value, for example `openssl rand -hex 32`; set the same value in the Python environment. Do not use it in frontend configuration.
- `ML_REQUEST_TIMEOUT_MS`, `ML_MAX_CANDIDATES`: bounded API timeout and candidate count.

Python (`ml-service/.env`): copy `ml-service/.env.example`, set the same private `ML_SERVICE_TOKEN`, and adjust model settings as documented in [ml-service/README.md](ml-service/README.md). Local Python binds to loopback by default. For a remote deployment, set appropriate host/network restrictions and a trusted secret manager.

All actual `.env` files are ignored by Git. The committed examples contain placeholders only.

## Start Python intelligence locally

In another terminal:

```sh
cd ml-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Put a private ML_SERVICE_TOKEN in ml-service/.env and apps/api/.env
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

The service does not need database credentials and does not connect to Supabase. Express retrieves only caller-visible records and forwards a bounded, minimized payload.

## Build and verification

```sh
npm run build
ml-service/.venv/bin/python -m pytest -q ml-service/tests
ml-service/.venv/bin/python ml-service/scripts/run_evaluation.py
git diff --check
```

The committed evaluation artifact comes from a manually labeled fictional demonstration set. Its metrics are resubstitution results and do not predict performance on real complaint data. Real evaluation requires privacy-reviewed, representative complaint pairs labeled by authorized reviewers.

## Deployment

Deploy the static frontend, Express API, and Python service separately. Configure `VITE_API_URL` in the frontend build environment; set Supabase and intelligence variables only on the API host; set `ML_SERVICE_TOKEN` on both server hosts; configure `WEB_ORIGIN` to the exact deployed client origin. Restrict the Python service to network access from the API and use TLS for remote service-to-service traffic. Configure Supabase Auth redirects and verify deployed RLS policies separately. A Vercel frontend deployment alone does not host the Express or Python services.

## Privacy and operation

Duplicate analysis is advisory; it never merges, deletes, rejects or updates complaints. Admin analysis and hotspots use records visible to the current user under Supabase RLS. Citizen duplicate comparison is likewise limited to rows visible to that user's RLS policies. The Python API is protected by a server-to-server token and must not be exposed as an unauthenticated public service. No citizen names, contact details, evidence images, or credentials are included in intelligence payloads or routine service logs.

## Known limits

- The default semantic Sentence Transformers model is disabled; lexical analysis remains available. Enabling semantic embeddings may require downloading model weights and extra dependencies.
- Duplicate comparisons are bounded to recent RLS-visible records; responses report when the configured candidate cap is reached.
- Hotspot results reflect only geocoded records visible to the administrator and are bounded by the API request limit.
- Duplicate analysis history is session-only. Persistent analysis history would require a separately reviewed schema change, which this task does not make.
- End-to-end Supabase, deployed Vercel, cross-service network, and role session behavior require configured project credentials and deployment access; local unit/build checks do not establish those results.
