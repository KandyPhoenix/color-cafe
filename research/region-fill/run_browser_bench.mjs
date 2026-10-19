// Runs browser_bench.html in headless Chromium (Playwright) and prints the JSON results.
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const root = '/home/user/color-cafe';
const srv = http.createServer((req,res)=>{ const p = path.join(root, decodeURIComponent(req.url.split('?')[0])); if(!fs.existsSync(p)){res.statusCode=404;return res.end();} res.setHeader('content-type', p.endsWith('.html')?'text/html':'image/png'); fs.createReadStream(p).pipe(res); }).listen(0);
const port = srv.address().port;
const page = process.argv[2] || 'garden-gate.png';
const throttle = process.argv[3] ? Number(process.argv[3]) : 1; // CPU throttle factor (4 ~ mid-range phone)
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] });
const ctx = await browser.newContext(); const pg = await ctx.newPage();
const cdp = await ctx.newCDPSession(pg); await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
await pg.goto(`http://127.0.0.1:${port}/research/region-fill/browser_bench.html`);
const results = await pg.evaluate((src) => window.runBench(src), `/pages/${page}`);
console.log(JSON.stringify({ page, cpuThrottle: throttle, results }, null, 1));
await browser.close(); srv.close();
