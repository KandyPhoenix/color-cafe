const {chromium}=require('/opt/node-tools/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});const pg=await b.newPage({viewport:{width:390,height:780}});const errs=[];pg.on('pageerror',e=>errs.push(e.message));
await pg.goto('http://127.0.0.1:8769/');await pg.waitForTimeout(600);await pg.evaluate(()=>localStorage.clear());await pg.reload();await pg.waitForTimeout(600);
await pg.click('.card[data-slug="water-bearer"]');await pg.waitForTimeout(2500);
const r=await pg.evaluate(()=>{let s=0;for(let i=0;i<P.colData.length;i+=4000)s+=P.colData[i];const id=P.byColor[1][0];paintRegion(id,'r');const j=P.idx[P.off[id]]*4;return {colSum:s,px:[P.colData[j],P.colData[j+1],P.colData[j+2]],fillpx:[P.fill.data[j],P.fill.data[j+1],P.fill.data[j+2],P.fill.data[j+3]],savedVal:P.save.f[id]}});
console.log(JSON.stringify({r,errs}));await b.close()})();
