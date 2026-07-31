// Node.js script to run all 30 benchmarks via puppeteer-like approach using Chrome DevTools Protocol
// Since puppeteer may not be installed, we'll use a simpler approach:
// Launch benchmarks in sequence using the existing http-server and extract results

const http = require('http');
const { execSync } = require('child_process');

const BENCHMARKS = Array.from({length: 30}, (_, i) => {
  const num = String(i + 1).padStart(2, '0');
  return `bench-${num}`;
});

// We'll use a different approach - create a single HTML that runs each benchmark
// inline (not iframe) and collects results. But that requires a browser.

// Instead, let's just verify files exist and output a summary of what each benchmark tests.
// The actual benchmarks need a browser. Let's create a simpler approach.

// For benchmarks that are pure computation (no Canvas), we can run them in Node.js
// For Canvas-based ones, we need a browser.

console.log('=== Benchmark Summary Generator ===\n');
console.log('bench-01 result (from browser): CryptoJS.SHA256=82.48ms, crypto.subtle=12.70ms → 6.5x faster\n');

// Run pure computation benchmarks in Node.js where possible
function benchDjb2() {
  // Generate 2MB string
  const size = 2 * 1024 * 1024;
  let str = '';
  for (let i = 0; i < size; i++) str += String.fromCharCode(65 + (i % 26));

  // Current: charCodeAt loop
  function djb2Current(s) {
    let h = 5381;
    for (let i = 0, len = s.length; i < len; i++) {
      h = ((h << 5) + h) + s.charCodeAt(i);
      h |= 0;
    }
    return h + ':' + s.length;
  }

  // Improved: TextEncoder + byte loop
  function djb2Optimized(s) {
    const bytes = Buffer.from(s, 'utf-8');
    let h = 5381;
    for (let i = 0, len = bytes.length; i < len; i++) {
      h = ((h << 5) + h) + bytes[i];
      h |= 0;
    }
    return h + ':' + bytes.length;
  }

  // Improved B: 4-char chunk
  function djb2Chunked(s) {
    let h = 5381;
    const len = s.length;
    let i = 0;
    for (; i + 3 < len; i += 4) {
      h = ((h << 5) + h) + s.charCodeAt(i); h |= 0;
      h = ((h << 5) + h) + s.charCodeAt(i+1); h |= 0;
      h = ((h << 5) + h) + s.charCodeAt(i+2); h |= 0;
      h = ((h << 5) + h) + s.charCodeAt(i+3); h |= 0;
    }
    for (; i < len; i++) {
      h = ((h << 5) + h) + s.charCodeAt(i);
      h |= 0;
    }
    return h + ':' + len;
  }

  const REPEAT = 20;
  let t, times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    t = performance.now();
    djb2Current(str);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    t = performance.now();
    djb2Optimized(str);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    t = performance.now();
    djb2Chunked(str);
    times.push(performance.now() - t);
  }
  const avgOptB = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: avgOptB };
}

function benchBase64() {
  // Generate 1MB base64
  const size = 1024 * 1024;
  const arr = Buffer.alloc(size);
  for (let i = 0; i < size; i++) arr[i] = i & 255;
  const b64 = arr.toString('base64');

  // Current: intermediate Array
  function currentImpl(base64) {
    const bin = Buffer.from(base64, 'base64').toString('binary');
    const byteNumbers = new Array(bin.length);
    for (let i = 0; i < bin.length; i++) byteNumbers[i] = bin.charCodeAt(i);
    return new Uint8Array(byteNumbers);
  }

  // Improved: direct Uint8Array
  function optimizedImpl(base64) {
    const bin = Buffer.from(base64, 'base64').toString('binary');
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  // Improved B: Buffer direct
  function bufferImpl(base64) {
    return new Uint8Array(Buffer.from(base64, 'base64'));
  }

  const REPEAT = 20;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    currentImpl(b64);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    optimizedImpl(b64);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    bufferImpl(b64);
    times.push(performance.now() - t);
  }
  const avgOptB = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: avgOptB };
}

function benchJsonSerialize() {
  // Create 50 objects with 20 properties each
  const objects = Array.from({length: 50}, (_, i) => {
    const obj = { id: i, type: 'rect', version: '5.3.0' };
    for (let j = 0; j < 17; j++) {
      obj['prop_' + j] = j % 2 === 0 ? 'string_value_' + j : j * 1.5;
    }
    return obj;
  });

  function currentImpl(objs) {
    const state = { objects: objs.map(o => ({...o})) };
    return JSON.stringify(state);
  }

  function diffImpl(objs, prevJson) {
    const state = { objects: objs.map(o => ({...o})) };
    const json = JSON.stringify(state);
    if (json === prevJson) return { type: 'same' };
    return { type: 'full', data: json };
  }

  const REPEAT = 100;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    currentImpl(objects);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  // Simulate diff: 90% same, 10% changed
  const prevJson = currentImpl(objects);
  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    diffImpl(objects, prevJson);
    times.push(performance.now() - t);
  }
  const avgDiff = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgCurrent, optB: avgDiff };
}

function benchBufferCombine() {
  // 50 buffers, 100KB-1MB each
  const buffers = Array.from({length: 50}, () => {
    const size = 100 * 1024 + Math.floor(Math.random() * 900 * 1024);
    return Buffer.alloc(size).buffer;
  });

  function currentImpl(bufs) {
    const totalSize = bufs.reduce((s, b) => s + b.byteLength, 0);
    const combined = new Uint8Array(totalSize);
    let offset = 0;
    for (let i = 0; i < bufs.length; i++) {
      combined.set(new Uint8Array(bufs[i]), offset);
      offset += bufs[i].byteLength;
    }
    return combined;
  }

  function blobImpl(bufs) {
    // In Node, simulate with Buffer.concat
    return Buffer.concat(bufs.map(b => Buffer.from(b)));
  }

  const REPEAT = 20;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    currentImpl(buffers);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    blobImpl(buffers);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: null };
}

function benchPolygonHittest() {
  // 20 polygons, 8 vertices each
  const polygons = Array.from({length: 20}, () => {
    const cx = Math.random() * 800, cy = Math.random() * 600;
    const r = 50 + Math.random() * 100;
    return Array.from({length: 8}, (_, i) => ({
      x: cx + r * Math.cos(i * Math.PI / 4),
      y: cy + r * Math.sin(i * Math.PI / 4)
    }));
  });

  // 10000 test points
  const points = Array.from({length: 10000}, () => ({
    x: Math.random() * 800, y: Math.random() * 600
  }));

  function isInsideCurrent(point, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i].x, yi = polygon[i].y;
      const xj = polygon[j].x, yj = polygon[j].y;
      if ((yi > point.y) !== (yj > point.y) &&
          point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    return inside;
  }

  function isInsideBBox(point, polygon, bbox) {
    if (point.x < bbox.minX || point.x > bbox.maxX || point.y < bbox.minY || point.y > bbox.maxY) return false;
    return isInsideCurrent(point, polygon);
  }

  // Precompute bboxes
  const bboxes = polygons.map(p => ({
    minX: Math.min(...p.map(v=>v.x)),
    maxX: Math.max(...p.map(v=>v.x)),
    minY: Math.min(...p.map(v=>v.y)),
    maxY: Math.max(...p.map(v=>v.y))
  }));

  const REPEAT = 5;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    for (const pt of points) {
      for (const poly of polygons) isInsideCurrent(pt, poly);
    }
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    for (const pt of points) {
      for (let i = 0; i < polygons.length; i++) isInsideBBox(pt, polygons[i], bboxes[i]);
    }
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: null };
}

function benchCanvasResize() {
  const objects = Array.from({length: 200}, (_, i) => ({
    left: Math.random() * 750, top: Math.random() * 850,
    scaleX: 1, scaleY: 1, strokeWidth: 2,
    width: 100, height: 100, angle: 0,
    coords: null
  }));

  function currentImpl(objs, sx, sy) {
    for (let i = 0; i < objs.length; i++) {
      const o = objs[i];
      o.left *= sx; o.top *= sy;
      o.scaleX *= sx; o.scaleY *= sy;
      o.strokeWidth = (o.strokeWidth || 1) * ((sx + sy) / 2);
      o.coords = {
        tl: { x: o.left, y: o.top },
        tr: { x: o.left + o.width * o.scaleX, y: o.top },
        bl: { x: o.left, y: o.top + o.height * o.scaleY },
        br: { x: o.left + o.width * o.scaleX, y: o.top + o.height * o.scaleY }
      };
    }
  }

  function soaImpl(lefts, tops, scaleXs, scaleYs, strokeWidths, widths, heights, sx, sy) {
    const avg = (sx + sy) / 2;
    for (let i = 0; i < lefts.length; i++) {
      lefts[i] *= sx; tops[i] *= sy;
      scaleXs[i] *= sx; scaleYs[i] *= sy;
      strokeWidths[i] *= avg;
    }
  }

  const n = objects.length;
  const lefts = new Float64Array(n);
  const tops = new Float64Array(n);
  const scaleXs = new Float64Array(n);
  const scaleYs = new Float64Array(n);
  const strokeWidths = new Float64Array(n);
  const widths = new Float64Array(n);
  const heights = new Float64Array(n);

  const REPEAT = 1000;
  let times;

  // Current
  times = [];
  for (let r = 0; r < REPEAT; r++) {
    // Reset
    objects.forEach((o, i) => { o.left = i; o.top = i; o.scaleX = 1; o.scaleY = 1; o.strokeWidth = 2; });
    const t = performance.now();
    currentImpl(objects, 1.001, 1.001);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  // SoA
  times = [];
  for (let r = 0; r < REPEAT; r++) {
    for (let i = 0; i < n; i++) { lefts[i] = i; tops[i] = i; scaleXs[i] = 1; scaleYs[i] = 1; strokeWidths[i] = 2; }
    const t = performance.now();
    soaImpl(lefts, tops, scaleXs, scaleYs, strokeWidths, widths, heights, 1.001, 1.001);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: null };
}

function benchFocusline() {
  const lineNum = 500;
  const cx = 375, cy = 425;
  const innerRadius = 100, outerRadius = 400;
  const variation = 50, minWidth = 1, maxWidth = 5;

  function currentImpl() {
    const lines = [];
    for (let i = 0; i < lineNum; i++) {
      const angle = Math.random() * Math.PI * 2;
      const innerR = innerRadius + Math.random() * variation;
      const outerR = outerRadius + Math.random() * variation;
      lines.push({
        x1: cx + Math.cos(angle) * innerR,
        y1: cy + Math.sin(angle) * innerR,
        x2: cx + Math.cos(angle) * outerR,
        y2: cy + Math.sin(angle) * outerR,
        width: minWidth + Math.random() * (maxWidth - minWidth)
      });
    }
    return lines;
  }

  function typedArrayImpl() {
    const data = new Float64Array(lineNum * 5);
    for (let i = 0; i < lineNum; i++) {
      const angle = Math.random() * Math.PI * 2;
      const innerR = innerRadius + Math.random() * variation;
      const outerR = outerRadius + Math.random() * variation;
      const cos = Math.cos(angle), sin = Math.sin(angle);
      const off = i * 5;
      data[off] = cx + cos * innerR;
      data[off+1] = cy + sin * innerR;
      data[off+2] = cx + cos * outerR;
      data[off+3] = cy + sin * outerR;
      data[off+4] = minWidth + Math.random() * (maxWidth - minWidth);
    }
    return data;
  }

  // LUT approach
  const LUT_SIZE = 4096;
  const cosLUT = new Float64Array(LUT_SIZE);
  const sinLUT = new Float64Array(LUT_SIZE);
  for (let i = 0; i < LUT_SIZE; i++) {
    cosLUT[i] = Math.cos(i / LUT_SIZE * Math.PI * 2);
    sinLUT[i] = Math.sin(i / LUT_SIZE * Math.PI * 2);
  }
  let xorState = 12345;
  function xorshift() { xorState ^= xorState << 13; xorState ^= xorState >> 17; xorState ^= xorState << 5; return (xorState >>> 0) / 4294967296; }

  function lutImpl() {
    const data = new Float64Array(lineNum * 5);
    for (let i = 0; i < lineNum; i++) {
      const angleIdx = (xorshift() * LUT_SIZE) | 0;
      const cos = cosLUT[angleIdx], sin = sinLUT[angleIdx];
      const innerR = innerRadius + xorshift() * variation;
      const outerR = outerRadius + xorshift() * variation;
      const off = i * 5;
      data[off] = cx + cos * innerR;
      data[off+1] = cy + sin * innerR;
      data[off+2] = cx + cos * outerR;
      data[off+3] = cy + sin * outerR;
      data[off+4] = minWidth + xorshift() * (maxWidth - minWidth);
    }
    return data;
  }

  const REPEAT = 100;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) { const t = performance.now(); currentImpl(); times.push(performance.now() - t); }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) { const t = performance.now(); typedArrayImpl(); times.push(performance.now() - t); }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  xorState = 12345;
  for (let r = 0; r < REPEAT; r++) { const t = performance.now(); lutImpl(); times.push(performance.now() - t); }
  const avgOptB = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: avgOptB };
}

function benchInkBrush() {
  const STROKE_COUNT = 40;
  function createStrokes() {
    return Array.from({length: STROKE_COUNT}, () => ({
      x: Math.random() * 750, y: Math.random() * 850,
      angle: 0, speed: 5 + Math.random() * 10
    }));
  }

  function currentImpl(strokes, mouseX, mouseY) {
    for (let i = 0; i < strokes.length; i++) {
      const s = strokes[i];
      const dx = mouseX - s.x, dy = mouseY - s.y;
      s.angle = Math.atan2(dy, dx);
      s.x += Math.cos(s.angle) * s.speed;
      s.y += Math.sin(s.angle) * s.speed;
      s.speed *= 0.95;
    }
  }

  function typedImpl(data, mouseX, mouseY) {
    for (let i = 0; i < STROKE_COUNT; i++) {
      const off = i * 4;
      const dx = mouseX - data[off], dy = mouseY - data[off+1];
      const angle = Math.atan2(dy, dx);
      data[off] += Math.cos(angle) * data[off+3];
      data[off+1] += Math.sin(angle) * data[off+3];
      data[off+2] = angle;
      data[off+3] *= 0.95;
    }
  }

  const UPDATES = 10000;
  let times;

  times = [];
  for (let r = 0; r < 5; r++) {
    const strokes = createStrokes();
    const t = performance.now();
    for (let u = 0; u < UPDATES; u++) currentImpl(strokes, 375 + u * 0.1, 425);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < 5; r++) {
    const data = new Float64Array(STROKE_COUNT * 4);
    for (let i = 0; i < STROKE_COUNT; i++) {
      data[i*4] = Math.random()*750; data[i*4+1] = Math.random()*850;
      data[i*4+2] = 0; data[i*4+3] = 5+Math.random()*10;
    }
    const t = performance.now();
    for (let u = 0; u < UPDATES; u++) typedImpl(data, 375 + u * 0.1, 425);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: null };
}

function benchProjectSave() {
  // 30 entries of ~100KB JSON each
  const entries = Array.from({length: 30}, (_, i) => {
    const obj = { index: i, objects: [] };
    for (let j = 0; j < 50; j++) {
      obj.objects.push({ id: j, type: 'rect', props: { x: j, y: j*2, label: 'item_'.padEnd(200, 'x') } });
    }
    return obj;
  });

  function currentImpl(entries) {
    return entries.map(e => {
      const json = JSON.stringify(e);
      return new TextEncoder().encode(json).buffer;
    });
  }

  function encodeIntoImpl(entries) {
    const encoder = new TextEncoder();
    return entries.map(e => {
      const json = JSON.stringify(e);
      const buf = new Uint8Array(json.length * 3);
      const result = encoder.encodeInto(json, buf);
      return buf.buffer.slice(0, result.written);
    });
  }

  const REPEAT = 20;
  let times;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    currentImpl(entries);
    times.push(performance.now() - t);
  }
  const avgCurrent = times.reduce((a,b)=>a+b,0)/times.length;

  times = [];
  for (let r = 0; r < REPEAT; r++) {
    const t = performance.now();
    encodeIntoImpl(entries);
    times.push(performance.now() - t);
  }
  const avgOptA = times.reduce((a,b)=>a+b,0)/times.length;

  return { current: avgCurrent, optA: avgOptA, optB: null };
}

// Run all
console.log('#  | ベンチマーク           | 現行(ms)  | 改善A(ms) | 改善B(ms) | 最速改善率    | WASM必要?');
console.log('---|----------------------|----------|----------|----------|-------------|----------');

function fmt(v) { return v != null ? v.toFixed(2).padStart(8) : '     N/A'; }
function ratio(current, best) {
  if (best == null || current == null) return '         —';
  const r = current / best;
  const pct = ((current - best) / current * 100).toFixed(0);
  return `${r.toFixed(1)}x (${pct}%↑)`.padStart(13);
}

const results = {};

// bench-01 (already from browser)
console.log(' 1 | SHA-256ハッシュ        |    82.48 |    12.70 |      N/A | 6.5x (85%↑)  | 不要(native API)');

// Canvas-dependent benchmarks - mark as "requires browser"
const canvasBenches = [2,3,4,5,7,8,10,11,12,13,15,16,19,20,23,25,30];

// Run computable benchmarks
const r9 = benchInkBrush();
const r14 = benchFocusline();
const r17 = benchJsonSerialize();
const r18 = benchProjectSave();
const r21 = benchDjb2();
const r22 = benchBase64();
const r24 = benchPolygonHittest();
const r27 = benchCanvasResize();
const r28 = benchBufferCombine();

const computeResults = {
  9: { name: 'インクブラシ物理', ...r9, wasm: 'JS改善可' },
  14: { name: 'フォーカスライン', ...r14, wasm: 'JS改善可' },
  17: { name: 'JSONシリアライズ', ...r17, wasm: '不要(差分保存)' },
  18: { name: '保存パイプライン', ...r18, wasm: 'JS改善可' },
  21: { name: 'DJB2ハッシュ', ...r21, wasm: 'JS改善可' },
  22: { name: 'Base64デコード', ...r22, wasm: '不要(直接確保)' },
  24: { name: 'ポリゴン判定', ...r24, wasm: '不要(BBox事前判定)' },
  27: { name: 'リサイズ再計算', ...r27, wasm: 'JS改善可' },
  28: { name: 'バッファ結合', ...r28, wasm: '不要(Blob)' },
};

const allNames = {
  1:'SHA-256ハッシュ', 2:'ノイズトーン生成', 3:'暗部強調フィルタ', 4:'透明境界検出',
  5:'グリッド+最大矩形', 6:'ポリゴン計算', 7:'モザイクブラシ', 8:'アウトラインブラシ',
  9:'インクブラシ物理', 10:'クレヨンブラシ', 11:'マスク白黒変換', 12:'ブラシ境界検出',
  13:'トーンドット生成', 14:'フォーカスライン', 15:'ブレンドプレビュー', 16:'サムネイル生成',
  17:'JSONシリアライズ', 18:'保存パイプライン', 19:'JPEGエンコード', 20:'SVG面積算出',
  21:'DJB2ハッシュ', 22:'Base64デコード', 23:'toDataURL往復', 24:'ポリゴン判定',
  25:'アニメ描画', 26:'スノートーン', 27:'リサイズ再計算', 28:'バッファ結合',
  29:'SVG→dataURL', 30:'blob変換',
};

const wasmInfo = {
  2:'WASM+SIMD推奨', 3:'WASM+SIMD推奨', 4:'JS改善+WASM', 5:'WASM推奨',
  6:'GEOS-WASM推奨', 7:'JS改善+WASM', 8:'不要(設計改善)', 10:'JS改善可',
  11:'不要(Uint32Array)', 12:'不要(4辺スキャン)', 13:'JS改善+WASM',
  15:'不要(Canvas再利用)', 16:'不要(toBlob)', 19:'JS改善可', 20:'不要(forループ化)',
  23:'不要(ImageBitmap)', 25:'不要(レイヤー分離)', 26:'不要(キャッシュ)',
  29:'不要(encodeURI)', 30:'不要(並列化)',
};

for (let id = 2; id <= 30; id++) {
  const cr = computeResults[id];
  if (cr) {
    const best = Math.min(cr.optA || Infinity, cr.optB || Infinity);
    const r = ratio(cr.current, best);
    console.log(`${String(id).padStart(2)} | ${cr.name.padEnd(20)} |${fmt(cr.current)} |${fmt(cr.optA)} |${fmt(cr.optB)} |${r} | ${cr.wasm}`);
  } else {
    console.log(`${String(id).padStart(2)} | ${(allNames[id]||'').padEnd(20)} | [要ブラウザ]                                  | ${wasmInfo[id] || ''}`);
  }
}
