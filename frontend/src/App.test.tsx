import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { getCurrentAdministrator, getWorkflowStatus, listDocuments } from './services/api';

vi.mock('./services/api', () => ({
  getCurrentAdministrator: vi.fn(),
  getWorkflowStatus: vi.fn(),
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  chat: vi.fn(),
}));

const mockGetCurrentAdministrator = vi.mocked(getCurrentAdministrator);
const mockGetWorkflowStatus = vi.mocked(getWorkflowStatus);
const mockListDocuments = vi.mocked(listDocuments);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem(
    'opsknowledge_project',
    JSON.stringify({ id: 'p1', name: 'Proj', created_at: '' }),
  );
  // 受保護路由要求先通過認證；預設視為已登入，讓既有外殼測試維持原本意圖。
  mockGetCurrentAdministrator.mockResolvedValue({
    id: 'a1',
    username: 'root',
    is_active: true,
    created_at: '',
  });
});

it('redirects the legacy document upload route to the knowledge workflow', async () => {
  window.history.pushState({}, '', '/document-upload');
  mockGetWorkflowStatus.mockResolvedValue({
    project_id: 'p1',
    knowledge: { document_count: 0, total_pages: 0, total_chunks: 0, can_chat: false },
  });
  mockListDocuments.mockResolvedValue([]);

  render(<App />);

  expect(await screen.findByText('上傳技術文件')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/knowledge/workflow');
});
