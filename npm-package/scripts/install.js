#!/usr/bin/env node
// Post-install: download the SkyVEx Windows binary from the matching GitHub Release.
// Keeps the npm package tiny; the ~40 MB exe is fetched on demand.
// Honors HTTPS_PROXY / HTTP_PROXY (via CONNECT tunnel) so it works behind Clash etc.,
// which matters for GitHub Release downloads inside mainland China.

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const pkg = require('../package.json');
const TAG = 'v' + pkg.version;
const ASSET = 'SkyVEx.exe';
const URL_ = `https://github.com/lingyunalingyun/SkyVEx/releases/download/${TAG}/${ASSET}`;

const destDir = path.join(__dirname, '..', 'bin');
const dest = path.join(destDir, ASSET);

if (process.platform !== 'win32') {
  console.error('SkyVEx is Windows-only; skipping binary download.');
  process.exit(0);
}

function proxyUrl() {
  return (
    process.env.HTTPS_PROXY || process.env.https_proxy ||
    process.env.HTTP_PROXY || process.env.http_proxy || ''
  );
}

// Open a single GET request, tunneling through the proxy if one is configured.
function get(targetUrl) {
  const target = new URL(targetUrl);
  const headers = { 'User-Agent': 'skyvex-npm-installer' };
  const proxy = proxyUrl();

  return new Promise((resolve, reject) => {
    if (!proxy) {
      https.get(targetUrl, { headers }, resolve).on('error', reject);
      return;
    }
    const p = new URL(proxy);
    const connect = http.request({
      host: p.hostname,
      port: p.port || 80,
      method: 'CONNECT',
      path: `${target.hostname}:${target.port || 443}`,
    });
    connect.on('connect', (res, socket) => {
      if (res.statusCode !== 200) {
        return reject(new Error(`Proxy CONNECT failed: HTTP ${res.statusCode}`));
      }
      https
        .get(
          {
            host: target.hostname,
            port: target.port || 443,
            path: target.pathname + target.search,
            socket,
            agent: false,
            headers,
          },
          resolve
        )
        .on('error', reject);
    });
    connect.on('error', reject);
    connect.end();
  });
}

async function download(url, file, redirects = 0) {
  if (redirects > 10) throw new Error('Too many redirects');
  const res = await get(url);

  if ([301, 302, 303, 307, 308].includes(res.statusCode)) {
    res.resume();
    return download(res.headers.location, file, redirects + 1);
  }
  if (res.statusCode !== 200) {
    res.resume();
    throw new Error(`Download failed: HTTP ${res.statusCode} for ${url}`);
  }

  const total = parseInt(res.headers['content-length'] || '0', 10);
  let received = 0;
  let lastPct = -1;
  await new Promise((resolve, reject) => {
    const out = fs.createWriteStream(file);
    res.on('data', (chunk) => {
      received += chunk.length;
      if (total) {
        const pct = Math.floor((received / total) * 100);
        if (pct !== lastPct && pct % 10 === 0) {
          process.stdout.write(`  downloading SkyVEx.exe ${pct}%\r`);
          lastPct = pct;
        }
      }
    });
    res.pipe(out);
    out.on('finish', () => out.close(resolve));
    out.on('error', reject);
    res.on('error', reject);
  });
}

(async () => {
  try {
    fs.mkdirSync(destDir, { recursive: true });
    console.log(`Fetching SkyVEx ${TAG} binary...`);
    await download(URL_, dest);
    console.log('\nSkyVEx installed. Run:  skyvex');
  } catch (err) {
    console.error('\nFailed to download SkyVEx binary:', err.message);
    console.error(`You can download it manually from:\n  ${URL_}`);
    process.exit(1);
  }
})();
