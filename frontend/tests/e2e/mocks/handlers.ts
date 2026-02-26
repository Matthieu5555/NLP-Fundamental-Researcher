/**
 * Mock handlers for E2E tests.
 *
 * Uses Playwright's page.route() to intercept fetch requests at the network level.
 * This works for all requests including SSE streams (the app uses fetch + ReadableStream,
 * not EventSource, so page.route intercepts everything).
 */

import { Page, Route } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function loadFixture(name: string) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', name), 'utf-8'));
}

const analysisSections = loadFixture('analysis-sections.json');
const valuationData = loadFixture('valuation-data.json');
const sessionsList = loadFixture('sessions-list.json');
const watchlistData = loadFixture('watchlist.json');
const usageStats = loadFixture('usage-stats.json');
const settingsData = loadFixture('settings.json');

const API = 'http://localhost:5001';

/** Format an SSE event line */
function sseEvent(data: string): string {
  return `data: ${data}\n\n`;
}

/** Build an SSE body from a sequence of events with delays baked in */
function buildSSEBody(events: string[]): string {
  return events.map(e => sseEvent(e)).join('');
}

/**
 * Mock the analysis run SSE stream.
 * Emits progress events then completes with cost info.
 */
export async function mockAnalysisRun(page: Page) {
  await page.route(`${API}/api/analysis/*/run`, async (route: Route) => {
    const events = [
      JSON.stringify({ status: 'running', message: 'Starting multi-agent analysis...', step: 1, total: 6 }),
      JSON.stringify({ status: 'running', message: 'Collecting financial data...', step: 2, total: 6 }),
      JSON.stringify({ status: 'running', message: 'Running bull/bear debate...', step: 3, total: 6 }),
      JSON.stringify({ status: 'running', message: 'Analyzing competitive moat...', step: 4, total: 6 }),
      JSON.stringify({ status: 'running', message: 'Building valuation models...', step: 5, total: 6 }),
      JSON.stringify({ status: 'complete', message: 'Analysis complete', step: 6, total: 6, cost_usd: 0.0842, cost_breakdown: { 'Research Agents': 0.0312, 'Debate Agent': 0.0215, 'Valuation Agent': 0.0180, 'Report Writer': 0.0135 } }),
      '[DONE]',
    ];

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
      body: buildSSEBody(events),
    });
  });
}

/**
 * Mock the chat stream SSE endpoint.
 * Emits text chunks then metadata events.
 */
export async function mockChatStream(page: Page, opts?: { withBeliefs?: boolean }) {
  await page.route(`${API}/api/chat/stream*`, async (route: Route) => {
    const textChunks = [
      'Apple\'s ',
      'return on equity ',
      'stands at an ',
      'exceptional **171.9%**, ',
      'driven by ',
      'massive share ',
      'buybacks that have ',
      'reduced the equity base ',
      'significantly.',
    ];

    const events: string[] = [
      JSON.stringify({ status: 'George is thinking...' }),
    ];

    // Text chunks (non-JSON data lines)
    for (const chunk of textChunks) {
      events.push(chunk);
    }

    events.push(JSON.stringify({ text_done: true }));

    events.push(JSON.stringify({
      sources: [
        { title: 'Apple 10-K FY2024', url: 'https://sec.gov/aapl', date: '2024-10-25' },
      ],
    }));

    if (opts?.withBeliefs) {
      events.push(JSON.stringify({
        new_beliefs: [
          {
            content: 'Apple has exceptional return on equity at 171.9%',
            type: 'confirmed_fact',
            badge: 'FACT',
            badge_color: '#059669',
            section: 'fundamentals',
            confidence: 0.95,
          },
        ],
      }));
    }

    events.push(JSON.stringify({ cost_usd: 0.0023 }));
    events.push('[DONE]');

    // Build body: JSON events use sseEvent, raw text chunks also use sseEvent
    const body = events.map(e => sseEvent(e)).join('');

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body,
    });
  });
}

/** Mock the analysis start endpoint */
export async function mockAnalysisStart(page: Page) {
  await page.route(`${API}/api/analysis/start`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'mock-session-' + Date.now(),
        ticker: 'AAPL',
        status: 'queued',
      }),
    });
  });
}

/** Mock the report sections endpoint */
export async function mockReportSections(page: Page) {
  await page.route(`${API}/api/reports/*/sections`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(analysisSections),
    });
  });
}

/** Mock valuation data endpoint */
export async function mockValuationData(page: Page) {
  await page.route(`${API}/api/reports/*/valuation-data`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(valuationData),
    });
  });
}

/** Mock company info endpoint */
export async function mockCompanyInfo(page: Page) {
  await page.route(`${API}/api/analysis/*/company-info`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_us: true, ticker: 'AAPL', company_name: 'Apple Inc.' }),
    });
  });
}

/** Mock financial statements endpoint */
export async function mockFinancialStatements(page: Page) {
  await page.route(`${API}/api/analysis/*/financial-statements`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ is_available: true, income_statements: [], balance_sheets: [], cash_flows: [], ratios: [], highlights: [] }),
    });
  });
}

/** Mock PDF export — returns a valid PDF large enough to pass the app's size check (>1000 bytes) */
export async function mockPdfExport(page: Page) {
  await page.route(`${API}/api/reports/*/export/pdf`, async (route: Route) => {
    // Build a PDF with padding to exceed the app's 1000-byte minimum check
    const pdfHeader = '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n' +
      '2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n' +
      '3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>>>endobj\n' +
      '4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n' +
      '5 0 obj<</Length 900>>stream\n' +
      'BT /F1 12 Tf 100 700 Td (AAPL Analysis Report) Tj ET\n' +
      ' '.repeat(850) + '\n' +
      'endstream\nendobj\n' +
      'xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000236 00000 n \n0000000306 00000 n \n' +
      'trailer<</Size 6/Root 1 0 R>>\nstartxref\n1280\n%%EOF';

    const pdfContent = Buffer.from(pdfHeader);

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="AAPL_analysis.pdf"',
      },
      body: pdfContent,
    });
  });
}

/** Mock sessions list endpoint */
export async function mockSessionsList(page: Page) {
  await page.route(`${API}/api/sessions/`, async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessionsList),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock session resume endpoint */
export async function mockSessionResume(page: Page) {
  await page.route(`${API}/api/sessions/*/resume`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'test-session-aapl-001',
        ticker: 'AAPL',
        sections: analysisSections.sections,
      }),
    });
  });
}

/** Mock session delete endpoint */
export async function mockSessionDelete(page: Page) {
  await page.route(`${API}/api/sessions/*`, async (route: Route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    } else {
      // Use fallback() to pass to the next matching route handler (e.g. sessions list)
      // instead of continue() which would send to the real server
      await route.fallback();
    }
  });
}

/** Mock session beliefs endpoint */
export async function mockSessionBeliefs(page: Page) {
  await page.route(`${API}/api/sessions/*/beliefs`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ beliefs: [] }),
    });
  });
}

/** Mock watchlist endpoints */
export async function mockWatchlist(page: Page) {
  await page.route(`${API}/api/watchlist`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(watchlistData),
    });
  });

  await page.route(`${API}/api/watchlist/*`, async (route: Route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    } else if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock settings endpoints */
export async function mockSettings(page: Page) {
  let currentSettings = { ...settingsData };

  await page.route(`${API}/api/settings/`, async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(currentSettings),
      });
    } else if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON();
      currentSettings = { ...currentSettings, ...body };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(currentSettings),
      });
    } else {
      await route.continue();
    }
  });

  await page.route(`${API}/api/settings/reset`, async (route: Route) => {
    currentSettings = { ...settingsData };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(currentSettings),
    });
  });
}

/** Mock usage stats endpoints */
export async function mockUsageStats(page: Page) {
  await page.route(`${API}/api/usage/stats`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(usageStats),
    });
  });

  await page.route(`${API}/api/usage/daily*`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        daily: [
          { date: '2025-01-15', requests: 12, cost_usd: 1.25 },
          { date: '2025-01-14', requests: 8, cost_usd: 0.85 },
          { date: '2025-01-13', requests: 15, cost_usd: 1.10 },
        ],
      }),
    });
  });
}

/** Mock the auth/me endpoint for authenticated state */
export async function mockAuthMe(page: Page) {
  await page.route(`${API}/api/auth/me`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'test-user-id',
        email: 'e2e-test@george-research.dev',
        display_name: 'E2E Test User',
        created_at: '2025-01-01T00:00:00Z',
      }),
    });
  });
}

/** Mock chat history */
export async function mockChatHistory(page: Page) {
  await page.route(`${API}/api/chat/*/history`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ messages: [] }),
    });
  });
}

/**
 * Set up all common mocks for a fully mocked analysis flow.
 * Call this at the start of tests that need the full analysis UI.
 */
export async function mockFullAnalysisFlow(page: Page) {
  await mockAnalysisStart(page);
  await mockAnalysisRun(page);
  await mockReportSections(page);
  await mockValuationData(page);
  await mockCompanyInfo(page);
  await mockFinancialStatements(page);
  await mockSettings(page);
  await mockSessionBeliefs(page);
}
