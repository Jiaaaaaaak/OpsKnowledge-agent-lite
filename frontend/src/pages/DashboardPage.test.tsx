import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import DashboardPage from './DashboardPage';
import * as api from '../services/api';

vi.mock('../services/api');

const HEALTHY = {
  status: 'ok',
  services: {
    api: 'ok',
    database: 'connected',
    vector: 'connected',
    redis: 'connected',
  },
  pulse: {
    cpu_percent: 28,
    memory_percent: 61,
    disk_percent: 42,
    uptime_seconds: 3600,
  },
  checked_at: '2026-06-28T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

it('renders the four approved dashboard groups', async () => {
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue(HEALTHY);

  render(<DashboardPage />);

  expect(await screen.findByText('System Pulse')).toBeInTheDocument();
  expect(screen.getByText('Knowledge Metrics')).toBeInTheDocument();
  expect(screen.getByText('Agent Workload')).toBeInTheDocument();
  expect(screen.getByText('Activity & Alerts')).toBeInTheDocument();
});

it('shows live pulse values from operational health', async () => {
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue(HEALTHY);

  render(<DashboardPage />);

  // System Pulse 卡片要反映真實的 operational health 數值（而非寫死）。
  expect(await screen.findByText('28%')).toBeInTheDocument(); // cpu
  expect(screen.getByText('61%')).toBeInTheDocument(); // memory
  expect(screen.getByText('42%')).toBeInTheDocument(); // disk
});

it('renders foundation-empty groups as zero with an empty-state label, not fabricated data', async () => {
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue(HEALTHY);

  render(<DashboardPage />);

  // 還沒有後端領域的指標必須誠實顯示 0 / 空狀態，不得捏造活動。
  expect(await screen.findByText('System Pulse')).toBeInTheDocument();
  expect(screen.getAllByText('尚無資料').length).toBeGreaterThan(0);
});
