# Demo account provisioning

Requested demo users:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@citycare.demo` | `Admin@123` |
| Worker | `worker@citycare.demo` | `Worker@123` |
| Citizen | `citizen@citycare.demo` | `Citizen@123` |

These accounts are not provisioned in this workspace because no Supabase project credentials were supplied. The `Use demo account` action fills the login form; authentication still goes through Supabase Auth and checks the stored role. Running the provisioning script is a deliberate operation against the project configured in `.env`; it creates/updates only these named accounts and a small demo dataset. It does not reset data. Do not use these published passwords for real accounts.

After running the script, manually test sign-in, role mismatch, logout, and direct API access for each demo user. Revoke or rotate these credentials before public deployment.
