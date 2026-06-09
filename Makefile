# ==============================================================================
# NormaCore — Makefile
# Works on: Linux, macOS, Windows (via WSL)
# Supports: CPU-only and NVIDIA GPU hosts
# ==============================================================================

SCRIPTS_DIR := scripts

DETECT_GPU     := $(SCRIPTS_DIR)/detect_gpu.sh
DETECT_COMPOSE := $(SCRIPTS_DIR)/detect_compose.sh
CHECK_PREREQS  := $(SCRIPTS_DIR)/check_prerequisites.sh
DETECT_RUNTIME := $(SCRIPTS_DIR)/detect_container_runtime.sh

# Ensure scripts are executable
$(shell chmod +x $(SCRIPTS_DIR)/*.sh $(SCRIPTS_DIR)/lib/*.sh 2>/dev/null)

.DEFAULT_GOAL := help

# ==============================================================================
# Help
# ==============================================================================

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Setup
# ==============================================================================

setup: ## One-time dev environment setup (uv sync, secrets baseline, pre-commit)
	cp .env.example .env
	cp compose.override.example.yaml compose.override.yaml
	uv sync --group dev
	uv run detect-secrets scan > .secrets.baseline
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

check: ## Verify all prerequisites are met
	@$(CHECK_PREREQS)

# ==============================================================================
# Compose
# ==============================================================================

compose: check ## Auto-detect GPU and start containers
	@PROFILE=$$($(DETECT_GPU)) && \
	COMPOSE=$$($(DETECT_COMPOSE)) && \
	RUNTIME=$$($(DETECT_RUNTIME)) && \
	[ "$$PROFILE" = "gpu" ] && PROFILE="$${PROFILE}-$${RUNTIME}" ; \
	echo "Starting with profile: $$PROFILE" && \
	$$COMPOSE -f compose.yaml --profile $$PROFILE up -d

compose-dev: check ## Start containers in dev mode with exposed ports (Auto-detect GPU)
	@PROFILE=$$($(DETECT_GPU)) && \
	COMPOSE=$$($(DETECT_COMPOSE)) && \
	RUNTIME=$$($(DETECT_RUNTIME)) && \
	echo "Starting in dev mode (ports exposed) and with profile: $$PROFILE" && \
	$$COMPOSE -f compose.yaml -f compose.override.yaml --profile $$PROFILE up -d

compose-cpu: check ## Force CPU mode regardless of hardware
	@COMPOSE=$$($(DETECT_COMPOSE)) && \
	echo "Starting in CPU mode..." && \
	$$COMPOSE -f compose.yaml --profile cpu up -d

compose-gpu: check ## Force GPU mode (requires NVIDIA drivers + container toolkit)
	@COMPOSE=$$($(DETECT_COMPOSE)) && \
	RUNTIME=$$($(DETECT_RUNTIME)) && \
	PROFILE="gpu-$${RUNTIME}" && \
	echo "Starting in GPU mode ($$PROFILE)..." && \
	$$COMPOSE -f compose.yaml --profile $$PROFILE up -d

compose-down: ## Stop all containers
	@COMPOSE=$$($(DETECT_COMPOSE)) && \
	$$COMPOSE -f compose.yaml --profile cpu --profile gpu-docker --profile gpu-podman \
	    down --remove-orphans

compose-logs: ## Tail container logs (usage: make compose-logs log=ollama-container tail=50)
	@COMPOSE=$$($(DETECT_COMPOSE)) && \
	$$COMPOSE -f compose.yaml logs -f --tail $${tail:-50} $(log)

compose-ps: ## Show running containers
	@COMPOSE=$$($(DETECT_COMPOSE)) && \
	$$COMPOSE -f compose.yaml ps

# ==============================================================================
# Model Management
# ==============================================================================

model-pull: ## Pull a model into Ollama (usage: make model-pull model=bge-m3)
	@RUNTIME=$$($(DETECT_RUNTIME)) && \
	$$RUNTIME exec ollama-container ollama pull $(model)

model-list: ## List installed models
	@RUNTIME=$$($(DETECT_RUNTIME)) && \
	$$RUNTIME exec ollama-container ollama list

model-rm: ## Remove a model (usage: make model-rm model=bge-m3)
	@RUNTIME=$$($(DETECT_RUNTIME)) && \
	$$RUNTIME exec ollama-container ollama rm $(model)

# ==============================================================================
# Development
# ==============================================================================

run: ## Start the API server locally (requires compose services running)
	uv run uvicorn src.normacore.api:app --reload --host 0.0.0.0 --port 8000

# ==============================================================================
# Ingestion & Evaluation
# ==============================================================================

ingest: ## Ingest a corpus (usage: make ingest CORPUS=<name>)
	uv run normacore-ingest --corpus-manifest corpora/$(CORPUS)/corpus.yaml --corpus-id $(CORPUS)

eval: ## Run retrieval eval harness (usage: make eval CORPUS=<name>)
	uv run normacore-eval --corpus-id $(CORPUS) --fixtures corpora/$(CORPUS)/eval/fixtures.yaml

# ==============================================================================
# Testing
# ==============================================================================

test: ## Run unit tests
	uv run pytest tests/ -v

test-cov: ## Run unit tests with coverage
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

# ==============================================================================
# Code Quality
# ==============================================================================

lint: ## Run ruff linter
	uv run ruff check src tests scripts

format: ## Format code with Black and isort
	uv run black src tests scripts
	uv run isort src tests scripts

# ==============================================================================
# Cleanup
# ==============================================================================

clean: ## Remove containers and volumes — WARNING: deletes all index data
	@read -p "This will delete all vector index data. Are you sure? [y/N] " confirm && \
	[ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Aborted." && exit 1) && \
	COMPOSE=$$($(DETECT_COMPOSE)) && \
	$$COMPOSE -f compose.yaml --profile cpu --profile gpu-docker --profile gpu-podman \
	    down --volumes --remove-orphans
