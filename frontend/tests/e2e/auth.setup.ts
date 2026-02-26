import { test as setup, expect } from '@playwright/test';

const TEST_EMAIL = 'e2e-test@george-research.dev';
const TEST_PASSWORD = 'TestPassword123!';

setup('authenticate', async ({ page }) => {
  await page.goto('/');

  // Click "Sign In" button to open auth modal
  await page.getByRole('button', { name: 'Sign In' }).click();

  // Fill login form
  await page.getByLabel('Email').fill(TEST_EMAIL);
  await page.getByLabel('Password').fill(TEST_PASSWORD);

  // Submit (use form-scoped locator to avoid matching the header Sign In button)
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click();

  // Wait for auth modal to close and authenticated UI to appear
  await expect(page.getByText('Analyze a Stock')).toBeVisible({ timeout: 10_000 });

  // Save auth state (localStorage tokens + cookies)
  await page.context().storageState({ path: 'tests/e2e/.auth/user.json' });
});
