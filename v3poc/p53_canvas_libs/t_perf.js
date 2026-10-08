const { chromium } = require('/opt/node-tools/node_modules/playwright'); const path=require('path'),fs=require('fs');
(async()=>{const b=await chromium.launch();const res=[];
for(const n of [200,2000,4000]) for(const cache of [true,false]){
  const p=await b.newPage();await p.goto('file://'+path.join(__dirname,'perf.html'));
  await p.evaluate(()=>document.fonts.load('20px IPAGothic'));
  res.push(await p.evaluate(([n,c])=>window.runPerf(n,c),[n,cache])); await p.close();}
console.log(res.map(r=>JSON.stringify(r)).join('\n'));fs.writeFileSync('out/perf.json',JSON.stringify(res,null,1));await b.close();})();
