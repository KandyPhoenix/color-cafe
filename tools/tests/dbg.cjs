const {chromium}=require('/opt/node-tools/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});const pg=await b.newPage({viewport:{width:390,height:780}});const errs=[];pg.on('pageerror',e=>errs.push(e.message));
await pg.goto('http://127.0.0.1:8769/');await pg.waitForTimeout(600);await pg.evaluate(()=>localStorage.clear());await pg.reload();await pg.waitForTimeout(600);
await pg.click('.card[data-slug="water-bearer"]');await pg.waitForTimeout(2500);
const r=await pg.evaluate(()=>{P.sel=1;P.hiDirty=true;buildHighlight();const ids=P.byColor[1].slice(0,3);for(const id of ids)paintRegion(id,'r');
 const cnt=(c)=>{const d=c.getContext('2d').getImageData(0,0,P.w,P.h).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>0)n++;return n};
 return {hi:cnt(P.hiC),fill:cnt(P.fillC),byColor1:P.byColor[1].length,area1:P.byColor[1].reduce((a,id)=>a+P.meta.regions[id-1].a,0),filledArea:ids.reduce((a,id)=>a+P.meta.regions[id-1].a,0),off:[P.off[ids[0]],P.off[ids[0]+1]]}});
console.log(JSON.stringify({r,errs}));await b.close()})();
