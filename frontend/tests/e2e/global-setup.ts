import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API_URL = 'http://localhost:5001';
const TEST_EMAIL = 'e2e-test@george-research.dev';
const TEST_PASSWORD = 'TestPassword123!';
const TEST_DISPLAY_NAME = 'E2E Test User';

async function globalSetup(config: FullConfig) {
  // Ensure auth state directory exists
  const authDir = path.join(__dirname, '.auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  // Add test user to authorized_users.csv if not present
  const csvPath = path.resolve(__dirname, '../../../data/authorized_users.csv');
  if (fs.existsSync(csvPath)) {
    const csv = fs.readFileSync(csvPath, 'utf-8');
    if (!csv.includes(TEST_EMAIL)) {
      fs.appendFileSync(csvPath, `\n${TEST_EMAIL}\n`);
    }
  }

  // Wait for backend to be ready
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`${API_URL}/health`);
      if (res.ok) break;
    } catch {
      // not ready yet
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  // Register test user (ignore error if already exists)
  try {
    const res = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: TEST_EMAIL,
        password: TEST_PASSWORD,
        display_name: TEST_DISPLAY_NAME,
      }),
    });
    if (res.ok) {
      console.log('[global-setup] Test user registered');
    } else {
      const body = await res.json().catch(() => ({}));
      console.log('[global-setup] Registration response:', res.status, body.detail || '');
    }
  } catch (err) {
    console.error('[global-setup] Registration failed:', err);
  }
}

export default globalSetup;
