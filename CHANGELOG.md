# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Core Pipeline

- `src/normacore/embedding.py` — async Ollama `/api/embed` client with retry
  logic and Pydantic response models
- `src/normacore/vector_store.py` — `VectorStore` ABC and `QdrantVectorStore`
  implementation with dense vector search
- `src/normacore/markdown_reader.py` — structure-aware Markdown reader
  supporting ISO/IEC, NIST, and unnumbered heading patterns
- `src/normacore/chunker.py` — structure-aware chunker with glossary detection
  and recursive fallback for oversized sections
- `src/normacore/ingest.py` — corpus ingestion pipeline with batched embedding
  and idempotent collection creation; `normacore-ingest` entry point
- `src/normacore/eval.py` — Recall@5 and MRR evaluation harness;
  `normacore-eval` entry point

#### Test Corpus

- `corpora/test-corpus/standard.md` — synthetic ISO-style Markdown corpus
- `corpora/test-corpus/corpus.yaml` — corpus manifest
- `corpora/test-corpus/eval/fixtures.yaml` — 5 curated eval queries

#### Developer Experience

- `compose.override.example.yaml` — dev-only port bindings template
  (copied to `compose.override.yaml` by `make setup`)
- `Makefile` — added `compose-dev`, `test-ingestion`, `test-eval` targets

#### API

- `src/normacore/api.py` — FastAPI application with four endpoints:
  `POST /v1/ingest`, `POST /v1/retrieve`, `GET /v1/corpora`, `GET /v1/health`
- `compose.yaml` — `rag` service added with Dockerfile, healthcheck, and
  corpora volume mount
- `Dockerfile` — production image for the NormaCore API service

#### Documentation

- `docs/` — ProperDocs site scaffolded with ProperDocs + Material theme
- `docs/index.md` — landing page
- `docs/getting-started/` — requirements, quick start, and configuration pages
- `properdocs.yaml` — site configuration with callouts, mkdocstrings, section-index

### Fixed

- `EmbeddingResponse` field renamed from `embedding` to `embeddings` to match
  Ollama `/api/embed` response schema
- `search_hybrid` simplified to dense-only search; sparse `Prefetch` with raw
  query text caused Qdrant 400 errors (sparse pipeline deferred to post-v0.1.0)
- Healthchecks updated to `/dev/tcp` TCP probe — Qdrant image ships neither
  `curl` nor `wget`
- `compose.yaml` port bindings moved to `compose.override.yaml`; production
  deployment no longer exposes Qdrant or Ollama ports to the host
- API routes prefixed with `/v1/` — all endpoints now at `/v1/retrieve`,
  `/v1/corpora`, `/v1/health`, etc.
- Healthcheck path updated to `/v1/health` after API route prefix change
- Compose service renamed from `api` to `rag`; image now tagged `normacore-rag`
- `test-ingestion` and `test-eval` Makefile targets removed — replaced by
  `make ingest` (API-driven) and `make eval` (CLI with injected localhost URLs)
- Corpora mount path made configurable via `LOCAL_CORPORA_PATH` in `.env`

### Known Limitations

- Sparse/hybrid RRF retrieval not functional — BGE-M3 sparse vectors not
  exposed by Ollama; dense-only search used; Qdrant native BM25 deferred
- Markdown ingestion only — PDF support planned for v0.2.0
- No reranking, query rewriting, or authentication

## [0.1.0-dev] — 2026-06-03

### Description

Initial project scaffold — no functional code yet. Architecture is fully
defined, infrastructure services are wired, and the development toolchain
is in place.

### Added

#### Architecture Decision Records

- ADR-001: system architecture and design principles
- ADR-002: tech stack (FastAPI, BGE-M3, Qdrant, Docling)
- ADR-003: consumer prompt orchestration and chunk injection pattern

#### Community & Legal

- `LICENSE` — Apache-2.0
- `CONTRIBUTING.md` — fork-and-PR workflow, commit conventions, pre-commit
  setup instructions
- `SECURITY.md` — vulnerability disclosure policy

#### Project Tooling

- `pyproject.toml` — project metadata, runtime and dev dependencies, tool
  configuration (Black, isort, ruff, pytest, coverage)
- `.pre-commit-config.yaml` — black, isort, ruff, detect-secrets, pytest hooks
- `Makefile` — setup, compose, model, ingest, eval, test, lint, format, clean
  targets

#### Infrastructure

- `compose.yaml` — Qdrant and Ollama services with CPU/GPU profiles,
  healthchecks, named volumes, bind mount support via
  `LOCAL_DOWNLOADED_MODELS_MOUNTED`
- `.env.example` — documented configuration keys for vector store, embedding
  service, and model storage

#### Application Scaffold

- `src/normacore/__init__.py` — version declaration
- `src/normacore/config.py` — Pydantic settings loaded from environment
  variables

#### Scripts

- `scripts/check_prerequisites.sh` — pre-flight runtime, daemon, compose,
  env, and GPU checks
- `scripts/detect_compose.sh` — detects available compose tool
- `scripts/detect_container_runtime.sh` — detects Docker or Podman
- `scripts/detect_gpu.sh` — detects NVIDIA GPU availability
- `scripts/install_host_deps.sh` — one-time host provisioning for Linux
  servers
- `scripts/lib/checks.sh` — shared check functions

#### Documentation

- `README.md` — project description, use cases, requirements, quick start,
  Makefile reference, project structure, ADR links
- `CHANGELOG.md` — this file
