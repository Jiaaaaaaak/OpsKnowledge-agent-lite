import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import StatusBar from './StatusBar';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import * as api from '../../services/api';

vi.mock('../../services/api');

const HEALTHY = {
  status: 'ok',
  services: { api: 'ok', database: 'connected', vector: 'connected', redis: 'connected' },
  pulse: { cpu_percent: 10, memory_percent: 20, disk_percent: 30, uptime_seconds: 60 },
  checked_at: '2026-06-28T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(api, 'getCurrentAdministrator').mockResolvedValue({
    id: 'a1',
    username: 'root',
    is_active: true,
    created_at: '',
  });
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue(HEALTHY);
});

function renderBar() {
  return render(
    <AuthProvider>
      <ProjectProvider>
        <MemoryRouter>
          <StatusBar />
        </MemoryRouter>
      </ProjectProvider>
    </AuthProvider>,
  );
}

it('names the toggle by overall status and reveals PostgreSQL on expand', async () => {
  renderBar();

  // 切換鈕的無障礙名稱用整體狀態描述（供鍵盤/螢幕報讀與 e2e 定位）。
  const toggle = await screen.findByRole('button', { name: '系統正常' });
  await userEvent.click(toggle);

  // 展開後服務細節用設計指定的 PostgreSQL 命名。
  expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
});

it('clears the persisted project selection on logout', async () => {
  localStorage.setItem(
    'opsknowledge_project',
    JSON.stringify({ id: 'p1', name: 'P', created_at: '' }),
  );
  vi.spyOn(api, 'logout').mockResolvedValue({ message: 'Logged out' });

  renderBar();
  await screen.findByRole('button', { name: '系統正常' });
  await userEvent.click(screen.getByRole('button', { name: '登出' }));

  await waitFor(() =>
    expect(localStorage.getItem('opsknowledge_project')).toBeNull(),
  );
});

it('still clears local state when the server logout call fails', async () => {
  localStorage.setItem(
    'opsknowledge_project',
    JSON.stringify({ id: 'p1', name: 'P', created_at: '' }),
  );
  vi.spyOn(api, 'logout').mockRejectedValue(new Error('500'));

  renderBar();
  await screen.findByRole('button', { name: '系統正常' });
  await userEvent.click(screen.getByRole('button', { name: '登出' }));

  // 伺服器登出失敗也要清本地專案選擇，且不可拋未處理例外。
  await waitFor(() =>
    expect(localStorage.getItem('opsknowledge_project')).toBeNull(),
  );
});
