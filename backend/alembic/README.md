# Alembic migrations

Async migration environment for AutoPilot AI.

```bash
# from backend/
alembic revision --autogenerate -m "describe change"   # generate
alembic upgrade head                                    # apply
alembic downgrade -1                                    # roll back one
```

The database URL is taken from application settings (`app.core.config`), not from
`alembic.ini`.
