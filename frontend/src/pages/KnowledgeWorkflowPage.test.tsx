import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KnowledgeWorkflowPage from './KnowledgeWorkflowPage';
import { getWorkflowStatus, listDocuments } from '../services/api';

const { mockUseProject } = vi.hoisted(() => ({ mockUseProject: vi.fn() }));

vi.mock('../context/ProjectContext', () => ({
  useProject: () => mockUseProject(),
}));

vi.mock('../services/api', () => ({
  getWorkflowStatus: vi.fn(),
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  chat: vi.fn(),
}));

const mockGetWorkflowStatus = vi.mocked(getWorkflowStatus);
const mockListDocuments = vi.mocked(listDocuments);

function knowledgeStatus(knowledge: Record<string, unknown>) {
  return {
    project_id: 'p1',
    event: {},
    knowledge: { document_count: 0, total_pages: 0, total_chunks: 0, can_chat: false, ...knowledge },
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <KnowledgeWorkflowPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseProject.mockReturnValue({ currentProject: { id: 'p1', name: 'Proj', created_at: '' } });
});

describe('KnowledgeWorkflowPage', () => {
  it('沒有文件時停在知識庫步驟並鎖定提問', async () => {
    mockGetWorkflowStatus.mockResolvedValue(knowledgeStatus({ can_chat: false, document_count: 0 }));
    mockListDocuments.mockResolvedValue([]);
    renderPage();

    // 停在知識庫上傳步驟
    expect(await screen.findByText('上傳技術文件')).toBeInTheDocument();
    // 「提問」步驟鎖定 → 按鈕停用，且沒有對話輸入框
    expect(screen.getByRole('button', { name: '提問' })).toBeDisabled();
    expect(screen.queryByPlaceholderText(/Docker volume/)).not.toBeInTheDocument();
  });

  it('有文件且可對話時進入提問步驟', async () => {
    mockGetWorkflowStatus.mockResolvedValue(
      knowledgeStatus({ can_chat: true, document_count: 2, total_pages: 5, total_chunks: 20 }),
    );
    mockListDocuments.mockResolvedValue([{ id: 'd1', filename: 'a.pdf', page_count: 5, chunk_count: 20 }]);
    renderPage();

    expect(await screen.findByPlaceholderText(/Docker volume/)).toBeInTheDocument();
  });
});
