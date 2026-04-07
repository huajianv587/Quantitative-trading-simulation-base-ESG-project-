import {
  copyFileSync,
  existsSync,
  mkdirSync,
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
  `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=/app/">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Redirecting...</title>
</head>
<body>
  <script>window.location.replace('/app/');</script>
</body>
</html>
`,
  'utf8',
);

writeFileSync(
  join(distDir, '_redirects'),
  '/ /app/ 302\n',
  'utf8',
);

if (!existsSync(join(distAppDir, 'app-config.js'))) {
  throw new Error('Failed to generate dist/app/app-config.js');
}

console.log(`Static frontend bundle generated in ${distDir}`);
console.log(`ESG_API_BASE_URL=${apiBaseUrl || '(same-origin)'}`);

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
