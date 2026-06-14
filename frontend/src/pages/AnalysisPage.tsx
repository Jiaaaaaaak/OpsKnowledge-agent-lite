import { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { PlaySquare, AlertCircle, ShieldAlert, ArrowRight, UploadCloud } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { analyzeIncidents } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';

export default function AnalysisPage() {
  const { currentProject } = useProject();
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

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

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setError(null);
    setResult(null);

    try {
      const res = await analyzeIncidents(currentProject.id);
      setResult(res);
    } catch (err: any) {
      const errMsg = err.message || '';
      if (errMsg.includes('400') || errMsg.includes('No cleaned records to analyze')) {
        setError('EMPTY_RECORDS');
      } else {
        setError(errMsg);
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Card>
        <div className="py-6 flex flex-col items-center text-center">
          <div className="p-4 bg-indigo-50 rounded-full mb-4">
            <PlaySquare className="w-8 h-8 text-indigo-600" />
          </div>
          <p className="text-slate-600 max-w-md mb-8">
            分析結果將寫入資料庫，您可以在「分析儀表板」中查看圖表，或是到「Agent 執行紀錄」回查本次各工具的 I/O 細節。
          </p>
          
          {error === 'EMPTY_RECORDS' && (
            <div className="mb-6 bg-slate-50 border border-slate-200 p-6 rounded-lg flex flex-col items-center max-w-md text-center">
              <UploadCloud className="w-10 h-10 text-slate-400 mb-3" />
              <h4 className="text-slate-800 font-medium mb-2">目前沒有可分析的事件</h4>
              <p className="text-sm text-slate-500 mb-4">請先匯入事件紀錄檔，或此專案的事件已全部分析過。</p>
              <Button onClick={() => navigate('/incident-upload')} variant="outline">
                前往匯入事件紀錄
              </Button>
            </div>
          )}

          {error && error !== 'EMPTY_RECORDS' && (
            <div className="mb-6 bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-md flex items-start max-w-lg text-left">
              <AlertCircle className="w-5 h-5 text-amber-500 mr-3 mt-0.5 shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {!error || error !== 'EMPTY_RECORDS' ? (
            <Button size="lg" onClick={handleAnalyze} disabled={isAnalyzing}>
              {isAnalyzing ? 'Agent 執行中 (需時數十秒)...' : '執行事件分析'}
            </Button>
          ) : null}
        </div>
      </Card>

      {result && (
        <div className="space-y-6">
          <Card className="border-emerald-200 bg-emerald-50/30">
            <div className="mb-6 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-800">執行完成</h3>
              <Badge variant={result.status === 'success' ? 'success' : 'warning'}>
                Status: {result.status}
              </Badge>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white p-4 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">已分析筆數</p>
                <p className="text-2xl font-semibold text-indigo-600">{result.summary?.records_analyzed || 0}</p>
              </div>
              <div className="bg-white p-4 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">需要人工複核</p>
                <p className="text-2xl font-semibold text-amber-600">{result.summary?.needs_review || 0}</p>
              </div>
              <div className="bg-white p-4 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">產生洞察數</p>
                <p className="text-2xl font-semibold text-emerald-600">{result.summary?.insights_created || 0}</p>
              </div>
              <div className="bg-white p-4 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">行動項目數</p>
                <p className="text-2xl font-semibold text-blue-600">{result.summary?.action_items_created || 0}</p>
              </div>
            </div>
            <div className="mt-4 text-right">
              <span className="text-xs text-slate-400 font-mono bg-white px-2 py-1 rounded border border-slate-200">
                Run ID: {result.agent_run_id}
              </span>
            </div>
          </Card>
          
          <div className="flex justify-end mt-8 border-t border-slate-200 pt-6">
            <Button 
              onClick={() => navigate('/dashboard')}
              className="flex items-center"
              size="lg"
            >
              分析完成！前往儀表板查看完整洞察報告
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}