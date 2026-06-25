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

    # CORS：允許的前端來源（逗號分隔）。預設僅前端 dev server；正式部署以 env 覆蓋成正式網域。
    # 不再用萬用 "*"，避免任意網站直接打公開操作面。
    cors_origins: str = "http://localhost:8501"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # 上傳限制：避免大檔一次讀進記憶體後拖垮 PDF parse / OCR / embedding。
    max_upload_mb: int = 20                   # 單檔大小上限（MB）
    max_pdf_pages: int = 500                  # 單份 PDF 頁數上限
    max_chunks_per_document: int = 5000       # 單份文件可產生的 chunk 數上限

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

    # Provider selection
    # "openai" — calls OpenAI-compatible API (requires a real OPENAI_API_KEY)
    # "ollama" — calls a local Ollama HTTP server (private / on-premise deployment)
    # "mock"   — deterministic local provider; no API key needed; safe for CI / local dev
    # 程式內建預設仍安全離線；專案 .env.example 則以 Ollama LLM + mock embedding
    # 作為面試 / 地端展示預設。
    embedding_provider: str = "mock"
    llm_provider: str = "mock"
    # 向量維度的單一真實來源；document_chunks.embedding 與各 provider 都依此值。
    # bge-m3（Ollama 多語 embedding）輸出 1024 維。
    embedding_dimensions: int = 1024
    mock_embedding_dim: int = 1024  # MockEmbeddingProvider 預設維度，需與 embedding_dimensions 一致
    embedding_batch_size: int = 16

    # OpenAI-compatible LLM
    openai_api_key: str = "sk-placeholder"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # Ollama (local LLM / embedding provider for private / on-premise deployment)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    # 多語 embedding 模型（跨語檢索：英文文件 + 中文問題）。bge-m3 輸出 1024 維。
    ollama_embedding_model: str = "bge-m3"
    ollama_timeout_seconds: float = 180.0

    # Reranker（第二階段 cross-encoder，經 HF text-embeddings-inference 提供）
    # 預設關閉：關閉時走單階段向量檢索，不需額外容器。
    reranker_enabled: bool = False
    reranker_base_url: str = "http://localhost:8080"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidate_k: int = 30          # 重排前由 pgvector 召回的候選數
    reranker_timeout_seconds: float = 30.0

    # Agent（自主 tool-calling 檢索）：每次對話最多幾步 LLM↔工具往返，作安全上限避免無限迴圈。
    agent_max_steps: int = 5

    # OCR fallback（掃描 / 影像型 PDF）：抽不到文字的頁才渲染 + Tesseract 辨識。
    # tesseract / poppler 不在時自動降級（等同關閉），不影響原生文字 PDF 與 CI。
    ocr_enabled: bool = True
    ocr_dpi: int = 200                       # 頁面渲染解析度（速度／準確度平衡）
    ocr_languages: str = "chi_tra+chi_sim+eng"
    ocr_min_chars: int = 20                  # 頁面 strip 後字數 < 此值即視為需 OCR
    ocr_timeout_seconds: float = 30.0        # 單頁 OCR 上限秒數，避免單頁卡死整份匯入


settings = Settings()
