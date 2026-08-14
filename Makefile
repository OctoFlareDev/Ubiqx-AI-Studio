PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
API_APP_DIR := apps/api

.PHONY: install install-api install-web dev-api dev-web test test-api test-e2e contract build

install: install-api install-web

install-api:
	$(PIP) install -r $(API_APP_DIR)/requirements.txt

install-web:
	npm install

dev-api:
	$(PYTHON) -m uvicorn app.main:app --app-dir $(API_APP_DIR) --reload --port 8000

dev-web:
	npm run dev:web

test: test-api

test-api:
	$(PYTHON) -m pytest $(API_APP_DIR)/tests -q

contract:
	$(PYTHON) scripts/generate_contract.py

test-e2e:
	npm run test:e2e

build:
	npm run build:web

