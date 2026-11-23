# REST API (initial)

Base URL defaults to `http://localhost:4000`. Protected routes require `Authorization: Bearer <Supabase access token>`. The API verifies the token, loads the profile role from Supabase, and uses the user JWT for database requests so RLS remains active.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/api/me` | Current user and profile |
| GET | `/api/complaints?status=&limit=` | List rows allowed by RLS |
| POST | `/api/complaints` | Citizen complaint creation (category, description, coordinates, location description required) |
| POST | `/api/complaints/:id/assign` | Administrator assigns or reassigns a verified complaint through a database RPC |
| PATCH | `/api/complaints/:id/status` | Admin review and worker progress update |

Responses avoid returning Supabase internal errors. The endpoint set is intentionally incomplete; image signing, worker and zone management screens, CSV reporting, registration, and password recovery still need implementation.
