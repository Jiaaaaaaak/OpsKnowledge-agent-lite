import { useState, useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { ShieldAlert, BarChart3, AlertTriangle, Lightbulb, UploadCloud, PlaySquare } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { getDashboard } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

export default function DashboardPage() {
  const { currentProject } = useProject();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (currentProject) {
      fetchData();
    }
  }, [currentProject]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getDashboard(currentProject!.id);
      setData(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

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

  if (loading) return <div className="p-8 text-center text-slate-500">載入中...</div>;
  if (error) return <div className="p-8 text-center text-red-500">發生錯誤: {error}</div>;
  if (!data) return null;

  const hasData = data.ticket_count > 0 || (data.top_insights && data.top_insights.length > 0);

  if (!hasData) {
    return (
      <div className="max-w-3xl mx-auto mt-12">
        <Card className="text-center py-16 border-dashed border-slate-300">
          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <BarChart3 className="w-8 h-8 text-slate-400" />
          </div>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">目前沒有分析資料</h2>
          <p className="text-slate-500 max-w-md mx-auto mb-8">
            儀表板需要經過 AI 事件分析後才能顯示洞察報告與行動項目。請按照以下流程建立資料：
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button onClick={() => navigate('/incident-upload')} variant="outline" className="w-full sm:w-auto flex items-center justify-center">
              <UploadCloud className="w-4 h-4 mr-2" />
              1. 匯入事件紀錄
            </Button>
            <div className="hidden sm:block text-slate-300">→</div>
            <Button onClick={() => navigate('/analysis')} className="w-full sm:w-auto flex items-center justify-center">
              <PlaySquare className="w-4 h-4 mr-2" />
              2. 執行 AI 分析
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">分析儀表板</h2>
        <p className="text-slate-600 mt-1">檢視事件洞察、高風險項目與建議的行動計畫。</p>
      </div>
      
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-6">
        <Card className="flex items-center p-6">
          <div className="p-4 bg-indigo-50 rounded-lg mr-4">
            <BarChart3 className="w-8 h-8 text-indigo-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">工單總數</p>
            <h3 className="text-3xl font-bold text-slate-800 mt-1">{data.ticket_count || 0}</h3>
          </div>
        </Card>
        <Card className="flex items-center p-6">
          <div className="p-4 bg-amber-50 rounded-lg mr-4">
            <AlertTriangle className="w-8 h-8 text-amber-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">需要人工複核</p>
            <h3 className="text-3xl font-bold text-slate-800 mt-1">{data.needs_review_count || 0}</h3>
          </div>
        </Card>
      </div>

      {/* Insights */}
      <Card title="重點洞察 (Top Insights)">
        {data.top_insights && data.top_insights.length > 0 ? (
          <div className="space-y-4">
            {data.top_insights.map((ins: any, idx: number) => (
              <div key={idx} className="p-4 border border-slate-100 bg-slate-50/50 rounded-lg">
                <div className="flex items-start">
                  <Lightbulb className="w-5 h-5 text-amber-500 mr-3 mt-0.5 shrink-0" />
                  <div>
                    <h4 className="font-semibold text-slate-800">{ins.title}</h4>
                    <p className="text-sm text-slate-600 mt-1 mb-3">{ins.summary}</p>
                    <div className="text-sm bg-white p-3 rounded border border-slate-200">
                      <span className="font-medium text-indigo-700">建議行動：</span> {ins.recommendation}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic py-4 text-center">尚無資料，請先執行「事件分析」</p>
        )}
      </Card>

      {/* Action Items */}
      <Card title="未處理行動項目 (Open Action Items)">
        {data.open_action_items && data.open_action_items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">標題</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">優先度</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">負責角色</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">說明</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {data.open_action_items.map((item: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm font-medium text-slate-900">{item.title}</td>
                    <td className="px-4 py-3 text-sm">
                      <Badge variant={item.priority === 'High' ? 'error' : item.priority === 'Medium' ? 'warning' : 'inactive'}>
                        {item.priority}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">{item.owner_role}</td>
                    <td className="px-4 py-3 text-sm text-slate-500 max-w-xs truncate" title={item.description}>{item.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic py-4 text-center">尚無資料</p>
        )}
      </Card>

    </div>
  );
}