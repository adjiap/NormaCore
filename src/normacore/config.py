"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """NormaCore runtime settings.

    All values are read from environment variables or .env file.
    Defaults point to the compose.yaml service names for container use,
    and to localhost for local development.
    """

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "bge-m3")


settings = Settings()
