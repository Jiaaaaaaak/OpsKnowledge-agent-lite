import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EventInsightsWorkflowPage from './EventInsightsWorkflowPage';
import { analyzeIncidents, getWorkflowStatus } from '../services/api';

// 以 hoisted 變數讓 vi.mock factory 取得可變的 navigate / project 替身
const { mockNavigate, mockUseProject } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockUseProject: vi.fn(),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/ProjectContext', () => ({
  useProject: () => mockUseProject(),
}));

vi.mock('../services/api', () => ({
  getWorkflowStatus: vi.fn(),
  analyzeIncidents: vi.fn(),
  uploadTickets: vi.fn(),
}));

const mockGetWorkflowStatus = vi.mocked(getWorkflowStatus);
const mockAnalyzeIncidents = vi.mocked(analyzeIncidents);

function eventStatus(overrides: Record<string, unknown>) {
  return {
    project_id: 'p1',
    event: {
      cleaned_ticket_count: 0,
      analyzed_ticket_count: 0,
      unanalyzed_ticket_count: 0,
      latest_run_id: null,
      latest_run_status: null,
      ...overrides,
    },
    knowledge: { document_count: 0, total_pages: 0, total_chunks: 0, can_chat: false },
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <EventInsightsWorkflowPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseProject.mockReturnValue({ currentProject: { id: 'p1', name: 'Proj', created_at: '' } });
});

describe('EventInsightsWorkflowPage 步驟定位', () => {
  it('未選擇專案時顯示專案必填空狀態', () => {
    mockUseProject.mockReturnValue({ currentProject: null });
    renderPage();
    expect(screen.getByText('尚未選擇專案')).toBeInTheDocument();
    expect(mockGetWorkflowStatus).not.toHaveBeenCalled();
  });

  it('尚無事件資料時停在匯入步驟', async () => {
    mockGetWorkflowStatus.mockResolvedValue(eventStatus({ cleaned_ticket_count: 0 }));
    renderPage();
    expect(await screen.findByText('匯入事件紀錄')).toBeInTheDocument();
  });

  it('有待分析事件時定位到分析步驟', async () => {
    mockGetWorkflowStatus.mockResolvedValue(
      eventStatus({ cleaned_ticket_count: 10, unanalyzed_ticket_count: 5 }),
    );
    renderPage();
    expect(await screen.findByRole('button', { name: '執行事件分析' })).toBeInTheDocument();
  });

  it('已有最新分析結果時定位到結果步驟', async () => {
    mockGetWorkflowStatus.mockResolvedValue(
      eventStatus({ cleaned_ticket_count: 10, unanalyzed_ticket_count: 0, latest_run_id: 'run-9', latest_run_status: 'success' }),
    );
    renderPage();
    expect(await screen.findByRole('button', { name: /開啟分析結果/ })).toBeInTheDocument();
  });
});

describe('EventInsightsWorkflowPage 分析流程', () => {
  it('分析成功後導向該次 run 的結果頁', async () => {
    mockGetWorkflowStatus.mockResolvedValue(
      eventStatus({ cleaned_ticket_count: 10, unanalyzed_ticket_count: 5 }),
    );
    mockAnalyzeIncidents.mockResolvedValue({ agent_run_id: 'run-123', status: 'success', summary: {} });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '執行事件分析' }));

    await waitFor(
      () => expect(mockNavigate).toHaveBeenCalledWith('/analysis/result/run-123'),
      { timeout: 2000 },
    );
  });

  it('分析失敗時留在分析步驟並提供重試', async () => {
    mockGetWorkflowStatus.mockResolvedValue(
      eventStatus({ cleaned_ticket_count: 10, unanalyzed_ticket_count: 5 }),
    );
    mockAnalyzeIncidents.mockRejectedValue(new Error('500 internal error'));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: '執行事件分析' }));

    expect(await screen.findByRole('button', { name: '重試' })).toBeInTheDocument();
    // 仍停留在分析步驟（分析卡片標題存在），且未導頁
    expect(screen.getByText('執行 AI 分析')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
