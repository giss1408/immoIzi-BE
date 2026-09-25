# immoizi backend

## Local development

```bash
cd immoizi
python manage.py migrate
python manage.py runserver
```

By default the project uses local SQLite at `immoizi/db.sqlite3`.

## Neon/Postgres database

Set `DATABASE_URL` in `immoizi/.env` to use an external Postgres database such as Neon:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Then run migrations against the configured database:

```bash
cd immoizi
python manage.py migrate
```

Useful production database settings:

```env
DATABASE_CONN_MAX_AGE=60
DATABASE_CONN_HEALTH_CHECKS=True
```

Keep `.env` private. Use `.env.example` as the shared template.

## Languages

The backend supports French and English through Django internationalization.

```env
LANGUAGE_CODE=fr
```

Supported language codes:

- `fr` for French
- `en` for English

Clients can send the `Accept-Language` HTTP header, for example `fr` or `en`, or use Django's `/i18n/setlang/` endpoint when session-based language switching is needed.

## Deploy on Render

The repository contains a Render Blueprint (`render.yaml`) that creates the
`immoizi-backend` web service (free plan, Frankfurt), built with `build.sh`
(install, `collectstatic`, `migrate`, optional demo seed) and served by gunicorn.
It uses an existing PostgreSQL database that you provide through `DATABASE_URL`.

Steps:

1. In the Render dashboard choose **New → Blueprint** and select this repository.
2. Fill in the secret values Render asks for:
   - `DATABASE_URL`: your PostgreSQL connection string. For a Render database,
     copy its **Internal Database URL** (the database must be in the same
     region as the service, Frankfurt); for Neon or another provider, use the
     external URL with `?sslmode=require`.
   - `DEMO_PASSWORD`: password for the `landlord_demo`, `tenant_demo` and
     `seeker_demo` accounts created by `seed_demo_data`
   - `CLOUDINARY_URL` (recommended): `cloudinary://<api_key>:<api_secret>@<cloud_name>`.
     Without it, uploaded photos and videos are lost on every deploy.
3. Apply. The API is then available at `https://<service>.onrender.com/graphql`,
   with a health check at `/healthz`.

Set `SEED_DEMO_DATA=False` for a real (non-test) environment.

Notes:

- The free web service sleeps after 15 minutes without traffic; the first
  request afterwards can take up to a minute.
- Render's free PostgreSQL expires after 30 days; Neon's free tier does not.
- To get a Django admin account (`/admin/`), add `DJANGO_SUPERUSER_USERNAME`,
  `DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` to the service's
  environment and redeploy; `build.sh` creates it once.

