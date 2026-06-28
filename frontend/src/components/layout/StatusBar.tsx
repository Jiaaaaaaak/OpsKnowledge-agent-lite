import { useEffect, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { getOperationalHealth, OperationalHealth } from '../../services/api';

function dot(state: string): string {
  // connected/ok → 綠；其餘（disconnected/degraded/not_configured）→ 琥珀/紅。
  if (state === 'ok' || state === 'connected') return 'bg-emerald-500';
  if (state === 'degraded') return 'bg-amber-500';
  return 'bg-red-500';
}

function pctOrDash(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}%`;
}

function Pill({ label, state }: { label: string; state: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-600">
      <span className={`h-1.5 w-1.5 rounded-full ${dot(state)}`} />
      {label}
      <span className="font-medium text-slate-800">{state}</span>
    </span>
  );
}

export default function StatusBar() {
  const [health, setHealth] = useState<OperationalHealth | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    getOperationalHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // foundation 階段：模型尚未設定、無任務系統，誠實顯示固定佔位值，不捏造。
  const overall = health?.status ?? 'unknown';
  const database = health?.services.database ?? 'unknown';
  const vector = health?.services.vector ?? 'unknown';
  const model = 'not_configured';
  const activeTasks = 0;

  // 切換鈕的無障礙名稱：用整體狀態描述（系統正常／降級／檢查中），而非把一堆 pill 文字串起來。
  const statusLabel =
    overall === 'ok' ? '系統正常' : overall === 'degraded' ? '系統降級' : '系統檢查中';

  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white">
      <div className="flex h-10 items-center px-6">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={statusLabel}
          aria-expanded={open}
          aria-controls={open ? 'statusbar-details' : undefined}
          className="flex items-center gap-4 rounded px-1 py-0.5 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <Pill label="狀態" state={overall} />
          <Pill label="DB" state={database} />
          <Pill label="向量" state={vector} />
          <Pill label="模型" state={model} />
          <span className="text-xs text-slate-600">
            進行中任務 <span className="font-medium text-slate-800">{activeTasks}</span>
          </span>
          <ChevronDown
            className={`h-3.5 w-3.5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </button>
      </div>

      {open && (
        <div
          id="statusbar-details"
          role="region"
          aria-label="服務細節"
          className="border-t border-slate-100 bg-slate-50 px-6 py-3"
        >
          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs sm:grid-cols-4">
            <Pill label="API" state={health?.services.api ?? 'unknown'} />
            <Pill label="PostgreSQL" state={database} />
            <Pill label="向量索引" state={vector} />
            <Pill label="Redis" state={health?.services.redis ?? 'unknown'} />
            <span className="text-slate-600">CPU <span className="font-medium text-slate-800">{pctOrDash(health?.pulse.cpu_percent)}</span></span>
            <span className="text-slate-600">記憶體 <span className="font-medium text-slate-800">{pctOrDash(health?.pulse.memory_percent)}</span></span>
            <span className="text-slate-600">磁碟 <span className="font-medium text-slate-800">{pctOrDash(health?.pulse.disk_percent)}</span></span>
            <span className="text-slate-600">模型 <span className="font-medium text-slate-800">{model}</span></span>
          </div>
        </div>
      )}
    </div>
  );
}
