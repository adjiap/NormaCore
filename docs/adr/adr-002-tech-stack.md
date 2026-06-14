# ADR-002: Tech Stack — Shared RAG Ingestion and Retrieval Platform

- Status: Proposed
- Date: 2026-06-02
- Deciders: Project owner (single-developer greenfield)
- Builds on: ADR-001 (system architecture, design principles, licensing boundary
  rule)

> [!NOTE]
> This ADR decides **what the platform is built with**. ADR-001 decides **what
> it does and why**. The two are designed to be read together.

> [!WARNING]
> License compliance is a hard constraint (ADR-001 §3, NFR-3). Every component
> below has been verified against its canonical license source. Components with
> copyleft licenses are documented as fallbacks with the required isolation
> pattern (ADR-001 §3.1), never as primary choices.

## 1. Context

ADR-001 defines the platform as a self-hostable, domain-agnostic, HTTP-native
ingestion and retrieval service. This ADR selects the concrete technologies to
implement it, guided by these constraints from ADR-001:

- Permissively licensed core (NFR-3).
- Air-gap capable, no cloud dependency at runtime (NFR-1).
- Single-machine deployable (NFR-5).
- All heavy components reached over HTTP (ADR-001 §6.2), so the stack must
  support multiple deployment topologies without code changes.

Where prior analysis from an adjacent project informed a decision, the
reasoning has been re-evaluated from first principles for this platform's
context. No decision is inherited — each is justified independently below.

## 2. API framework — FastAPI

Decision: FastAPI + Pydantic + Uvicorn.

Rationale:

- FastAPI auto-generates an OpenAPI spec (NFR-6), which is the machine-readable
  contract for the retrieval API and the foundation for any future client SDK
  (ADR-001 §7.4).
- Pydantic models define the request/response contract, the chunk schema, and
  the corpus metadata — one type system from ingestion to API response.
- Async-native, which suits the HTTP-client-heavy architecture (embedding
  calls, vector store queries).
- MIT licensed; the standard Python web framework for this shape of service.

Alternatives considered:

- Flask / Django: lack async-native support and auto-generated OpenAPI.
- gRPC: stronger typing but worse tooling for ad-hoc consumers (curl, Postman,
  browser). HTTP+JSON is the lower-friction choice for a service whose value
  proposition is "any consumer, any stack."
- Litestar: capable but smaller ecosystem; FastAPI's community and
  documentation are a pragmatic advantage for a single-developer project.

## 3. Embedding model — BGE-M3

Decision: `BAAI/bge-m3` as the embedding model.

This decision was validated against prior analysis from an adjacent project and
confirmed independently for this platform. The reasoning:

- Multilingual including German (relevant for ISO/DIN standards with German
  terminology), and consistently rated the strongest open-source multilingual
  embedding model in 2026 comparisons.
- Native multi-functionality: produces dense **and** sparse (lexical) vectors
  from one model, plus a ColBERT-style multi-vector output, supporting inputs
  up to 8192 tokens. This directly enables the hybrid dense+sparse retrieval
  pattern (ADR-001 §6.1) without a second model.
- Servable over HTTP via Ollama's embeddings endpoint or Hugging Face Text
  Embeddings Inference (TEI). This is what makes the topology-agnostic
  architecture (ADR-001 §9.3) possible — the embedding service can run on the
  same host or a remote node, reached via the same HTTP client.
- MIT licensed — NFR-3 clean.
- ~1.06 GB at F16, fitting comfortably on modest hardware.

Alternatives considered:

- multilingual-E5: supports German but lacks native sparse output.
- Qwen3-Embedding: higher quality on some benchmarks but the strong variants
  require substantially more VRAM.
- IBM Granite Embedding: smaller ecosystem and less multilingual coverage.

> [!TIP]
> Sparse vector generation via BGE-M3 was evaluated on both Ollama and TEI.
> Neither exposes sparse output for this model architecture. Qdrant native BM25
> (SparseVectorParams, modifier=idf) is used for the sparse component instead.

### 3.1 Embedding service deployment

The embedding model is served over HTTP, not loaded in-process. Two supported
serving paths:

| Path | Image / tool    | Notes                                           |
|------|-----------------|-------------------------------------------------|
| A    | Ollama          | Simpler setup; `ollama pull bge-m3`             |
| B    | HF TEI          | Purpose-built for embeddings; BGE-M3 model card |
|      |                 | explicitly lists TEI support                    |

The choice is a deployment-time decision, not an architecture decision. The
platform calls `EMBEDDING_BASE_URL` + `EMBEDDING_MODEL` and does not know
which serving path is behind the endpoint.

## 4. Vector store — Qdrant

Decision: Qdrant as the primary vector store.

Rationale:

- The platform is an HTTP-native service (ADR-001 §3, §7). Qdrant is a
  **server** with an HTTP/REST + gRPC API by default — it is the same shape as
  the platform itself. No wrapper, no adapter needed.
- Native sparse-vector support: Qdrant ingests BGE-M3's native sparse vectors
  directly, giving a stronger hybrid than BM25 approximations. This is the
  highest-quality hybrid retrieval path available without a second system.
- Collection-based namespacing maps directly to the corpus model (ADR-001 §4.1):
  one Qdrant collection per corpus.
- Apache-2.0 licensed — NFR-3 clean.
- Designed for the single-machine-to-cluster range that the platform's
  deployment topologies span (ADR-001 §9.3).

Alternatives considered:

- **LanceDB (Apache-2.0, embedded/in-process):** Evaluated during prior
  analysis for host-local deployments. LanceDB is the right shape for a library, not a service —
  it has no first-class server mode. Since this platform *is* a service,
  wrapping LanceDB behind a bespoke HTTP layer would reinvent what Qdrant
  already provides. LanceDB remains a documented fallback for a future
  "embedded library mode" if one is ever needed.

- **Chroma (Apache-2.0, client/server):** Viable as a simpler alternative.
  Lacks Qdrant's native sparse-vector hybrid, which means the platform would
  fall back to Chroma's built-in BM25 — a weaker hybrid. Documented as a
  fallback if Qdrant proves operationally heavy for a given deployment.

- **pgvector:** Excluded. It is a PostgreSQL extension, so adopting it
  reintroduces a full database server. The platform should not require a
  database — the vector index is the only persistence layer needed.

### 4.1 Qdrant deployment

Qdrant runs as a Docker container with a pinned image tag, a healthcheck, and a
named volume for the index. The platform's `compose.yaml` includes it as a
service. Configuration:

- `QDRANT_URL` — endpoint for the Qdrant HTTP API (default:
  `http://qdrant:6333`).
- One collection per corpus, created by the ingestion command.

## 5. Document parsing — phased, with primary and fallback paths

### 5.1 Phase 1 (v0.1.0) — Markdown

No external parsing library needed. The platform reads structured `.md` files
directly, splitting on heading hierarchy (`#`, `##`, `###`, etc.) to produce
structure-aware chunks. This is implemented as project code — a markdown reader
that emits the normalised intermediate representation (section/heading/text
triples with metadata).

### 5.2 Phase 2 (v0.2.0) — PDF

Structured PDF ingestion for technical standards (ISO 26262 and similar). The
parsing library must:

- Preserve heading hierarchy and reading order.
- Extract tables with structure.
- Handle multi-column layouts.
- Be self-hostable with no external API dependency.
- Be permissively licensed (NFR-3).

#### 5.2.1 Research findings — PDF parser landscape (June 2026)

| Library                  | License                     | Structure | OCR/VLM         | Self-host | Status        |
|--------------------------|-----------------------------|-----------|-----------------|-----------|---------------|
| **Docling**              | MIT (codebase)              | Yes       | VLM via Granite | Yes       | **Primary**   |
| **Granite-Docling-258M** | Apache 2.0 (model)          | Yes       | Built-in VLM    | Yes       | VLM for above |
| PyMuPDF4LLM             | AGPL-3.0                    | Yes       | No native OCR   | Yes       | Fallback only |
| Marker                   | GPL-3.0+ (code); cc-by-nc-  | Yes       | Surya OCR       | Yes       | Excluded      |
|                          | sa-4.0 (model weights)      |           |                 |           |               |
| MinerU                   | Custom (Apache-2.0 based,   | Yes       | Built-in VLM    | Yes       | Monitor       |
|                          | additional conditions)       |           |                 |           |               |

#### 5.2.2 Primary choice — Docling + Granite-Docling-258M

Decision: Docling (MIT) with the Granite-Docling-258M VLM (Apache 2.0) as the
primary PDF parsing path.

Rationale:

- **License-clean:** MIT codebase + Apache 2.0 model — both permissive, no
  copyleft risk, NFR-3 satisfied without process isolation.
- **Structure-aware:** Layout analysis, heading detection, table recognition,
  reading order — exactly what structured ISO/technical PDFs need.
- **VLM path replaces OCR:** Granite-Docling-258M is a 258M-parameter
  vision-language model that processes pages in one shot, avoiding traditional
  OCR entirely. IBM Research reports 30× speedup over OCR-based pipelines.
  The model runs on CPU or GPU and fits easily on modest hardware.
- **Output formats:** Markdown and JSON natively — the Markdown output maps
  directly to the platform's normalised intermediate representation.
- **Future-proof:** Docling handles PDF, DOCX, PPTX, XLSX, HTML, and images,
  so the later format phases (ADR-001 §5.1) are covered by the same library.
- **Active ecosystem:** 37k+ GitHub stars, IBM + Red Hat backing, donated to
  the Linux Foundation's Agentic AI Foundation, purpose-built `docling-eval`
  framework for quality measurement.
- **Self-hostable:** Runs entirely locally, no external API required (NFR-1).

Granite-Docling-258M is servable via Ollama (`ollama pull ibm/granite-docling:258m`)
or via the Docling library's built-in VLM pipeline (`--pipeline vlm
--vlm-model granite_docling`), so the deployment model aligns with the
platform's HTTP-oriented architecture.

#### 5.2.3 Documented fallback — PyMuPDF4LLM (AGPL-3.0, containerised)

If Docling's output quality falls short on specific ISO PDFs during testing,
PyMuPDF4LLM is the documented fallback. It provides strong heading-aware,
multi-column, table-extracting PDF-to-Markdown conversion.

> [!WARNING]
> PyMuPDF4LLM is licensed under AGPL-3.0 (dual-licensed with Artifex
> Commercial). **It must not be imported into the platform's Python process.**
> The required integration pattern per ADR-001 §3.1 is:
>
> - Run PyMuPDF4LLM as a **separate Docker container** exposing an HTTP
>   endpoint (e.g. a thin FastAPI wrapper that accepts a PDF and returns
>   Markdown).
> - The platform communicates with it only over the network boundary.
> - The copyleft obligation applies only to the isolated container, not to the
>   platform or its consumers.
> - The container's Dockerfile and wrapper code must be AGPL-3.0-compatible
>   and the source offered per AGPL §13.
>
> This fallback is not part of the default deployment and is not included in
> the platform's `compose.yaml`. It is a documented, operator-initiated
> alternative for cases where Docling is insufficient.

#### 5.2.4 Excluded — Marker (GPL-3.0+)

Marker is GPL-3.0+ for the code and cc-by-nc-sa-4.0 for the model weights.
The model weights license prohibits commercial use above $5M revenue and
restricts redistribution. Even with the containerised isolation pattern, the
model weight restrictions make it unsuitable for a platform intended for
commercial use alongside proprietary code. Excluded.

#### 5.2.5 Monitor — MinerU (custom Apache-2.0-based license)

MinerU recently moved from AGPL-3.0 to a custom license described as "based on
Apache 2.0 with additional conditions." The additional conditions have not been
reviewed in detail. MinerU's capabilities are strong (VLM + OCR dual engine,
109 languages, structure preservation), and if the license terms are confirmed
as compatible, it could be a strong alternative to Docling. Flagged for
monitoring and legal review if needed.

### 5.3 Embedded visual content — images and tables

This section records decisions on visual content found inside ingested
documents. These decisions apply to all current and planned format phases
(Markdown, PDF, DOCX).

#### 5.3.1 Embedded images

Decision: extract and index the caption and immediately surrounding text
only. Image pixels are not stored, described, or embedded.

Rationale: for normative technical standards (ISO 26262, MIL-STD-882E,
and similar), figures are almost always accompanied by a caption and
surrounded by explanatory prose. The retrieval value is in that text, not
the visual content itself. Generating VLM descriptions of figures during
ingestion adds per-image inference cost, introduces hallucination risk in
stored metadata, and has not been shown to improve Recall@5 or MRR on
this corpus type.

Docling extracts captions and figure references as part of its layout
analysis output. The `pdf.py` reader (v0.2.0) will preserve this text in
the `DocumentSection` IR and pass it to the chunker alongside surrounding
prose. No additional step is required.

Revisit trigger: eval harness shows systematic misses on figure-heavy
sections that cannot be explained by caption quality alone.

Out of scope until explicitly revisited:

- VLM-based image description stored as retrievable text
- Image pixel storage or visual embedding
- Standalone image ingestion (e.g. `.png`, `.jpg` files as corpus sources)
- Visual search or multimodal retrieval

#### 5.3.2 Tables

Decision: preserve table structure as inline Markdown text. No special
chunking or relational representation.

For **PDF sources**, Docling extracts tables with row/column structure and
renders them as Markdown tables in its output. This passes through the IR
unchanged and is embedded as part of the containing section's text.

For **Markdown sources**, the reader already captures raw Markdown table
syntax as part of the section body. No transformation is applied.

In both cases the chunker treats table text the same as prose. A table
that exceeds the token limit triggers the standard recursive fallback
(paragraph split, then sentence split). This is a known limitation: a
large table split mid-row loses structural coherence. It is accepted for
v0.1.0–v0.2.0 given that most normative tables in technical standards fit
within the 512-token limit.

Revisit trigger: eval harness shows retrieval failures on table-heavy
sections, or a consuming project reports citation errors tracing back to
split table rows.

Out of scope until explicitly revisited:

- Table-aware chunking (split on row boundaries, not token count)
- Relational or structured table storage
- Table-to-text normalisation (e.g. flattening a matrix into sentences)

#### 5.3.3 OCR for scanned content

Decision: out of scope. NormaCore targets *authored* structured documents
— PDFs produced from digital source files, not scanned paper documents.

Docling exposes an OCR fallback flag but it is not enabled by default and
has not been tested against NormaCore's eval harness. Enabling it
introduces a separate quality dimension (OCR accuracy) that the current
harness does not measure.

Revisit trigger: a corpus operator explicitly needs scanned document
support and is willing to author eval fixtures covering OCR output quality.

## 6. Retrieval orchestration — lean, not a framework

Decision: implement retrieval as project code, not via LlamaIndex, LangChain,
or Haystack.

This decision was validated against prior analysis and confirmed independently.
The reasoning:

- The retrieval flow is a single-shot query → embed → search → fuse → return
  pipeline with no agentic routing, no multi-step reasoning, and no tool use.
  A framework adds dependency weight and API churn for no functional gain.
- Keeping retrieval as project code preserves the small SBOM and audit surface
  (NFR-4).
- Escape hatch: if a future need (multi-stage pipelines, complex routing)
  justifies a framework, Haystack is the documented upgrade target
  (Apache-2.0, pipeline-oriented, audit-friendly).

## 7. Deployment topologies

The platform is deployable across multiple topologies. The pipeline logic is
identical; only endpoint configuration and container placement change.

### 7.1 Topology 1 — all-in-one (default for v0.1.0)

All services on one host:

```
compose.yaml:
  services:
    api:        # FastAPI app
    qdrant:     # Vector store
    embedding:  # BGE-M3 via Ollama or TEI
```

- Strongest air-gap posture (NFR-1).
- Simplest deployment; single `docker compose up`.
- Constrained by host resources (RAM, VRAM if GPU-accelerated embedding).

### 7.2 Topology 2 — split embedding

Embedding service on a separate internal node. The API server and Qdrant remain
on the primary host. `EMBEDDING_BASE_URL` points to the remote node.

- Frees host resources for Qdrant and the API.
- Keeps the vector index local.

### 7.3 Topology 3 — fully distributed

API server on one host; Qdrant and embedding on separate node(s). All
communication over HTTP.

- Centralised, independently scalable.
- Strongest resource headroom.
- Heaviest operational footprint.

### 7.4 Configuration

Topology is controlled entirely by environment variables:

| Variable             | Default (topology 1)            | Override for remote |
|----------------------|---------------------------------|---------------------|
| `QDRANT_URL`         | `http://qdrant:6333`            | Remote Qdrant URL   |
| `EMBEDDING_BASE_URL` | `http://embedding:11434`        | Remote embedding URL|
| `EMBEDDING_MODEL`    | `bge-m3`                        | —                   |

No code changes between topologies. The `compose.yaml` shipped with the repo
is topology 1; operators override variables for other topologies.

## 8. Licensing summary

| Component           | License       | Role                | Verified via                  |
|---------------------|---------------|---------------------|-------------------------------|
| FastAPI             | MIT           | API framework       | PyPI / GitHub                 |
| Pydantic            | MIT           | Data models         | PyPI / GitHub                 |
| Qdrant              | Apache-2.0    | Vector store        | GitHub LICENSE                |
| BGE-M3              | MIT           | Embedding model     | Hugging Face model card       |
| Docling (codebase)  | MIT           | PDF parsing         | GitHub LICENSE                |
| Granite-Docling-258M| Apache-2.0    | VLM for Docling     | Hugging Face model card       |
| Ollama              | MIT           | Model serving       | GitHub LICENSE                |
| HF TEI              | Apache-2.0    | Model serving (alt) | GitHub LICENSE                |

All primary components are MIT or Apache-2.0. No copyleft in the core stack.

## 9. Updated stack summary

| Layer                   | Choice                                              |
|-------------------------|-----------------------------------------------------|
| API framework           | FastAPI + Pydantic + Uvicorn (MIT)                  |
| Embedding model         | BGE-M3 (MIT), served via Ollama or TEI              |
| Vector store            | Qdrant (Apache-2.0); Chroma as fallback             |
| Document parsing (MD)   | Project code (structure-aware heading split)         |
| Document parsing (PDF)  | Docling + Granite-Docling-258M (MIT / Apache-2.0);  |
|                         | PyMuPDF4LLM as containerised AGPL fallback          |
| Retrieval orchestration | Project code (lean); Haystack as escape hatch        |
| Deployment              | Docker Compose; topology via env vars               |

## 10. Consequences

### 10.1 Positive

- Every primary component is permissively licensed — the platform can live
  alongside or be consumed by proprietary code without copyleft risk.
- Docling + Granite-Docling covers PDF, DOCX, PPTX, and images under one
  library, reducing the integration surface for future format phases.
- Qdrant's native sparse-vector support gives the strongest hybrid retrieval
  without a second system.
- The topology is controlled entirely by environment variables — no code
  changes between all-in-one and distributed deployments.

### 10.2 Negative / trade-offs

- Qdrant is a heavier operational component than an embedded store (LanceDB);
  justified by the platform's service-native architecture.
- Docling's VLM path (Granite-Docling-258M) requires either a GPU or
  CPU-based inference, adding resource requirements beyond a pure text-parsing
  library. Mitigated by the model's small size (258M params).
- The AGPL fallback (PyMuPDF4LLM) requires container isolation, which is
  operationally heavier than a pip install. Justified by NFR-3.

### 10.3 Out of scope (deferred decisions)

- Reranker model selection (deferred until evaluation shows the hybrid
  baseline is insufficient).
- Python SDK for the retrieval API (deferred to post-v0.1.0).
- DOCX / PPTX ingestion (future format phase; Docling supports them).
- CI/CD pipeline configuration.
- Monitoring and observability stack.
- Embedded image description (VLM inference on figures; see §5.4)
- Standalone image ingestion and visual retrieval
- OCR for scanned documents (Docling OCR flag available but untested and disabled by default)

## 11. Open items

- Confirm Qdrant vs Chroma selection in review (Qdrant recommended).
- Benchmark Docling + Granite-Docling-258M against representative ISO 26262
  PDFs during v0.2.0 development; if structure extraction is insufficient,
  evaluate the PyMuPDF4LLM containerised fallback.
- Review MinerU's custom license terms if Docling proves insufficient.
- Re-verify Ollama's MIT license against its canonical LICENSE file (verified
  via GitHub, not independently confirmed via package metadata).
- Confirm the embedding serving path (Ollama vs TEI) during v0.1.0
  development based on operational simplicity.

## References

[^1]: [Docling — GitHub (MIT)](https://github.com/docling-project/docling)
[^2]: [Granite-Docling-258M — Hugging Face (Apache 2.0)](https://huggingface.co/ibm-granite/granite-docling-258M)
[^3]: [BAAI/bge-m3 — Hugging Face (MIT)](https://huggingface.co/BAAI/bge-m3)
[^4]: [Qdrant — GitHub (Apache-2.0)](https://github.com/qdrant/qdrant)
[^5]: [pymupdf4llm LICENSE — GitHub (AGPL-3.0)](https://github.com/pymupdf/pymupdf4llm/blob/main/LICENSE)
[^6]: [marker-pdf — PyPI (GPL-3.0-or-later)](https://pypi.org/project/marker-pdf/)
[^7]: [MinerU — GitHub (custom Apache-2.0-based license)](https://github.com/opendatalab/mineru)
[^8]: [Docling: IBM Open-Source Document Processing — IDP-Software](https://idp-software.com/vendors/docling/)
[^9]: [IBM Granite-Docling announcement](https://ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)
[^10]: [Chroma — Wikipedia (Apache-2.0)](https://en.wikipedia.org/wiki/Chroma_(vector_database))
