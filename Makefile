.PHONY: install dev run sample migrate migrate-dump thumbnails build deploy clean help

# Python executable detection
PYTHON := $(shell command -v python3 2> /dev/null || echo python)
VENV_PIP := ./venv/bin/pip
VENV_PYTHON := ./venv/bin/python
VENV_FLASK := ./venv/bin/flask
VENV_GUNICORN := ./venv/bin/gunicorn

# Default target
help:
	@echo "Příroda Olomouckého Kraje Kiosk - Build Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install    - Create venv and install dependencies"
	@echo "  make dev        - Run Flask development server"
	@echo "  make run        - Run with Gunicorn (production)"
	@echo ""
	@echo "Data:"
	@echo "  make sample     - Generate sample data for testing"
	@echo "  make migrate    - Run interactive data migration"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy     - Deploy to Raspberry Pi via rsync"
	@echo "  make clean      - Remove cache files"

# Development
install:
	$(PYTHON) -m venv venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt

dev:
	FLASK_ENV=development FLASK_APP=server.app $(VENV_FLASK) run --host=0.0.0.0 --port=5000

run:
	$(VENV_GUNICORN) -w 2 -b 0.0.0.0:5000 server.app:app

# Data migration
sample:
	$(VENV_PYTHON) scripts/migrate-data.py sample -o ./data

migrate:
	@echo "Interactive migration not yet implemented."
	@echo "Use one of:"
	@echo "  make sample                                    - Generate sample data"
	@echo "  $(VENV_PYTHON) scripts/migrate-data.py dump -f /path/to/dump.sql"
	@echo "  $(VENV_PYTHON) scripts/migrate-data.py db -u root -d olomouc"

migrate-dump:
	@if [ -z "$(DUMP)" ]; then echo "Usage: make migrate-dump DUMP=/path/to/file.sql"; exit 1; fi
	$(VENV_PYTHON) scripts/migrate-data.py dump -f $(DUMP) -o ./data

# Image processing
thumbnails:
	$(VENV_PYTHON) scripts/generate-thumbnails.py

# Deployment
deploy:
	rsync -avz --delete \
		--exclude 'venv' \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude '.git' \
		./ pi@kiosk:/home/pi/priroda-kiosk/

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
