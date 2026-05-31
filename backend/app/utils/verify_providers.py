"""驗證目前設定的 LLM / Embedding provider 是否能正常呼叫。

用法：
    python -m app.utils.verify_providers   # 於 backend/ 目錄下執行

特性：
- 直接重用既有的 get_llm_provider() / get_embedding_provider() 工廠，
  不改動主架構，也不影響 mock 模式行為。
- mock / ollama / openai 任一模式皆可執行（會測試「當下設定」的 provider）。
- 絕不印出 API 金鑰；金鑰只顯示遮罩後的摘要，錯誤訊息也會做去敏處理。
- 金鑰缺漏或無效時回傳清楚的錯誤，並以非 0 結束碼結束（方便 CI 使用）。
"""
from __future__ import annotations

from app.core.config import settings
from app.services.embedding_service import get_embedding_provider
from app.services.llm_service import get_llm_provider

# 與 embedding_service 一致：視為「未設定」的金鑰預設值
_PLACEHOLDER_KEYS = {"", "sk-placeholder", "sk-your-key-here"}


def _mask_key(key: str) -> str:
    """只回傳遮罩後的摘要，不洩漏金鑰本體。"""
    if not key or key in _PLACEHOLDER_KEYS:
        return "未設定（仍是 placeholder）"
    # 僅顯示非機密的前綴與長度，足以辨識「有沒有換成真金鑰」
    return f"已設定（前綴 {key[:3]}…，長度 {len(key)}）"


def _scrub(text: str) -> str:
    """從任意輸出（多半是錯誤訊息）中移除金鑰本體，避免意外外洩。"""
    key = settings.openai_api_key
    if key and key not in _PLACEHOLDER_KEYS:
        text = text.replace(key, "***REDACTED***")
    return text


def _print_providers() -> None:
    print("== Provider 設定 ==")
    print(f"  LLM_PROVIDER       = {settings.llm_provider}")
    print(f"  EMBEDDING_PROVIDER = {settings.embedding_provider}")
    print(f"  LLM_MODEL          = {settings.llm_model}")
    print(f"  EMBEDDING_MODEL    = {settings.embedding_model}")
    print(f"  OPENAI_BASE_URL    = {settings.openai_base_url}")
    print(f"  OPENAI_API_KEY     = {_mask_key(settings.openai_api_key)}")
    if settings.llm_provider == "ollama":
        print(f"  OLLAMA_BASE_URL    = {settings.ollama_base_url}")
        print(f"  OLLAMA_MODEL       = {settings.ollama_model}")
    print()


def _test_llm() -> bool:
    print("== 測試 LLM（一次短請求）==")
    try:
        provider = get_llm_provider()
        answer, usage = provider.complete(
            "You are a health-check probe. Reply with a single short word.",
            "Reply with the word: OK",
        )
        snippet = (answer or "").strip().replace("\n", " ")[:80]
        print(f"  [成功] provider = {type(provider).__name__}")
        print(f"         回應片段：{snippet!r}")
        print(f"         usage：{usage}")
        ok = True
    except Exception as exc:  # noqa: BLE001 — 驗證工具需攔截所有失敗並友善回報
        print(f"  [失敗] {type(exc).__name__}: {_scrub(str(exc))[:300]}")
        ok = False
    print()
    return ok


def _test_embedding() -> bool:
    print("== 測試 Embedding（一次短請求）==")
    try:
        provider = get_embedding_provider()
        vectors = provider.embed(["health check probe"])
        if not vectors or not vectors[0]:
            raise RuntimeError("provider 回傳空向量")
        first = vectors[0]
        print(f"  [成功] provider = {type(provider).__name__}")
        print(f"         向量維度：{len(first)}")
        print(f"         前 3 維：{[round(x, 4) for x in first[:3]]}")
        ok = True
    except Exception as exc:  # noqa: BLE001
        print(f"  [失敗] {type(exc).__name__}: {_scrub(str(exc))[:300]}")
        ok = False
    print()
    return ok


def main() -> int:
    _print_providers()

    # openai 模式但金鑰還是 placeholder：提早給出明確指引（兩個測試仍會照跑並回報失敗）
    uses_openai = "openai" in (settings.llm_provider, settings.embedding_provider)
    if uses_openai and settings.openai_api_key in _PLACEHOLDER_KEYS:
        print("  [警告] provider 設為 openai，但 OPENAI_API_KEY 尚未設定（仍是 placeholder）。")
        print("         請在 backend/.env 填入有效金鑰後再執行。\n")

    llm_ok = _test_llm()
    emb_ok = _test_embedding()

    print("== 總結 ==")
    print(f"  LLM       : {'PASS' if llm_ok else 'FAIL'}")
    print(f"  Embedding : {'PASS' if emb_ok else 'FAIL'}")
    return 0 if (llm_ok and emb_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
