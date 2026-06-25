"""add pg_trgm + trigram index for CJK / exact-term keyword search

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25

english FTS parser 無法切分中文（無空格的中文詞會變成單一 lexeme），導致中文關鍵詞 /
錯誤碼 / 指令這類 exact term 的 keyword 檢索不穩。改用 pg_trgm 對 content 做子字串比對
（語言中性），與既有 tsvector 並用；本 migration 只建 extension 與 trigram 索引，
不重建既有的 search_vector 欄位（零資料風險）。
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # GIN trigram 索引讓 content ILIKE '%term%'（含中文子字串）的查詢可走索引。
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm
        ON document_chunks USING gin (content gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_content_trgm")
    # 不丟棄 pg_trgm extension：可能有其他物件依賴，保留較安全。
