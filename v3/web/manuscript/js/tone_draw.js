// トーンを画面に描く（目安）。正本は値（ToneSpec）で、書き出しの網点はサーバー（print_export/page_render.py）が描く。
// 画面で網点の1周期が 3 画素より細かくなる倍率では、点を描くと干渉の縞が出るので、同じ濃さの灰色で見せる。
import { PRINT_INK } from "./print_colors.js";
const MIN_PERIOD_PX = 3;

function rng(seed) {
  let a = (seed >>> 0) || 1;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

const tiles = new Map();
function tile(key, size, draw) {
  if (!tiles.has(key)) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    draw(c.getContext("2d"), size);
    tiles.set(key, c);
  }
  return tiles.get(key);
}

function rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// ctx：mm の座標（box の左上が原点でなく、呼んだ側の座標）。box：[x0,y0,x1,y1]。zoom：1mm が何画素か
export function drawTone(ctx, spec, box, zoom) {
  const [x0, y0, x1, y1] = box;
  const w = x1 - x0, h = y1 - y0;
  const color = spec.color || PRINT_INK;
  const d = spec.density;
  ctx.save();
  if (spec.kind === "dots" || spec.kind === "lines") {
    const period = 25.4 / spec.lines_per_inch;
    if (period * zoom < MIN_PERIOD_PX) {
      ctx.fillStyle = rgba(color, d);
      ctx.fillRect(x0, y0, w, h);
    } else {
      const S = 32;
      const t = spec.kind === "dots"
        ? tile(`d|${color}|${d.toFixed(2)}`, S, (c) => {
          c.fillStyle = color;
          c.beginPath(); c.arc(S / 2, S / 2, S * Math.sqrt(Math.min(d, 0.95) / Math.PI), 0, Math.PI * 2); c.fill();
        })
        : tile(`l|${color}|${d.toFixed(2)}`, S, (c) => { c.fillStyle = color; c.fillRect(0, (S - S * d) / 2, S, S * d); });
      const p = ctx.createPattern(t, "repeat");
      const k = period / S;
      p.setTransform(new DOMMatrix().rotateSelf(spec.angle_deg || 0).scaleSelf(k, k));
      ctx.fillStyle = p;
      ctx.fillRect(x0, y0, w, h);
    }
  } else if (spec.kind === "sand" || spec.kind === "snow") {
    const S = 128;
    const g = spec.grain_mm;
    const t = tile(`s|${spec.kind}|${color}|${d.toFixed(2)}|${spec.seed}`, S, (c) => {
      const r = rng(spec.seed);
      c.fillStyle = color;
      const n = Math.round(S * S * d / 12);
      for (let i = 0; i < n; i++) { c.beginPath(); c.arc(r() * S, r() * S, 1.2 + r() * 1.3, 0, Math.PI * 2); c.fill(); }
    });
    const p = ctx.createPattern(t, "repeat");
    const k = (g * 2) / 2.5;
    p.setTransform(new DOMMatrix().scaleSelf(k, k));
    ctx.fillStyle = p;
    ctx.fillRect(x0, y0, w, h);
  } else if (spec.kind === "gradient") {
    const a = ((spec.angle_deg || 0) * Math.PI) / 180;
    const cx = x0 + w / 2, cy = y0 + h / 2, L = (Math.abs(w * Math.cos(a)) + Math.abs(h * Math.sin(a))) / 2;
    const gr = ctx.createLinearGradient(cx - Math.cos(a) * L, cy - Math.sin(a) * L, cx + Math.cos(a) * L, cy + Math.sin(a) * L);
    gr.addColorStop(0, rgba(color, d));
    gr.addColorStop(1, rgba(color, spec.density_end ?? 0));
    ctx.fillStyle = gr;
    ctx.fillRect(x0, y0, w, h);
  } else if (spec.kind === "focus_lines") {
    const r = rng(spec.seed);
    const [cx, cy] = spec.center_mm;
    const R = Math.hypot(Math.max(Math.abs(x0 - cx), Math.abs(x1 - cx)), Math.max(Math.abs(y0 - cy), Math.abs(y1 - cy)));
    const inner = R * spec.inner_ratio;
    ctx.fillStyle = rgba(color, Math.max(0.2, d));
    for (let i = 0; i < spec.line_count; i++) {
      const a = (i / spec.line_count) * Math.PI * 2 + r() * 0.05;
      const wid = (0.004 + r() * 0.012);
      const rin = inner * (0.85 + r() * 0.3);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a - wid) * R, cy + Math.sin(a - wid) * R);
      ctx.lineTo(cx + Math.cos(a) * rin, cy + Math.sin(a) * rin);
      ctx.lineTo(cx + Math.cos(a + wid) * R, cy + Math.sin(a + wid) * R);
      ctx.fill();
    }
  } else if (spec.kind === "speed_lines") {
    const r = rng(spec.seed);
    const a = ((spec.angle_deg || 0) * Math.PI) / 180;
    const ux = Math.cos(a), uy = Math.sin(a);
    const cx = x0 + w / 2, cy = y0 + h / 2, L = Math.hypot(w, h) / 2;
    ctx.strokeStyle = rgba(color, Math.max(0.25, d));
    for (let i = 0; i < spec.line_count; i++) {
      const off = (r() * 2 - 1) * L, s = (r() * 2 - 1) * L * 0.5, len = L * (0.6 + r());
      ctx.lineWidth = 0.15 + r() * 0.35;
      ctx.beginPath();
      ctx.moveTo(cx - uy * off + ux * (s - len / 2), cy + ux * off + uy * (s - len / 2));
      ctx.lineTo(cx - uy * off + ux * (s + len / 2), cy + ux * off + uy * (s + len / 2));
      ctx.stroke();
    }
  }
  ctx.restore();
}

export const TONE_KINDS = [
  ["dots", "網点"], ["lines", "線"], ["sand", "砂目"], ["gradient", "グラデ"], ["snow", "雪"], ["focus_lines", "集中線"], ["speed_lines", "スピード線"],
];
