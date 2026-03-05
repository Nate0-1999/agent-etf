# Migrations

SQL migrations in this folder are applied in lexical order by:

```bash
make migrate
```

`DATABASE_URL` must point at a reachable Postgres instance before running migrations.
