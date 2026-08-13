#!/usr/bin/env node
// Launcher: start the downloaded SkyVEx GUI and return the terminal immediately.

const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const exe = path.join(__dirname, 'SkyVEx.exe');

if (process.platform !== 'win32') {
  console.error('SkyVEx runs on Windows only.');
  process.exit(1);
}
if (!fs.existsSync(exe)) {
  console.error('SkyVEx.exe not found. Try reinstalling:  npm install -g skyvex');
  process.exit(1);
}

const child = spawn(exe, process.argv.slice(2), {
  detached: true,
  stdio: 'ignore',
});
child.on('error', (err) => {
  console.error('Failed to launch SkyVEx:', err.message);
  process.exit(1);
});
child.unref();
