import { test, expect } from '@playwright/test';
import {
  mockFullAnalysisFlow,
  mockChatStream,
  mockChatHistory,
} from '../mocks/handlers';

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await mockFullAnalysisFlow(page);
    await mockChatHistory(page);
  });

  async function runAnalysisFirst(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.getByPlaceholder('e.g., AAPL, MSFT, GOOGL').fill('AAPL');
    await page.getByRole('button', { name: 'Analyze' }).click();

    // Wait for analysis to complete and chat to appear
    await expect(page.getByText('Dive Deeper on AAPL')).toBeVisible({ timeout: 15_000 });
  }

  test('chat interface appears after analysis completes', async ({ page }) => {
    await runAnalysisFirst(page);

    await expect(page.getByText('Dive Deeper on AAPL')).toBeVisible();
    await expect(page.getByPlaceholder('Ask a question about the analysis...')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Send' })).toBeVisible();
  });

  test('example questions are shown when chat is empty', async ({ page }) => {
    await runAnalysisFirst(page);

    await expect(page.getByText('Example questions:')).toBeVisible();
    await expect(page.getByText('What is the return on equity?')).toBeVisible();
    await expect(page.getByText('What are the biggest risks?')).toBeVisible();
  });

  test('clicking example question fills input', async ({ page }) => {
    await runAnalysisFirst(page);

    await page.getByText('What is the return on equity?').click();
    const input = page.getByPlaceholder('Ask a question about the analysis...');
    await expect(input).toHaveValue('What is the return on equity?');
  });

  test('send message and receive streaming response', async ({ page }) => {
    await mockChatStream(page);
    await runAnalysisFirst(page);

    // Type and send a message
    await page.getByPlaceholder('Ask a question about the analysis...').fill('What is the ROE?');
    await page.getByRole('button', { name: 'Send' }).click();

    // User message should appear
    await expect(page.getByText('What is the ROE?')).toBeVisible();

    // Assistant response should stream in
    await expect(page.getByText('171.9%')).toBeVisible({ timeout: 10_000 });

    // Sources should appear
    await expect(page.getByText('Sources:')).toBeVisible();
    await expect(page.getByText('Apple 10-K FY2024')).toBeVisible();
  });

  test('belief extraction shows notice', async ({ page }) => {
    await mockChatStream(page, { withBeliefs: true });
    await runAnalysisFirst(page);

    await page.getByPlaceholder('Ask a question about the analysis...').fill('Apple has great ROE');
    await page.getByRole('button', { name: 'Send' }).click();

    // Should show belief notice
    await expect(page.getByText('Constant took note of that')).toBeVisible({ timeout: 10_000 });
  });

  test('send button is disabled while streaming', async ({ page }) => {
    // Set up a slow chat mock that takes 2s to respond
    await page.route(`http://localhost:5001/api/chat/stream*`, async (route) => {
      await new Promise(r => setTimeout(r, 2000));
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body: 'data: Response text\n\ndata: {"text_done":true}\n\ndata: {"cost_usd":0.001}\n\ndata: [DONE]\n\n',
      });
    });
    await runAnalysisFirst(page);

    await page.getByPlaceholder('Ask a question about the analysis...').fill('Question');
    await page.getByRole('button', { name: 'Send' }).click();

    // During streaming, the Send button shows a spinner (not the text "Send")
    // and the input should be disabled
    await expect(page.getByPlaceholder('Ask a question about the analysis...')).toBeDisabled({ timeout: 2_000 });
  });

  test('send button is disabled when input is empty', async ({ page }) => {
    await runAnalysisFirst(page);

    const sendButton = page.getByRole('button', { name: 'Send' });
    await expect(sendButton).toBeDisabled();
  });
});
