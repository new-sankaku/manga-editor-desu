const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const url = 'file://' + path.join(__dirname, 'edit.html');
(async () => {
  const b = await chromium.launch();
  const res = {};
  for (const target of ['IText', 'Textbox']) {
    const p = await b.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => m.type()==='error' && errs.push(m.text()));
    await p.goto(url);
    res.fabricVersion = await p.evaluate(() => fabric.version);
    const cdp = await p.context().newCDPSession(p);
    await p.evaluate(t => { const o = t === 'IText' ? canvas.getObjects()[0] : canvas.getObjects()[1]; window.o = o; canvas.setActiveObject(o); o.enterEditing(); o.hiddenTextarea.focus(); canvas.requestRenderAll(); }, target);
    const st = () => p.evaluate(() => ({ text: o.text, ta: o.hiddenTextarea.value, editing: o.isEditing, selStart: o.selectionStart, composing: !!(o.inCompositionMode), len: o.text.length }));
    const pix = () => p.evaluate(() => { const c = document.getElementById('c'); const d = c.getContext('2d').getImageData(0,0,800,400).data; let n=0; for (let i=0;i<d.length;i+=4) if (d[i+3]>0 && d[i]<128) n++; return n; });
    const log = [];
    log.push({ step: 'start', ...(await st()), dark: await pix() });
    await p.keyboard.type('ab');
    log.push({ step: 'ascii typed ab', ...(await st()), dark: await pix() });
    // IME: composition "にほ" (変換中)
    await cdp.send('Input.imeSetComposition', { text: 'にほ', selectionStart: 2, selectionEnd: 2 });
    await p.waitForTimeout(100);
    log.push({ step: 'imeSetComposition にほ', ...(await st()), dark: await pix() });
    await cdp.send('Input.imeSetComposition', { text: '日本', selectionStart: 2, selectionEnd: 2 });
    await p.waitForTimeout(100);
    log.push({ step: 'imeSetComposition 日本 (conversion candidate)', ...(await st()), dark: await pix() });
    await cdp.send('Input.insertText', { text: '日本' });
    await p.waitForTimeout(100);
    log.push({ step: 'insertText 日本 (commit)', ...(await st()), dark: await pix() });
    // second composition then commit different text
    await cdp.send('Input.imeSetComposition', { text: 'ご', selectionStart: 1, selectionEnd: 1 });
    await cdp.send('Input.insertText', { text: '語' });
    await p.waitForTimeout(100);
    log.push({ step: 'compose ご -> commit 語', ...(await st()), dark: await pix() });
    // backspace works after
    await p.keyboard.press('Backspace');
    log.push({ step: 'Backspace', ...(await st()) });
    await p.evaluate(() => o.exitEditing());
    res[target] = { log, finalText: await p.evaluate(() => o.text), errors: errs };
    if (target==='IText') await p.screenshot({ path: 'out/_tmp_ime.png' });
    await p.close();
  }
  fs.writeFileSync('out/ime.json', JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res, null, 1));
  await b.close();
})();
