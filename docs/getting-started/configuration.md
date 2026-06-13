# Configuration

All configuration is done via environment variables, loaded from `.env`.
Copy `.env.example` to get started:

```bash
cp .env.example .env
```

## Reference

| Variable                          | Default                         | Description                                                                  |
|-----------------------------------|---------------------------------|------------------------------------------------------------------------------|
| `API_HOST`                        | `0.0.0.0`                       | Host the API binds to                                                        |
| `API_PORT`                        | `8000`                          | Port the API listens on                                                      |
| `LOG_LEVEL`                       | `INFO`                          | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                          |
| `LOG_FILE`                        | `logs/normacore.log`            | Log file path                                                                |
| `QDRANT_URL`                      | `http://qdrant:6333`            | Qdrant vector store endpoint                                                 |
| `EMBEDDING_BASE_URL`              | `http://ollama-container:11434` | Embedding service endpoint                                                   |
| `EMBEDDING_MODEL`                 | `bge-m3`                        | Embedding model name                                                         |
| `LOCAL_CORPORA_PATH`              | `./corpora`                     | Host path to mount as the corpora directory                                  |
| `LOCAL_DOWNLOADED_MODELS_MOUNTED` | _(empty)_                       | Host path for Ollama model storage. Leave empty to use a named Docker volume |

## Deployment topologies

The topology is controlled entirely by `QDRANT_URL` and `EMBEDDING_BASE_URL`
— no code changes needed between deployments.

| Topology             | `QDRANT_URL`                  | `EMBEDDING_BASE_URL`            |
|----------------------|-------------------------------|---------------------------------|
| All-in-one (default) | `http://qdrant:6333`          | `http://ollama-container:11434` |
| Split embedding      | `http://qdrant:6333`          | `http://<remote-node>:11434`    |
| Fully distributed    | `http://<remote-qdrant>:6333` | `http://<remote-node>:11434`    |
