from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    LLM_MODEL: str = "meta/llama-3.3-70b-instruct"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_INITIAL_DELAY_SECONDS: float = 1.0
    LLM_RETRY_MAX_DELAY_SECONDS: float = 10.0
    LLM_RETRY_MAX_TOKENS: int = 8192

    DB_PATH: str = "./data/arxiv.db"
    DATA_DIR: str = "./data"

    FETCH_CRON_HOUR: int = 9
    FETCH_CRON_MINUTE: int = 0

    WORKER_CONCURRENCY: int = 2
    FETCH_MAX_RESULTS_PER_QUERY: int = 50
    FETCH_LOOKBACK_DAYS: int = 2
    FETCH_CATEGORY_ALLOWLIST: str = "cs.AI,cs.CL,cs.CV,cs.GR,cs.MA,cs.MM"
    FETCH_CATEGORY_PREFIX: str = "cs."
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    SUMMARY_PDF_MAX_CHARS: int = 60000

    @property
    def data_dir_path(self) -> Path:
        return Path(self.DATA_DIR).resolve()

    @property
    def pdfs_dir(self) -> Path:
        p = self.data_dir_path / "pdfs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def figures_dir(self) -> Path:
        p = self.data_dir_path / "figures"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        return f"sqlite:///{Path(self.DB_PATH).resolve()}"

    @property
    def cors_allow_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
