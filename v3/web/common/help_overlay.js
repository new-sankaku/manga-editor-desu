// キーの一覧（? で開く。V3細部の決めごと 22.3）。今の画面と道具で効くキーだけを、強い順（道具 → 画面 → どの画面でも）に出す。
// 探す欄で、すること・キーのどちらからでも絞れる。利用者が変えたキーには「変えた」を付ける。
import { html, render, nothing } from "../vendor/lit-html-3.2.1/lit-html.js";
import { live } from "../vendor/lit-html-3.2.1/directives/live.js";
import * as km from "./keymap.js";
import { icon } from "./shell.js";

let dlg = null;
let query = "";

function rows(scope) {
  const q = query.trim().toLowerCase();
  return km.KEYS.filter((k) => k.scope === scope && km.isBound(k.id)).filter((k) => {
    if (!q) return true;
    return k.label.toLowerCase().includes(q) || km.keyLabels(k.id).some((l) => l.toLowerCase().includes(q));
  });
}
function kbds(id) {
  const ls = km.keyLabels(id);
  return ls.length ? ls.map((l) => html`<kbd>${l}</kbd> `) : html`<span class="meta">キーなし</span>`;
}

function draw() {
  const scopes = km.activeScopes();
  const st = km.userKeysState();
  const groups = scopes.map((s) => [s, rows(s)]).filter(([, r]) => r.length);
  render(html`
    <div class="v3-dlg-h"><span class="h2 grow" id="v3-help-title">キーの一覧（${km.SCOPES[km.currentScreen()]}）</span>
      <button class="btn sm" id="v3-help-settings" @click=${openSettings}>${icon("keyboard")}キーを変える</button>
      <button class="btn sm" id="v3-help-close" @click=${() => dlg.close()}>${icon("x")}閉じる</button></div>
    <div class="v3-dlg-b">
      <label class="v3-search">${icon("search")}<input class="field" id="v3-help-q" type="search" placeholder="すること・キーで探す"
        aria-label="キーを探す" .value=${live(query)} @input=${(e) => { query = e.target.value; draw(); }}></label>
      ${st.why ? html`<div class="note need">${icon("triangle-alert")}<span>${st.why}</span></div>` : nothing}
      ${groups.length ? groups.map(([s, r]) => html`<section class="v3-keys-g" data-scope=${s}>
        <div class="lbl">${km.SCOPES[s] ?? s}${s.includes(":") ? "（選んでいる道具）" : ""}</div>
        <table class="keys-t">${r.map((k) => html`<tr data-id=${k.id}><th>${kbds(k.id)}</th>
          <td>${k.label}${k.hold ? html` <span class="flag mut">押している間</span>` : nothing}${km.isMissing(k.id) ? html` <span class="flag warn">この画面にまだ無い</span>` : nothing}${km.isCustom(k.id) ? html` <span class="flag ai">変えた</span>` : nothing}</td></tr>`)}</table>
      </section>`) : html`<p class="meta">「${query}」に合うキーはありません</p>`}
      <p class="meta">${km.IS_MAC ? "⌘ は Cmd、⌥ は Option です。" : "Mac では Ctrl の所が ⌘（Cmd）になります。"}文字を打っている間は、Esc と Ctrl+Enter のような印の付いた物だけが効きます。</p>
    </div>`, dlg);
}

async function openSettings() {
  dlg.close();
  const m = await import("./key_settings.js");
  m.openKeySettings();
}

export function openHelp() {
  if (!dlg) {
    dlg = document.createElement("dialog");
    dlg.className = "v3-dlg"; dlg.id = "v3-help"; dlg.setAttribute("aria-labelledby", "v3-help-title");
    document.body.append(dlg);
    km.onChange(() => { if (dlg.open) draw(); });
  }
  query = "";
  draw();
  dlg.showModal();
  dlg.querySelector("#v3-help-q").focus();
}
export function toggleHelp() { if (dlg?.open) dlg.close(); else openHelp(); }
