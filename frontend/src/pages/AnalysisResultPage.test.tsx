import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AnalysisResultPage from './AnalysisResultPage';
import { getAnalysisResult } from '../services/api';

vi.mock('../services/api', () => ({
  getAnalysisResult: vi.fn(),
}));

const mockGetAnalysisResult = vi.mocked(getAnalysisResult);

function renderResult(id = 'run-1') {
  return render(
    <MemoryRouter initialEntries={[`/analysis/result/${id}`]}>
      <Routes>
        <Route path="/analysis/result/:agentRunId" element={<AnalysisResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AnalysisResultPage', () => {
  it('渲染摘要、洞察與行動項目', async () => {
    mockGetAnalysisResult.mockResolvedValue({
      run: {
        id: 'run-1',
        project_id: 'p1',
        task_type: 'analyze_incidents',
        model_name: 'gpt-test',
        status: 'success',
        latency_ms: 1200,
        created_at: '2026-06-15',
        error_message: null,
      },
      summary: { records_analyzed: 8, needs_review: 2, insights_created: 1, action_items_created: 1 },
      insights: [{ id: 'i1', title: 'Top: storage_issue', summary: 'sum', evidence: [], recommendation: 'rec' }],
      action_items: [
        { id: 'a1', title: 'Fix disk', description: 'desc', priority: 'high', owner_role: 'SRE', status: 'open' },
      ],
    });

    renderResult();

    // 洞察與行動項目區塊
    expect(await screen.findByText('Top: storage_issue')).toBeInTheDocument();
    expect(screen.getByText('產生的洞察')).toBeInTheDocument();
    expect(screen.getByText('行動項目')).toBeInTheDocument();
    expect(screen.getByText('Fix disk')).toBeInTheDocument();
    // 摘要數字（已分析筆數）
    expect(screen.getByText('8')).toBeInTheDocument();
  });

  it('找不到 run 時顯示錯誤狀態與返回入口', async () => {
    mockGetAnalysisResult.mockRejectedValue(new Error('Agent run not found'));
    renderResult('missing');

    expect(await screen.findByText('找不到此分析結果')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回事件洞察流程' })).toBeInTheDocument();
  });
});
