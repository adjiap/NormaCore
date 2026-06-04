# ADR-003: Prompt Orchestration — Chunk Injection Pattern for NormaCore Consumers

- Status: Proposed
- Date: 2026-06-03
- Deciders: Project owner (single-developer)
- Relates to: ADR-001 (NormaCore system architecture); ADR-002 (NormaCore tech stack)
- Scope: **Consuming applications**, not NormaCore itself. This ADR documents
  the recommended pattern for any application that calls `POST /retrieve` and
  passes the results to an LLM.

> [!NOTE]
> NormaCore stops at retrieval. It returns ranked chunks with metadata. This
> ADR answers the next question: *how does a consuming application turn those
> chunks into a grounded LLM prompt?* The pattern described here applies to
> any project that depends on NormaCore as a retrieval backend — including
> the two known consuming projects at the time of writing.

---

## 1. Context and problem statement

NormaCore exposes a `POST /retrieve` endpoint that returns ranked chunks,
each carrying `corpus_id`, `section_id`, `heading_path`, `source`, and a
relevance score. A consuming application receives these chunks and must
construct an LLM prompt that:

1. Grounds the model's answer in the retrieved content only.
2. Preserves attribution so the model can cite the exact clause or section.
3. Handles multi-corpus queries (e.g. "review these requirements against
   ISO 26262 *and* MIL-STD-882E simultaneously").
4. Keeps the system prompt stable and cacheable across requests, separating
   persistent instructions from dynamic per-request context.

Without a documented pattern, each consuming project will independently
invent an ad-hoc prompt structure, leading to inconsistent citation formats,
context rot (too many chunks injected without labelling), and untraceable
answers.

### 1.1 The known consumers

At the time of writing, two projects beyond NormaCore are planned that will
call `POST /retrieve`:

- **Project A** — requirement review tool: takes a requirements list and
  reviews each item against one or more standards corpora.
- **Project B** — safety analysis assistant: answers domain-specific queries
  grounded in selected standards.

Both share the same structural need: retrieve → inject → generate → cite.
This ADR documents a shared pattern both projects can adopt.

---

## 2. The chunk injection pattern

### 2.1 Overview

Chunk injection is the act of inserting NormaCore-retrieved chunks into an
LLM prompt as labelled, structured context — immediately before the user's
actual task instruction. The model is instructed via the system prompt to
treat the injected context as the authoritative source and to cite back to
it using the chunk metadata.

The flow per request is:

```
1. Consuming app receives user task (query or requirements list).
2. App calls POST /retrieve for each relevant corpus:
     POST /retrieve  { corpus_id: "iso-26262-v4",   query: "<task>", top_k: 5 }
     POST /retrieve  { corpus_id: "mil-std-882e-d",  query: "<task>", top_k: 5 }
3. App assembles the prompt (see section 2.2).
4. App calls the LLM with the assembled prompt.
5. LLM returns an answer with citations in the format defined by the
   system prompt.
```

### 2.2 Prompt structure

The prompt is split across two roles: `system` and `user`. They have
distinct responsibilities and must not be mixed.

#### System prompt (static, per application)

The system prompt defines the model's role, grounding rules, citation
format, and refusal behaviour. It does not contain retrieved chunks — it
is stable across all requests from a given application and can be cached.

```
You are a functional safety engineer reviewing technical documents.

Rules:
- Answer ONLY using the reference context provided in the user message.
- If the answer cannot be found in the provided context, respond with:
  "Not covered by the provided standards."
- Do not use prior knowledge outside the provided context.
- Every factual claim in your answer must include a citation in this format:
  [corpus_id > section_id > heading]
  Example: [iso-26262-v4 > §8.4.2 > Hazard and Risk Assessment]
```

Adapt the role description and citation format per consuming project. The
grounding instruction ("answer ONLY using…") and the refusal instruction
("if not found, say so") are mandatory in all consumers.

#### User message (dynamic, per request)

The user message contains three parts in order:

1. **Reference context block** — the injected chunks, labelled by source.
2. **Separator** — a visual boundary between context and task.
3. **Task instruction** — the actual user query or requirements to review.

```
## Reference Context

### [iso-26262-v4]
[1] §8.4.2 > Hazard and Risk Assessment
"A hazard analysis and risk assessment (HARA) shall be performed to
identify and categorise the hazardous events..."

[2] §3.75 > Glossary — ASIL
"Automotive Safety Integrity Level (ASIL): one of four levels to specify
the item's or element's necessary requirements of ISO 26262..."

### [mil-std-882e-d]
[3] §3.1 > Definitions — PHA
"Preliminary Hazard Analysis: a disciplined analysis of the hazard
characteristics of a system performed before detailed design..."

[4] §4.2.3 > Task 203 — Hazard Identification
"The contractor shall identify hazards associated with the system and
subsystem design..."

---

## Task

Review the following requirements against both standards above.
For each requirement, identify: compliance status, relevant clauses,
and any gaps or conflicts between the two standards.

Requirements:
1. The system shall perform hazard analysis prior to design freeze.
2. All identified hazards shall be assigned a risk level using a
   structured classification method.
```

### 2.3 Chunk formatting rules

Each injected chunk must be formatted as:

```
[<ordinal>] <section_id> > <heading_path[-1]>
"<chunk text>"
```

- `ordinal` — sequential integer for in-answer back-reference (e.g. "as
  stated in [3]").
- `section_id` — from NormaCore chunk metadata (e.g. `§4.2.3`).
- `heading_path[-1]` — the deepest heading in the path, giving the chunk
  its identity without repeating the full hierarchy.
- `chunk text` — the raw text from NormaCore, enclosed in double quotes.
  Do not paraphrase or summarise; the LLM must see the original wording.

Full `heading_path` is available in the metadata and can be logged for
traceability, but only the leaf heading appears in the prompt to reduce
token usage.

### 2.4 Multi-corpus grouping

When querying more than one corpus, group chunks under a `### [corpus_id]`
heading. Do not interleave chunks from different corpora — grouped context
makes it easier for the model to distinguish sources and reduces citation
errors.

### 2.5 Separator

Use `---` on its own line as the separator between the reference context
block and the task instruction. This is a visual convention, not a
technical requirement. XML tags (`<context>` / `</context>`) are an
acceptable alternative and may produce more reliable behaviour with models
that support structured input.

The separator signals to the model (and to developers reading prompt logs)
where retrieved context ends and the actual task begins.

---

## 3. Retrieval call design

### 3.1 Query construction

The query sent to `POST /retrieve` should reflect what the model needs to
reason about, not the literal user input. For a requirement review task,
derive one query per requirement or per semantic cluster, not one query for
the entire requirements list.

```python
# Example — one retrieve call per requirement
for req in requirements:
    chunks_iso   = retrieve("iso-26262-v4",  query=req.text, top_k=3)
    chunks_mil   = retrieve("mil-std-882e-d", query=req.text, top_k=3)
    context = build_context_block([chunks_iso, chunks_mil])
    answer  = llm(system_prompt, user_prompt(context, req))
```

Alternatively, derive a single semantic query from the full task and
retrieve once per corpus. Use per-requirement retrieval when precision
matters; use task-level retrieval for open-ended questions.

### 3.2 top_k guidance

| Use case                          | Recommended top_k |
|-----------------------------------|-------------------|
| Single factoid / definition       | 3                 |
| Requirement review (per req)      | 3–5               |
| Open-ended analysis               | 5–7               |
| Cross-standard comparison         | 5 per corpus      |

Keep total injected tokens below ~4 000 to avoid context rot (retrieved
chunks diluting each other). Prefer fewer, higher-ranked chunks over many
lower-ranked ones.

### 3.3 Score filtering

NormaCore returns a relevance score per chunk. Consuming applications
should filter out chunks below a minimum score threshold before injection.
A reasonable default is to drop chunks with score < 0.5 (or equivalent
normalised score). This prevents injecting weakly-relevant content that
confuses the model.

---

## 4. Citation traceability

The citation format `[corpus_id > section_id > heading]` is designed to
be machine-parseable. Consuming applications should:

- Log the full chunk metadata (corpus_id, section_id, heading_path,
  chunk_index, score) alongside every LLM call.
- Parse citations from the model's answer and cross-reference them against
  the logged metadata to verify the model cited a chunk that was actually
  retrieved (not hallucinated).
- Surface the citation to the end user as a human-readable reference:
  e.g. "ISO 26262:2018, Part 3, §8.4.2 — Hazard and Risk Assessment".

This traceability chain — NormaCore chunk → injected context → LLM
citation → logged metadata — is what makes the system auditable. It is
the consuming application's responsibility to close this loop; NormaCore
provides the metadata, the system prompt defines the citation format, and
the application logs and validates the output.

---

## 5. Options considered

### 5.1 Option A — chunks in system prompt

Inject retrieved chunks into the system prompt rather than the user
message.

Rejected. The system prompt is meant to be stable and cacheable. Injecting
dynamic, per-request retrieved content into it defeats caching, inflates
token costs on every request, and mixes persistent behaviour rules with
ephemeral context. Most LLM providers cache the system prompt prefix;
invalidating it on every request removes that benefit.

### 5.2 Option B — no separator, inline context

Embed the reference context inline within the task instruction without a
visual separator or labelling.

Rejected. Without clear labelling, the model cannot distinguish which
text is retrieved context (authoritative) and which is the user's task
description. Citation accuracy degrades. Prompt logs become unreadable.

### 5.3 Option C — XML tags instead of Markdown headings

Use `<context>`, `<source>`, `<chunk>` XML tags to delimit context blocks
instead of Markdown `###` headings and `---` separators.

Not rejected — this is a valid and sometimes superior alternative,
particularly for models with strong XML-following behaviour (e.g. Claude).
The `---` / Markdown convention is chosen as the default because it is
more readable in logs and works consistently across all major models.
XML tags are documented as an acceptable alternative (section 2.5).

### 5.4 Option D — one prompt per corpus, merge answers

Query each corpus independently, generate a separate LLM answer per
corpus, then merge the answers in a second LLM call.

Not rejected for all cases — this pattern is appropriate when corpora are
very large and top_k alone cannot surface all relevant clauses. For the
known consuming projects (requirement review, safety analysis), single-pass
multi-corpus injection is sufficient and avoids the latency and cost of a
second LLM call. Documented here as a future escalation path if single-pass
quality is insufficient.

---

## 6. Consequences

### 6.1 Positive

- A shared pattern across consuming projects means citation formats,
  grounding rules, and log structures are consistent and comparable.
- The separation of system prompt (stable) and user message (dynamic)
  enables prompt caching and reduces per-request token costs.
- Chunk labelling with `corpus_id > section_id > heading` makes citations
  auditable end-to-end without any additional tooling.
- The pattern is model-agnostic: it works with any LLM that accepts a
  system/user message structure (OpenAI-compatible, Anthropic, Ollama
  local models).

### 6.2 Negative / trade-offs

- Per-requirement retrieval (section 3.1) multiplies the number of
  `POST /retrieve` calls linearly with the number of requirements. For a
  50-requirement list, this is 50 × (number of corpora) calls. Acceptable
  for the current scale; revisit if latency becomes a bottleneck.
- The citation cross-reference check (section 4) requires the consuming
  application to implement log parsing logic. This is a small but real
  implementation cost.
- top_k and score filtering defaults (section 3.2–3.3) will need
  per-corpus tuning once NormaCore's eval harness produces baseline
  Recall@5 and MRR metrics. The values here are starting defaults, not
  validated constants.

### 6.3 Out of scope

- Prompt caching implementation details (LLM provider-specific).
- Reranking of retrieved chunks before injection (NormaCore future
  enhancement; when available, consuming apps should prefer the reranked
  order).
- Agentic / multi-turn retrieval loops (where the model decides which
  corpus to query next). Deferred; single-pass retrieval is sufficient
  for the known use cases.
- End-user citation rendering UI (consuming application concern).

---

## 7. Open items

- Validate score filtering threshold (0.5) against NormaCore eval harness
  results once available.
- Decide whether Project A and Project B share a common prompt library
  (thin shared Python module) or maintain independent system prompts.
- Evaluate XML tag alternative (section 5.3) empirically once a candidate
  LLM is selected for each consuming project.
- Define the log schema for citation cross-reference (section 4) — JSON
  structure, retention policy, tooling.
