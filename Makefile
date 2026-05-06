.PHONY: up down logs logs-worker shell-db deploy-flows run-light run-heavy reset check help

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
	@echo "  check         - Verify all services are healthy"

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

check:
	@echo "==> Container health"
	@docker compose ps
	@echo ""
	@echo "==> Prefect API"
	@docker compose exec -T prefect-worker python -c \
	  "import urllib.request; r = urllib.request.urlopen('http://prefect-server:4200/api/health'); print('Prefect:', r.status)"
	@echo ""
	@echo "==> Heavy worker"
	@docker compose exec -T heavy-worker python -c \
	  "import urllib.request; r = urllib.request.urlopen('http://localhost:8000/health'); print('Heavy worker:', r.status)"
	@echo ""
	@echo "==> Database row counts"
	@docker compose exec -T postgres psql -U $${POSTGRES_USER:-adipa} -d $${POSTGRES_DB:-adipa_db} -c \
	  "SELECT 'exchange_rates' AS table, COUNT(*) FROM exchange_rates UNION ALL \
	   SELECT 'courses', COUNT(*) FROM courses UNION ALL \
	   SELECT 'course_prices', COUNT(*) FROM course_prices UNION ALL \
	   SELECT 'price_alerts', COUNT(*) FROM price_alerts;"
