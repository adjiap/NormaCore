# NormaCore

> [!WARNING]
> This project is not yet functional. Infrastructure scaffolding is in place
> but no ingestion or retrieval code has been written yet.

NormaCore is a self-hostable, HTTP-native RAG ingestion and retrieval platform
for structured documents — technical standards, specifications, and handbooks.
It provides a shared vector index that multiple AI-assisted tools can query
over a single `POST /retrieve` endpoint, eliminating duplicated ingestion
pipelines across projects.

## What it does

1. Ingests structured documents (Markdown, PDF) into a namespaced vector index
2. Chunks documents structure-first — on heading and clause boundaries, with
   heading path carried into every chunk as metadata
3. Retrieves ranked chunks over HTTP using hybrid dense + sparse search (BGE-M3
   + Qdrant RRF fusion)
4. Verifies retrieval quality per corpus with a built-in eval harness
   (`Recall@5 ≥ 0.85`, `MRR ≥ 0.70`) before any consumer depends on it

NormaCore stops at retrieval. It has no chat UI, no agent loop, and no user
management. Any tool that can make an HTTP request can query it.

## Use cases

> [!TIP]
> Basically, it is *Norm-as-a-Service*

- Compliance tooling that needs to query ISO, IEC, MIL-STD, or similar
  standards without re-implementing an ingestion pipeline per project
- Safety analysis assistants grounded in normative documents
- Any multi-tool architecture where several applications share the same
  document corpus

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Docker or Podman with the Compose plugin
- NVIDIA GPU optional — CPU mode is fully supported

> [!NOTE]
> Windows users should run via WSL. All scripts report as Linux via `uname`
> — no separate Windows branch is needed.

## Quick start

```bash
git clone https://github.com/adjiap/normacore.git
cd normacore
make setup
make compose           # auto-detects GPU, starts Qdrant + Ollama
```

Then pull the embedding model:

```bash
make model-pull model=bge-m3
```

Once functional (v0.1.0), ingest a corpus and query it:

```bash
make ingest CORPUS=my-corpus
curl -X POST http://localhost:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"corpus_id": "my-corpus", "query": "definition of risk"}'
```

## Makefile targets

| Target                         | Description                          |
|--------------------------------|--------------------------------------|
| `make setup`                   | One-time dev environment setup       |
| `make check`                   | Verify all prerequisites             |
| `make compose`                 | Auto-detect GPU and start containers |
| `make compose-cpu`             | Force CPU mode                       |
| `make compose-gpu`             | Force GPU mode                       |
| `make compose-down`            | Stop all containers                  |
| `make compose-logs`            | Tail container logs                  |
| `make model-pull model=<name>` | Pull a model into Ollama             |
| `make model-list`              | List installed models                |
| `make ingest CORPUS=<name>`    | Ingest a corpus                      |
| `make eval CORPUS=<name>`      | Run retrieval eval harness           |
| `make run`                     | Start API server locally             |
| `make test`                    | Run unit tests with coverage         |
| `make lint`                    | Run ruff linter                      |
| `make format`                  | Format with Black and isort          |
| `make clean`                   | Remove containers and volumes        |

## Project structure

```sh
normacore/
├── src/normacore/         # application source
├── tests/                 # pytest test suite
├── scripts/               # shell scripts (detect runtime, GPU, prereqs)
├── corpora/               # document corpora and eval fixtures
├── docs/adr/              # architecture decision records
├── compose.yaml           # Qdrant + Ollama services
└── .env.example           # configuration reference
```

## Architecture decisions

- [ADR-001 — System Architecture](docs/adr/adr-001-system-architecture.md)
- [ADR-002 — Tech Stack](docs/adr/adr-002-tech-stack.md)
- [ADR-003 — Consumer Prompt Orchestration](docs/adr/adr-003-consumer-prompt-orchestration.md)

## License

[Apache-2.0](LICENSE)
