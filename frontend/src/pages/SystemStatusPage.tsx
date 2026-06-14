
import { Card } from '../components/ui/Card';
import { useHealthCheck } from '../hooks/useHealthCheck';
import { Badge } from '../components/ui/Badge';
import { Server, Database, Activity, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

export default function SystemStatusPage() {
  const { status, loading, error } = useHealthCheck();

  const getStatusIcon = (state: string) => {
    if (state === 'ok' || state === 'connected') return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
    if (state === 'error' || state === 'disconnected') return <XCircle className="w-5 h-5 text-red-500" />;
    return <AlertTriangle className="w-5 h-5 text-amber-500" />;
  };

  return (
    <div className="space-y-6">
      <Card>
        
        {loading ? (
          <div className="py-8 text-center text-slate-500">載入中...</div>
        ) : error ? (
          <div className="bg-red-50 text-red-700 p-4 rounded-md flex items-start">
            <XCircle className="w-5 h-5 mr-3 mt-0.5" />
            <div>
              <h4 className="font-medium">連線失敗</h4>
              <p className="text-sm mt-1">{error}</p>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            
            <div className="py-4 flex items-center justify-between">
              <div className="flex items-center">
                <div className="p-2 bg-slate-50 rounded text-slate-600 mr-4">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-medium text-slate-900">API Server</h4>
                  <p className="text-xs text-slate-500">FastAPI Backend (v{status?.version || 'unknown'})</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                {getStatusIcon(status?.status)}
                <Badge variant={status?.status === 'ok' ? 'success' : 'error'}>
                  {status?.status === 'ok' ? 'Operational' : 'Error'}
                </Badge>
              </div>
            </div>

            <div className="py-4 flex items-center justify-between">
              <div className="flex items-center">
                <div className="p-2 bg-slate-50 rounded text-slate-600 mr-4">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-medium text-slate-900">PostgreSQL</h4>
                  <p className="text-xs text-slate-500">關聯式資料庫 (事件與元資料)</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                {getStatusIcon(status?.db)}
                <Badge variant={status?.db === 'connected' ? 'success' : 'error'}>
                  {status?.db === 'connected' ? 'Connected' : 'Disconnected'}
                </Badge>
              </div>
            </div>

            <div className="py-4 flex items-center justify-between">
              <div className="flex items-center">
                <div className="p-2 bg-slate-50 rounded text-slate-600 mr-4">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-medium text-slate-900">pgvector</h4>
                  <p className="text-xs text-slate-500">PostgreSQL 向量檢索</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                {getStatusIcon(status?.vector)}
                <Badge variant={status?.vector === 'connected' ? 'success' : 'error'}>
                  {status?.vector === 'connected' ? 'Connected' : 'Disconnected'}
                </Badge>
              </div>
            </div>

          </div>
        )}

      </Card>
    </div>
  );
}
