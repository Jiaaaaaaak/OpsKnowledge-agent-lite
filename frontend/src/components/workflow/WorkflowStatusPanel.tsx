import { AlertTriangle, FileText, Layers, ListChecks } from 'lucide-react';

interface WorkflowStatusPanelProps {
  // 後端 /workflow-status 回傳內容，沿用前端既有的 any 慣例
  status: any;
  // 只顯示與當前工作流程相關的區塊
  variant: 'event' | 'knowledge';
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

// 顯示專案層級的工作流程事實（待分析事件、文件數、頁數、chunk 數等）。
export function WorkflowStatusPanel({ status, variant }: WorkflowStatusPanelProps) {
  if (!status) return null;

  if (variant === 'event') {
    const event = status.event || {};
    return (
      <div className="space-y-2">
        <MetricRow
          icon={<ListChecks className="h-4 w-4 text-slate-400" />}
          label="已清理工單"
          value={event.cleaned_ticket_count ?? 0}
        />
        <MetricRow
          icon={<ListChecks className="h-4 w-4 text-slate-400" />}
          label="已分析工單"
          value={event.analyzed_ticket_count ?? 0}
        />
        <MetricRow
          icon={<AlertTriangle className="h-4 w-4 text-amber-400" />}
          label="待分析工單"
          value={event.unanalyzed_ticket_count ?? 0}
          highlight={(event.unanalyzed_ticket_count ?? 0) > 0}
        />
      </div>
    );
  }

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
