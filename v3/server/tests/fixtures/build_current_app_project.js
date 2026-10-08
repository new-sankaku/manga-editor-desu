// 今のアプリを Chromium で動かし、見本のプロジェクトを作って保存する
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const OUT = process.argv[2];
const APP = 'file:///home/user/manga-editor-desu/.claude/worktrees/agent-af425a97c3f63269f/index.html';

const summary = (p) => p.evaluate(() => canvas.getObjects().map(o => [o.type, o.name, o.customType || '', !!o.isPanel].join('|')));

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(APP);
  await p.waitForTimeout(4000);
  // 最初の案内：言語を選び、案内を飛ばす
  if (await p.locator('.tutorial-lang-btn').count()) { await p.locator('.tutorial-lang-btn').first().click(); await p.waitForTimeout(1500); }
  if (await p.locator('#tutorialSkipBtn').count()) { await p.locator('#tutorialSkipBtn').click(); await p.waitForTimeout(800); }
  console.log('overlay left', await p.locator('.tutorial-overlay').count());

  // 1. コマの型を選ぶ（左のパネルを開いて、型の一覧の3番目を押す）
  await p.evaluate(() => { document.getElementById('svg-container-template').style.display = 'block'; });
  await p.locator('#svg-preview-area-vertical > *').nth(6).click();
  await p.waitForTimeout(1500);
  console.log('after template', await summary(p));

  // 2. 1つ目のコマにプロンプトを入れる（プロンプトの入力欄と同じ項目に入れる）
  await p.evaluate(() => {
    const panels = canvas.getObjects().filter(o => o.isPanel);
    panels[0].text2img_prompt = '1girl, school uniform, classroom';
    panels[0].text2img_negative = 'lowres';
    panels[0].text2img_seed = 12345;
    panels[0].text2img_width = 832;
    panels[0].text2img_height = 1216;
    canvas.setActiveObject(panels[0]);
  });

  // 3. 1つ目のコマに絵を入れる（画像を落としたときと同じ putImageInFrame）
  await p.evaluate(() => new Promise((resolve) => {
    const c = document.createElement('canvas'); c.width = 320; c.height = 240;
    const g = c.getContext('2d'); g.fillStyle = '#c84'; g.fillRect(0, 0, 320, 240);
    g.fillStyle = '#048'; g.beginPath(); g.arc(160, 120, 80, 0, Math.PI * 2); g.fill();
    fabric.Image.fromURL(c.toDataURL('image/png'), (img) => {
      const panel = canvas.getObjects().filter(o => o.isPanel)[0];
      const cx = panel.left + panel.width * panel.scaleX / 2, cy = panel.top + panel.height * panel.scaleY / 2;
      putImageInFrame(img, cx, cy);
      img.text2img_prompt = 'image prompt: sunset';
      resolve();
    });
  }));
  await p.waitForTimeout(800);
  console.log('after image', await summary(p));

  // 4. 2つ目のコマにトーン（トーンのパネルの処理）
  await p.evaluate(() => {
    const panels = canvas.getObjects().filter(o => o.isPanel);
    canvas.setActiveObject(panels[1]);
    toneStart();
  });
  await p.waitForTimeout(1500);
  await p.evaluate(() => toneEnd());
  console.log('after tone', await summary(p));

  // 5. 縦書きの文字（文字のパネルの「縦書き」）と横書きの文字
  await p.evaluate(() => { canvas.discardActiveObject(); document.getElementById('text-area').style.display = 'block'; });
  await p.locator('#verticalText').click();
  await p.waitForTimeout(500);
  await p.evaluate(() => {
    const t = canvas.getObjects().filter(o => o.type === 'vertical-textbox' || o.name === 'verticalText').pop();
    if (t) { t.set('text', 'こんにちは'); t.set({ left: 400, top: 120 }); t.setCoords(); }
    canvas.discardActiveObject();
  });
  await p.locator('#text-area button', { hasText: '' }).first().click();
  await p.waitForTimeout(500);
  await p.evaluate(() => {
    const objs = canvas.getObjects();
    const t = objs[objs.length - 1];
    if (t && (t.type === 'textbox' || t.type === 'i-text')) { t.set('text', 'Narration'); t.set({ left: 60, top: 700 }); t.setCoords(); }
    canvas.discardActiveObject();
  });
  console.log('after text', await summary(p));

  // 6. フキダシ（フキダシのパネルの型の1つ目）
  await p.evaluate(() => { document.getElementById('speech-bubble-area1').style.display = 'block'; lazyLoadSpeechBubbles(); });
  await p.waitForTimeout(1500);
  const bubbleCount = await p.locator('#speech-bubble-preview img').count();
  console.log('bubble previews', bubbleCount);
  if (bubbleCount > 0) {
    await p.locator('#speech-bubble-preview img').first().click();
    await p.waitForTimeout(1000);
  }
  await p.evaluate(() => {
    const t = canvas.getObjects().find(o => o.customType === 'speechBubbleText');
    if (t) { t.set('text', 'セリフです'); }
  });
  console.log('after bubble', await summary(p));

  // 7. ペンの線（ペンで1本引く）
  await p.evaluate(() => { canvas.isDrawingMode = true; canvas.freeDrawingBrush = new fabric.PencilBrush(canvas); canvas.freeDrawingBrush.width = 4; });
  const box = await p.locator('canvas.upper-canvas').boundingBox();
  await p.mouse.move(box.x + 100, box.y + 400); await p.mouse.down();
  for (let i = 0; i < 10; i++) await p.mouse.move(box.x + 100 + i * 15, box.y + 400 + (i % 2) * 20);
  await p.mouse.up();
  await p.evaluate(() => { canvas.isDrawingMode = false; });
  await p.waitForTimeout(800);
  console.log('after pen', await summary(p));

  // 8. 2ページ目を足す（下のページの一覧の「＋」→ 足す）
  await p.evaluate(() => btmSaveProjectFile(null, false));
  await p.waitForTimeout(1500);
  await p.locator('.btm-add-btn').last().dispatchEvent('click');
  await p.waitForTimeout(500);
  await p.locator('#btm-dialog-submit').click();
  await p.waitForTimeout(2500);
  await p.evaluate(() => { document.getElementById('svg-container-template').style.display = 'block'; });
  await p.locator('#svg-preview-area-vertical > *').nth(0).click();
  await p.waitForTimeout(1200);
  await p.evaluate(() => { canvas.discardActiveObject(); });
  await p.locator('#verticalText').click();
  await p.waitForTimeout(400);
  await p.evaluate(() => {
    const t = canvas.getObjects().filter(o => o.type === 'vertical-textbox' || o.name === 'verticalText').pop();
    if (t) { t.set('text', '二ページ目'); t.set({ left: 300, top: 300 }); t.setCoords(); }
  });
  console.log('page2', await summary(p));

  // 9. 保存（メニューの「プロジェクトを保存」）
  const [dl] = await Promise.all([
    p.waitForEvent('download', { timeout: 60000 }),
    p.evaluate(() => document.getElementById('projectSave').click()),
  ]);
  await dl.saveAs(OUT);
  console.log('saved', OUT, dl.suggestedFilename());
  console.log('ERR', errs.slice(0, 8));
  await b.close();
})();
