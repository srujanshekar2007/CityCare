# Demo account verification

CityCare's demo accounts are managed in Supabase Authentication and must have matching rows in `public.profiles` with roles `admin`, `worker`, and `citizen`. Passwords are not stored in this repository or displayed by the login page.

To verify an account, open Supabase Dashboard → Authentication → Users, search by its email, and confirm the email is verified. Then check the corresponding `public.profiles` row and test the account through the deployed login form. Do not recreate an account when an Auth user already exists.

The server-side provisioning scripts read passwords from environment variables when explicitly run. Keep those values in a trusted local/server environment and never place them in frontend variables or source control.
