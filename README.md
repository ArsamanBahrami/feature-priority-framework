# Feature Priority Framework MVP

This is a lightweight internal app for submitting, scoring, ranking, and managing feature requests.

## What it does

- saves feature requests in SQLite locally or Postgres in production
- supports create, edit, and delete
- automatically calculates a priority score
- includes status management and simple filters
- includes login, role-based access, and admin-managed team accounts
- supports optional Microsoft SSO via Microsoft Entra ID
- serves a plain web UI that the team can access on your internal network

## Run it locally

```bash
APP_ADMIN_EMAIL=you@company.com APP_ADMIN_PASSWORD='change-me-now' python3 app.py
```

Then open:

`http://localhost:8000`

If you do not set `APP_ADMIN_PASSWORD` on the first run, the app will generate a temporary admin password and print it in the terminal.

## Files

- `app.py`: HTTP server, API, SQLite setup, auth, sessions
- `app.py`: HTTP server, API, SQLite/Postgres setup, auth, sessions, Microsoft SSO
- `index.html`: app UI
- `styles.css`: visual design
- `script.js`: frontend behavior
- `feature_priority.db`: SQLite database created on first run for local use
- `.app_secret`: local signing secret created on first run unless `APP_SECRET` is set

## Notes

- The database is seeded with a couple of sample features the first time it starts.
- For team access, run this on a machine or internal server your colleagues can reach, then point them to that host and port.
- Roles:
  - `admin`: manage users and all features
  - `editor`: create, edit, and delete features
  - `viewer`: read-only access
- Use the admin panel in the app to create teammate accounts.

## Deployment Notes

- Set `APP_HOST=0.0.0.0` to expose the server on your internal network.
- Set `APP_PORT` if `8000` is already in use.
- Render sets `PORT` automatically; the app now supports that directly.
- Set a stable `APP_SECRET` in production so session cookies remain valid across restarts.
- Put this behind your normal internal reverse proxy when you deploy it for the team.

## Render + Supabase

This app is ready to run on Render with Supabase Postgres.

### What to set in Render

- `DATABASE_URL`
- `APP_SECRET`
- `APP_ADMIN_EMAIL`
- `APP_ADMIN_PASSWORD`

### Which Supabase connection string to use

Use the Supabase **session pooler** or another pooled connection string for application traffic.

### Start command

Render can use:

```bash
python app.py
```

The included `render.yaml` also provides a simple starting point if you want to deploy from a repo.

## Microsoft SSO

This app can use Microsoft Entra ID for sign-in while keeping the rest of the app unchanged.

### Render environment variables

- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_TENANT_ID`
- `MICROSOFT_ALLOWED_DOMAINS`
- `MICROSOFT_AUTO_PROVISION`
- `MICROSOFT_DEFAULT_ROLE`
- Optional: `MICROSOFT_REDIRECT_URI`

### Recommended values

- `MICROSOFT_TENANT_ID`: your Entra tenant ID or `organizations`
- `MICROSOFT_ALLOWED_DOMAINS`: your company domain, for example `example.com`
- `MICROSOFT_AUTO_PROVISION`: `true`
- `MICROSOFT_DEFAULT_ROLE`: `viewer`

### Microsoft Entra app registration

Create a Web app registration and add this redirect URI:

```text
https://your-render-app.onrender.com/api/auth/callback/microsoft
```

For local development, you can use:

```text
http://localhost:8000/api/auth/callback/microsoft
```
