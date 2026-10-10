.PHONY: backend backend-down backend-account backend-test

COMPOSE = docker compose -f deploy/local.compose.yaml
PYTHON ?= python3

# First run asks for a local account. Later runs reuse its hash and signing key.
backend:
	$(PYTHON) scripts/setup_auth.py
	$(COMPOSE) up --build

backend-down:
	$(COMPOSE) down

backend-account:
	$(PYTHON) scripts/setup_auth.py --add-user
	@echo "Restart the backend to load the account: docker compose -f deploy/local.compose.yaml restart backend"

backend-test:
	$(COMPOSE) run --build --rm -T tests
