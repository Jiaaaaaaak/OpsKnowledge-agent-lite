import { FileText, Layers } from 'lucide-react';

interface WorkflowStatusPanelProps {
  // 後端 /workflow-status 回傳內容，沿用前端既有的 any 慣例
  status: any;
}

interface MetricRowProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  highlight?: boolean;
}

function MetricRow({ icon, label, value, highlight }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2">
      <span className="flex items-center gap-2 text-sm text-slate-600">
        {icon}
        {label}
      </span>
      <span className={`text-sm font-semibold ${highlight ? 'text-amber-600' : 'text-slate-800'}`}>
        {value}
      </span>
    </div>
  );
}

// 顯示知識庫工作流程狀態（文件數、頁數、chunk 數）。
export function WorkflowStatusPanel({ status }: WorkflowStatusPanelProps) {
  if (!status) return null;

  const knowledge = status.knowledge || {};
  return (
    <div className="space-y-2">
      <MetricRow
        icon={<FileText className="h-4 w-4 text-slate-400" />}
        label="文件數"
        value={knowledge.document_count ?? 0}
      />
      <MetricRow
        icon={<FileText className="h-4 w-4 text-slate-400" />}
        label="總頁數"
        value={knowledge.total_pages ?? 0}
      />
      <MetricRow
        icon={<Layers className="h-4 w-4 text-slate-400" />}
        label="索引 chunks"
        value={knowledge.total_chunks ?? 0}
      />
    </div>
  );
}
