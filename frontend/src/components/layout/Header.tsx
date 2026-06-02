import { useLocation } from 'react-router-dom';
import { useHealthCheck } from '../../hooks/useHealthCheck';
import { Badge } from '../ui/Badge';

const routeDetails: Record<string, { title: string; description: string }> = {
  '/projects': { title: '專案設定', description: '選擇既有專案或建立新專案。' },
  '/dashboard': { title: '儀表板', description: '檢視事件與工單的分析指標與行動項目。' },
  '/documents': { title: '資料上傳', description: '上傳技術文件 PDF 或事件紀錄檔。' },
  '/chat': { title: '知識庫問答 (RAG)', description: '基於 RAG 技術檢索文件並回答維運問題。' },
  '/analysis': { title: '事件分析 Agent', description: '啟動多工具 Agent 進行事件嚴重程度分析與洞察。' },
  '/agent-runs': { title: 'Agent 執行紀錄', description: '檢視 AI 代理的歷史執行軌跡與工具呼叫細節。' },
  '/status': { title: '系統狀態', description: '檢視各項後端服務連線健康度。' },
};

export default function Header() {
  const location = useLocation();
  const { status, loading } = useHealthCheck();
  
  const currentRoute = Object.keys(routeDetails).find(path => location.pathname.startsWith(path));
  const details = currentRoute ? routeDetails[currentRoute] : { title: 'OpsKnowledge', description: '' };

  const isApiOk = status?.status === 'ok';

  return (
    <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6 shrink-0">
      <div>
        <h1 className="text-lg font-semibold text-slate-800 leading-tight">{details.title}</h1>
        <p className="text-sm text-slate-500">{details.description}</p>
      </div>
      
      <div className="flex items-center space-x-3">
        {loading ? (
          <Badge>檢查中...</Badge>
        ) : isApiOk ? (
          <Badge variant="success" className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 block"></span>
            API 正常
          </Badge>
        ) : (
          <Badge variant="error" className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 block"></span>
            服務異常
          </Badge>
        )}
      </div>
    </header>
  );
}