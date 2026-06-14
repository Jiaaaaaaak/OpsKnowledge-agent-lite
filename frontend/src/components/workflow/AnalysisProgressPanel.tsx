import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';

// 事件分析的四個前端估計階段（與後端 4-tool agent 對應）。
const STAGES = ['分類事件', '判定嚴重程度', '產生洞察', '建立行動項目'];

// 進度未完成前的上限：估計進度只前進到 92%，待 API resolve 後才到 100%。
const ESTIMATE_CEILING = 92;

interface AnalysisProgressPanelProps {
  // 分析 API 進行中
  active: boolean;
  // 父層確認 API 已成功 resolve
  completed: boolean;
}

// 事件分析專用的分階段進度面板，進度為前端估計值。
export function AnalysisProgressPanel({ active, completed }: AnalysisProgressPanelProps) {
  const [progress, setProgress] = useState(0);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (active && !completed) {
      // 啟動時重置，並以固定間隔朝上限緩慢推進
      setProgress(0);
      intervalRef.current = window.setInterval(() => {
        setProgress((prev) => {
          if (prev >= ESTIMATE_CEILING) return ESTIMATE_CEILING;
          // 越接近上限推進越慢，營造逐步收斂感
          const step = prev < 60 ? 4 : 2;
          return Math.min(prev + step, ESTIMATE_CEILING);
        });
      }, 600);
    }

    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [active, completed]);

  useEffect(() => {
    if (completed) setProgress(100);
  }, [completed]);

  // 依進度換算目前所在階段（完成時全部標記為已完成）
  const currentStageIndex = completed
    ? STAGES.length
    : Math.min(Math.floor((progress / ESTIMATE_CEILING) * STAGES.length), STAGES.length - 1);

  return (
    <div className="space-y-4">
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            completed ? 'bg-emerald-500' : 'bg-indigo-500'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <ul className="space-y-2">
        {STAGES.map((stage, index) => {
          const done = index < currentStageIndex;
          const current = index === currentStageIndex && !completed;
          return (
            <li key={stage} className="flex items-center gap-3 text-sm">
              {done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
              ) : current ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-500" />
              ) : (
                <span className="h-4 w-4 shrink-0 rounded-full border border-slate-300" />
              )}
              <span
                className={
                  done ? 'text-slate-500' : current ? 'font-medium text-indigo-700' : 'text-slate-400'
                }
              >
                {stage}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
