const {chromium}=require('/opt/node-tools/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});const errs=[];const out={};
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true});
const pg=await ctx.newPage();pg.on('pageerror',e=>errs.push(e.message));pg.on('console',m=>{if(m.type()==='error')errs.push('console:'+m.text())});
await pg.goto('http://127.0.0.1:8769/');await pg.waitForTimeout(800);
out.cards=await pg.$$eval('#grid .card',a=>a.length);
await pg.screenshot({path:'g.png'});
await pg.click('.card[data-slug="water-bearer"]');await pg.waitForTimeout(2500);
out.loaded=await pg.evaluate(()=>({mode:P.page.mode,regions:P.meta.regions.length,sel:P.sel,pal:document.querySelectorAll('#pal .sw').length}));
// tap a region of the selected colour
const t=await pg.evaluate(()=>{const id=P.byColor[P.sel].find(id=>!P.filled[id]);const r=P.meta.regions[id-1];const rc=cv.getBoundingClientRect();return {id,x:rc.left+(r.x-cam.x)*cam.z,y:rc.top+(r.y-cam.y)*cam.z}});
await pg.touchscreen.tap(t.x,t.y);await pg.waitForTimeout(300);
out.afterTap=await pg.evaluate((id)=>({filled:!!P.filled[id],n:P.save.n,saved:JSON.parse(localStorage.getItem('cc-save-water-bearer')).n}),t.id);
// wrong colour tap
const w=await pg.evaluate(()=>{const id=P.meta.regions.find(r=>r.c!==P.sel&&!P.filled[r.id]).id;const r=P.meta.regions[id-1];const rc=cv.getBoundingClientRect();return {id,x:rc.left+(r.x-cam.x)*cam.z,y:rc.top+(r.y-cam.y)*cam.z}});
await pg.touchscreen.tap(w.x,w.y);await pg.waitForTimeout(200);
out.wrongTap=await pg.evaluate((id)=>({filled:!!P.filled[id],toast:document.getElementById('toast').textContent}),w.id);
await pg.screenshot({path:'p1.png'});
// go back and check studio
await pg.click('#back');await pg.waitForTimeout(300);await pg.click('.tab[data-t="studio"]');await pg.waitForTimeout(300);
out.studio=await pg.$$eval('#grid .card',a=>a.map(x=>x.dataset.slug));
// mandala free colour
await pg.click('.tab[data-t="mandalas"]');await pg.click('.card[data-slug="ocean-mandala"]');await pg.waitForTimeout(2000);
const m=await pg.evaluate(()=>{const r=P.meta.regions[Math.floor(P.meta.regions.length/2)];const rc=cv.getBoundingClientRect();return {id:r.id,x:rc.left+(r.x-cam.x)*cam.z,y:rc.top+(r.y-cam.y)*cam.z,sel:P.sel}});
await pg.touchscreen.tap(m.x,m.y);await pg.waitForTimeout(300);
out.mandala=await pg.evaluate((id)=>({filled:!!P.filled[id],val:P.save.f[id],n:P.save.n}),m.id);
await pg.screenshot({path:'p2.png'});
console.log(JSON.stringify({out,errs}));await b.close()})();
