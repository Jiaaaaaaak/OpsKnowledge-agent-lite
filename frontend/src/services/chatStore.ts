// 對話狀態的模組層 store：把「送出請求 → 等待 → 寫回答案」的生命週期從 React 元件抽離，
// 讓使用者切換頁面（元件卸載）後請求仍持續，完成時通知當前掛載的頁面更新。
// 同時集中草稿持久化與前端問答快取。
import { chat } from './api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: any[];
  isError?: boolean;
  cached?: boolean;
}

export interface ChatDraft {
  input: string;
  topK: number;
  messages: ChatMessage[];
}

export const defaultDraft: ChatDraft = { input: '', topK: 5, messages: [] };

// ── 草稿持久化（per project，localStorage）──────────────────────────────
function getDraftKey(projectId: string) {
  return `opsknowledge_rag_chat_${projectId}`;
}

export function loadDraft(projectId: string): ChatDraft {
  const saved = localStorage.getItem(getDraftKey(projectId));
  if (!saved) return defaultDraft;
  try {
    return { ...defaultDraft, ...JSON.parse(saved) };
  } catch {
    return defaultDraft;
  }
}

// 合併寫入：read-modify-write，避免「輸入框持久化」與「訊息持久化」互相覆蓋。
export function saveDraft(projectId: string, partial: Partial<ChatDraft>) {
  const cur = loadDraft(projectId);
  localStorage.setItem(getDraftKey(projectId), JSON.stringify({ ...cur, ...partial }));
}

// ── 前端問答快取：相同 文件數+模式+topK+問題 已答過就重用，省一次後端往返 ──
// docCount 納入 key → 上傳新文件後該專案快取自然失效。
function qaCacheKey(projectId: string) {
  return `opsknowledge_qa_cache_${projectId}`;
}
function readQaCache(projectId: string): Record<string, { answer: string; citations: any[] }> {
  try {
    return JSON.parse(localStorage.getItem(qaCacheKey(projectId)) || '{}');
  } catch {
    return {};
  }
}
function writeQaCache(projectId: string, key: string, value: { answer: string; citations: any[] }) {
  const cache = readQaCache(projectId);
  cache[key] = value;
  localStorage.setItem(qaCacheKey(projectId), JSON.stringify(cache));
}
function makeQaKey(docCount: number, topK: number, question: string) {
  return `${docCount}|${topK}|${question.trim()}`;
}

// ── 進行中請求（in-memory，per project）+ 訂閱 ──────────────────────────
const pending = new Map<string, string>(); // projectId -> 進行中的問題
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

// 訂閱 store 變動（送出 / 完成 / 進行中狀態改變都會觸發），回傳取消訂閱函式。
export function subscribeChat(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function isPending(projectId: string): boolean {
  return pending.has(projectId);
}

export function pendingQuestion(projectId: string): string | undefined {
  return pending.get(projectId);
}

function nextId(offset = 0) {
  return (Date.now() + offset).toString();
}

// 送出一則提問。請求在模組層執行，與呼叫端元件生命週期解耦：
// 即使元件卸載，promise 仍會完成、把答案寫進草稿並 emit 通知當前掛載的頁面。
export function submitChat(
  projectId: string,
  opts: { question: string; topK: number; docCount: number },
): void {
  const userText = opts.question.trim();
  if (!userText || pending.has(projectId)) return;

  // 先把使用者訊息寫進草稿並通知，畫面立即顯示提問。
  const base: ChatMessage[] = [
    ...loadDraft(projectId).messages,
    { id: nextId(), role: 'user', content: userText },
  ];
  saveDraft(projectId, { input: '', messages: base });
  emit();

  // 快取命中：直接重用先前答案，不打後端。
  const cacheKey = makeQaKey(opts.docCount, opts.topK, userText);
  const cached = readQaCache(projectId)[cacheKey];
  if (cached) {
    saveDraft(projectId, {
      messages: [
        ...base,
        { id: nextId(1), role: 'assistant', content: cached.answer, citations: cached.citations, cached: true },
      ],
    });
    emit();
    return;
  }

  // 標記進行中 → 畫面顯示「正在輸出」；切頁再回來仍能讀到此狀態。
  pending.set(projectId, userText);
  emit();

  // 一律走自主 agent（/agent-chat）；agent 對非閒聊問題一定會檢索，確保答案接地。
  chat(projectId, userText, opts.topK, true)
    .then((res: any) => {
      const answer = res.answer || '（空回覆）';
      const citations = res.citations || [];
      saveDraft(projectId, {
        messages: [
          ...loadDraft(projectId).messages,
          { id: nextId(1), role: 'assistant', content: answer, citations },
        ],
      });
      writeQaCache(projectId, cacheKey, { answer, citations });
    })
    .catch((err: any) => {
      saveDraft(projectId, {
        messages: [
          ...loadDraft(projectId).messages,
          { id: nextId(1), role: 'assistant', content: `發生錯誤: ${err.message}`, isError: true },
        ],
      });
    })
    .finally(() => {
      pending.delete(projectId);
      emit();
    });
}
