const { chromium } = require('/opt/node-tools/node_modules/playwright'); const path=require('path');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:300,height:300}});const errs=[];p.on('pageerror',e=>errs.push(String(e)));p.on('console',m=>errs.push(m.type()+':'+m.text()));
await p.goto('file://'+path.join(__dirname,'h9.html'));await p.waitForTimeout(2500);
console.log(await p.evaluate(()=>{const e=document.querySelector('img-halftone');const cv=e.shadowRoot&&e.shadowRoot.querySelector('canvas');return {defined:!!customElements.get('img-halftone'),hasShadow:!!e.shadowRoot,canvas:!!cv,w:cv&&cv.width,cls:e.className}}),errs.slice(0,4));
await b.close();})();
