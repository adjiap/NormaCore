# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-16

### Added

#### Core Pipeline

- `src/normacore/retrieval/embedding.py` — async Ollama `/api/embed` client
  with retry logic and Pydantic response models
- `src/normacore/retrieval/vector_store.py` — `VectorStore` ABC and
  `QdrantVectorStore` implementation with dense vector search
- `src/normacore/ingestion/readers/base.py` — `DocumentSection` IR dataclass,
  format-agnostic contract between all readers and the chunker
- `src/normacore/ingestion/readers/markdown.py` — structure-aware Markdown
  reader supporting ISO/IEC, NIST, and unnumbered heading patterns
- `src/normacore/ingestion/chunker.py` — structure-aware chunker with glossary
  detection and recursive fallback for oversized sections
- `src/normacore/ingestion/ingest.py` — corpus ingestion pipeline with batched
  embedding and idempotent collection creation; `normacore-ingest` entry point
- `src/normacore/eval.py` — Recall@5 and MRR evaluation harness;
  `normacore-eval` entry point
- `src/normacore/api/api.py` — FastAPI application with four endpoints:
  `POST /v1/ingest`, `POST /v1/retrieve`, `GET /v1/corpora`, `GET /v1/health`

#### Test Corpus

- `corpora/test-corpus/standard.md` — synthetic ISO-style Markdown corpus
- `corpora/test-corpus/corpus.yaml` — corpus manifest
- `corpora/test-corpus/eval/fixtures.yaml` — 5 curated eval queries

#### Infrastructure

- `compose.yaml` — `rag` service with Dockerfile, healthcheck, and corpora
  volume mount; Qdrant and Ollama services with CPU/GPU profiles
- `Dockerfile` — production image; non-root user, `uv` managed deps
- `compose.override.example.yaml` — dev-only port bindings template

#### Developer Experience

- `Makefile` — `compose-dev`, `compose-rebuild` targets; `ingest` and `eval`
  targets calling API and CLI respectively
- `docs/assets/system-overview.png` — Excalidraw system overview diagram

#### Documentation

- `docs/architecture.md` — system overview, ingestion/retrieval/eval pipeline
  diagrams, deployment model, source layout, ADR links
- `docs/guides/corpus-format.md` — corpus.yaml format, source fields,
  ingestion, retrieval, corpus ID conventions
- `docs/guides/eval-fixtures.md` — fixtures.yaml format, chunk_id mapping,
  quality thresholds, fixture authoring guidance
- `docs/api-reference.md` — endpoint summary, link to Swagger UI
- `docs/getting-started/` — requirements, quick start, configuration pages
- `docs/index.md` — landing page
- `properdocs.yaml` — site configuration with Mermaid, callouts,
  mkdocstrings, section-index
- `docs/adr/adr-002-tech-stack.md` — §5.3 added: embedded image handling,
  table representation, OCR scope decisions

### Fixed

- `EmbeddingResponse` field renamed from `embedding` to `embeddings` to match
  Ollama `/api/embed` response schema
- `search_hybrid` simplified to dense-only search; sparse `Prefetch` caused
  Qdrant 400 errors; deferred to post-v0.1.0
- Healthchecks updated to `/dev/tcp` TCP probe — Qdrant and Ollama images
  ship neither `curl` nor `wget`
- `compose.yaml` port bindings moved to `compose.override.yaml`; production
  deployment no longer exposes Qdrant or Ollama ports to the host
- API routes prefixed with `/v1/`
- Healthcheck path updated to `/v1/health`
- Compose service renamed from `api` to `rag`
- Corpora mount path made configurable via `LOCAL_CORPORA_PATH`
- `uvicorn.run()` app path corrected to `normacore.api.api:app` after
  subpackage refactor
- Dockerfile `uv sync` changed to `--no-group dev --no-group docs` —
  `--no-dev` does not suppress `[dependency-groups]` in uv
- `readme` field removed from `pyproject.toml` — `README.md` excluded by
  `.dockerignore` caused hatchling build failure in Docker
- `build-system` switched from `setuptools + setuptools_scm` to `hatchling`
- `if` statement fix for GPU profile detection in `compose` and
  `compose-rebuild` Makefile targets
- `.pre-commit-config.yaml` `check-yaml` hook updated with `--unsafe` flag
  to allow Python object tags in `properdocs.yaml`
- Eval fixture `min_rank` for scope query loosened from 1 to 3

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

[0.1.0]: https://github.com/adjiap/normacore/compare/v0.1.0-dev...v0.1.0
[0.1.0-dev]: https://github.com/adjiap/normacore/releases/tag/v0.1.0-dev
