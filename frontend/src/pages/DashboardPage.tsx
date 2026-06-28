import { useEffect, useState } from 'react';
import { Activity, Boxes, Cpu, ListChecks } from 'lucide-react';
import { getOperationalHealth, OperationalHealth } from '../services/api';

function formatUptime(seconds: number | null): string {
  if (seconds === null) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value)}%`;
}

function BentoCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <header className="mb-4 flex items-center gap-2">
        <span className="text-indigo-500">{icon}</span>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      </header>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  );
}

// 還沒有後端領域的群組：誠實顯示 0 + 空狀態，不捏造活動。
function EmptyMetrics({ labels }: { labels: string[] }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        {labels.map((l) => (
          <Metric key={l} label={l} value="0" />
        ))}
      </div>
      <p className="mt-3 text-xs italic text-slate-400">尚無資料</p>
    </>
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<OperationalHealth | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getOperationalHealth()
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  const pulse = health?.pulse;
  const refreshed = health?.checked_at
    ? new Date(health.checked_at).toLocaleTimeString()
    : '—';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">營運儀表板</h1>
        <p className="text-sm text-slate-500">OpsWeave foundation 即時營運概況</p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <BentoCard title="System Pulse" icon={<Cpu className="h-4 w-4" />}>
          {error ? (
            <p className="text-sm text-error">無法取得營運健康資料</p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Metric label="CPU" value={pct(pulse?.cpu_percent ?? null)} />
                <Metric label="記憶體" value={pct(pulse?.memory_percent ?? null)} />
                <Metric label="磁碟" value={pct(pulse?.disk_percent ?? null)} />
                <Metric label="運行時間" value={formatUptime(pulse?.uptime_seconds ?? null)} />
              </div>
              <p className="mt-3 text-xs text-slate-400">更新於 {refreshed}</p>
            </>
          )}
        </BentoCard>

        <BentoCard title="Knowledge Metrics" icon={<Boxes className="h-4 w-4" />}>
          <EmptyMetrics labels={['知識庫', '文件', '區塊', '索引中']} />
        </BentoCard>

        <BentoCard title="Agent Workload" icon={<ListChecks className="h-4 w-4" />}>
          <EmptyMetrics labels={['排隊中', '執行中', '成功', '失敗']} />
        </BentoCard>

        <BentoCard title="Activity & Alerts" icon={<Activity className="h-4 w-4" />}>
          <p className="text-sm text-slate-500">近期完成、失敗與復原連結會顯示在此。</p>
          <p className="mt-3 text-xs italic text-slate-400">尚無資料</p>
        </BentoCard>
      </div>
    </div>
  );
}
