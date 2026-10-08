const { chromium } = require('/opt/node-tools/node_modules/playwright'); const { PNG } = require('pngjs'); const path=require('path'),fs=require('fs');
const N4=[[1,0],[-1,0],[0,1],[0,-1]];
function analyse(buf){const p=PNG.sync.read(buf);const W=p.width,H=p.height;const bin=new Uint8Array(W*H);let dark=0;
  for(let i=0;i<W*H;i++){if(p.data[i*4]<128){bin[i]=1;dark++;}}
  const seen=new Uint8Array(W*H);const cs=[];
  for(let i=0;i<W*H;i++){if(bin[i]&&!seen[i]){let sx=0,sy=0,n=0;const st=[i];seen[i]=1;
    while(st.length){const j=st.pop();const x=j%W,y=(j/W)|0;sx+=x;sy+=y;n++;for(const [dx,dy] of N4){const nx=x+dx,ny=y+dy;if(nx<0||ny<0||nx>=W||ny>=H)continue;const k=ny*W+nx;if(bin[k]&&!seen[k]){seen[k]=1;st.push(k);}}}
    cs.push([sx/n,sy/n,n]);}}
  const angs=[],dists=[];
  if(cs.length>3&&cs.length<2500){for(const a of cs){if(a[0]<40||a[0]>W-40||a[1]<40||a[1]>H-40)continue;let best=1e9,bd=null;for(const b of cs){if(a===b)continue;const dx=b[0]-a[0],dy=b[1]-a[1];const d=Math.hypot(dx,dy);if(d<best){best=d;bd=[dx,dy];}}
    if(bd){let an=Math.atan2(bd[1],bd[0])*180/Math.PI;an=((an%90)+90)%90;angs.push(an);dists.push(best);}}}
  const med=a=>a.length?+a.slice().sort((x,y)=>x-y)[a.length>>1].toFixed(1):null;
  return {darkRatio:+(dark/(W*H)).toFixed(3),components:cs.length,latticeAngleMedian:med(angs),pitchMedianPx:med(dists)};}
(async()=>{const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});const p=await b.newPage({viewport:{width:900,height:900}});
const errs=[];p.on('pageerror',e=>errs.push(String(e)));
await p.goto('file://'+path.join(__dirname,'halftone.html'));
const cases=[];
for(const g of [0.1,0.25,0.5,0.75,0.9]) cases.push({g,o:{frequency:20,angle:45,shape:'circle',invert:true}});
for(const g of [0.1,0.25,0.5,0.75,0.9]) for(const c of [1.5,2.2,3]) cases.push({g,o:{frequency:20,angle:45,shape:'circle',invert:true,contrast:c}});
for(const f of [10,20,30]) cases.push({g:0.5,o:{frequency:f,angle:0,shape:'circle',invert:true}});
for(const a of [0,15,45,75]) cases.push({g:0.5,o:{frequency:20,angle:a,shape:'circle',invert:true}});
for(const s of ['circle','square','diamond','line','cross','ellipse']) cases.push({g:0.5,o:{frequency:20,angle:45,shape:s,invert:true}});
const rows=[];const ONLY=process.env.ONLY_CONTRAST==='1';
for(const c of cases){ if(ONLY&&c.o.contrast===undefined)continue;
  await p.evaluate(()=>{document.getElementById('grid').innerHTML='';});
  const r=await p.evaluate(async c=>{const x=await window.makeOne(c.g,c.o);return x.snap();},c);
  const buf=Buffer.from(r.split(',')[1],'base64');
  rows.push({gray:c.g,...c.o,...analyse(buf)});
  if(c.g===0.5&&c.o.angle===45&&c.o.frequency===20&&['circle','diamond','line'].includes(c.o.shape)) fs.writeFileSync(`out/_ht_${c.o.shape}.png`,buf);
}
console.log(rows.map(r=>JSON.stringify(r)).join('\n'));
if(!ONLY)fs.writeFileSync('out/halftone_webgl.json',JSON.stringify({lib:'halftone-webgl 1.0.5',viewport:'400x400 (dpr 1)',rows,errors:errs},null,1));await b.close();})();
