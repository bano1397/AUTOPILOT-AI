.PHONY: check check-backend check-frontend check-e2e check-docs diagrams install-hooks

# The exact gates CI runs (.github/workflows/ci.yml). Keep the two in sync:
# if a gate is added here, add it there too.
check: check-backend check-frontend check-e2e check-docs

check-backend:
	cd backend && ruff check . && mypy app && pytest

check-frontend:
	cd frontend && npm run lint && npm run type-check && npm run build

# Playwright starts its own backend + frontend on dedicated ports (8100/3100),
# using the stub providers, so this needs no model server and no network.
check-e2e:
	cd frontend && npm run test:e2e

# Diagram sources are derived from the markdown; this catches drift.
check-docs:
	python3 scripts/export-diagrams.py --check

diagrams:
	python3 scripts/export-diagrams.py

# Installs a pre-push hook that runs `make check`. Phase 0 of the completion
# plan existed because a refactor landed on main without the suite being run.
install-hooks:
	@printf '#!/bin/sh\nexec make check\n' > .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "pre-push hook installed (runs 'make check'); bypass with --no-verify"
