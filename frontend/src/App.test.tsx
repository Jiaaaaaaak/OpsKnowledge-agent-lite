import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import {
  getCurrentAdministrator,
  getOperationalHealth,
  getWorkflowStatus,
  listDocuments,
} from './services/api';

vi.mock('./services/api', () => ({
  // 預設匯出（axios 實例）：useHealthCheck 透過它打 /health。
  default: { get: vi.fn().mockResolvedValue({ status: 'ok' }) },
  getCurrentAdministrator: vi.fn(),
  getOperationalHealth: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  getWorkflowStatus: vi.fn(),
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  chat: vi.fn(),
}));

const mockGetCurrentAdministrator = vi.mocked(getCurrentAdministrator);
const mockGetOperationalHealth = vi.mocked(getOperationalHealth);
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
  // StatusBar 在外殼掛載時會抓營運健康；給個健康回應，讓既有外殼測試不受影響。
  mockGetOperationalHealth.mockResolvedValue({
    status: 'ok',
    services: { api: 'ok', database: 'connected', vector: 'connected', redis: 'connected' },
    pulse: { cpu_percent: 1, memory_percent: 1, disk_percent: 1, uptime_seconds: 1 },
    checked_at: '2026-06-28T00:00:00Z',
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
