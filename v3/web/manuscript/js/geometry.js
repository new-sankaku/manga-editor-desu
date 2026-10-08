// 形の計算（mm）。コマを切る計算はサーバー（v3server/panel_layout/panel_frame_editing.py）と同じ式にする。
// 画面で先に見せるためだけに使い、正本はサーバーが返した形で置き換える。

export const PT_MM = 25.4 / 72;
const EPS = 1e-6;

export function bbox(points) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of points) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return [x0, y0, x1, y1];
}

export function area(P) {
  let a = 0;
  for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; }
  return Math.abs(a) / 2;
}

export function centroid(P) {
  const [x0, y0, x1, y1] = bbox(P);
  return [(x0 + x1) / 2, (y0 + y1) / 2];
}

export function pointInPolygon([x, y], P) {
  let inside = false;
  for (let i = 0, j = P.length - 1; i < P.length; j = i++) {
    const [xi, yi] = P[i], [xj, yj] = P[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// 切る線に直角な単位の向き（サーバーの line_normal と同じ）
export function lineNormal(direction, angleDeg) {
  if (direction === "horizontal") return [0, 1];
  if (direction === "vertical") return [1, 0];
  const a = (angleDeg * Math.PI) / 180;
  return [-Math.sin(a), Math.cos(a)];
}

function clipHalf(P, n, c) {
  const out = [];
  for (let i = 0; i < P.length; i++) {
    const p = P[i], q = P[(i + 1) % P.length];
    const dp = n[0] * p[0] + n[1] * p[1] - c, dq = n[0] * q[0] + n[1] * q[1] - c;
    if (dp >= 0) out.push(p);
    if ((dp >= 0) !== (dq >= 0)) { const t = dp / (dp - dq); out.push([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]); }
  }
  return out.filter((p, i) => i === 0 || Math.hypot(p[0] - out[i - 1][0], p[1] - out[i - 1][1]) > EPS);
}

// コマを1本の線で2つに分ける（サーバーの split_polygon と同じ）。分けられなければ理由を投げる
export function splitPolygon(P, through, n, gap) {
  const c = n[0] * through[0] + n[1] * through[1];
  const a = clipHalf(P, n, c + gap / 2);
  const b = clipHalf(P, [-n[0], -n[1]], -(c - gap / 2));
  if (a.length < 3 || b.length < 3 || area(a) <= EPS || area(b) <= EPS) {
    throw new Error("切る線がコマを横切っていない（または間の幅がコマより広い）");
  }
  return [a, b];
}

// 線がコマの中を通る区間（ナイフの線を、押す前から見せるため）。通らなければ null
export function chordThrough(P, through, n) {
  const d = [n[1], -n[0]];
  let tMin = Infinity, tMax = -Infinity;
  for (let i = 0; i < P.length; i++) {
    const p = P[i], q = P[(i + 1) % P.length];
    const e = [q[0] - p[0], q[1] - p[1]];
    const den = d[0] * e[1] - d[1] * e[0];
    if (Math.abs(den) < EPS) continue;
    const w = [p[0] - through[0], p[1] - through[1]];
    const t = (w[0] * e[1] - w[1] * e[0]) / den;
    const s = (w[0] * d[1] - w[1] * d[0]) / den;
    if (s >= -EPS && s <= 1 + EPS) { tMin = Math.min(tMin, t); tMax = Math.max(tMax, t); }
  }
  if (!Number.isFinite(tMin) || tMax - tMin < EPS) return null;
  return [[through[0] + d[0] * tMin, through[1] + d[1] * tMin], [through[0] + d[0] * tMax, through[1] + d[1] * tMax]];
}

// 2つのコマを包む形（サーバーの merged_polygon と同じ凸包）
export function convexHull(points) {
  const pts = [...new Map(points.map((p) => [`${p[0]},${p[1]}`, p])).values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return pts;
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [], upper = [];
  for (const p of pts) { while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), p) <= 0) lower.pop(); lower.push(p); }
  for (const p of [...pts].reverse()) { while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), p) <= 0) upper.pop(); upper.push(p); }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

// 2つのコマが隣り合っているか（枠の辺どうしの近さで見る。サーバーが最後に決める）
export function polygonsNear(a, b, tol) {
  const segDist = (p, q, r) => {
    const dx = q[0] - p[0], dy = q[1] - p[1];
    const t = Math.max(0, Math.min(1, ((r[0] - p[0]) * dx + (r[1] - p[1]) * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(p[0] + t * dx - r[0], p[1] + t * dy - r[1]);
  };
  for (const r of a) for (let i = 0; i < b.length; i++) if (segDist(b[i], b[(i + 1) % b.length], r) <= tol) return true;
  for (const r of b) for (let i = 0; i < a.length; i++) if (segDist(a[i], a[(i + 1) % a.length], r) <= tol) return true;
  return false;
}

export const r2 = (v) => Math.round(v * 100) / 100;
export const roundPts = (P) => P.map(([x, y]) => [r2(x), r2(y)]);

// ---------------------------------------------------------------- フキダシの形
// 箱（mm の [x0, y0, x1, y1]）に合わせた外形の多角形。外形は正本に入れる（書き出しは外形を描く）
export const BALLOON_FORMS = [
  ["ellipse", "楕円", "circle"],
  ["rounded", "角丸", "square"],
  ["burst", "叫び", "zap"],
  ["cloud", "もこもこ", "cloud"],
];

export function balloonOutline(form, box, pad) {
  const [x0, y0, x1, y1] = box;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const rx = (x1 - x0) / 2 + pad, ry = (y1 - y0) / 2 + pad;
  const out = [];
  if (form === "rounded") {
    const r = Math.min(rx, ry) * 0.35;
    const corners = [[cx + rx - r, cy - ry + r, -90], [cx + rx - r, cy + ry - r, 0], [cx - rx + r, cy + ry - r, 90], [cx - rx + r, cy - ry + r, 180]];
    for (const [ox, oy, a0] of corners) for (let k = 0; k <= 6; k++) {
      const a = ((a0 + (k * 90) / 6) * Math.PI) / 180;
      out.push([ox + r * Math.cos(a), oy + r * Math.sin(a)]);
    }
    return roundPts(out);
  }
  const n = form === "burst" ? 28 : form === "cloud" ? 72 : 48;
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    let k = 1;
    if (form === "burst") k = i % 2 ? 0.78 : 1.12;
    if (form === "cloud") k = 1 + 0.07 * Math.abs(Math.sin(a * 5));
    out.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]);
  }
  return roundPts(out);
}

// しっぽ：外形の真ん中から先へ向かう、根元の幅 baseW・曲がり bend（しっぽの長さとの比）の形。
// 書き出しの描き方（サーバー）と同じかは未検証。画面では外形の縁から先までの三角に近い形で見せる
export function tailPolygon(outline, target, baseW, bend) {
  if (!target || !baseW) return null;
  const [cx, cy] = centroid(outline);
  const dx = target[0] - cx, dy = target[1] - cy;
  const len = Math.hypot(dx, dy);
  if (len < EPS) return null;
  const ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
  const b1 = [cx + nx * baseW / 2, cy + ny * baseW / 2], b2 = [cx - nx * baseW / 2, cy - ny * baseW / 2];
  const pts = [b1];
  const steps = 8;
  for (let i = 1; i < steps; i++) {
    const t = i / steps;
    const off = Math.sin(t * Math.PI) * (bend || 0) * len;
    const w = (1 - t) * baseW / 2;
    pts.push([cx + dx * t + nx * (w + off), cy + dy * t + ny * (w + off)]);
  }
  pts.push(target);
  for (let i = steps - 1; i >= 1; i--) {
    const t = i / steps;
    const off = Math.sin(t * Math.PI) * (bend || 0) * len;
    const w = (1 - t) * baseW / 2;
    pts.push([cx + dx * t - nx * (w - off), cy + dy * t - ny * (w - off)]);
  }
  pts.push(b2);
  return pts;
}

// 行列 [a,b,c,d,e,f]（fabric と同じ並び）で点を写す
export function apply(m, [x, y]) { return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]; }
