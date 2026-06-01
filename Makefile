.PHONY: help up down restart logs ps build verify queues smoke clean e2e e2e-fast

help:
	@echo "Multi-Agent RAG — see README.md, ARCHITECTURE.md, docs/PORTFOLIO.md"
	@echo "  make up        - build + start the full stack (detached)"
	@echo "  make down      - stop the stack (keep volumes)"
	@echo "  make clean     - stop the stack AND delete volumes"
	@echo "  make restart   - restart all services"
	@echo "  make logs      - tail logs for all services"
	@echo "  make ps        - show service status"
	@echo "  make verify    - check RabbitMQ queues + Prometheus targets"
	@echo "  make queues    - list declared RabbitMQ queues"
	@echo "  make smoke     - submit a test ingestion job via the API"
	@echo "  make e2e       - run full end-to-end + failure-simulation suite"
	@echo "  make e2e-fast  - run E2E suite, skipping the slow retry-exhaustion test"

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	docker compose down -v

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

queues:
	docker compose exec rabbitmq rabbitmqctl list_queues name durable arguments

verify:
	@echo "== RabbitMQ queues =="
	docker compose exec rabbitmq rabbitmqctl list_queues name messages durable
	@echo "== Prometheus targets =="
	curl -s http://localhost:9090/api/v1/targets | python3 -c "import sys,json;[print(t['labels']['job'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"

smoke:
	curl -s -X POST http://localhost:8000/ingest \
	  -H 'Content-Type: application/json' \
	  -d '{"document_uri":"s3://bucket/sample.pdf"}' | python3 -m json.tool

e2e:
	./scripts/e2e_test.sh

e2e-fast:
	RUN_SLOW=0 ./scripts/e2e_test.sh
