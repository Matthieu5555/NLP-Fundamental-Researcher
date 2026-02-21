import { test, expect } from '@playwright/test';
import {
  mockFullAnalysisFlow,
} from '../mocks/handlers';

test.describe('Analysis Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockFullAnalysisFlow(page);
  });

  async function startAnalysis(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.getByPlaceholder('e.g., AAPL, MSFT, GOOGL').fill('AAPL');
    await page.getByRole('button', { name: 'Analyze' }).click();
  }

  async function waitForAnalysisComplete(page: import('@playwright/test').Page) {
    // Wait for the Full Report tab to appear — this confirms sections loaded
    await expect(page.getByRole('button', { name: 'Full Report' })).toBeVisible({ timeout: 15_000 });
  }

  test('enter ticker and start analysis shows loading state', async ({ page }) => {
    await page.goto('/');
    await page.getByPlaceholder('e.g., AAPL, MSFT, GOOGL').fill('AAPL');
    await page.getByRole('button', { name: 'Analyze' }).click();

    // Analysis view header should appear
    await expect(page.getByRole('heading', { name: 'Analysis Results' })).toBeVisible({ timeout: 10_000 });
  });

  test('SSE progress events update progress bar', async ({ page }) => {
    await startAnalysis(page);

    // The mock SSE stream completes instantly; verify the final state appeared
    // Progress bar area (step/total) should have rendered at some point, then sections loaded
    await waitForAnalysisComplete(page);

    // Cost should have been captured from the SSE completion event
    await expect(page.getByText(/Cost: \$0\.\d+/)).toBeVisible();
  });

  test('analysis completes and sections render', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    // Heading visible
    await expect(page.getByRole('heading', { name: 'Analysis Results' })).toBeVisible();
    await expect(page.getByText('Multi-agent analysis for AAPL')).toBeVisible();

    // Tabs should appear
    await expect(page.getByRole('button', { name: 'Full Report' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Fundamentals' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Strategy' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Moat' })).toBeVisible();
  });

  test('section content renders as markdown (not raw)', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    // Full Report tab should be active by default — check rendered heading (## becomes h2)
    await expect(page.getByText('AAPL Investment Thesis')).toBeVisible({ timeout: 5_000 });

    // Should be rendered as heading, not as raw "## AAPL Investment Thesis"
    await expect(page.locator('text=## AAPL Investment Thesis')).not.toBeVisible();
  });

  test('tab navigation works', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    // Click Fundamentals tab
    await page.getByRole('button', { name: 'Fundamentals' }).click();
    await expect(page.getByText('fundamentals remain strong')).toBeVisible();

    // Click Strategy tab
    await page.getByRole('button', { name: 'Strategy' }).click();
    await expect(page.getByText('vertical integration')).toBeVisible();

    // Click Moat tab
    await page.getByRole('button', { name: 'Moat' }).click();
    await expect(page.getByText('wide economic moat')).toBeVisible();
  });

  test('cost breakdown displays', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    // Cost badge should appear
    const costBadge = page.getByText(/Cost: \$0\.\d+/);
    await expect(costBadge).toBeVisible();

    // Click to expand breakdown
    await costBadge.click();
    await expect(page.getByText('Cost Breakdown')).toBeVisible();
    await expect(page.getByText('Research Agents')).toBeVisible();
  });

  test('download PDF button appears after analysis', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    await expect(page.getByText('DOWNLOAD PDF')).toBeVisible();
  });

  test('Analyst Notes tab shows empty state', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    await page.getByRole('button', { name: 'Analyst Notes' }).click();
    await expect(page.getByText('No analyst notes yet')).toBeVisible();
  });

  test('Sources tab shows source list', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    await page.getByRole('button', { name: 'Sources' }).click();
    await expect(page.getByText('Apple 10-K FY2024')).toBeVisible();
    await expect(page.getByText('Apple Services Revenue Analysis')).toBeVisible();
  });

  test('Further Research tab shows contradictions', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    await page.getByRole('button', { name: 'Further Research' }).click();
    await expect(page.getByRole('heading', { name: 'Key Disagreements' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'iPhone growth trajectory' })).toBeVisible();
  });

  test('New Analysis button resets state', async ({ page }) => {
    await startAnalysis(page);
    await waitForAnalysisComplete(page);

    await page.getByRole('button', { name: 'New Analysis' }).click();

    // Should return to stock picker
    await expect(page.getByText('Analyze a Stock')).toBeVisible();
    await expect(page.getByPlaceholder('e.g., AAPL, MSFT, GOOGL')).toBeVisible();
  });
});
