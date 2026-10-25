const {chromium}=require('/opt/node-tools/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});const errs=[];
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true});const pg=await ctx.newPage();pg.on('pageerror',e=>errs.push(e.message));
await pg.goto('http://127.0.0.1:8769/');await pg.waitForTimeout(600);await pg.evaluate(()=>localStorage.clear());await pg.reload();await pg.waitForTimeout(600);
await pg.click('.card[data-slug="water-bearer"]');await pg.waitForTimeout(2500);
// select colour 2 and zoom in on an item of it, fill 3 items
await pg.evaluate(()=>{P.sel=1;P.hiDirty=true;renderPal();const ids=P.byColor[1].slice(0,3);for(const id of ids)paintRegion(id,'r');const r=P.meta.regions[P.byColor[1][3]-1];cam.z=fitZ()*2.2;cam.x=r.x-cv.clientWidth/2/cam.z;cam.y=r.y-cv.clientHeight/2/cam.z;draw()});
await pg.waitForTimeout(400);await pg.screenshot({path:'hatch.png'});console.log(JSON.stringify(errs));await b.close()})();
