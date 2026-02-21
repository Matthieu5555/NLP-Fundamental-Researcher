import { test, expect } from '@playwright/test';
import { mockUsageStats, mockSettings } from '../mocks/handlers';

test.describe('Usage Statistics', () => {
  test.beforeEach(async ({ page }) => {
    await mockUsageStats(page);
    await mockSettings(page);
  });

  test('usage stats modal opens from user button', async ({ page }) => {
    await page.goto('/');

    // Click the user name / usage stats button
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByRole('heading', { name: 'Usage Statistics' })).toBeVisible();
  });

  test('shows current month stats', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByText('Last 30 Days')).toBeVisible();
    await expect(page.getByText('42')).toBeVisible(); // requests
    await expect(page.getByText('$3.75')).toBeVisible(); // cost
    await expect(page.getByText('156.8k')).toBeVisible(); // tokens
    await expect(page.getByText('34%')).toBeVisible(); // cache hit rate
  });

  test('shows all-time stats', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByText('All Time')).toBeVisible();
    await expect(page.getByText('128 requests')).toBeVisible();
    await expect(page.getByText('$12.50 total cost')).toBeVisible();
  });

  test('shows top tickers', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByText('Top Tickers')).toBeVisible();
    await expect(page.getByText('AAPL')).toBeVisible();
    await expect(page.getByText('MSFT')).toBeVisible();
    await expect(page.getByText('GOOGL')).toBeVisible();
  });

  test('shows recent activity', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByText('Recent Activity')).toBeVisible();
    await expect(page.getByText('12 requests')).toBeVisible();
    await expect(page.getByText('$1.25')).toBeVisible();
  });

  test('close usage modal', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('View usage statistics').click();

    await expect(page.getByRole('heading', { name: 'Usage Statistics' })).toBeVisible();

    // Close via X button
    await page.locator('.fixed button:has(svg)').first().click();

    await expect(page.getByRole('heading', { name: 'Usage Statistics' })).not.toBeVisible();
  });
});
