import { test, expect } from '@playwright/test';
import { mockFullAnalysisFlow, mockPdfExport } from '../mocks/handlers';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('PDF Export', () => {
  test.beforeEach(async ({ page }) => {
    await mockFullAnalysisFlow(page);
    await mockPdfExport(page);
  });

  async function runAnalysisFirst(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.getByPlaceholder('e.g., AAPL, MSFT, GOOGL').fill('AAPL');
    await page.getByRole('button', { name: 'Analyze' }).click();
    // Wait for the Full Report tab — confirms sections loaded
    await expect(page.getByRole('button', { name: 'Full Report' })).toBeVisible({ timeout: 15_000 });
  }

  test('download PDF button triggers download', async ({ page }) => {
    await runAnalysisFirst(page);

    // Set up download listener before clicking
    const downloadPromise = page.waitForEvent('download');

    await page.getByText('DOWNLOAD PDF').click();

    const download = await downloadPromise;

    // Verify download was triggered
    expect(download.suggestedFilename()).toMatch(/AAPL.*\.pdf$/);
  });

  test('downloaded file is valid PDF', async ({ page }) => {
    await runAnalysisFirst(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByText('DOWNLOAD PDF').click();
    const download = await downloadPromise;

    // Save to temp path and verify
    const downloadPath = path.join(__dirname, '..', '.tmp', 'test-download.pdf');
    const dir = path.dirname(downloadPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    await download.saveAs(downloadPath);

    // Read file and check PDF header
    const content = fs.readFileSync(downloadPath);
    expect(content.length).toBeGreaterThan(100);
    expect(content.toString('ascii', 0, 5)).toBe('%PDF-');

    // Clean up
    fs.unlinkSync(downloadPath);
  });

  test('PDF download button shows loading state', async ({ page }) => {
    // Override with a slow response that takes 2s
    await page.route('http://localhost:5001/api/reports/*/export/pdf', async (route) => {
      await new Promise(r => setTimeout(r, 2000));
      // Must be > 1000 bytes to pass the app's size check
      const padding = ' '.repeat(1100);
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': 'attachment; filename="AAPL_analysis.pdf"',
        },
        body: Buffer.from(`%PDF-1.4\n${padding}\n%%EOF`),
      });
    });

    await runAnalysisFirst(page);

    await page.getByText('DOWNLOAD PDF').click();

    // Should show loading text while waiting for the slow response
    await expect(page.getByText('Generating PDF...')).toBeVisible({ timeout: 3_000 });
  });
});
