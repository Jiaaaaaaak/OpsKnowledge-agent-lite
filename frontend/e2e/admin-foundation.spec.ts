import { expect, Page, test } from '@playwright/test';

// 對「已啟動的整體 stack」執行（docker compose up 後的 http://localhost:8501）。
// 設計為可重複執行（idempotent）：DB 尚無管理員時 bootstrap 建立，已存在時改用一般登入，
// 兩種路徑都用同一組固定憑證，因此不需要每次手動重置資料庫。
const USERNAME = 'admin';
const PASSWORD = 'correct horse battery staple';

// 進入登入頁，依目前模式（建立管理員／登入）完成驗證並抵達 Dashboard。
async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('使用者名稱').fill(USERNAME);
  await page.getByLabel('密碼').fill(PASSWORD);

  // 表單只在 /auth/status 回來後才渲染，按鈕文字一次到位，可直接判斷模式。
  const bootstrapButton = page.getByRole('button', { name: '建立管理員' });
  if (await bootstrapButton.isVisible()) {
    await bootstrapButton.click();
  } else {
    await page.getByRole('button', { name: '登入' }).click();
  }

  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
}

test('administrator reaches the operational dashboard', async ({ page }) => {
  await signIn(page);

  // 點開固定狀態列的細節面板，驗證依賴服務都顯示。
  await page.getByRole('button', { name: /系統正常|系統降級/ }).click();
  await expect(page.getByText('PostgreSQL')).toBeVisible();
  await expect(page.getByText('Redis')).toBeVisible();
});

test('administrator can log out and log back in', async ({ page }) => {
  await signIn(page);

  await page.getByRole('button', { name: '登出' }).click();
  await expect(page.getByRole('heading', { name: '登入 OpsWeave' })).toBeVisible();

  // 登出後（管理員已存在）以一般登入再次進入。
  await page.getByLabel('使用者名稱').fill(USERNAME);
  await page.getByLabel('密碼').fill(PASSWORD);
  await page.getByRole('button', { name: '登入' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
