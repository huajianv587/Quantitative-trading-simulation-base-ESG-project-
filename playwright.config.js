const fs = require('fs');
const path = require('path');
const { defineConfig } = require('@playwright/test');

function hashWorkspacePortSeed(input) {
  let hash = 0;
  for (const char of String(input || '')) {
    hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
  }
  return hash;
}

const defaultPort = 39123 + (hashWorkspacePortSeed(__dirname) % 1000);
const port = Number(process.env.E2E_PORT || defaultPort);
const reuseExistingServer = String(process.env.E2E_REUSE_SERVER || '').toLowerCase() === 'true';
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
    reuseExistingServer,
    timeout: 240000,
    env: {
      ...process.env,
      E2E_PORT: String(port),
    },
  },
});
