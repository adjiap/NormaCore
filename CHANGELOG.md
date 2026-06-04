# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
