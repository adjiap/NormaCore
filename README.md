# NormaCore

NormaCore is a self-hostable, HTTP-native RAG ingestion and retrieval platform
for structured documents — technical standards, specifications, and handbooks.
It provides a shared vector index that multiple AI-assisted tools can query
over a single `POST /v1/retrieve` endpoint, eliminating duplicated ingestion
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

## Quick start

```bash
git clone https://github.com/adjiap/normacore.git
cd normacore
make setup
make compose-dev
make model-pull model=bge-m3
make ingest CORPUS=test-corpus
```

Query it:

```bash
curl -X POST http://localhost:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"corpus_id": "test-corpus", "query": "definition of risk"}'
```

Explore the API interactively at `http://localhost:8000/docs`.

## Documentation

Full documentation including configuration reference, API reference, corpus
format guide, evaluation harness, and production deployment notes is available
at **[adjiap.github.io/normacore](https://adjiap.github.io/normacore)**.

## License

[Apache-2.0](LICENSE)
