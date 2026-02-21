import { defineConfig, devices } from '@playwright/test';

const BACKEND_PORT = 5001;
const FRONTEND_PORT = 5173;

export default defineConfig({
  testDir: './tests/e2e/specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }], ['list']],
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },

  projects: [
    // Setup project: login and save auth state
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
      testDir: './tests/e2e',
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/e2e/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],

  globalSetup: './tests/e2e/global-setup.ts',
  globalTeardown: './tests/e2e/global-teardown.ts',

  webServer: [
    {
      command: 'cd .. && python -m backend.main',
      port: BACKEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      port: FRONTEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
  ],
});
