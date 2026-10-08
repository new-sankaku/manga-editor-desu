const { chromium } = require('/opt/node-tools/node_modules/playwright');
const { PNG } = require('pngjs'); const path=require('path'), fs=require('fs');
function stats(buf){ const p=PNG.sync.read(buf); let n=0,sx=0,sy=0,x0=1e9,y0=1e9,x1=-1,y1=-1;
  for(let y=0;y<p.height;y++)for(let x=0;x<p.width;x++){const i=(y*p.width+x)*4; if(p.data[i]<140&&p.data[i+3]>0){n++;sx+=x;sy+=y;x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}}
  return n? {n, cx:+(sx/n/p.width).toFixed(2), cy:+(sy/n/p.height).toFixed(2), w:+((x1-x0+1)/p.width).toFixed(2), h:+((y1-y0+1)/p.height).toFixed(2)}:{n:0}; }
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:900,height:700}});
await p.goto('file://'+path.join(__dirname,'vertical.html'));
const chars=[...'あ「」ー、。！？…A1'];
// 単独セル：DOM縦書き / Fabric素朴 / Fabric補正
const out={};
for(const ch of chars){
  await p.evaluate(ch=>{document.getElementById('cells').innerHTML='<div id="d" class="cell dom">'+ch+'</div><canvas id="f1" width="60" height="60"></canvas><canvas id="f2" width="60" height="60"></canvas>';
    const a=new fabric.StaticCanvas('f1',{backgroundColor:'#fff'}); a.add(new fabric.Text(ch,{fontSize:40,fontFamily:'IPAGothic',originX:'center',originY:'center',left:30,top:30}));a.renderAll();
    const c=new fabric.StaticCanvas('f2',{backgroundColor:'#fff'}); window.placeChar(c,ch,30,30,40);c.renderAll();},ch);
  await p.waitForTimeout(50);
  out[ch]={dom:stats(await (await p.$('#d')).screenshot()),plain:stats(await (await p.$('#f1')).screenshot()),rule:stats(await (await p.$('#f2')).screenshot())};
}
fs.writeFileSync('out/vertical_cells.json',JSON.stringify(out,null,1));
for(const ch of chars){const o=out[ch];console.log(ch,'DOM',o.dom.cx,o.dom.cy,o.dom.w,o.dom.h,'| plain',o.plain.cx,o.plain.cy,o.plain.w,o.plain.h,'| rule',o.rule.cx,o.rule.cy,o.rule.w,o.rule.h)}
await p.goto('file://'+path.join(__dirname,'vertical.html'));await p.waitForTimeout(300);
await p.screenshot({path:'out/vertical.png'});
await b.close();})();
