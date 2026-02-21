import { test, expect } from '@playwright/test';
import {
  mockSessionsList,
  mockSessionResume,
  mockSessionDelete,
  mockSessionBeliefs,
  mockReportSections,
  mockValuationData,
  mockCompanyInfo,
  mockFinancialStatements,
  mockSettings,
} from '../mocks/handlers';

test.describe('Sessions', () => {
  test.beforeEach(async ({ page }) => {
    await mockSessionsList(page);
    await mockSessionResume(page);
    await mockSessionDelete(page);
    await mockSessionBeliefs(page);
    await mockReportSections(page);
    await mockValuationData(page);
    await mockCompanyInfo(page);
    await mockFinancialStatements(page);
    await mockSettings(page);
  });

  test('session browser opens and lists sessions', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    // Modal should open with sessions
    await expect(page.getByText('Resume Past Analysis')).toBeVisible();
    await expect(page.getByText('2 sessions saved')).toBeVisible();
    await expect(page.getByText('AAPL')).toBeVisible();
    await expect(page.getByText('MSFT')).toBeVisible();
  });

  test('session browser shows search', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    // Search input should be present
    const searchInput = page.getByPlaceholder('Search by ticker...');
    await expect(searchInput).toBeVisible();

    // Filter by ticker
    await searchInput.fill('AAPL');
    await expect(page.getByText('AAPL')).toBeVisible();
    // MSFT should be filtered out
    await expect(page.locator('h3:has-text("MSFT")')).not.toBeVisible();
  });

  test('resume session loads existing analysis', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    // Click on AAPL session
    await page.getByText('Comprehensive analysis of Apple Inc.').click();

    // Modal should close and analysis should load
    await expect(page.getByText('Resume Past Analysis')).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole('heading', { name: 'Analysis Results' })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Multi-agent analysis for AAPL')).toBeVisible();
  });

  test('delete session removes it from list', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    // Should show 2 sessions initially
    await expect(page.getByText('2 sessions saved')).toBeVisible();

    // Accept the confirm dialog
    page.on('dialog', dialog => dialog.accept());

    // Hover over MSFT session to reveal delete button and click it
    // Session cards have "group" class — filter to the one containing MSFT
    const msftSession = page.locator('.group').filter({ hasText: 'MSFT' });
    await msftSession.hover();
    await msftSession.locator('[title="Delete session"]').click();

    // MSFT should be removed
    await expect(page.locator('h3:has-text("MSFT")')).not.toBeVisible({ timeout: 5_000 });
  });

  test('close session browser with X button', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    await expect(page.getByText('Resume Past Analysis')).toBeVisible();

    // Close the modal
    await page.locator('.fixed button:has(svg)').first().click();
    await expect(page.getByText('Resume Past Analysis')).not.toBeVisible();
  });

  test('session shows metadata', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Resume Analysis' }).click();

    // Each session should show message count and date
    await expect(page.getByText('5 messages')).toBeVisible();
    await expect(page.getByText('3 messages')).toBeVisible();
  });
});
