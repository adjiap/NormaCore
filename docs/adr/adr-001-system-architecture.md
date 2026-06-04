# ADR-001: System Architecture — Shared RAG Ingestion and Retrieval Platform

- Status: Accepted
- Date: 2026-06-02
- Deciders: Project owner (single-developer greenfield)
- Relates to: ADR-002 (tech stack); handover document (idea origin and prior art)

> [!NOTE]
> This ADR defines the **architecture and design constraints** for the platform.
> The **tech stack** (embedding model, vector store, API framework, document
> parsing) is decided in ADR-002. The two ADRs are designed to be read together
> but are separable: this one answers *what the system does and why*; ADR-002
> answers *what it is built with*.

## 1. Context and problem statement

Multiple AI-assisted tools and applications need to query the same or
overlapping document corpora — technical standards, specifications, handbooks,
and similar structured public documents. Today, each consuming tool must own its
own ingestion pipeline, embedding infrastructure, and vector index. This
duplicates effort, fragments the corpus, and makes retrieval quality
inconsistent across tools.

The industry offers several self-hostable RAG platforms, but every existing tool
bundles application-layer concerns (chat UIs, agents, user management) with
the ingestion and retrieval infrastructure. None is designed as a lean,
domain-agnostic ingestion + retrieval microservice that downstream tools
consume as a dependency.

### 1.1 The gap

Embedding pipelines and vector indexes are **infrastructure**, not application
logic, and belong in a shared service rather than inside any single consuming
tool. What is missing is:

- A self-hostable service that accepts structured documents, chunks them
  intelligently, embeds them, and stores them in a shared, namespaced vector
  index.
- An HTTP retrieval API that any consumer (any language, any stack) can call
  with a simple request.
- A first-class accuracy evaluation harness that verifies retrieval quality
  before any consumer depends on a newly ingested corpus.
- A deployment model that works both standalone and embedded inside an existing
  compose stack.

This ADR designs that service.

## 2. Prior art — evaluated and rejected

The following tools were evaluated during the ideation session. Each is a
capable product, but none matches the shape of a lean retrieval primitive.

### 2.1 R2R (SciPhi-AI, MIT)

The closest match. A self-hostable RAG engine with a containerised RESTful API,
multimodal ingestion, hybrid search, and Python + JS SDKs. However:

- Feature-heavy: agentic deep research, knowledge graphs, user management —
  application-layer concerns this platform explicitly avoids.
- Leans on PostgreSQL + pgvector rather than a dedicated vector store, which
  reintroduces a database where this platform wants a lightweight, file-backed
  or single-container store.
- Designed as an end-to-end RAG application, not a retrieval primitive.

R2R was evaluated as a fork candidate and rejected: stripping its application
layer and swapping its vector store would be a deeper rewrite than a
greenfield build.

<https://github.com/SciPhi-AI/R2R>

### 2.2 RAGFlow (infiniflow, Apache-2.0)

Strong document understanding, template-based chunking with visual inspection,
and traceable citations. Ships as a full application with chat UI, knowledge
base UI, and user management. Not designed to be consumed as a service
dependency by other tools.

<https://github.com/infiniflow/ragflow>

### 2.3 AnythingLLM (Mintplex Labs)

100% offline capable, 9+ vector database backends, 53k+ GitHub stars. Again an
end-user application (desktop + Docker), not a programmatic
ingestion/retrieval service.

<https://github.com/Mintplex-Labs/anything-llm>

### 2.4 Others (Kotaemon, Dify)

Document QA web UIs with multi-user login and hybrid retrieval. Applications,
not infrastructure primitives.

### 2.5 Conclusion

Every evaluated tool bundles the application layer with the ingestion and
retrieval infrastructure. The accuracy evaluation harness as a first-class
feature is absent from all of them. A greenfield build is the correct approach.

## 3. Design principles

1. **Infrastructure, not application.** The platform provides ingestion and
   retrieval. It does not provide chat, agents, user management, or any
   downstream application logic.

2. **Domain-agnostic.** The platform is not "ISO standards" or "safety
   documents" — it is a generic document ingestion and retrieval service.
   Domain specificity lives in the corpus, not the engine.

3. **Self-hostable and air-gap capable.** The platform must be deployable with
   no internet egress, no cloud dependency, and no external API requirement.
   Cloud-hosted embedding or inference may be used as an explicit, documented
   exception at deployment time but is never required.

4. **Permissively licensed.** Every component in the core platform must be MIT,
   Apache-2.0, or BSD-3-Clause. Components with copyleft licenses (AGPL, GPL)
   may only be used if they run as isolated, separately containerised services
   communicating over a well-defined API boundary, and only as documented
   fallbacks — never in the core codebase (see section 3.1).

5. **Evaluation as a first-class feature.** The repository ships tooling that
   lets an operator verify retrieval accuracy before any consumer depends on a
   newly ingested corpus.

6. **Consumer-agnostic retrieval.** The retrieval API is language- and
   stack-agnostic. Any tool that can make an HTTP request can query the index.

### 3.1 Licensing boundary rule

> [!WARNING]
> If a component is licensed under AGPL-3.0 or GPL-3.0 and is imported as a
> library into the platform's Python process, the copyleft obligation
> propagates to the entire service (AGPL §13 / GPL §5). This conflicts with
> the platform's goal of being usable alongside or by proprietary code.
>
> The safe integration pattern for copyleft components is **process isolation**:
> run the component as a separate container behind an HTTP API. The platform
> code communicates with it only over the network boundary, which is generally
> considered an "aggregate" rather than a derivative work. The copyleft
> obligation then applies only to the isolated container, not to the platform
> or its consumers.
>
> This pattern is documented here so that future contributors do not
> accidentally import a copyleft dependency into the core codebase. Any
> copyleft integration must be reviewed against this rule.

## 4. Corpus model

### 4.1 Namespaced corpora

The vector index is partitioned per document corpus. Each corpus occupies its
own namespace (a separate collection, table, or equivalent in the vector store).
Retrieval is always scoped to a named corpus — there is no cross-corpus query
by default. This prevents contamination between unrelated document sets and
allows independent lifecycle management (ingest, re-index, delete) per corpus.

### 4.2 Standard-scoping within a corpus

A corpus may contain documents from a single standard or specification (e.g.
ISO 26262, MIL-STD-882E) plus associated glossaries or supplements. The
platform treats this as opaque: it does not interpret the standard's semantics.
The consuming application decides which corpus to query.

### 4.3 Corpus metadata

Every chunk carries metadata:

- `corpus_id` — the namespace identifier.
- `source` — the document within the corpus (e.g. `iso-26262-part-1`,
  `glossary`).
- `section` — the structural identifier (clause number, heading path).
- `heading_path` — the full heading hierarchy, carried into the chunk text as
  contextual headers (section 5.2).
- `chunk_index` — ordinal position within the source document.

This metadata enables filtered retrieval (section 7.3) and traceable citations
for consuming applications.

## 5. Ingestion pipeline

### 5.1 Supported input formats (phased)

| Phase   | Format     | Notes                                                     |
|---------|------------|-----------------------------------------------------------|
| v0.1.0  | Markdown   | Structured `.md` files with heading hierarchy             |
| v0.2.0  | PDF        | Structured PDFs (ISO standards, technical specifications) |
| Future  | DOCX, PPTX | Deferred — parsing library selection supports them        |

The ingestion pipeline is format-aware: a format-specific reader produces a
normalised intermediate representation (structured text with heading hierarchy
and metadata), which the chunker then processes uniformly regardless of source
format.

### 5.2 Chunking strategy

The chunking strategy is derived from 2026 RAG best-practice literature and
prior analysis conducted during the ideation phase:

- **Primary split: structure-aware.** Chunk on the document's own boundaries
  (section, clause, heading) so a retrieved chunk is a self-contained unit.
  For structured documents, this step alone is the single biggest and easiest
  retrieval-quality improvement available.

- **Fallback for oversized sections:** Where a section exceeds the target size
  band, fall back to recursive splitting on paragraph/sentence boundaries.
  Recursive ~512-token splitting is the best-performing general default in
  2026 benchmarks.

- **Contextual headers:** Carry the heading path into each child chunk before
  embedding. This makes chunks self-contained without a full semantic or
  late-chunking pass.

- **Glossary / definition entries:** One chunk per entry; do not split or merge.

### 5.3 Chunk sizing defaults

| Parameter       | Default       | Rationale                                        |
|-----------------|---------------|--------------------------------------------------|
| Target size     | 256–512 tokens | Sweet spot for factoid / definition retrieval    |
| Overlap         | 10–20%        | Provisional — validate against eval harness      |
| Max size        | ~512 tokens   | Longer only for genuinely multi-concept passages |
| Glossary entries| Atomic        | Already at the small end of the band             |

These are starting defaults to be tuned against the evaluation harness
(section 8), not fixed constants.

### 5.4 Embedding

Embed every chunk via the embedding service (HTTP endpoint). Store the dense
vector; if the vector store supports native sparse vectors, store those too
for hybrid retrieval. Otherwise, let the store's built-in full-text / BM25
index cover the lexical half.

### 5.5 Indexing model

Default: **build-time indexing.** The corpus is static (standards do not change
between revisions), so a CLI ingestion command builds the index once per corpus.
The index is persisted to a volume or directory.

The ingestion command is a repeatable build step:

```
make ingest CORPUS=iso-26262 SOURCE=./corpora/iso-26262/
```

Re-running the command rebuilds the index for that corpus from scratch
(idempotent). Runtime indexing (hot-add documents to a live index) is a
future enhancement, not a v0.1.0 requirement.

## 6. Retrieval design

### 6.1 RAG architecture type — Hybrid (Advanced)

The platform implements Hybrid RAG: dense semantic search combined with
sparse/lexical search, fused via Reciprocal Rank Fusion (RRF). This is the
correct tier for the target use case (factoid / definition / clause lookup
against structured documents) and is the de facto 2026 production baseline.

- **Not Naive RAG:** pure dense top-k misses exact terms (codes, clause
  numbers, German technical vocabulary).
- **Not Graph RAG:** there is no cross-document relationship graph to traverse.
- **Not Agentic RAG:** retrieval is single-shot per query, not a multi-step
  tool-using loop.

### 6.2 Retrieval flow

1. Consumer sends a query to `POST /retrieve` with a `corpus_id` and query
   text.
2. The platform embeds the query via the embedding service.
3. Dense search + sparse/BM25 search run against the corpus namespace.
4. Results are fused (RRF) and the top-k chunks are returned with metadata
   and relevance scores.

### 6.3 Default parameters

| Parameter | Default | Notes                                        |
|-----------|---------|----------------------------------------------|
| top_k     | 5       | Tuneable per request; keep small to avoid     |
|           |         | context rot                                  |
| alpha     | 0.7     | Dense weight in hybrid fusion (0.0 = pure    |
|           |         | sparse, 1.0 = pure dense); tuneable          |

### 6.4 Deferred enhancements

The following are out of the initial release and added only when the evaluation
harness shows the hybrid baseline is insufficient, in ascending order of cost:

1. Reranking (cross-encoder second stage)
2. Multi-query / HyDE query expansion
3. Semantic or late chunking
4. GraphRAG (only if a relational, multi-hop need ever emerges)

## 7. Retrieval API shape (decision with tradeoffs)

### 7.1 Option A — HTTP only

All consumers call the platform over HTTP. The API exposes:

- `POST /ingest` — submit a document for ingestion (or trigger a corpus build).
- `POST /retrieve` — query a corpus and receive ranked chunks.
- `GET /corpora` — list available corpora.
- `GET /health` — healthcheck.

Pros:
- Truly language- and stack-agnostic: any consumer that can make an HTTP
  request can use the platform.
- Single integration pattern to document and maintain.
- Clean process boundary — the platform is a black box to consumers.

Cons:
- Python consumers pay serialisation overhead on every call.
- No type-safe client — consumers must construct requests manually or
  maintain their own client wrapper.

### 7.2 Option B — HTTP + thin Python SDK

The platform ships a small Python client package (e.g. `pip install
<platform>-client`) that wraps the HTTP API with typed methods and Pydantic
response models.

Pros:
- Python consumers get type safety, IDE completion, and request construction
  for free.
- Non-Python consumers still use HTTP directly — no second integration path.
- The SDK is a thin wrapper, not a second API surface — it calls the same HTTP
  endpoints.

Cons:
- A second deliverable to maintain and version alongside the service.
- Risk of the SDK drifting from the API if not tested together.

### 7.3 Option C — direct store access for Python consumers

Python consumers import the platform's retrieval module and call the vector
store directly (in-process), bypassing the HTTP API.

Pros:
- Lowest latency for Python consumers.
- No network dependency.

Cons:
- Breaks the "infrastructure as a service" model — consumers must share the
  platform's Python environment and vector store dependency.
- Couples consumers to the platform's internals (store driver, embedding
  model).
- Makes the deployment model ambiguous: is the platform a service or a
  library?
- Two fundamentally different integration paths to document and maintain.

### 7.4 Recommendation

**Option A (HTTP only) for v0.1.0**, with Option B (thin Python SDK) as a
documented future enhancement. Rationale:

- The platform's core value proposition is "any consumer, any stack, one
  `POST /retrieve`." HTTP-only enforces that contract from day one.
- A Python SDK is a convenience layer, not a prerequisite. It can be added
  later without breaking any existing consumer.
- Option C is rejected: it undermines the service boundary that justifies the
  platform's existence as a shared dependency.

The API will produce an OpenAPI spec (auto-generated by FastAPI), which serves
as the machine-readable contract for any future SDK or client generator.

## 8. Evaluation harness (first-class requirement)

### 8.1 Purpose

An operator must be able to run a single command and get a clear pass/fail
signal that a freshly ingested corpus is retrievable with acceptable accuracy
before any consuming application depends on it.

```
make eval CORPUS=iso-26262
```

### 8.2 Two-layer evaluation

The harness combines two complementary approaches:

**Layer 1 — Curated query fixtures (per corpus).**
A human-authored set of `(query, expected_chunk_ids)` pairs that represent the
"must-find" retrieval cases for a given corpus. These are ground-truth fixtures
that catch regressions and validate that critical content is retrievable.

- Stored alongside the corpus definition (e.g. `corpora/iso-26262/eval/`).
- Each fixture specifies a query, the expected chunk(s), and the minimum
  acceptable rank position.

**Layer 2 — Auto-generated from chunk metadata.**
Automatically generate evaluation queries from the indexed chunks themselves
(e.g. by using the chunk's heading or first sentence as a query and expecting
the chunk to appear in top-k). This provides broad coverage without manual
fixture authorship and catches systematic chunking or embedding failures.

### 8.3 Metrics

| Metric      | Definition                                                 | Default threshold |
|-------------|------------------------------------------------------------|-------------------|
| Recall@k    | Fraction of expected chunks found in top-k results         | ≥ 0.85 at k=5    |
| MRR         | Mean Reciprocal Rank of the first relevant result          | ≥ 0.70            |

Thresholds are per-corpus defaults, overridable in the corpus eval
configuration. A corpus passes if both metrics meet their thresholds; otherwise
the eval command exits non-zero.

### 8.4 CI integration

The eval harness is a pytest suite that can run in CI. For CI, the harness
requires a running instance of the platform (embedding service + vector store +
indexed corpus). The recommended CI pattern is:

1. `docker compose up` (platform services).
2. `make ingest CORPUS=<target>` (build the index).
3. `make eval CORPUS=<target>` (run the harness).
4. `docker compose down`.

## 9. Deployment model

### 9.1 Standalone

The repository ships its own `compose.yaml`. An operator:

1. Clones the repo.
2. Supplies a corpus (structured documents in a directory).
3. Runs `docker compose up`.
4. Runs `make ingest CORPUS=<name> SOURCE=./path/to/docs/`.
5. Has a live ingestion + retrieval service at `http://localhost:<port>`.

No dependency on any consuming application's stack.

### 9.2 Embedded

Documented integration pattern for operators who want to add the platform as a
service inside their own existing `compose.yaml`:

- The platform services (API, vector store, embedding) join an external Docker
  network.
- Consumers reach the API via `RETRIEVAL_API_URL` environment variable.
- The docs provide a copy-paste `services:` block and the required environment
  variables.

This must be a copy-paste operation, not a research task.

### 9.3 Deployment topologies

The platform supports multiple topologies:

| Topology          | API server | Embedding        | Vector store     | Notes                         |
|-------------------|------------|------------------|------------------|-------------------------------|
| All-in-one        | host       | host (container) | host (container) | Simplest; single-machine      |
| Split embedding   | host       | remote node      | host             | Frees host resources          |
| Fully distributed | host       | remote node      | remote node      | Centralised, scalable         |

The pipeline logic is identical across topologies; only endpoint configuration
changes. This is enforced by the design principle that all heavy components
(embedding, vector store) are reached through HTTP clients (section 6.2).

## 10. Non-functional requirements

| ID    | Requirement                                                    |
|-------|----------------------------------------------------------------|
| NFR-1 | Air-gap capable: no internet egress required at runtime        |
| NFR-2 | GDPR-compatible: no data leaves the deployment perimeter       |
| NFR-3 | Permissively licensed core (MIT / Apache-2.0 / BSD-3); copyleft|
|       | only behind process isolation (section 3.1)                    |
| NFR-4 | All dependencies pinned; SBOM maintained                       |
| NFR-5 | Single-machine deployable (no k8s requirement for base case)   |
| NFR-6 | OpenAPI spec auto-generated for the retrieval API              |

## 11. Consequences

### 11.1 Positive

- A single, shared ingestion and retrieval service replaces per-tool
  duplication of embedding infrastructure.
- The HTTP API makes the platform consumable by any language or stack.
- The evaluation harness gives operators a measurable confidence signal
  before depending on a corpus.
- The deployment model supports both standalone and embedded use with
  minimal configuration.

### 11.2 Negative / trade-offs

- A greenfield build is more work than forking an existing tool; justified
  by the prior-art analysis (section 2) showing no existing tool matches
  the required shape.
- HTTP-only retrieval adds serialisation overhead for Python consumers;
  acceptable given the small query volume and the architectural clarity
  it provides.
- The evaluation harness requires curated fixtures per corpus, which is
  manual effort; the auto-generated layer reduces but does not eliminate
  this cost.

### 11.3 Out of scope

- Chat, agents, or any application-layer UI.
- User management or authentication (consumers are trusted services).
- Runtime hot-add of documents (build-time indexing only for v0.1.0).
- The tech stack (decided in ADR-002).

## 12. Open items

- **Repo name** — must be generic, no domain specificity. Candidates to
  evaluate: `retrieval-core`, `docvault`, `chunkbase`, `vectra`,
  `corpus-engine`. Decision required before scaffolding.
- Confirm the retrieval API shape recommendation (Option A) in review.
- Define the corpus directory convention and manifest format.
- Determine whether `POST /ingest` is a v0.1.0 API endpoint or whether
  ingestion remains CLI-only until a later release.
