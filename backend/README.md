# AutoPilot AI — Backend

FastAPI backend for the AutoPilot AI platform. See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
for the full design.

## Quickstart (development)

```bash
# from backend/
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate on Unix
pip install -e ".[dev]"

# copy environment template (from repo root)
cp ../.env.example ../.env

# run the API
uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health

## Quality gates

```bash
ruff check .        # lint
mypy app            # type-check (strict)
pytest              # tests
```

> A comprehensive README, Docker instructions, and the full guide set are
> delivered in later milestones (see the roadmap in the architecture doc).
