import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import Sidebar from './Sidebar';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import * as api from '../../services/api';

vi.mock('../../services/api');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(api, 'getCurrentAdministrator').mockResolvedValue({
    id: 'a1',
    username: 'root',
    is_active: true,
    created_at: '',
  });
});

function renderSidebar() {
  return render(
    <AuthProvider>
      <ProjectProvider>
        <MemoryRouter>
          <Sidebar />
        </MemoryRouter>
      </ProjectProvider>
    </AuthProvider>,
  );
}

it('shows the administrator name and a logout control in the footer', async () => {
  renderSidebar();

  // 使用者名稱與登出移到側邊欄下方。
  expect(await screen.findByText('root')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '登出' })).toBeInTheDocument();
});

it('clears the persisted project selection on logout', async () => {
  localStorage.setItem(
    'opsknowledge_project',
    JSON.stringify({ id: 'p1', name: 'P', created_at: '' }),
  );
  vi.spyOn(api, 'logout').mockResolvedValue({ message: 'Logged out' });

  renderSidebar();
  await userEvent.click(await screen.findByRole('button', { name: '登出' }));

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

  renderSidebar();
  await userEvent.click(await screen.findByRole('button', { name: '登出' }));

  // 伺服器登出失敗也要清本地專案選擇，且不可拋未處理例外。
  await waitFor(() =>
    expect(localStorage.getItem('opsknowledge_project')).toBeNull(),
  );
});
