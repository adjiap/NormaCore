# Corpus Format

A corpus is a named collection of documents that NormaCore ingests into a
shared vector index. Each corpus lives in its own directory under `corpora/`
and is described by a `corpus.yaml` manifest.

## Directory structure

```sh
corpora/
└── my-corpus/
    ├── corpus.yaml
    ├── standard.md
    └── eval/
        └── fixtures.yaml
```

## corpus.yaml

```yaml
corpus_id: my-corpus
description: A short human-readable description of the corpus.
sources:
  - name: standard
    path: ./standard.md
    type: markdown
  - name: glossary
    path: ./glossary.md
    type: markdown
eval_fixtures: ./eval/
```

### Fields

| Field           | Required | Description                                                                                                        |
|-----------------|----------|--------------------------------------------------------------------------------------------------------------------|
| `corpus_id`     | Yes      | Unique identifier. Used as the Qdrant collection name and in all API calls. Must be URL-safe (lowercase, hyphens). |
| `description`   | No       | Human-readable description. Not used at runtime.                                                                   |
| `sources`       | Yes      | List of source documents to ingest.                                                                                |
| `eval_fixtures` | No       | Path to the directory containing `fixtures.yaml`.                                                                  |

### Source fields

| Field  | Required | Description                                                                                     |
|--------|----------|-------------------------------------------------------------------------------------------------|
| `name` | Yes      | Identifier for this source within the corpus. Stored as metadata on every chunk.                |
| `path` | Yes      | Path to the source file, relative to `corpus.yaml`.                                             |
| `type` | Yes      | Format of the source file. Currently only `markdown` is supported. `pdf` is planned for v0.2.0. |

## Ingesting a corpus

```bash
make ingest CORPUS=my-corpus
```

This calls `POST /v1/ingest` with `{"corpus_id": "my-corpus"}`. NormaCore
resolves the manifest at `corpora/my-corpus/corpus.yaml` and indexes all
sources. Re-running is idempotent — the collection is recreated from scratch
on each call.

## Querying a corpus

Once ingested, query the corpus via `POST /v1/retrieve`:

```sh
curl -X POST http://localhost:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "corpus_id": "my-corpus",
    "query": "definition of risk",
    "top_k": 5,
    "alpha": 0.7
  }'
```

### Request fields

| Field       | Required | Default | Description                                               |
|-------------|----------|---------|-----------------------------------------------------------|
| `corpus_id` | Yes      | —       | Must match the `corpus_id` in `corpus.yaml`               |
| `query`     | Yes      | —       | Plain text query string                                   |
| `top_k`     | No       | 5       | Number of chunks to return (1–20)                         |
| `alpha`     | No       | 0.7     | Dense search weight (0.0 = sparse only, 1.0 = dense only) |

### Response

Each result carries the chunk text and its full metadata:

```json
{
  "results": [
    {
      "text": "1 Scope\n\nThis document specifies...",
      "score": 0.91,
      "metadata": {
        "corpus_id": "my-corpus",
        "source": "standard",
        "section_id": "1",
        "heading_path": ["1 Scope"]
      }
    }
  ],
  "query_time_ms": 42.3
}
```

The `section_id` and `heading_path` in the metadata are what consuming
applications use to construct citations. See
[ADR-003](../adr/adr-003-consumer-prompt-orchestration.md) for the
recommended chunk injection pattern.

## Corpus ID conventions

- Lowercase, hyphens only: `iso-26262`, `mil-std-882e`, `my-handbook`
- Include a version suffix when the document has numbered revisions:
  `iso-26262-v4`, `nist-sp-800-53-r5`
- Keep it short — it appears in every API request and every chunk's metadata
