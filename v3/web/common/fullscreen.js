// 全画面と「絵だけ」（V3細部の決めごと 22.5）。どの画面でも同じ。
// - 絵だけ：パネルを隠し、絵と小さい道具の帯だけを残す。<html data-focus> を付け、[data-v3-panel] を隠す（common/keys.css）。
//   画面ごとの残し方（画像生成の候補の帯・確認の読み通す表示など）は、その画面の CSS と描き方が data-focus を見て決める
// - パネルを一時的に出す：絵だけの間に Tab。<html data-peek> を付ける（Photoshop・CLIP STUDIO PAINT の Tab と同じ考え）
// - 全画面：Fullscreen API（document.documentElement.requestFullscreen）。<html data-fullscreen> は fullscreenchange で
//   付け外しするので、ブラウザの側で抜けても（Esc・F11・ブラウザのボタン）画面の状態は合ったままになる
// - Esc は1回で1つずつ抜ける：道具（画面が先に受ける）→ 絵だけ → 全画面
// - 絵だけかどうかは画面ごとに localStorage の v3.view.<画面> に残す（このブラウザだけの見た目の好み）。
//   全画面は残さない（ブラウザは人の操作の無いときに全画面にさせない）
// - 変わったら window に "v3-view" の出来事を送る（detail：{ focus, peek, fullscreen }）
let screen = null;
const S = { focus: false, peek: false };
const root = document.documentElement;
const KEY = () => `v3.view.${screen}`;

export function viewState() { return { focus: S.focus, peek: S.peek, fullscreen: !!document.fullscreenElement }; }

function apply() {
  root.toggleAttribute("data-focus", S.focus);
  root.toggleAttribute("data-peek", S.focus && S.peek);
  root.toggleAttribute("data-fullscreen", !!document.fullscreenElement);
  drawBar();
  window.dispatchEvent(new CustomEvent("v3-view", { detail: viewState() }));
}

export function startView(screenId) {
  screen = screenId;
  try { S.focus = localStorage.getItem(KEY()) === "focus"; } catch { S.focus = false; /* 読めない環境では毎回パネルを出して始める */ }
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && navigator.keyboard?.unlock) navigator.keyboard.unlock();
    apply();
  });
  apply();
}

export function setFocus(on) {
  S.focus = on; S.peek = false;
  try { localStorage.setItem(KEY(), on ? "focus" : ""); } catch { /* 残せない環境では、この表示の間だけ */ }
  apply();
}
export function toggleFocus() { setFocus(!S.focus); }
// 絵だけでないときは何もしない（false：Tab をふつうの「次の欄へ」に回す）
export function togglePeek() {
  if (!S.focus) return false;
  S.peek = !S.peek; apply();
  return true;
}
export async function toggleFullscreen() {
  if (document.fullscreenElement) { await document.exitFullscreen(); return; }
  await root.requestFullscreen({ navigationUI: "hide" });
  // Chromium は全画面の間 Esc をページへ渡せる（Keyboard Lock。長押しでブラウザが抜ける）。これで Esc の順を守る。
  // ほかのブラウザには無く、そこでは最初の Esc でブラウザが全画面を抜ける（V3細部の決めごと 22.5）
  if (navigator.keyboard?.lock) await navigator.keyboard.lock(["Escape"]).catch((e) => console.warn("Esc をページで受けられません", e));
}
// Esc：絵だけ → 全画面 の順に1つ抜ける。抜けた物が無ければ false
export function exitOne() {
  if (S.focus) { setFocus(false); return true; }
  if (document.fullscreenElement) { document.exitFullscreen(); return true; }
  return false;
}

// ---------------------------------------------------------------- 絵だけ・全画面の間の小さい帯
let bar = null;
function button(id, icon, text, fn) {
  const b = document.createElement("button");
  b.type = "button"; b.className = "v3-viewbar-b"; b.dataset.view = id;
  if (window.lucide) {
    const svg = window.lucide.createElement(window.lucide.icons[icon]);
    svg.classList.add("lucide"); svg.setAttribute("aria-hidden", "true");
    b.append(svg);
  }
  b.append(document.createTextNode(text));
  b.addEventListener("click", fn);
  return b;
}
function drawBar() {
  const st = viewState();
  if (!bar) {
    bar = document.createElement("div");
    bar.className = "v3-viewbar"; bar.setAttribute("role", "toolbar"); bar.setAttribute("aria-label", "表示");
    bar.append(
      button("peek", "PanelsTopLeft", "パネル", () => togglePeek()),
      button("fullscreen", "Fullscreen", "全画面", () => toggleFullscreen()),
      button("exit", "Minimize2", "抜ける", () => exitOne()));
    for (const b of bar.children) {
      b.dataset.key = { peek: "view.peek", fullscreen: "view.fullscreen", exit: "view.exit" }[b.dataset.view];
      b.title = b.textContent;
      b.append(document.createElement("kbd"));
    }
    document.body.append(bar);
  }
  bar.hidden = !(st.focus || st.fullscreen);
  bar.querySelector("[data-view=peek]").hidden = !st.focus;
  bar.querySelector("[data-view=peek]").setAttribute("aria-pressed", String(st.peek));
  bar.querySelector("[data-view=fullscreen]").setAttribute("aria-pressed", String(st.fullscreen));
}
