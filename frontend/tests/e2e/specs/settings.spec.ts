import { test, expect } from '@playwright/test';
import { mockSettings } from '../mocks/handlers';

test.describe('Settings', () => {
  test.beforeEach(async ({ page }) => {
    await mockSettings(page);
  });

  test('settings modal opens', async ({ page }) => {
    await page.goto('/');

    // Click settings button (gear icon)
    await page.getByTitle('Settings').click();

    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  });

  test('settings modal shows all sections', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Check key sections
    await expect(page.getByText('Master System Prompt')).toBeVisible();
    await expect(page.getByText('LLM Configuration')).toBeVisible();
    await expect(page.getByText('UI Preferences')).toBeVisible();
    await expect(page.getByText('Analysis Preferences')).toBeVisible();
  });

  test('change theme setting', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Click Dark theme button
    await page.getByRole('button', { name: 'Dark' }).click();

    // Save button should be enabled (has changes)
    await expect(page.getByRole('button', { name: 'Save Settings' })).toBeEnabled();

    // Save
    await page.getByRole('button', { name: 'Save Settings' }).click();

    // Success message
    await expect(page.getByText('Settings saved successfully')).toBeVisible();
  });

  test('change LLM model', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Change model via select
    const modelSelect = page.locator('select').first();
    await modelSelect.selectOption('anthropic/claude-opus-4.6');

    // Save
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await expect(page.getByText('Settings saved successfully')).toBeVisible();
  });

  test('reset to defaults', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Accept the confirm dialog
    page.on('dialog', dialog => dialog.accept());

    // Click Reset to Defaults
    await page.getByRole('button', { name: 'Reset to Defaults' }).click();

    await expect(page.getByText('Settings reset to defaults')).toBeVisible();
  });

  test('cancel closes modal without saving', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Click Cancel
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Modal should close
    await expect(page.getByRole('heading', { name: 'Settings' })).not.toBeVisible();
  });

  test('save button disabled when no changes', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Save button should be disabled initially (no changes)
    await expect(page.getByRole('button', { name: 'Save Settings' })).toBeDisabled();
  });

  test('temperature slider updates', async ({ page }) => {
    await page.goto('/');
    await page.getByTitle('Settings').click();

    // Verify temperature label shows current value
    await expect(page.getByText('Temperature: 0.7')).toBeVisible();
  });
});
