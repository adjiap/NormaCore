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
3. Retrieves ranked chunks over HTTP using hybrid dense + sparse search
4. Verifies retrieval quality per corpus with a built-in eval harness
   (`Recall@5 ≥ 0.85`, `MRR ≥ 0.70`) before any consumer depends on it

NormaCore stops at retrieval. It has no chat UI, no agent loop, and no user
management. Any tool that can make an HTTP request can query it.

> [!TIP]
> Basically, it is *Norm-as-a-Service*

## Use cases

- Compliance tooling that needs to query ISO, IEC, MIL-STD, or similar
  standards without re-implementing an ingestion pipeline per project
- Safety analysis assistants grounded in normative documents
- Any multi-tool architecture where several applications share the same
  document corpus

## Getting started

New here? Head to [Requirements](getting-started/requirements.md) first, then
follow the [Quick Start](getting-started/quick-start.md) guide.
