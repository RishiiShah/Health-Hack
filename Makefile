.PHONY: backend web backend-test

PYTHON ?= backend/.venv/bin/python

# The API on http://localhost:8000 against the production database and accounts in the root .env. No Docker.
backend:
	cd backend && ../$(PYTHON) -m app

# The web app on http://localhost:5173; Vite forwards API calls to the backend above.
web:
	cd web && npm run dev

# Tests use a disposable local PostgreSQL (CC_TEST_DATABASE_URL), never the production database.
backend-test:
	cd backend && ../$(PYTHON) -m pytest -q
