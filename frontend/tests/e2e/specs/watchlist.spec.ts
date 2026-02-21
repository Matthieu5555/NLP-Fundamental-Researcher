import { test, expect } from '@playwright/test';
import { mockWatchlist, mockSettings, mockSessionResume, mockReportSections, mockValuationData, mockCompanyInfo, mockFinancialStatements, mockSessionBeliefs } from '../mocks/handlers';

test.describe('Watchlist', () => {
  test.beforeEach(async ({ page }) => {
    await mockWatchlist(page);
    await mockSettings(page);
  });

  test('watchlist button toggles dashboard', async ({ page }) => {
    await page.goto('/');

    // Click Watchlist button
    await page.getByRole('button', { name: 'Watchlist' }).click();

    // Watchlist should appear
    await expect(page.getByRole('heading', { name: 'Watchlist' })).toBeVisible({ timeout: 5_000 });
  });

  test('watchlist shows items with prices and fair value gaps', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Watchlist' }).click();

    // Table headers (use columnheader role to avoid matching other text)
    await expect(page.getByRole('columnheader', { name: 'Ticker' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Price' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Fair Value' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Gap' })).toBeVisible();

    // AAPL row
    await expect(page.getByText('Apple Inc.')).toBeVisible();
    await expect(page.getByText('$183.25')).toBeVisible();
    await expect(page.getByText('$205.00')).toBeVisible();
    await expect(page.getByText('+11.9%')).toBeVisible();

    // MSFT row
    await expect(page.getByText('Microsoft Corporation')).toBeVisible();
    await expect(page.getByText('$415.80')).toBeVisible();
    await expect(page.getByText('-8.6%')).toBeVisible();
  });

  test('remove item from watchlist', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Watchlist' }).click();

    await expect(page.getByText('Apple Inc.')).toBeVisible({ timeout: 5_000 });

    // Click Remove on AAPL row
    const aaplRow = page.locator('tr:has-text("AAPL")');
    await aaplRow.getByRole('button', { name: 'Remove' }).click();

    // AAPL should be removed from the list
    await expect(page.getByText('Apple Inc.')).not.toBeVisible({ timeout: 3_000 });
  });

  test('navigate to session from watchlist item', async ({ page }) => {
    // Also need session/analysis mocks for navigation
    await mockSessionResume(page);
    await mockReportSections(page);
    await mockValuationData(page);
    await mockCompanyInfo(page);
    await mockFinancialStatements(page);
    await mockSessionBeliefs(page);

    await page.goto('/');
    await page.getByRole('button', { name: 'Watchlist' }).click();

    await expect(page.getByText('Apple Inc.')).toBeVisible({ timeout: 5_000 });

    // Click View on AAPL row
    const aaplRow = page.locator('tr:has-text("AAPL")');
    await aaplRow.getByRole('button', { name: 'View' }).click();

    // Should load the analysis
    await expect(page.getByRole('heading', { name: 'Analysis Results' })).toBeVisible({ timeout: 10_000 });
  });

  test('watchlist refresh button reloads data', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Watchlist' }).click();

    await expect(page.getByText('Apple Inc.')).toBeVisible({ timeout: 5_000 });

    // Click Refresh
    await page.getByRole('button', { name: 'Refresh' }).click();

    // Data should still be present (mock returns same data)
    await expect(page.getByText('Apple Inc.')).toBeVisible();
  });
});
