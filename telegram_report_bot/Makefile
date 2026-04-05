PYTHON ?= python3

.PHONY: test build up down logs run-web

test:
	$(PYTHON) -m unittest discover -s tests -v

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f bot web postgres caddy

run-web:
	uvicorn employee_report_bot.web:create_app --factory --host 0.0.0.0 --port 8000 --reload
