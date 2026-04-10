from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Uncloud Medical GraphRAG Backend"
    app_env: str = "development"

    firecrawl_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-6"

    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "medical-rag-password"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "iknl_cancer_knowledge"

    postgres_url: str = "postgresql://kankerwijzer:kankerwijzer@localhost:5432/kankerwijzer"

    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 1024

    abstention_threshold: float = 0.45  # calibrated in Step 12

    request_timeout_seconds: float = 30.0
    local_search_default_limit: int = 5

    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1],
    )
    team_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2],
    )
    hackathon_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4],
    )

    @property
    def kanker_dataset_path(self) -> Path:
        return self.hackathon_root / "data" / "kanker_nl_pages_all.json"

    @property
    def reports_dir(self) -> Path:
        return self.hackathon_root / "data" / "reports"

    @property
    def scientific_publications_dir(self) -> Path:
        return self.hackathon_root / "data" / "scientific_publications"

    @property
    def sample_output_dir(self) -> Path:
        return self.team_root / "artifacts" / "source_samples"


@lru_cache
def get_settings() -> Settings:
    return Settings()
