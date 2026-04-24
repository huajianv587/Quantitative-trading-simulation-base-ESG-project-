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
const TEXT_AUDIT_PATTERNS = [
  { token: '鈥', reason: 'broken quote/dash mojibake' },
  { token: '鈽', reason: 'broken icon mojibake' },
  { token: '鈹', reason: 'broken comment glyph mojibake' },
  { token: '涓?', reason: 'broken zh label mojibake' },
  { token: '馃', reason: 'broken emoji mojibake' },
  { token: '鈫?', reason: 'broken arrow mojibake' },
  { token: '鈿?', reason: 'broken symbol mojibake' },
  { token: '杩斿洖', reason: 'broken Chinese copy mojibake' },
  { token: '瀵嗙爜', reason: 'broken password copy mojibake' },
  { token: '鐮旂┒', reason: 'broken research copy mojibake' },
];

const rawApiBaseUrl = String(process.env.ESG_API_BASE_URL || '').trim();
const apiBaseUrl = rawApiBaseUrl ? rawApiBaseUrl.replace(/\/+$/, '') : '';

prepareDistBundle();
copyDirectory(frontendDir, distAppDir);

writeFileSync(
  join(distAppDir, 'app-config.js'),
  apiBaseUrl
    ? `window.__ESG_APP_ORIGIN__ = window.__ESG_APP_ORIGIN__ || window.location.origin;\nwindow.__ESG_API_BASE_URL__ = window.__ESG_API_BASE_URL__ || ${JSON.stringify(apiBaseUrl)};\n`
    : `window.__ESG_APP_ORIGIN__ = window.__ESG_APP_ORIGIN__ || window.location.origin;\nwindow.__ESG_API_BASE_URL__ = window.__ESG_API_BASE_URL__ || window.location.origin;\n`,
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

validateAppConfig(join(distAppDir, 'app-config.js'), apiBaseUrl);
auditRuntimeText(frontendDir, 'frontend');
auditRuntimeText(distAppDir, 'dist/app');

console.log(`Static frontend bundle generated in ${distDir}`);
console.log(`ESG_API_BASE_URL=${apiBaseUrl || '(same-origin default)'}`);
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

function prepareDistBundle() {
  mkdirSync(distDir, { recursive: true });
  resetDirectoryContents(distAppDir);
  removeIfExists(join(distDir, 'index.html'));
}

function resetDirectoryContents(targetDir) {
  mkdirSync(targetDir, { recursive: true });
  for (const entry of readdirSync(targetDir, { withFileTypes: true })) {
    removeIfExists(join(targetDir, entry.name));
  }
}

function removeIfExists(targetPath) {
  if (!existsSync(targetPath)) return;
  try {
    rmSync(targetPath, { recursive: true, force: true, maxRetries: 3, retryDelay: 120 });
  } catch (error) {
    if (error?.code !== 'EPERM') {
      throw error;
    }
    console.warn(`build_static_frontend: unable to fully remove ${targetPath}; continuing with overwrite mode`);
  }
}

function readText(path) {
  return readFileSync(path, 'utf8');
}

function validateAppConfig(path, expectedBaseUrl) {
  const content = readText(path);
  if (expectedBaseUrl) {
    if (!content.includes(expectedBaseUrl)) {
      throw new Error(`Invalid dist app config at ${path}. Expected API base ${expectedBaseUrl}, got: ${content.trim()}`);
    }
    return;
  }
  if (!content.includes('window.location.origin')) {
    throw new Error(`Invalid dist app config at ${path}. Expected same-origin fallback, got: ${content.trim()}`);
  }
}

function auditRuntimeText(rootDir, label) {
  const failures = [];
  walkFiles(rootDir, (path) => {
    const ext = path.split('.').pop()?.toLowerCase();
    if (!['js', 'mjs', 'css', 'html'].includes(ext || '')) return;
    const raw = readText(path);
    const normalized = stripComments(raw, ext);
    for (const pattern of TEXT_AUDIT_PATTERNS) {
      if (normalized.includes(pattern.token)) {
        failures.push(`${label}: ${path} -> ${pattern.reason} (${pattern.token})`);
        break;
      }
    }
  });
  if (failures.length) {
    throw new Error(`Static bundle text audit failed:\n${failures.join('\n')}`);
  }
}

function walkFiles(dir, visit) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const nextPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(nextPath, visit);
      continue;
    }
    if (entry.isFile()) visit(nextPath);
  }
}

function stripComments(text, ext) {
  if (ext === 'css') return text.replace(/\/\*[\s\S]*?\*\//g, '');
  if (ext === 'html') return text.replace(/<!--[\s\S]*?-->/g, '');
  if (ext === 'js' || ext === 'mjs') {
    return text
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '');
  }
  return text;
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
