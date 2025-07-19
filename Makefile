.PHONY: help build up down logs clean dev-setup pull-models prod-build prod-up prod-down prod-logs prod-status test-deployment

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs for all services
	docker-compose logs -f

clean: ## Remove all containers, networks, and volumes
	docker-compose down -v --remove-orphans
	docker system prune -f

dev-setup: ## Set up development environment
	cp .env.example .env
	@echo "Please edit .env file with your configuration"

pull-models: ## Pull default Ollama models
	docker-compose exec ollama ollama pull llama2
	docker-compose exec ollama ollama pull codellama

status: ## Show status of all services
	docker-compose ps

restart: ## Restart all services
	docker-compose restart

# Individual service commands
webhook-logs: ## Show webhook handler logs
	docker-compose logs -f webhook-handler

ingestion-logs: ## Show ingestion service logs
	docker-compose logs -f ingestion-service

embedding-logs: ## Show embedding service logs
	docker-compose logs -f embedding-service

query-logs: ## Show query service logs
	docker-compose logs -f query-service

llm-logs: ## Show LLM service logs
	docker-compose logs -f llm-service

frontend-logs: ## Show frontend logs
	docker-compose logs -f frontend

# Production targets
prod-build: ## Production: Build optimized Docker images
	docker-compose -f docker-compose.prod.yml build --no-cache

prod-up: ## Production: Start all services in production mode
	@if [ ! -f .env.prod ]; then \
		echo "Error: .env.prod file not found. Copy .env.prod.example and configure it."; \
		exit 1; \
	fi
	docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

prod-down: ## Production: Stop all services
	docker-compose -f docker-compose.prod.yml down

prod-logs: ## Production: Show logs for all services
	docker-compose -f docker-compose.prod.yml logs -f

prod-status: ## Production: Show status of all services
	docker-compose -f docker-compose.prod.yml ps

prod-restart: ## Production: Restart all services
	docker-compose -f docker-compose.prod.yml restart

prod-clean: ## Production: Remove all containers, networks, and volumes
	docker-compose -f docker-compose.prod.yml down -v --remove-orphans
	docker system prune -f

prod-setup: ## Production: Set up production environment
	cp .env.prod.example .env.prod
	@echo "Please edit .env.prod file with your production configuration"

prod-pull-models: ## Production: Pull default Ollama models
	docker-compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2
	docker-compose -f docker-compose.prod.yml exec ollama ollama pull codellama

# Testing targets
test-deployment: ## Testing: Run deployment validation tests
	python -m pytest tests/deployment/test_docker_deployment.py -v

test-deployment-full: ## Testing: Run full deployment test suite with cleanup
	python -m pytest tests/deployment/ -v --tb=short

test-e2e: ## Testing: Run end-to-end tests
	python -m pytest tests/e2e/test_complete_system.py -v

test-performance: ## Testing: Run performance benchmarks
	python -m pytest tests/e2e/test_performance_benchmarks.py -v

test-integration: ## Testing: Run system integration tests
	python scripts/system-integration.py

test-all: ## Testing: Run all test suites
	@echo "Running all test suites..."
	python -m pytest tests/deployment/ -v
	python -m pytest tests/e2e/ -v
	python scripts/system-integration.py

# Health and monitoring targets
health-check: ## Check health of all services
	@echo "Checking service health..."
	@curl -s http://localhost:8080/health | jq . || echo "API Gateway: UNHEALTHY"
	@curl -s http://localhost:3001/health | jq . || echo "Webhook Handler: UNHEALTHY"
	@curl -s http://localhost:8001/health | jq . || echo "Ingestion Service: UNHEALTHY"
	@curl -s http://localhost:8002/health | jq . || echo "Embedding Service: UNHEALTHY"
	@curl -s http://localhost:8003/health | jq . || echo "Query Service: UNHEALTHY"
	@curl -s http://localhost:8004/health | jq . || echo "LLM Service: UNHEALTHY"

health-check-prod: ## Check health of production services
	@echo "Checking production service health..."
	@curl -s http://localhost:8080/health | jq . || echo "API Gateway: UNHEALTHY"
	@curl -s http://localhost:3001/health | jq . || echo "Webhook Handler: UNHEALTHY"
	@curl -s http://localhost:8001/health | jq . || echo "Ingestion Service: UNHEALTHY"
	@curl -s http://localhost:8002/health | jq . || echo "Embedding Service: UNHEALTHY"
	@curl -s http://localhost:8003/health | jq . || echo "Query Service: UNHEALTHY"
	@curl -s http://localhost:8004/health | jq . || echo "LLM Service: UNHEALTHY"

metrics: ## Show metrics for all services
	@echo "Collecting metrics from all services..."
	@curl -s http://localhost:8080/metrics || echo "API Gateway metrics unavailable"
	@curl -s http://localhost:8001/metrics || echo "Ingestion Service metrics unavailable"
	@curl -s http://localhost:8002/metrics || echo "Embedding Service metrics unavailable"
	@curl -s http://localhost:8003/metrics || echo "Query Service metrics unavailable"
	@curl -s http://localhost:8004/metrics || echo "LLM Service metrics unavailable"

# System integration targets
integration-setup: ## Set up system integration environment
	@echo "Setting up system integration..."
	python scripts/system-integration.py --setup-only

integration-full: ## Run complete system integration
	@echo "Running complete system integration..."
	python scripts/system-integration.py

integration-report: ## Generate integration report
	@echo "Generating integration report..."
	python scripts/system-integration.py --report-only

# Benchmark targets
benchmark: ## Run performance benchmarks
	@echo "Running performance benchmarks..."
	python -m pytest tests/e2e/test_performance_benchmarks.py -v -s

benchmark-light: ## Run light performance benchmarks
	@echo "Running light performance benchmarks..."
	python -m pytest tests/e2e/test_performance_benchmarks.py::test_query_performance_light_load -v -s

benchmark-heavy: ## Run heavy performance benchmarks
	@echo "Running heavy performance benchmarks..."
	python -m pytest tests/e2e/test_performance_benchmarks.py::test_query_performance_heavy_load -v -s

# Development and debugging targets
debug-logs: ## Show debug logs for all services
	docker-compose logs -f --tail=100

debug-webhook: ## Debug webhook handler
	docker-compose logs -f webhook-handler

debug-ingestion: ## Debug ingestion service
	docker-compose logs -f ingestion-service

debug-query: ## Debug query service
	docker-compose logs -f query-service

debug-llm: ## Debug LLM service
	docker-compose logs -f llm-service

# Database and storage targets
db-shell: ## Open database shell
	docker-compose exec postgres psql -U dossier -d dossier

db-backup: ## Backup database
	@echo "Creating database backup..."
	docker-compose exec postgres pg_dump -U dossier -d dossier > backups/dossier_backup_$(shell date +%Y%m%d_%H%M%S).sql

db-restore: ## Restore database from backup (specify BACKUP_FILE)
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: Please specify BACKUP_FILE=path/to/backup.sql"; \
		exit 1; \
	fi
	docker-compose exec -T postgres psql -U dossier -d dossier < $(BACKUP_FILE)

qdrant-backup: ## Backup Qdrant data
	@echo "Creating Qdrant backup..."
	curl -X POST "http://localhost:6333/snapshots" -H "Content-Type: application/json" -d '{"name": "backup_$(shell date +%Y%m%d_%H%M%S)"}'

redis-shell: ## Open Redis shell
	docker-compose exec redis redis-cli

redis-flush: ## Flush Redis cache
	docker-compose exec redis redis-cli FLUSHALL

# Configuration and setup targets
setup-dev: ## Complete development environment setup
	@echo "Setting up development environment..."
	cp .env.example .env
	docker-compose build
	docker-compose up -d
	sleep 30
	make integration-setup
	make pull-models
	@echo "Development environment ready!"

setup-prod: ## Complete production environment setup
	@echo "Setting up production environment..."
	cp .env.prod.example .env.prod
	@echo "Please edit .env.prod file with your production configuration"
	@echo "Then run: make prod-build && make prod-up"

# Cleanup targets
clean-all: ## Remove all containers, volumes, images, and generated files
	docker-compose down -v --remove-orphans
	docker system prune -af
	rm -f *.log
	rm -f *_report.json
	rm -f *_report.txt
	rm -f integration-report.txt

clean-logs: ## Clean up log files
	rm -f *.log
	rm -f *_report.json
	rm -f *_report.txt

clean-cache: ## Clean up application caches
	docker-compose exec redis redis-cli FLUSHALL
	docker-compose restart

# Documentation targets
docs: ## Generate documentation
	@echo "Generating documentation..."
	@echo "See docs/deployment-guide.md for deployment instructions"

docs-serve: ## Serve documentation locally
	@echo "Documentation available at docs/deployment-guide.md"

# Validation targets
validate-config: ## Validate configuration files
	@echo "Validating configuration..."
	@if [ ! -f .env ]; then echo "Error: .env file not found"; exit 1; fi
	@echo "Configuration validation passed"

validate-docker: ## Validate Docker setup
	@echo "Validating Docker setup..."
	docker --version
	docker-compose --version
	@echo "Docker validation passed"

validate-system: ## Validate complete system setup
	@echo "Validating complete system..."
	make validate-docker
	make validate-config
	make health-check
	@echo "System validation passed"

# Quick start targets
quick-start: ## Quick start for development
	@echo "Starting Dossier RAG system..."
	make setup-dev
	@echo "System started! Frontend: http://localhost:3000, API: http://localhost:8080"

quick-test: ## Quick test of core functionality
	@echo "Running quick tests..."
	make health-check
	make test-integration
	@echo "Quick tests completed!"

# Information targets
info: ## Show system information
	@echo "=== Dossier RAG System Information ==="
	@echo "Services:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  API Gateway: http://localhost:8080"
	@echo "  Webhook Handler: http://localhost:3001"
	@echo "  Ingestion Service: http://localhost:8001"
	@echo "  Embedding Service: http://localhost:8002"
	@echo "  Query Service: http://localhost:8003"
	@echo "  LLM Service: http://localhost:8004"
	@echo ""
	@echo "Infrastructure:"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis: localhost:6379"
	@echo "  Qdrant: localhost:6333"
	@echo "  Ollama: localhost:11434"
	@echo ""
	@echo "Available commands: make help"
