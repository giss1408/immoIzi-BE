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
