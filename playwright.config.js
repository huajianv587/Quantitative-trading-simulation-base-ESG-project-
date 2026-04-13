const fs = require('fs');
const path = require('path');
const { defineConfig } = require('@playwright/test');

const port = Number(process.env.E2E_PORT || 39123);
const venvPython = process.platform === 'win32'
  ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
  : path.join(__dirname, '.venv', 'bin', 'python');
const pythonCommand = fs.existsSync(venvPython) ? `"${venvPython}"` : 'python';

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 120000,
  expect: {
    timeout: 15000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: `${pythonCommand} scripts/run_e2e_server.py`,
    url: `http://127.0.0.1:${port}/health`,
    reuseExistingServer: true,
    timeout: 240000,
    env: {
      ...process.env,
      E2E_PORT: String(port),
    },
  },
});
