import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const root='/home/user/color-cafe';
const srv=http.createServer((req,res)=>{const p=path.join(root,decodeURIComponent(req.url.split('?')[0]));if(!fs.existsSync(p)){res.statusCode=404;return res.end();}res.setHeader('content-type',p.endsWith('.html')?'text/html':'image/png');fs.createReadStream(p).pipe(res);}).listen(0);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,args:['--no-sandbox']});
const ctx=await browser.newContext(); const pg=await ctx.newPage(); const cdp=await ctx.newCDPSession(pg);
await pg.goto(`http://127.0.0.1:${srv.address().port}/research/region-fill/browser_bench.html`);
for (const thr of [1,4]){ await cdp.send('Emulation.setCPUThrottlingRate',{rate:thr});
  for (const page of fs.readdirSync(root+'/pages').filter(f=>f.endsWith('.png'))){
    for (const [tc,th] of [[200,64],[230,64]]){
      const r=await pg.evaluate(([s,a,b])=>window.runPipeline(s,a,b),[`/pages/${page}`,tc,th]);
      console.log(`throttle x${thr} ${page.padEnd(24)} core>=${tc} halo>=${th}: regions=${r.regions} decode=${r.decodeMs}ms label=${r.labelMs}ms grow=${r.growMs}ms(${r.grownPx}px) bbox=${r.bboxMs}ms TOTAL=${r.totalLoadMs}ms | fill largest ${r.fillLargestPx}px+put=${r.fillLargestAndPutMs}ms`);
    } } }
await browser.close(); srv.close();
