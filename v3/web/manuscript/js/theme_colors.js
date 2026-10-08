// canvas（Fabric）に塗る画面の色を、common/theme.css の色の組から読む所。原稿の画面で色を読むのはここだけ。
// 色の組を差し替えたら readTheme() を呼び直し、描き直す（PageView.retheme）。
// 紙の上の色（紙・裁ち落としの外・紙の縁・文字）は .paper の組（theme.css の「紙の物」）から読む。
// 原稿のデータとしての色（フキダシの線の黒・塗りの白など、書き出しに入る色）は画面の色ではないので print_colors.js に置く。

// 画面の色：役目 → 色の組の名前
const SCREEN = { ai: "--ai", aiLine: "--ai-line", need: "--need", badLine: "--bad-line", on: "--on" };
// 紙の上の色
const PAPER = { paper: "--surface", pasteboard: "--bg", edge: "--line-2", ink: "--ink" };

export const C = {};

function readFrom(el, names) {
  const cs = getComputedStyle(el);
  for (const [k, name] of Object.entries(names)) {
    const v = cs.getPropertyValue(name).trim();
    if (!v) throw new Error(`色の組に ${name} がありません（common/theme.css）`);
    C[k] = v;
  }
}

// host：原稿の画面の中の要素。紙の組を読むため、.paper を付けた見えない要素をその下に置く
export function readTheme(host) {
  readFrom(document.documentElement, SCREEN);
  let probe = host.querySelector(":scope > .paper.theme-probe");
  if (!probe) {
    probe = document.createElement("div");
    probe.className = "paper theme-probe";
    probe.hidden = true;
    host.append(probe);
  }
  readFrom(probe, PAPER);
  return C;
}

// 色の組の色（#RRGGBB）に透けを付ける。色の組が #RRGGBB でなければ止める（別の書き方を黙って読み違えないため）
export function alpha(color, a) {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) throw new Error(`透けを付けられない色の書き方：${color}`);
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
