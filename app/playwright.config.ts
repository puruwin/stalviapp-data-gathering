import { defineConfig } from '@playwright/test';

const baseURL = process.env.E2E_WEB_URL ?? 'http://localhost:8082';
const proxy = process.env.E2E_PROXY_SERVER
  ? { server: process.env.E2E_PROXY_SERVER, bypass: 'localhost,127.0.0.1,[::1]' }
  : undefined;

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    proxy,
  },
  projects: ['chromium', 'firefox', 'webkit'].flatMap((browserName) =>
    ['desktop', 'mobile'].map((size) => ({
      name: `${size}-${browserName}`,
      use: {
        browserName: browserName as 'chromium' | 'firefox' | 'webkit',
        viewport: size === 'desktop' ? { width: 1280, height: 900 } : { width: 390, height: 844 },
        hasTouch: size === 'mobile',
        // Firefox no admite el modo isMobile; sí el viewport estrecho y los eventos táctiles.
        isMobile: size === 'mobile' && browserName !== 'firefox',
        launchOptions: browserName === 'chromium' && process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
          ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
          : {},
      },
    }))),
  webServer: process.env.E2E_WEB_URL ? undefined : {
    command: 'npm run web -- --host localhost --port 8082 --max-workers 2',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      CI: '1', EXPO_OFFLINE: '1', EXPO_NO_TELEMETRY: '1',
      EXPO_PUBLIC_API_URL: process.env.E2E_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
});
