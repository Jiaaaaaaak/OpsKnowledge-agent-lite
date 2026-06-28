"""營運健康聚合。

把分散的依賴檢查（PostgreSQL、pgvector、Redis）與主機 pulse（CPU／記憶體／磁碟／
uptime）收斂成單一結構，供需登入的營運儀表板與固定狀態列使用。
任一依賴失敗只降級為 degraded，絕不讓健康檢查本身拋例外。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import psutil
import redis

from app.core.config import settings
from app.db.session import check_db_connection, check_vector_extension

# 進程啟動時間，用來算 app uptime（非系統開機時間）。
_STARTED_AT = time.monotonic()

# 先觸發一次取樣建立基準，避免首次 cpu_percent(interval=None) 一律回 0.0 誤導狀態列。
psutil.cpu_percent(interval=None)

# Redis PING 的 socket 逾時：健康檢查必須快速失敗，不能因為 Redis 卡住而拖住整個請求。
_REDIS_TIMEOUT_SECONDS = 1.0


def check_database() -> str:
    return "connected" if check_db_connection() else "disconnected"


def check_vector() -> str:
    return "connected" if check_vector_extension() else "disconnected"


def check_redis() -> str:
    client = None
    try:
        client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
            socket_timeout=_REDIS_TIMEOUT_SECONDS,
        )
        return "connected" if client.ping() else "disconnected"
    except Exception:
        # 連線拒絕／逾時／認證等任何錯誤都只降級，不外拋。
        return "disconnected"
    finally:
        # 此端點會被狀態列持續輪詢，明確關閉連線池，不依賴 GC 回收 socket。
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _pulse() -> dict:
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "uptime_seconds": int(time.monotonic() - _STARTED_AT),
        }
    except Exception:
        # psutil 在受限容器／cgroup 下可能拋例外；主機 metrics 取不到也不得讓健康端點 500，
        # 以 None 回報並維持回應結構完整（status 仍由依賴狀態決定）。
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "disk_percent": None,
            "uptime_seconds": None,
        }


def build_operational_health() -> dict:
    services = {
        "api": "ok",
        "database": check_database(),
        "vector": check_vector(),
        "redis": check_redis(),
    }
    # api 永遠 ok（能執行到這就代表 API 活著）；其餘任一非 connected 即整體 degraded。
    degraded = any(
        value != "connected" for key, value in services.items() if key != "api"
    )
    return {
        "status": "degraded" if degraded else "ok",
        "services": services,
        "pulse": _pulse(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
