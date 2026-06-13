# Quick Start

## 1. Clone and set up

```bash
git clone https://github.com/adjiap/normacore.git
cd normacore
make setup
```

`make setup` copies `.env.example` → `.env` and installs the development
environment. Review `.env` before proceeding — the defaults work for a
single-machine deployment.

## 2. Start the stack

```bash
make compose-dev
```

This auto-detects your GPU and starts three services with ports exposed:

| Service       | Port    | Description                     |
|---------------|---------|---------------------------------|
| NormaCore API | `8000`  | The retrieval and ingestion API |
| Qdrant        | `6333`  | Vector store + web UI           |
| Ollama        | `11434` | Embedding model server          |

## 3. Pull the embedding model

```bash
make model-pull model=bge-m3
```

This pulls BGE-M3 into Ollama. It is ~1 GB and only needs to be done once.

## 4. Ingest a corpus

```bash
make ingest CORPUS=test-corpus
```

This calls `POST /v1/ingest` and indexes the bundled test corpus into Qdrant.
You should see a response like:

```json
{
    "corpus_id": "test-corpus",
    "chunks_indexed": 10,
    "elapsed_ms": 6986.99
}
```

## 5. Query it

```bash
curl -X POST http://localhost:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"corpus_id": "test-corpus", "query": "What is the scope?"}'
```

## 6. Explore the API

The interactive Swagger UI is available at:

```sh
http://localhost:8000/docs
```

It documents all endpoints with request/response schemas and lets you try them
directly from the browser.
