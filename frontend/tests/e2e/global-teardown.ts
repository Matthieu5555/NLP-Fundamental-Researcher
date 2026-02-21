import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function globalTeardown(config: FullConfig) {
  // Clean up auth state file
  const authFile = path.join(__dirname, '.auth/user.json');
  if (fs.existsSync(authFile)) {
    fs.unlinkSync(authFile);
  }

  // Remove test user email from authorized_users.csv
  const csvPath = path.resolve(__dirname, '../../../data/authorized_users.csv');
  if (fs.existsSync(csvPath)) {
    const lines = fs.readFileSync(csvPath, 'utf-8').split('\n');
    const filtered = lines.filter(line => line.trim() !== 'e2e-test@constant.dev');
    fs.writeFileSync(csvPath, filtered.join('\n'));
  }

  console.log('[global-teardown] Cleaned up test data');
}

export default globalTeardown;
