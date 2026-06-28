import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import StatusBar from './StatusBar';
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
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue(HEALTHY);
});

it('names the toggle by overall status and reveals PostgreSQL on expand', async () => {
  render(<StatusBar />);

  // 切換鈕的無障礙名稱用整體狀態描述（供鍵盤/螢幕報讀與 e2e 定位）。
  const toggle = await screen.findByRole('button', { name: '系統正常' });
  await userEvent.click(toggle);

  // 展開後服務細節用設計指定的 PostgreSQL 命名。
  expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
});
