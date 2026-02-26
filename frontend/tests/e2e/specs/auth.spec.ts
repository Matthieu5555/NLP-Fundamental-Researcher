import { test, expect } from '@playwright/test';

const API = 'http://localhost:5001';

// Auth tests run WITHOUT the shared storageState — they test the login flow itself.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe('Authentication', () => {
  test('shows welcome page for unauthenticated user', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Welcome to George')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Get Started' })).toBeVisible();
    await expect(page.getByRole('banner').getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('opens auth modal on Sign In click', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
  });

  test('switches between login and register forms', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();

    // Should show login form
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();

    // Switch to register
    await page.getByRole('button', { name: 'Create one' }).click();
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible();
    await expect(page.getByLabel('Display Name')).toBeVisible();
    await expect(page.getByLabel('Confirm Password')).toBeVisible();

    // Switch back to login — click the "Sign in" link next to "Already have an account?"
    await page.getByText('Already have an account?').locator('..').getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });

  test('login with valid credentials shows app', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();

    await page.getByLabel('Email').fill('e2e-test@george-research.dev');
    await page.getByLabel('Password').fill('TestPassword123!');
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click();

    // Auth modal should close and main app should appear
    await expect(page.getByText('Analyze a Stock')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('E2E Test User')).toBeVisible();
  });

  test('login with wrong password shows error', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();

    await page.getByLabel('Email').fill('e2e-test@george-research.dev');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click();

    // Should show error message
    await expect(page.locator('.bg-red-50')).toBeVisible({ timeout: 5_000 });
  });

  test('register with non-whitelisted email shows error', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();
    await page.getByRole('button', { name: 'Create one' }).click();

    await page.locator('#registerEmail').fill('nobody@example.com');
    await page.locator('#registerPassword').fill('TestPassword123!');
    await page.getByLabel('Confirm Password').fill('TestPassword123!');
    await page.getByRole('button', { name: 'Create Account' }).click();

    // Should show error about unauthorized email
    await expect(page.locator('.bg-red-50')).toBeVisible({ timeout: 5_000 });
  });

  test('register with mismatched passwords shows client-side error', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();
    await page.getByRole('button', { name: 'Create one' }).click();

    await page.locator('#registerEmail').fill('e2e-test@george-research.dev');
    await page.locator('#registerPassword').fill('TestPassword123!');
    await page.getByLabel('Confirm Password').fill('DifferentPassword!');
    await page.getByRole('button', { name: 'Create Account' }).click();

    await expect(page.getByText('Passwords do not match')).toBeVisible();
  });

  test('logout clears auth state and returns to welcome', async ({ page }) => {
    // First, login
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();
    await page.getByLabel('Email').fill('e2e-test@george-research.dev');
    await page.getByLabel('Password').fill('TestPassword123!');
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByText('Analyze a Stock')).toBeVisible({ timeout: 10_000 });

    // Now logout
    await page.getByRole('button', { name: 'Sign Out' }).click();

    // Should return to welcome page
    await expect(page.getByText('Welcome to George')).toBeVisible({ timeout: 5_000 });
  });

  test('closing auth modal with Escape key', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('banner').getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();

    await page.keyboard.press('Escape');

    // Modal should close, welcome page still visible
    await expect(page.getByRole('heading', { name: 'Sign In' })).not.toBeVisible();
    await expect(page.getByText('Welcome to George')).toBeVisible();
  });

  test('unauthenticated user clicking Get Started opens auth modal', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Get Started' }).click();
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });
});
