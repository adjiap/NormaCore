
# Evaluation Fixtures

NormaCore ships a built-in retrieval quality harness that verifies a corpus
is retrievable with acceptable accuracy before any consumer depends on it.
Fixtures are the ground-truth queries that drive the harness.

## Running the harness

```sh
make eval CORPUS=my-corpus
```

The harness loads fixtures from `corpora/my-corpus/eval/fixtures.yaml`,
runs each query against the live index, and reports Recall@5 and MRR.
Exit code is `0` on pass, `1` on fail.

## fixtures.yaml format

```yaml
- query: "What is the definition of risk?"
  expected_chunks:
    - chunk_id: "3.1"
      min_rank: 1

- query: "What are the general requirements for functional safety?"
  expected_chunks:
    - chunk_id: "4.1"
      min_rank: 3
```

### Fields

| Field             | Required | Description                                                                                                                                      |
|-------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `query`           | Yes      | The plain text query to send to `POST /v1/retrieve`.                                                                                             |
| `expected_chunks` | Yes      | List of chunks expected to appear in the results.                                                                                                |
| `chunk_id`        | Yes      | The `section_id` of the expected chunk. Must match the `section_id` in the chunk's metadata exactly.                                             |
| `min_rank`        | Yes      | The result must appear at or above this position in the ranked list. `1` means it must be the top result. `3` means it must appear in the top 3. |

## How chunk_id maps to section_id

The `chunk_id` in a fixture corresponds to the `section_id` field in the
chunk metadata returned by `POST /v1/retrieve`. For Markdown sources, this
is extracted from the heading text:

| Heading                        | section_id             |
|--------------------------------|------------------------|
| `# 1 Scope`                    | `1`                    |
| `## 1.2 Field of Application`  | `1.2`                  |
| `### 1.2.1 Inclusions`         | `1.2.1`                |
| `## A.1 Normative References`  | `A.1`                  |
| `## Introduction` (unnumbered) | positional, e.g. `0.1` |

To find the correct `chunk_id` for a fixture, run `make ingest` first, then
call `POST /v1/retrieve` with a test query and inspect the `section_id` in
the returned metadata.

## Quality thresholds

| Metric   | Default threshold | Definition                                         |
|----------|-------------------|----------------------------------------------------|
| Recall@5 | ≥ 0.85            | Fraction of expected chunks found in top-5 results |
| MRR      | ≥ 0.70            | Mean Reciprocal Rank of the first relevant result  |

Both metrics must meet their thresholds for the harness to pass. Thresholds
can be overridden via CLI flags:

```sh
uv run normacore-eval \
  --corpus-id my-corpus \
  --fixtures corpora/my-corpus/eval/fixtures.yaml \
  --recall-threshold 0.80 \
  --mrr-threshold 0.60
```

## Writing good fixtures

- **Cover the must-find cases.** Write fixtures for the clauses a consuming
  application is most likely to query. A missed clause in a safety case is
  a more serious failure than a low MRR score.
- **Use specific queries.** Vague queries like "requirements" will match many
  chunks. Specific queries like "definition of ASIL" have a clear expected
  result.
- **Start with 5–10 fixtures.** The auto-generated layer (heading-as-query)
  provides broad coverage. Curated fixtures cover the high-value cases.
- **Tune min_rank honestly.** If a chunk consistently appears at rank 2 or 3,
  set `min_rank: 3`. Setting it to `1` when retrieval doesn't support it
  causes false failures.
