import { useLocation } from 'react-router-dom';
import { useHealthCheck } from '../../hooks/useHealthCheck';
import { Badge } from '../ui/Badge';
import { useProject } from '../../context/ProjectContext';

const routeDetails: Record<string, { title: string; description: string }> = {
  '/projects': { title: '專案設定', description: '選擇既有專案或建立新專案。' },
  '/dashboard': { title: '分析儀表板', description: '檢視事件洞察、高風險項目與建議的行動計畫。' },
  '/incident-upload': { title: '匯入事件紀錄', description: '上傳 CSV/Excel/JSON 事件資料進行清理與正規化。' },
  '/document-upload': { title: '上傳技術文件', description: '上傳 PDF 技術文件以建立向量索引知識庫。' },
  '/chat': { title: '知識庫問答 (RAG)', description: '基於 RAG 技術檢索文件並回答維運問題。' },
  '/analysis': { title: '執行 AI 分析', description: '啟動多工具 Agent 進行事件分析與洞察產生。' },
  '/agent-runs': { title: 'Agent 執行紀錄', description: '檢視 AI 代理的歷史執行軌跡與工具呼叫細節。' },
  '/status': { title: '系統狀態', description: '檢視各項後端服務連線健康度。' },
  '/insights/workflow': { title: '事件洞察流程', description: '依序匯入事件、執行 AI 分析，並檢視分析結果。' },
  '/knowledge/workflow': { title: '知識庫問答流程', description: '上傳文件建立知識庫，並進行 RAG 對話。' },
};

export default function Header() {
  const location = useLocation();
  const { status, loading } = useHealthCheck();
  const { currentProject } = useProject();

  const currentRoute = Object.keys(routeDetails).find(path => location.pathname.startsWith(path));
  const details = currentRoute ? routeDetails[currentRoute] : { title: '當前工作流程', description: '' };

  const isApiOk = status?.status === 'ok';

  return (
    <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-4">
        <div className="flex flex-col">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider bg-indigo-50 px-1.5 py-0.5 rounded">
              {currentProject ? currentProject.name : '未選擇專案'}
            </span>
            <span className="text-slate-300">/</span>
            <h1 className="text-lg font-semibold text-slate-800 leading-tight">{details.title}</h1>
          </div>
          <p className="text-sm text-slate-500">{details.description}</p>
        </div>
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