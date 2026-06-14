import { useState, useEffect } from 'react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ShieldAlert, Clock, Cpu, ServerCog, RefreshCw } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { listAgentRuns, listToolCalls } from '../services/api';
import { Link } from 'react-router-dom';

export default function AgentRunsPage() {
  const { currentProject } = useProject();
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any>(null);
  const [toolCalls, setToolCalls] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [toolsLoading, setToolsLoading] = useState(false);

  useEffect(() => {
    if (currentProject) {
      fetchRuns();
    }
  }, [currentProject]);

  useEffect(() => {
    if (selectedRun) {
      fetchToolCalls(selectedRun.id);
    }
  }, [selectedRun]);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const data = await listAgentRuns(currentProject!.id);
      const nextRuns = data as any[];
      setRuns(nextRuns);
      setSelectedRun((prev: any) => {
        if (!prev) return nextRuns[0] || null;
        return nextRuns.find((run) => run.id === prev.id) || nextRuns[0] || null;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!currentProject || loading) return;
    await fetchRuns();
    if (selectedRun) {
      await fetchToolCalls(selectedRun.id);
    }
  };

  const fetchToolCalls = async (runId: string) => {
    setToolsLoading(true);
    try {
      const data = await listToolCalls(runId);
      setToolCalls(data as any[]);
    } catch (err) {
      console.error(err);
    } finally {
      setToolsLoading(false);
    }
  };

  if (!currentProject) {
    return (
      <div className="py-12 text-center">
        <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-900">尚未選擇專案</h3>
        <p className="text-slate-500 mt-2 mb-6">請先至「專案設定」選擇或建立一個專案。</p>
        <Link to="/projects"><button className="px-4 py-2 bg-indigo-600 text-white rounded-md">前往專案設定</button></Link>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-end shrink-0">
        <Button
          type="button"
          variant="secondary"
          onClick={handleRefresh}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          重新整理
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0 flex-1">
        {/* Runs List Sidebar */}
        <div className="lg:col-span-1 bg-card rounded-lg border border-slate-200 shadow-sm flex flex-col h-full min-h-0 overflow-hidden">
          <div className="p-4 border-b border-slate-100 bg-slate-50 font-medium text-slate-800 shrink-0">
            執行紀錄清單
          </div>
          <div className="min-h-0 overflow-y-auto flex-1 p-2 space-y-2">
            {loading ? (
              <p className="text-center text-sm text-slate-500 mt-4">載入中...</p>
            ) : runs.length === 0 ? (
              <p className="text-center text-sm text-slate-500 mt-4 italic">尚無紀錄</p>
            ) : (
              runs.map((run) => (
                <button
                  key={run.id}
                  onClick={() => setSelectedRun(run)}
                  className={`w-full text-left p-3 rounded-md border transition-colors ${
                    selectedRun?.id === run.id 
                      ? 'border-indigo-500 bg-indigo-50/50' 
                      : 'border-slate-200 hover:border-indigo-200 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold text-sm text-slate-800">{run.task_type}</span>
                    <Badge variant={run.status === 'success' ? 'success' : run.status === 'error' ? 'error' : 'warning'}>
                      {run.status}
                    </Badge>
                  </div>
                  <div className="text-xs text-slate-500 font-mono truncate">{new Date(run.created_at).toLocaleString()}</div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Details View */}
        <div className="lg:col-span-2 h-full overflow-hidden">
          {selectedRun ? (
            <div className="h-full overflow-y-auto pr-1 space-y-3">
              <div className="bg-card rounded-lg border border-slate-200 shadow-sm p-4">
                <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center">
                  <Cpu className="w-4 h-4 mr-2 text-indigo-500" />
                  Run Details
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="bg-slate-50 px-3 py-2 rounded border border-slate-100">
                    <p className="text-[11px] text-slate-500 mb-0.5">Status</p>
                    <p className="text-sm font-medium text-slate-800 truncate">{selectedRun.status}</p>
                  </div>
                  <div className="bg-slate-50 px-3 py-2 rounded border border-slate-100">
                    <p className="text-[11px] text-slate-500 mb-0.5">Model</p>
                    <p className="text-sm font-medium text-slate-800 truncate">{selectedRun.model_name}</p>
                  </div>
                  <div className="bg-slate-50 px-3 py-2 rounded border border-slate-100">
                    <p className="text-[11px] text-slate-500 mb-0.5">Latency</p>
                    <p className="text-sm font-medium text-slate-800">{selectedRun.latency_ms} ms</p>
                  </div>
                </div>
                {selectedRun.error_message && (
                  <div className="bg-red-50 text-red-700 p-2 rounded text-xs mt-3">
                    {selectedRun.error_message}
                  </div>
                )}
              </div>

              <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-100 bg-slate-50 font-medium text-slate-800 flex items-center">
                  <ServerCog className="w-4 h-4 mr-2 text-slate-500" />
                  工具呼叫軌跡 (Tool Calls)
                </div>
                <div className="p-4 space-y-4 bg-slate-50/50">
                  {toolsLoading ? (
                    <p className="text-center text-sm text-slate-500">載入工具紀錄...</p>
                  ) : toolCalls.length === 0 ? (
                    <p className="text-center text-sm text-slate-500 italic">本次執行未呼叫任何工具</p>
                  ) : (
                    toolCalls.map((tc) => (
                      <div key={tc.id} className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div className="bg-slate-100 px-4 py-2 border-b border-slate-200 flex justify-between items-center">
                          <div className="font-medium text-sm text-slate-800 flex items-center">
                            {tc.error_message ? '🔴' : '🟢'} <span className="ml-2 font-mono text-indigo-700">{tc.tool_name}</span>
                          </div>
                          <div className="text-xs text-slate-500 flex items-center">
                            <Clock className="w-3 h-3 mr-1" />
                            {tc.latency_ms || 0} ms
                          </div>
                        </div>
                        {tc.error_message && (
                          <div className="p-3 bg-red-50 text-red-700 text-xs border-b border-red-100">
                            {tc.error_message}
                          </div>
                        )}
                        <div className="grid grid-cols-1 xl:grid-cols-2 xl:divide-x divide-slate-100">
                          <div className="p-4">
                            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Input JSON</p>
                            <pre className="text-[10px] bg-slate-50 p-2 rounded text-slate-700 overflow-x-auto">
                              {JSON.stringify(tc.input_json, null, 2)}
                            </pre>
                          </div>
                          <div className="p-4">
                            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Output JSON</p>
                            <pre className="text-[10px] bg-slate-50 p-2 rounded text-slate-700 overflow-x-auto">
                              {JSON.stringify(tc.output_json, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 border-2 border-dashed border-slate-200 rounded-lg">
              <p>請從左側選擇一筆紀錄查看詳細</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
