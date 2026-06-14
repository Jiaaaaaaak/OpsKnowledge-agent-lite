import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, LayoutDashboard, ListTree, Lightbulb, UploadCloud } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { getAnalysisResult } from '../services/api';

const PRIORITY_VARIANT: Record<string, 'error' | 'warning' | 'inactive'> = {
  high: 'error',
  medium: 'warning',
  low: 'inactive',
};

export default function AnalysisResultPage() {
  const { agentRunId } = useParams<{ agentRunId: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentRunId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getAnalysisResult(agentRunId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentRunId]);

  if (isLoading) {
    return (
      <div className="py-12 text-center text-slate-500">載入分析結果中...</div>
    );
  }

  if (error) {
    return (
      <div className="py-12 text-center">
        <AlertCircle className="mx-auto mb-4 h-12 w-12 text-amber-500" />
        <h3 className="text-lg font-medium text-slate-900">找不到此分析結果</h3>
        <p className="mx-auto mt-2 mb-6 max-w-md text-slate-500">{error}</p>
        <Link to="/insights/workflow">
          <Button>返回事件洞察流程</Button>
        </Link>
      </div>
    );
  }

  const run = data?.run || {};
  const summary = data?.summary || {};
  const insights = data?.insights || [];
  const actionItems = data?.action_items || [];
  const hasOutputs = insights.length > 0 || actionItems.length > 0;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">分析結果</h2>
          <p className="mt-1 font-mono text-xs text-slate-400">Run ID: {run.id}</p>
        </div>
        <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'error' : 'warning'}>
          Status: {run.status}
        </Badge>
      </div>

      <Card>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">已分析筆數</p>
            <p className="text-2xl font-semibold text-indigo-600">{summary.records_analyzed || 0}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">需人工複核</p>
            <p className="text-2xl font-semibold text-amber-600">{summary.needs_review || 0}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">產生洞察數</p>
            <p className="text-2xl font-semibold text-emerald-600">{summary.insights_created || 0}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">行動項目數</p>
            <p className="text-2xl font-semibold text-blue-600">{summary.action_items_created || 0}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
          <span>模型：{run.model_name}</span>
          <span>耗時：{run.latency_ms != null ? `${run.latency_ms} ms` : '—'}</span>
          <span>建立時間：{run.created_at}</span>
          {run.error_message && <span className="text-red-500">錯誤：{run.error_message}</span>}
        </div>
      </Card>

      {!hasOutputs && (
        <Card>
          <div className="py-6 text-center text-sm text-slate-500">
            此次分析沒有產生洞察或行動項目。可能是事件量不足或皆無顯著模式。
          </div>
        </Card>
      )}

      {insights.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-slate-800">產生的洞察</h3>
          {insights.map((insight: any) => (
            <Card key={insight.id}>
              <div className="flex items-start gap-3">
                <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div>
                  <h4 className="font-medium text-slate-800">{insight.title}</h4>
                  <p className="mt-1 text-sm text-slate-600">{insight.summary}</p>
                  {insight.recommendation && (
                    <p className="mt-2 text-sm text-indigo-700">建議：{insight.recommendation}</p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {actionItems.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-slate-800">行動項目</h3>
          <Card className="overflow-hidden !p-0">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">項目</th>
                  <th className="px-4 py-3 font-medium">優先級</th>
                  <th className="px-4 py-3 font-medium">負責角色</th>
                  <th className="px-4 py-3 font-medium">狀態</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {actionItems.map((item: any) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800">{item.title}</p>
                      {item.description && <p className="mt-0.5 text-xs text-slate-500">{item.description}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={PRIORITY_VARIANT[item.priority] || 'inactive'}>{item.priority}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{item.owner_role || '—'}</td>
                    <td className="px-4 py-3 text-slate-600">{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-6">
        <Button variant="outline" onClick={() => navigate('/insights/workflow')} className="flex items-center">
          <UploadCloud className="mr-2 h-4 w-4" />
          匯入更多事件
        </Button>
        <Link to="/agent-runs">
          <Button variant="outline" className="flex items-center">
            <ListTree className="mr-2 h-4 w-4" />
            查看 Agent 執行紀錄
          </Button>
        </Link>
        <Button onClick={() => navigate('/dashboard')} className="flex items-center">
          <LayoutDashboard className="mr-2 h-4 w-4" />
          查看完整儀表板
        </Button>
      </div>

      <div>
        <Link to="/insights/workflow" className="inline-flex items-center text-sm text-slate-500 hover:text-indigo-600">
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回事件洞察流程
        </Link>
      </div>
    </div>
  );
}
