import { useEffect, useMemo, useState } from 'react';
import { Button } from '../components/ui/Button';
import { Send, Bot, User, ShieldAlert, AlertCircle, FileText, RefreshCw } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { chat, listDocuments } from '../services/api';
import { Link } from 'react-router-dom';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: any[];
  isError?: boolean;
}

interface UploadedDocument {
  id: string;
  filename: string;
  document_type: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
}

interface ChatDraft {
  input: string;
  topK: number;
  messages: ChatMessage[];
}

const defaultDraft: ChatDraft = {
  input: '',
  topK: 5,
  messages: [],
};

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

export default function ChatPage() {
  const { currentProject } = useProject();
  const [input, setInput] = useState(defaultDraft.input);
  const [topK, setTopK] = useState(defaultDraft.topK);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(defaultDraft.messages);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [draftProjectId, setDraftProjectId] = useState<string | null>(null);
  const projectId = currentProject?.id;

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
    localStorage.setItem(
      getDraftKey(projectId),
      JSON.stringify({ input, topK, messages })
    );
  }, [draftProjectId, input, messages, projectId, topK]);

  const loadDocuments = async () => {
    if (!projectId) return;
    setIsLoadingDocuments(true);
    setDocumentError(null);
    try {
      const res = await listDocuments(projectId);
      setDocuments(res || []);
    } catch (err: any) {
      setDocumentError(err.message);
    } finally {
      setIsLoadingDocuments(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [projectId]);

  const documentSummary = useMemo(() => {
    const totalPages = documents.reduce((sum, doc) => sum + doc.page_count, 0);
    const totalChunks = documents.reduce((sum, doc) => sum + doc.chunk_count, 0);
    return { totalPages, totalChunks };
  }, [documents]);

  if (!currentProject) {
    return (
      <div className="py-12 text-center">
        <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-900">尚未選擇專案</h3>
        <p className="text-slate-500 mt-2 mb-6">請先至「專案設定」選擇或建立一個專案。</p>
        <Link to="/projects"><Button>前往專案設定</Button></Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isSubmitting) return;

    const userText = input.trim();
    const newMsg: ChatMessage = { id: Date.now().toString(), role: 'user', content: userText };

    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setIsSubmitting(true);

    try {
      const res: any = await chat(currentProject.id, userText, topK);
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.answer || '（空回覆）',
        citations: res.citations || []
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `發生錯誤: ${err.message}`,
        isError: true
      }]);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4">
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm px-4 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <FileText className="w-4 h-4 text-indigo-600" />
              已上傳文件
              <span className="text-xs font-medium text-slate-500">
                {documents.length} 份 · {documentSummary.totalPages} 頁 · {documentSummary.totalChunks} chunks
              </span>
            </div>
            {documentError && (
              <p className="mt-1 text-xs text-red-600">文件清單載入失敗: {documentError}</p>
            )}
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={loadDocuments}
            disabled={isLoadingDocuments}
            className="self-start sm:self-auto"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoadingDocuments ? 'animate-spin' : ''}`} />
            重新整理
          </Button>
        </div>

        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {documents.length === 0 ? (
            <Link
              to="/document-upload"
              className="text-sm text-slate-500 hover:text-indigo-600"
            >
              尚未找到文件，前往上傳技術文件
            </Link>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
                title={doc.filename}
              >
                <p className="max-w-56 truncate text-sm font-medium text-slate-800">{doc.filename}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {doc.page_count} 頁 · {doc.chunk_count} chunks
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex justify-end items-center px-2">
        <label className="text-sm text-slate-600 mr-2 font-medium">檢索段落數 (Top K):</label>
        <input 
          type="range" 
          min="1" max="10" 
          value={topK} 
          onChange={(e) => setTopK(Number(e.target.value))}
          className="w-32 accent-indigo-600"
        />
        <span className="text-sm font-medium text-slate-900 ml-2 w-4">{topK}</span>
      </div>

      <div className="bg-white rounded-lg shadow-sm flex-1 flex flex-col overflow-hidden border border-slate-200">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400">
              <Bot className="w-12 h-12 mb-4 opacity-40 text-indigo-400" />
              <p>開始向知識庫提問</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-sm ${
                  msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border border-slate-200 text-indigo-600'
                }`}>
                  {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                </div>
                <div className="max-w-[85%] flex flex-col gap-2">
                  <div className={`rounded-2xl px-5 py-3.5 shadow-sm ${
                    msg.role === 'user' 
                      ? 'bg-indigo-600 text-white rounded-tr-sm' 
                      : msg.isError 
                        ? 'bg-red-50 border border-red-200 text-red-800 rounded-tl-sm flex items-start gap-2'
                        : 'bg-white border border-slate-100 text-slate-800 rounded-tl-sm'
                  }`}>
                    {msg.isError && <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-red-500" />}
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                  
                  {/* Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 space-y-2">
                      <p className="text-xs font-semibold text-slate-500 uppercase">引用來源 ({msg.citations.length})</p>
                      {msg.citations.map((c, idx) => (
                        <details key={idx} className="group bg-white border border-slate-200 rounded-md text-xs overflow-hidden">
                          <summary className="px-3 py-2 cursor-pointer font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 list-none flex justify-between">
                            <span>[{idx + 1}] {c.filename || '?'} · chunk {c.chunk_index || '?'}</span>
                            <span className="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
                          </summary>
                          <div className="p-3 border-t border-slate-100 text-slate-600 bg-white">
                            <p className="whitespace-pre-wrap font-mono text-[10px] bg-slate-50 p-2 rounded mb-2">
                              doc: {c.document_id}<br/>chunk: {c.chunk_id}
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
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white border border-slate-200 text-indigo-600 flex items-center justify-center shadow-sm">
                <Bot className="w-5 h-5" />
              </div>
              <div className="bg-white border border-slate-100 shadow-sm rounded-2xl rounded-tl-sm px-5 py-4">
                <div className="flex space-x-1.5">
                  <div className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 bg-white border-t border-slate-200">
          <form onSubmit={handleSubmit} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="例如：Docker volume 重啟後消失，該檢查哪些設定？"
              className="w-full bg-white border border-slate-300 text-slate-900 text-sm rounded-full focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 block pl-6 pr-28 py-3.5 transition-shadow shadow-sm"
              disabled={isSubmitting}
            />
            <div className="absolute right-2 flex items-center">
              <Button 
                type="submit" 
                size="sm" 
                className="rounded-full !px-5"
                disabled={!input.trim() || isSubmitting}
              >
                {isSubmitting ? '思考中...' : (
                  <>
                    <span className="mr-2">送出</span>
                    <Send className="w-4 h-4" />
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
