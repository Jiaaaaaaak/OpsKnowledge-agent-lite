import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, ArrowRight, Bot, FileText, RefreshCw, Send, User } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useProject } from '../context/ProjectContext';
import { chat, getWorkflowStatus, listDocuments, uploadDocument } from '../services/api';
import { ProjectRequiredState } from '../components/workflow/ProjectRequiredState';
import { UploadPanel } from '../components/workflow/UploadPanel';
import { WorkflowStatusPanel } from '../components/workflow/WorkflowStatusPanel';
import { WorkflowStepper, WorkflowStep } from '../components/workflow/WorkflowStepper';

type StepId = 'project' | 'knowledge' | 'ask';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: any[];
  isError?: boolean;
}

interface ChatDraft {
  input: string;
  topK: number;
  messages: ChatMessage[];
}

const defaultDraft: ChatDraft = { input: '', topK: 5, messages: [] };

function getDraftKey(projectId: string) {
  return `opsknowledge_rag_chat_${projectId}`;
}

function loadDraft(projectId: string): ChatDraft {
  const saved = localStorage.getItem(getDraftKey(projectId));
  if (!saved) return defaultDraft;
  try {
    return { ...defaultDraft, ...JSON.parse(saved) };
  } catch {
    return defaultDraft;
  }
}

export default function KnowledgeWorkflowPage() {
  const { currentProject } = useProject();
  const projectId = currentProject?.id;

  const [status, setStatus] = useState<any>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [activeStep, setActiveStep] = useState<StepId | null>(null);

  // 嵌入式 RAG 對話狀態（沿用 ChatPage 的草稿持久化行為）
  const [input, setInput] = useState(defaultDraft.input);
  const [topK, setTopK] = useState(defaultDraft.topK);
  const [messages, setMessages] = useState<ChatMessage[]>(defaultDraft.messages);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [draftProjectId, setDraftProjectId] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!projectId) return;
    setIsLoadingStatus(true);
    setStatusError(null);
    try {
      const [statusRes, docRes] = await Promise.all([
        getWorkflowStatus(projectId),
        listDocuments(projectId),
      ]);
      setStatus(statusRes);
      setDocuments(docRes || []);
    } catch (err: any) {
      setStatusError(err.message);
    } finally {
      setIsLoadingStatus(false);
    }
  }, [projectId]);

  useEffect(() => {
    setActiveStep(null);
    setStatus(null);
    setDocuments([]);
    loadStatus();
  }, [loadStatus]);

  // 切換專案時載入該專案的對話草稿
  useEffect(() => {
    if (!projectId) return;
    const draft = loadDraft(projectId);
    setInput(draft.input);
    setTopK(draft.topK);
    setMessages(draft.messages);
    setDraftProjectId(projectId);
  }, [projectId]);

  useEffect(() => {
    if (!projectId || draftProjectId !== projectId) return;
    localStorage.setItem(getDraftKey(projectId), JSON.stringify({ input, topK, messages }));
  }, [draftProjectId, input, messages, projectId, topK]);

  const canChat = Boolean(status?.knowledge?.can_chat);

  const naturalStep: StepId = useMemo(() => {
    if (canChat) return 'ask';
    return 'knowledge';
  }, [canChat]);

  const currentStep: StepId = activeStep ?? naturalStep;

  const steps: WorkflowStep[] = useMemo(() => {
    const docCount = status?.knowledge?.document_count ?? 0;
    const def: { id: StepId; label: string; description?: string }[] = [
      { id: 'project', label: '選擇專案' },
      { id: 'knowledge', label: '建立知識庫', description: docCount > 0 ? `${docCount} 份文件` : undefined },
      { id: 'ask', label: '提問' },
    ];
    return def.map((s): WorkflowStep => {
      let stepStatus: WorkflowStep['status'] = 'available';
      if (s.id === currentStep) {
        stepStatus = 'current';
      } else if (s.id === 'project') {
        stepStatus = 'complete';
      } else if (s.id === 'knowledge') {
        stepStatus = canChat ? 'complete' : 'available';
      } else if (s.id === 'ask') {
        stepStatus = canChat ? 'available' : 'locked';
      }
      return { ...s, status: stepStatus };
    });
  }, [status, canChat, currentStep]);

  const handleStepClick = (stepId: string) => {
    // 沒有可用知識庫時不允許跳到提問
    if (stepId === 'ask' && !canChat) return;
    setActiveStep(stepId as StepId);
  };

  const documentSummary = useMemo(() => {
    const totalPages = documents.reduce((sum, doc) => sum + (doc.page_count || 0), 0);
    const totalChunks = documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
    return { totalPages, totalChunks };
  }, [documents]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isSubmitting || !canChat || !projectId) return;

    const userText = input.trim();
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'user', content: userText }]);
    setInput('');
    setIsSubmitting(true);

    try {
      const res: any = await chat(projectId, userText, topK);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: res.answer || '（空回覆）',
          citations: res.citations || [],
        },
      ]);
    } catch (err: any) {
      // 保留失敗的提問，附帶錯誤訊息供重試
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: `發生錯誤: ${err.message}`,
          isError: true,
        },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!currentProject) {
    return <ProjectRequiredState />;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">知識庫問答流程</h2>
        <p className="mt-1 text-slate-600">先上傳技術文件建立向量索引，再以 RAG 對話查詢並檢視引用來源。</p>
      </div>

      <WorkflowStepper steps={steps} onStepClick={handleStepClick} />

      <div className="grid gap-6 md:grid-cols-[1fr_260px]">
        <div className="space-y-6">
          {currentStep === 'knowledge' && (
            <UploadPanel
              title="上傳技術文件"
              description="上傳 PDF 技術文件，系統會自動切塊並建立向量索引。"
              accept=".pdf"
              idleLabel="開始上傳"
              loadingLabel="上傳並建立索引中..."
              selectedFileLabel="支援 PDF 格式"
              onUpload={async (file) => {
                const res = await uploadDocument(projectId!, file);
                await loadStatus();
                return res;
              }}
              renderResult={(result) => (
                <div className="space-y-4">
                  <div className="rounded-md border border-emerald-100 bg-emerald-50 p-4 text-sm text-emerald-700">
                    已索引「{result.filename}」：{result.page_count || 0} 頁 · {result.chunk_count || 0} chunks
                  </div>
                  <div className="flex justify-end">
                    <Button onClick={() => setActiveStep('ask')} disabled={!canChat} className="flex items-center">
                      下一步：開始提問
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            />
          )}

          {currentStep === 'ask' && (
            <div className="flex h-[calc(100vh-16rem)] flex-col space-y-4">
              {!canChat ? (
                <Card>
                  <div className="py-6 text-center text-sm text-slate-500">
                    尚無可查詢的知識庫，請先上傳技術文件。
                  </div>
                </Card>
              ) : (
                <>
                  <div className="flex justify-end px-2">
                    <label className="mr-2 text-sm font-medium text-slate-600">檢索段落數 (Top K):</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                      className="w-32 accent-indigo-600"
                    />
                    <span className="ml-2 w-4 text-sm font-medium text-slate-900">{topK}</span>
                  </div>

                  <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                    <div className="flex-1 space-y-6 overflow-y-auto bg-slate-50/50 p-6">
                      {messages.length === 0 ? (
                        <div className="flex h-full flex-col items-center justify-center text-slate-400">
                          <Bot className="mb-4 h-12 w-12 text-indigo-400 opacity-40" />
                          <p>開始向知識庫提問</p>
                        </div>
                      ) : (
                        messages.map((msg) => (
                          <div
                            key={msg.id}
                            className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                          >
                            <div
                              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full shadow-sm ${
                                msg.role === 'user'
                                  ? 'bg-indigo-600 text-white'
                                  : 'border border-slate-200 bg-white text-indigo-600'
                              }`}
                            >
                              {msg.role === 'user' ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
                            </div>
                            <div className="flex max-w-[85%] flex-col gap-2">
                              <div
                                className={`rounded-2xl px-5 py-3.5 shadow-sm ${
                                  msg.role === 'user'
                                    ? 'rounded-tr-sm bg-indigo-600 text-white'
                                    : msg.isError
                                      ? 'flex items-start gap-2 rounded-tl-sm border border-red-200 bg-red-50 text-red-800'
                                      : 'rounded-tl-sm border border-slate-100 bg-white text-slate-800'
                                }`}
                              >
                                {msg.isError && <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />}
                                <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                              </div>

                              {msg.citations && msg.citations.length > 0 && (
                                <div className="mt-2 space-y-2">
                                  <p className="text-xs font-semibold uppercase text-slate-500">
                                    引用來源 ({msg.citations.length})
                                  </p>
                                  {msg.citations.map((c, idx) => (
                                    <details
                                      key={idx}
                                      className="group overflow-hidden rounded-md border border-slate-200 bg-white text-xs"
                                    >
                                      <summary className="flex list-none cursor-pointer justify-between bg-slate-50 px-3 py-2 font-medium text-slate-700 hover:bg-slate-100">
                                        <span>
                                          [{idx + 1}] {c.filename || '?'} · chunk {c.chunk_index ?? '?'}
                                        </span>
                                        <span className="text-slate-400 transition-transform group-open:rotate-180">▼</span>
                                      </summary>
                                      <div className="border-t border-slate-100 bg-white p-3 text-slate-600">
                                        <p className="mb-2 whitespace-pre-wrap rounded bg-slate-50 p-2 font-mono text-[10px]">
                                          doc: {c.document_id}
                                          <br />
                                          chunk: {c.chunk_id}
                                        </p>
                                        {c.snippet}
                                      </div>
                                    </details>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                      {isSubmitting && (
                        <div className="flex items-start gap-4">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-indigo-600 shadow-sm">
                            <Bot className="h-5 w-5" />
                          </div>
                          <div className="rounded-2xl rounded-tl-sm border border-slate-100 bg-white px-5 py-4 shadow-sm">
                            <div className="flex space-x-1.5">
                              <div className="h-2 w-2 animate-bounce rounded-full bg-indigo-300" style={{ animationDelay: '0ms' }} />
                              <div className="h-2 w-2 animate-bounce rounded-full bg-indigo-300" style={{ animationDelay: '150ms' }} />
                              <div className="h-2 w-2 animate-bounce rounded-full bg-indigo-300" style={{ animationDelay: '300ms' }} />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="border-t border-slate-200 bg-white p-4">
                      <form onSubmit={handleSubmit} className="relative flex items-center">
                        <input
                          type="text"
                          value={input}
                          onChange={(e) => setInput(e.target.value)}
                          placeholder="例如：Docker volume 重啟後消失，該檢查哪些設定？"
                          className="block w-full rounded-full border border-slate-300 bg-white py-3.5 pl-6 pr-28 text-sm text-slate-900 shadow-sm transition-shadow focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
                          disabled={isSubmitting}
                        />
                        <div className="absolute right-2 flex items-center">
                          <Button type="submit" size="sm" className="rounded-full !px-5" disabled={!input.trim() || isSubmitting}>
                            {isSubmitting ? (
                              '思考中...'
                            ) : (
                              <>
                                <span className="mr-2">送出</span>
                                <Send className="h-4 w-4" />
                              </>
                            )}
                          </Button>
                        </div>
                      </form>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card title="知識庫狀態">
            {statusError ? (
              <p className="text-sm text-red-600">狀態載入失敗：{statusError}</p>
            ) : (
              <WorkflowStatusPanel status={status} variant="knowledge" />
            )}
            <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
              <FileText className="h-3.5 w-3.5" />
              {documents.length} 份 · {documentSummary.totalPages} 頁 · {documentSummary.totalChunks} chunks
            </div>
            <div className="mt-4">
              <Button variant="secondary" size="sm" onClick={loadStatus} disabled={isLoadingStatus} className="w-full">
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoadingStatus ? 'animate-spin' : ''}`} />
                重新整理
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
