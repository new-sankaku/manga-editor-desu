// canvas（fabric.js と 2D の canvas）で描く色を、色の組（common/theme.css の名前）から読む1か所。
// CSS の変数は canvas に効かないので、getComputedStyle で値を読んで渡す。JS に色の値を書かない（test/theme_check.mjs）。
// 名前が組に無いときは止める（色を補わない）。

function raw(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  if (!v) throw new Error(`色の組に --${name} がありません（common/theme.css）`);
  return v;
}

// 色の値を [r, g, b] にする。読み解きは canvas の fillStyle に任せる（#…・rgb()・名前のどれでも同じ形の値に直る）
let probe = null;
export function themeRgb(name) {
  probe ??= document.createElement("canvas").getContext("2d");
  probe.fillStyle = raw(name);
  const s = probe.fillStyle;
  if (s.startsWith("#")) return [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16));
  const m = s.match(/\d+(\.\d+)?/g);
  return m.slice(0, 3).map(Number);
}
export function themeColor(name, alpha = 1) {
  const [r, g, b] = themeRgb(name);
  return `rgba(${r},${g},${b},${alpha})`;
}

// 画像生成の画面（js/stage.js・js/app.js）が絵の上に描く色
export function canvasColors() {
  return {
    mask: themeColor("mask"),               // 囲んだ範囲（マスクの canvas を塗る。送る絵は白に直すので値は送る物に効かない）
    maskLine: themeColor("mask"),           // 多角形・描き足す枠の線
    maskFill: themeColor("mask", 0.15),     // 多角形を描いている途中の中
    extendFill: themeColor("mask", 0.06),   // 描き足す枠の中
    handle: themeColor("on"),               // 枠の角のつまみの縁
    pointer: themeColor("pointer"),         // ペンの先の輪
    protectRgb: themeRgb("protect"),        // 人の手の範囲（api.maskOverlay に渡す [r,g,b]）
  };
}
