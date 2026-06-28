import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from './AuthContext';
import LoginPage from '../pages/LoginPage';
import * as api from '../services/api';

// 整個 api 模組自動 mock：所有匯出變成 vi.fn()，再針對個別案例覆寫行為。
vi.mock('../services/api');

const ADMIN = { id: 'a1', username: 'root', is_active: true, created_at: '' };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  window.history.pushState({}, '', '/');
});

it('redirects an anonymous visitor to the administrator login', async () => {
  // 還沒登入：/auth/me 回 401，受保護的應用外殼不得出現，要被導到登入頁。
  vi.spyOn(api, 'getCurrentAdministrator').mockRejectedValue(new Error('401'));

  render(<App />);

  expect(
    await screen.findByRole('heading', { name: '登入 OpsWeave' }),
  ).toBeInTheDocument();
});

it('shows a generic alert when credentials are rejected', async () => {
  vi.spyOn(api, 'getCurrentAdministrator').mockRejectedValue(new Error('401'));
  vi.spyOn(api, 'login').mockRejectedValue(new Error('Invalid username or password'));

  render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>DASHBOARD</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );

  await userEvent.type(await screen.findByLabelText('使用者名稱'), 'root');
  await userEvent.type(screen.getByLabelText('密碼'), 'wrong');
  await userEvent.click(screen.getByRole('button', { name: '登入' }));

  // 通用錯誤訊息：不得透露是帳號不存在還是密碼錯誤。
  expect(await screen.findByRole('alert')).toHaveTextContent('帳號或密碼錯誤');
  expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument();
});

it('enters the application after a successful login', async () => {
  vi.spyOn(api, 'getCurrentAdministrator').mockRejectedValue(new Error('401'));
  vi.spyOn(api, 'login').mockResolvedValue(ADMIN);

  render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>DASHBOARD</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );

  await userEvent.type(await screen.findByLabelText('使用者名稱'), 'root');
  await userEvent.type(screen.getByLabelText('密碼'), 'correct');
  await userEvent.click(screen.getByRole('button', { name: '登入' }));

  await waitFor(() => expect(api.login).toHaveBeenCalledWith('root', 'correct'));
  // 登入成功後導入應用外殼。
  expect(await screen.findByText('DASHBOARD')).toBeInTheDocument();
});

it('switches to administrator bootstrap when no administrator exists', async () => {
  vi.spyOn(api, 'getCurrentAdministrator').mockRejectedValue(new Error('401'));
  vi.spyOn(api, 'getAuthStatus').mockResolvedValue({ bootstrap_required: true });
  vi.spyOn(api, 'bootstrap').mockResolvedValue(ADMIN);

  render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>DASHBOARD</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );

  // 首次安裝：應切換到「建立管理員」而非一般登入。
  const submit = await screen.findByRole('button', { name: '建立管理員' });
  await userEvent.type(screen.getByLabelText('使用者名稱'), 'admin');
  await userEvent.type(screen.getByLabelText('密碼'), 'correct horse battery staple');
  await userEvent.click(submit);

  await waitFor(() =>
    expect(api.bootstrap).toHaveBeenCalledWith('admin', 'correct horse battery staple'),
  );
  expect(await screen.findByText('DASHBOARD')).toBeInTheDocument();
});
