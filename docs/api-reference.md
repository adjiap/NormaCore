# API Reference

> [!NOTE]
> NormaCore uses FastAPI backend that automatically generates Swagger UI when the stack is running.

The interactive API reference is available at `http://localhost:8000/docs`
when the stack is running. It includes full request and response schemas,
field-level validation rules, and a try-it-out interface for all endpoints.

The raw OpenAPI spec is available at `http://localhost:8000/openapi.json`
and can be imported into Postman, Insomnia, or any OpenAPI-compatible client.

## Endpoints summary

| Method | Path           | Description                                             |
|--------|----------------|---------------------------------------------------------|
| `POST` | `/v1/ingest`   | Ingest a corpus from its manifest into the vector store |
| `POST` | `/v1/retrieve` | Query a corpus and return ranked chunks                 |
| `GET`  | `/v1/corpora`  | List all available corpus IDs                           |
| `GET`  | `/v1/health`   | Liveness healthcheck                                    |
