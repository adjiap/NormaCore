# Requirements

## Host requirements

| Requirement                        | Minimum | Notes                       |
|------------------------------------|---------|-----------------------------|
| Python                             | 3.12+   | Managed via `uv`            |
| [`uv`](https://docs.astral.sh/uv/) | Latest  | Dependency and venv manager |
| Docker or Podman                   | Latest  | With Compose plugin         |
| RAM                                | 8 GB    | 16 GB recommended with GPU  |
| Disk                               | 5 GB    | For models and vector index |

> [!NOTE]
> Windows users should run via WSL. All scripts report as Linux via `uname` —
> no separate Windows branch is needed.

> [!NOTE]
> An NVIDIA GPU is optional — CPU mode is fully supported, though embedding
> will be significantly slower on large corpora.

## Network requirements

NormaCore is fully air-gap capable. No internet egress is required at runtime.
The only outbound connections needed are during initial setup to pull container
images and the embedding model.
