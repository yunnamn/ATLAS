import { defineConfig } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

process.env.PLAYWRIGHT_BROWSERS_PATH ??= '/tmp/atlas-playwright'
const database = join(mkdtempSync(join(tmpdir(), 'atlas-e2e-')), 'test.db')
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    launchOptions: {
      executablePath:
        process.env.CHROMIUM_EXECUTABLE_PATH ??
        (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined),
    },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command:
        'cd ../backend && .venv/bin/alembic upgrade head && .venv/bin/python -m atlas.seed && .venv/bin/uvicorn atlas.main:app --host 127.0.0.1 --port 8001',
      env: { ATLAS_DATABASE_URL: `sqlite:///${database}` },
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'npm run dev -- --port 5174 --strictPort',
      env: { ATLAS_API_PROXY: 'http://127.0.0.1:8001' },
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
