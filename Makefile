.PHONY: up down logs logs-worker shell-db deploy-flows run-light run-heavy reset help

help:
	@echo "Available targets:"
	@echo "  up            - Start all services"
	@echo "  down          - Stop all services"
	@echo "  logs          - Tail logs from all services"
	@echo "  logs-worker   - Tail logs from prefect-worker only"
	@echo "  shell-db      - Open psql shell in postgres container"
	@echo "  deploy-flows  - Register flows in Prefect"
	@echo "  run-light     - Run light pipeline manually"
	@echo "  run-heavy     - Run heavy pipeline manually"
	@echo "  reset         - Stop, remove volumes, and restart"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

logs-worker:
	docker compose logs -f prefect-worker

shell-db:
	docker compose exec postgres psql -U $${POSTGRES_USER:-adipa} -d $${POSTGRES_DB:-adipa_db}

deploy-flows:
	docker compose restart prefect-worker

run-light:
	docker compose exec prefect-worker python -c "from light_pipeline import fetch_exchange_rates; fetch_exchange_rates()"

run-heavy:
	docker compose exec prefect-worker python -c "from heavy_pipeline import run_heavy_pipeline; run_heavy_pipeline()"

reset:
	docker compose down -v
	docker compose up -d --build
