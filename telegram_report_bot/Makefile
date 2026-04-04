PYTHON ?= python3

.PHONY: test build up down logs

test:
	$(PYTHON) -m unittest discover -s tests -v

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f bot postgres
