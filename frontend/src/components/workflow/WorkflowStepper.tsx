import { CheckCircle2, Lock } from 'lucide-react';

// 工作流程步驟狀態：已完成 / 進行中 / 可進入 / 鎖定
export type WorkflowStepStatus = 'complete' | 'current' | 'available' | 'locked';

export interface WorkflowStep {
  id: string;
  label: string;
  description?: string;
  status: WorkflowStepStatus;
}

interface WorkflowStepperProps {
  steps: WorkflowStep[];
  // 點擊可進入（available / complete / current）的步驟時觸發
  onStepClick?: (stepId: string) => void;
}

export function WorkflowStepper({ steps, onStepClick }: WorkflowStepperProps) {
  return (
    <ol className="flex flex-col gap-1 sm:flex-row sm:items-stretch sm:gap-2">
      {steps.map((step, index) => {
        const clickable = step.status !== 'locked' && Boolean(onStepClick);
        const isLocked = step.status === 'locked';
        const isComplete = step.status === 'complete';
        const isCurrent = step.status === 'current';

        return (
          <li key={step.id} className="flex-1">
            <button
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onStepClick?.(step.id)}
              className={`flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
                isCurrent
                  ? 'border-indigo-300 bg-indigo-50'
                  : isComplete
                    ? 'border-emerald-200 bg-emerald-50/50'
                    : isLocked
                      ? 'border-slate-200 bg-slate-50 opacity-60'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
              } ${clickable ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                  isComplete
                    ? 'bg-emerald-600 text-white'
                    : isCurrent
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-200 text-slate-500'
                }`}
              >
                {isComplete ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : isLocked ? (
                  <Lock className="h-3.5 w-3.5" />
                ) : (
                  index + 1
                )}
              </span>
              <span className="min-w-0">
                <span
                  className={`block truncate text-sm font-medium ${
                    isCurrent ? 'text-indigo-700' : isLocked ? 'text-slate-400' : 'text-slate-800'
                  }`}
                >
                  {step.label}
                </span>
                {step.description && (
                  <span className="block truncate text-xs text-slate-500">{step.description}</span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
