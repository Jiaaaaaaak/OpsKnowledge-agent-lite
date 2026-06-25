from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


class KeywordRetriever:
    """PostgreSQL full-text retriever over document chunks."""

    def __init__(self, *, db_session: Session | None = None) -> None:
        self._db_session = db_session

    @staticmethod
    def _row_value(row, key: str):
        mapping = getattr(row, "_mapping", None)
        if mapping is not None and key in mapping:
            return mapping[key]
        return getattr(row, key)

    @contextmanager
    def _session_scope(self) -> Iterator[tuple[Session, bool]]:
        if self._db_session is not None:
            yield self._db_session, False
            return

        db = SessionLocal()
        try:
            yield db, True
        finally:
            db.close()

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        # 兩路並用：
        #  1) tsvector 全文比對（英文 token、stemming）。
        #  2) pg_trgm 子字串比對（content ILIKE '%term%'）——語言中性，補足 english parser
        #     無法切分中文的弱點，讓中文關鍵詞 / 錯誤碼 / 指令這類 exact term 也能穩定命中。
        # 排序：tsvector rank + 精確子字串命中加權，讓 exact term 命中排前。
        search_sql = text(
            """
            WITH query AS (
                SELECT websearch_to_tsquery('english', :query) AS q
            )
            SELECT
                dc.id::text AS chunk_id,
                dc.content AS content,
                dc.metadata AS metadata,
                dc.document_id::text AS document_id,
                d.filename AS filename,
                dc.chunk_index AS chunk_index,
                ts_rank_cd(dc.search_vector, query.q)
                    + CASE WHEN dc.content ILIKE '%' || :query || '%' THEN 1.0 ELSE 0 END AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            CROSS JOIN query
            WHERE d.project_id = CAST(:project_id AS uuid)
              AND (
                  dc.search_vector @@ query.q
                  OR dc.content ILIKE '%' || :query || '%'
              )
            ORDER BY rank DESC, dc.chunk_index ASC
            LIMIT :top_k
            """
        )
        with self._session_scope() as (db, _owns_session):
            rows = db.execute(
                search_sql,
                {"project_id": str(project_id), "query": query, "top_k": top_k},
            ).fetchall()

        hits: list[dict] = []
        for row in rows:
            chunk_id = self._row_value(row, "chunk_id")
            document_id = self._row_value(row, "document_id")
            filename = self._row_value(row, "filename")
            chunk_index = self._row_value(row, "chunk_index")
            metadata = dict(self._row_value(row, "metadata") or {})
            metadata.update(
                {
                    "project_id": str(project_id),
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "filename": filename,
                    "chunk_index": chunk_index,
                }
            )
            rank = self._row_value(row, "rank")
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": self._row_value(row, "content"),
                    "metadata": metadata,
                    "score": float(rank) if rank is not None else None,
                    "source": "keyword",
                }
            )
        return hits
