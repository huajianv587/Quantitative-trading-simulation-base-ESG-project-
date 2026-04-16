import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');
const frontendDir = join(projectRoot, 'frontend');
const distDir = join(projectRoot, 'dist');
const distAppDir = join(distDir, 'app');
const landingEntryPath = resolveLandingEntry();

const apiBaseUrl = String(process.env.ESG_API_BASE_URL || '').trim().replace(/\/+$/, '');

rmSync(distDir, { recursive: true, force: true });
mkdirSync(distAppDir, { recursive: true });
copyDirectory(frontendDir, distAppDir);

writeFileSync(
  join(distAppDir, 'app-config.js'),
  `window.__ESG_API_BASE_URL__ = ${JSON.stringify(apiBaseUrl)};\n`,
  'utf8',
);

writeFileSync(
  join(distDir, 'index.html'),
  readText(landingEntryPath),
  'utf8',
);

if (!existsSync(join(distAppDir, 'app-config.js'))) {
  throw new Error('Failed to generate dist/app/app-config.js');
}

console.log(`Static frontend bundle generated in ${distDir}`);
console.log(`ESG_API_BASE_URL=${apiBaseUrl || '(same-origin)'}`);
console.log(`Landing page source=${landingEntryPath}`);

function copyDirectory(sourceDir, targetDir) {
  mkdirSync(targetDir, { recursive: true });

  for (const entry of readdirSync(sourceDir, { withFileTypes: true })) {
    const sourcePath = join(sourceDir, entry.name);
    const targetPath = join(targetDir, entry.name);

    if (entry.isDirectory()) {
      copyDirectory(sourcePath, targetPath);
      continue;
    }

    if (entry.isFile() || statSync(sourcePath).isFile()) {
      copyFileSync(sourcePath, targetPath);
    }
  }
}

function readText(path) {
  return readFileSync(path, 'utf8');
}

function resolveLandingEntry() {
  const candidates = [join(projectRoot, 'esg_quant_landing_v2.html')];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  throw new Error(`Unable to locate landing entry. Checked: ${candidates.join(', ')}`);
}
