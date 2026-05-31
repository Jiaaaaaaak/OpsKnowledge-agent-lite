from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 專案根目錄的 .env 絕對路徑（config.py 位於 backend/app/core/，往上三層為專案根目錄）。
# 錨定成絕對路徑，讓設定不論從哪個目錄執行（專案根目錄或 backend/）都讀同一份 .env，
# 避免「相對 CWD 找不到 .env 而退回預設值」的問題。
# 正式環境仍可由 Docker / OS 環境變數覆蓋（其優先序高於 .env 檔）。
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # App
    app_name: str = "OpsKnowledge Agent Lite"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "opsknowledge"
    postgres_user: str = "opsuser"
    postgres_password: str = "opspassword"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_name: str = "opsknowledge_docs"

    # Provider selection
    # "openai" — calls OpenAI-compatible API (requires a real OPENAI_API_KEY)
    # "ollama" — calls a local Ollama HTTP server (private / on-premise deployment)
    # "mock"   — deterministic local provider; no API key needed; safe for CI / local dev
    # 預設 "mock"：與 .env.example 與 README "defaults to mock mode" 的承諾一致；
    # 跑測試或第一次 spin up（沒有 .env）時不會因為缺 OPENAI_API_KEY 而崩。
    embedding_provider: str = "mock"
    llm_provider: str = "mock"
    mock_embedding_dim: int = 384  # fixed vector dimension used by MockEmbeddingProvider

    # OpenAI-compatible LLM
    openai_api_key: str = "sk-placeholder"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # Ollama (local LLM provider for private / on-premise deployment)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"


settings = Settings()
