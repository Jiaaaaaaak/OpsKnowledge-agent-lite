import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, ListTree, PlaySquare, RefreshCw, UploadCloud } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useProject } from '../context/ProjectContext';
import { analyzeIncidents, getWorkflowStatus, uploadTickets } from '../services/api';
import { ProjectRequiredState } from '../components/workflow/ProjectRequiredState';
import { UploadPanel } from '../components/workflow/UploadPanel';
import { WorkflowStatusPanel } from '../components/workflow/WorkflowStatusPanel';
import { AnalysisProgressPanel } from '../components/workflow/AnalysisProgressPanel';
import { WorkflowStepper, WorkflowStep } from '../components/workflow/WorkflowStepper';

type StepId = 'project' | 'upload' | 'analyze' | 'result';

export default function EventInsightsWorkflowPage() {
  const { currentProject } = useProject();
  const navigate = useNavigate();
  const projectId = currentProject?.id;

  const [status, setStatus] = useState<any>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);
  const [activeStep, setActiveStep] = useState<StepId | null>(null);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeCompleted, setAnalyzeCompleted] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!projectId) return;
    setIsLoadingStatus(true);
    setStatusError(null);
    try {
      const res = await getWorkflowStatus(projectId);
      setStatus(res);
    } catch (err: any) {
      setStatusError(err.message);
    } finally {
      setIsLoadingStatus(false);
    }
  }, [projectId]);

  useEffect(() => {
    setActiveStep(null);
    setStatus(null);
    loadStatus();
  }, [loadStatus]);

  const event = status?.event || {};
  const cleanedCount = event.cleaned_ticket_count ?? 0;
  const unanalyzedCount = event.unanalyzed_ticket_count ?? 0;
  const latestRunId = event.latest_run_id ?? null;

  // 依工作流程狀態推導「自然落點」步驟
  const naturalStep: StepId = useMemo(() => {
    if (cleanedCount === 0) return 'upload';
    if (unanalyzedCount > 0) return 'analyze';
    if (latestRunId) return 'result';
    return 'analyze';
  }, [cleanedCount, unanalyzedCount, latestRunId]);

  // activeStep 為使用者點選的覆寫值，未覆寫時跟隨自然落點
  const currentStep: StepId = activeStep ?? naturalStep;

  const steps: WorkflowStep[] = useMemo(() => {
    const def: { id: StepId; label: string; description?: string }[] = [
      { id: 'project', label: '選擇專案' },
      { id: 'upload', label: '匯入事件', description: `${cleanedCount} 筆已清理` },
      { id: 'analyze', label: 'AI 分析', description: unanalyzedCount > 0 ? `${unanalyzedCount} 筆待分析` : undefined },
      { id: 'result', label: '分析結果' },
    ];

    return def.map((s): WorkflowStep => {
      let stepStatus: WorkflowStep['status'] = 'available';
      if (s.id === currentStep) {
        stepStatus = 'current';
      } else if (s.id === 'project') {
        stepStatus = 'complete';
      } else if (s.id === 'upload') {
        stepStatus = cleanedCount > 0 ? 'complete' : 'available';
      } else if (s.id === 'analyze') {
        stepStatus = cleanedCount > 0 ? 'available' : 'locked';
      } else if (s.id === 'result') {
        stepStatus = latestRunId ? 'available' : 'locked';
      }
      return { ...s, status: stepStatus };
    });
  }, [cleanedCount, unanalyzedCount, latestRunId, currentStep]);

  const handleStepClick = (stepId: string) => {
    setActiveStep(stepId as StepId);
  };

  const handleAnalyze = async () => {
    if (!projectId) return;
    setIsAnalyzing(true);
    setAnalyzeCompleted(false);
    setAnalyzeError(null);
    try {
      const res: any = await analyzeIncidents(projectId);
      setAnalyzeCompleted(true);
      // 短暫顯示完成狀態後導向該次 run 的結果頁
      setTimeout(() => navigate(`/analysis/result/${res.agent_run_id}`), 800);
    } catch (err: any) {
      const msg = err.message || '';
      if (msg.includes('400') || msg.includes('No cleaned records to analyze')) {
        setAnalyzeError('EMPTY_RECORDS');
      } else {
        setAnalyzeError(msg);
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!currentProject) {
    return <ProjectRequiredState />;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">事件洞察流程</h2>
        <p className="mt-1 text-slate-600">依序匯入事件、執行 AI 分析，並檢視該次分析的洞察與行動項目。</p>
      </div>

      <WorkflowStepper steps={steps} onStepClick={handleStepClick} />

      <div className="grid gap-6 md:grid-cols-[1fr_260px]">
        <div className="space-y-6">
          {currentStep === 'upload' && (
            <UploadPanel
              title="匯入事件紀錄"
              description="上傳歷史事件或工單資料 (CSV / Excel / JSON)，系統會自動清理與正規化。"
              accept=".csv,.xlsx,.json"
              idleLabel="開始上傳"
              loadingLabel="處理中..."
              selectedFileLabel="支援 CSV, Excel, JSON 格式"
              onUpload={async (file) => {
                const res = await uploadTickets(projectId!, file);
                await loadStatus();
                return res;
              }}
              renderResult={(result) => (
                <div className="space-y-6">
                  <div className="grid grid-cols-3 gap-4">
                    <Card className="bg-slate-50 text-center">
                      <p className="mb-1 text-sm text-slate-500">原始列數</p>
                      <p className="text-2xl font-semibold text-slate-800">{result.raw_count || 0}</p>
                    </Card>
                    <Card className="border-emerald-100 bg-emerald-50 text-center">
                      <p className="mb-1 text-sm text-emerald-600">清理後筆數</p>
                      <p className="text-2xl font-semibold text-emerald-700">{result.cleaned_count || 0}</p>
                    </Card>
                    <Card className="border-red-100 bg-red-50 text-center">
                      <p className="mb-1 text-sm text-red-600">失敗筆數</p>
                      <p className="text-2xl font-semibold text-red-700">{result.failed_count || 0}</p>
                    </Card>
                  </div>
                  <div className="flex justify-end border-t border-slate-200 pt-6">
                    <Button size="lg" onClick={() => setActiveStep('analyze')} className="flex items-center">
                      下一步：執行 AI 分析
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            />
          )}

          {currentStep === 'analyze' && (
            <Card title="執行 AI 分析" description="啟動 4-tool agent 依序分類、判定嚴重程度、產生洞察與建立行動項目。">
              <div className="flex flex-col items-center py-4 text-center">
                <div className="mb-4 rounded-full bg-indigo-50 p-4">
                  <PlaySquare className="h-8 w-8 text-indigo-600" />
                </div>

                {(isAnalyzing || analyzeCompleted) && (
                  <div className="mb-6 w-full max-w-md text-left">
                    <AnalysisProgressPanel active={isAnalyzing} completed={analyzeCompleted} />
                  </div>
                )}

                {analyzeError === 'EMPTY_RECORDS' && (
                  <div className="mb-6 flex max-w-md flex-col items-center rounded-lg border border-slate-200 bg-slate-50 p-6 text-center">
                    <UploadCloud className="mb-3 h-10 w-10 text-slate-400" />
                    <h4 className="mb-2 font-medium text-slate-800">目前沒有可分析的事件</h4>
                    <p className="mb-4 text-sm text-slate-500">請先匯入事件紀錄，或此專案的事件已全部分析過。</p>
                    <div className="flex gap-2">
                      <Button variant="outline" onClick={() => setActiveStep('upload')}>
                        匯入更多事件
                      </Button>
                      {latestRunId && (
                        <Button onClick={() => navigate(`/analysis/result/${latestRunId}`)}>查看最新結果</Button>
                      )}
                    </div>
                  </div>
                )}

                {analyzeError && analyzeError !== 'EMPTY_RECORDS' && (
                  <div className="mb-6 flex max-w-lg flex-col gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 text-left text-amber-800">
                    <div className="flex items-start">
                      <AlertCircle className="mr-3 mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                      <span className="text-sm">{analyzeError}</span>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleAnalyze}>
                        重試
                      </Button>
                      <Link to="/agent-runs">
                        <Button size="sm" variant="outline" className="flex items-center">
                          <ListTree className="mr-2 h-4 w-4" />
                          查看 Agent 執行紀錄
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}

                {!isAnalyzing && !analyzeCompleted && analyzeError !== 'EMPTY_RECORDS' && (
                  <Button size="lg" onClick={handleAnalyze} disabled={isAnalyzing}>
                    執行事件分析
                  </Button>
                )}
              </div>
            </Card>
          )}

          {currentStep === 'result' && (
            <Card title="分析結果" description="檢視此專案最近一次的分析結果。">
              <div className="flex flex-col items-center gap-4 py-6 text-center">
                {latestRunId ? (
                  <>
                    <p className="max-w-md text-sm text-slate-500">
                      最近一次分析狀態：{event.latest_run_status || '未知'}。開啟結果頁檢視洞察與行動項目。
                    </p>
                    <Button size="lg" onClick={() => navigate(`/analysis/result/${latestRunId}`)} className="flex items-center">
                      開啟分析結果
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <p className="text-sm text-slate-500">尚無分析結果，請先執行 AI 分析。</p>
                )}
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title="工作流程狀態">
            {statusError ? (
              <p className="text-sm text-red-600">狀態載入失敗：{statusError}</p>
            ) : (
              <WorkflowStatusPanel status={status} variant="event" />
            )}
            <div className="mt-4">
              <Button variant="secondary" size="sm" onClick={loadStatus} disabled={isLoadingStatus} className="w-full">
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoadingStatus ? 'animate-spin' : ''}`} />
                重新整理
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
