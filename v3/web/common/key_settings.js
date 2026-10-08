// キーを変える画面（V3細部の決めごと 22.4）。画面どうしをつなぐ帯の「キー」と、キーの一覧の「キーを変える」から開く。
// - 全部の画面の操作を、効く所ごとに出す（common/key_catalog.js の全部）
// - 「足す」を押してからキーを押すと割り当てる（Esc でやめる）。重なる相手があれば、その場で出し、
//   「相手から外して割り当てる」か「やめる」を選ぶ（Photoshop・Krita の、重なりをその場で知らせて選ばせるやり方）
// - 残す先はサーバーの利用者ごとの設定（/me/settings の other.keymap）。どのブラウザでも同じ割り当てになる
// - 初めに戻す（1つずつ・全部）。今のアプリ（js/shortcut.js）のキーを読み込む（違う物だけを並べ、選んで読み込む）
import { html, render, nothing } from "../vendor/lit-html-3.2.1/lit-html.js";
import { live } from "../vendor/lit-html-3.2.1/directives/live.js";
import * as km from "./keymap.js";
import { CURRENT_APP_NOT_MAPPED } from "./key_catalog.js";
import { icon } from "./shell.js";
import * as api from "../js/api.js";

let dlg = null;
const S = { query: "", rec: null, conflict: null, importing: false, busy: false, error: null };

function scopeOrder() {
  const here = km.currentScreen();
  const all = Object.keys(km.SCOPES);
  // 今の画面を先に出す
  return [...all.filter((s) => s === "global" || s === here || s.startsWith(`${here}:`)), ...all.filter((s) => !(s === "global" || s === here || s.startsWith(`${here}:`)))];
}
function match(k) {
  const q = S.query.trim().toLowerCase();
  return !q || k.label.toLowerCase().includes(q) || km.keyLabels(k.id).some((l) => l.toLowerCase().includes(q)) || (km.SCOPES[k.scope] ?? "").includes(q);
}

async function act(fn) {
  S.busy = true; S.error = null; draw();
  try { await fn(); } catch (e) { console.error(e); S.error = `残せませんでした：${api.errorText(e)}`; }
  S.busy = false; draw();
}

function startRec(id) {
  if (S.rec) km.suspend(false);
  S.rec = { id }; S.conflict = null; km.suspend(true); draw();
  dlg.querySelector(`[data-id="${id}"] .v3-rec`)?.focus();
}
function stopRec() { if (S.rec) km.suspend(false); S.rec = null; draw(); }

function onRecKey(e) {
  if (!S.rec) return;
  const k = km.entry(S.rec.id);
  // 押している間の物は、修飾キーだけ（Alt など）も受ける。修飾キーは離したときに決める
  const str = km.keyFromEvent(e, false);
  if (!str) return;
  e.preventDefault(); e.stopPropagation();
  if (str === "Escape") { stopRec(); return; }
  assign(k.id, str);
}
function onRecKeyUp(e) {
  if (!S.rec || !km.entry(S.rec.id).hold) return;
  const str = km.keyFromEvent(e, true);
  if (!["Alt", "Shift", "Control", "Meta"].includes(str)) return;
  e.preventDefault(); e.stopPropagation();
  assign(S.rec.id, str);
}
function assign(id, str) {
  const keys = km.keysOf(id);
  if (keys.some((x) => km.normalize(x) === km.normalize(str))) { stopRec(); return; }
  const others = km.conflicts(id, str);
  km.suspend(false); S.rec = null;
  if (others.length) { S.conflict = { id, key: str, others }; draw(); return; }
  act(() => km.setKeys(id, [...keys, str]));
}
function takeOver() {
  const { id, key, others } = S.conflict;
  const map = { [id]: [...km.keysOf(id), key] };
  for (const o of others) map[o.id] = km.keysOf(o.id).filter((x) => !clashes(x, key));
  S.conflict = null;
  act(() => km.setMany(map));
}
function clashes(a, b) {
  const x = km.normalize(a), y = km.normalize(b);
  return x === y || x.startsWith(`${y} `) || y.startsWith(`${x} `);
}

function importRows() {
  return km.KEYS.filter((k) => k.current && !k.current.every((c) => km.keysOf(k.id).some((x) => km.normalize(x) === km.normalize(c))));
}
function doImport() {
  const map = {};
  for (const k of importRows()) map[k.id] = [...km.keysOf(k.id), ...k.current.filter((c) => !km.keysOf(k.id).some((x) => km.normalize(x) === km.normalize(c)))];
  // 読み込んだキーどうし・今の割り当てとの重なりは、読み込んだ後の「重なっているキー」に出す
  S.importing = false;
  act(() => km.setMany(map));
}

function row(k) {
  const keys = km.keysOf(k.id);
  const rec = S.rec?.id === k.id;
  const cf = S.conflict?.id === k.id ? S.conflict : null;
  return html`<tr data-id=${k.id} class=${rec ? "rec" : ""}>
    <td class="v3-ks-l">${k.label}${k.hold ? html` <span class="flag mut">押している間</span>` : nothing}${km.isCustom(k.id) ? html` <span class="flag ai">変えた</span>` : nothing}
      ${cf ? html`<div class="note bad v3-conflict" role="alert">${icon("triangle-alert")}<span><kbd>${km.keyLabel(cf.key)}</kbd> は
        ${cf.others.map((o, i) => html`${i ? "・" : ""}「${o.label}」（${km.SCOPES[o.scope]}）`)} と重なります。
        <span class="acts"><button class="btn sm" id="v3-ks-take" @click=${takeOver}>相手から外して割り当てる</button>
        <button class="btn ghost sm" @click=${() => { S.conflict = null; draw(); }}>やめる</button></span></span></div>` : nothing}</td>
    <td class="v3-ks-k">${keys.map((x) => html`<span class="v3-chip"><kbd>${km.keyLabel(x)}</kbd><button class="ibtn" title="外す" aria-label="${km.keyLabel(x)} を外す"
        ?disabled=${S.busy} @click=${() => act(() => km.setKeys(k.id, keys.filter((y) => y !== x)))}>${icon("x")}</button></span>`)}
      ${rec ? html`<button class="btn sm ai v3-rec" @keydown=${onRecKey} @keyup=${onRecKeyUp} @blur=${stopRec}>キーを押してください（Esc でやめる）</button>`
        : html`<button class="btn ghost sm" data-add ?disabled=${S.busy} @click=${() => startRec(k.id)}>${icon("plus")}足す</button>`}
      ${km.isCustom(k.id) ? html`<button class="btn ghost sm" data-reset ?disabled=${S.busy} @click=${() => act(() => km.setKeys(k.id, km.entry(k.id).keys))}>${icon("rotate-ccw")}初めに戻す</button>` : nothing}</td></tr>`;
}

function draw() {
  const st = km.userKeysState();
  const conflicts = km.allConflicts();
  const imp = importRows();
  render(html`
    <div class="v3-dlg-h"><span class="h2 grow" id="v3-ks-title">キーを変える</span>
      <button class="btn sm" @click=${() => dlg.close()}>${icon("x")}閉じる</button></div>
    <div class="v3-dlg-b">
      <p class="meta">割り当ては利用者ごとにサーバーへ残します（どのブラウザで開いても同じです）。「足す」を押してからキーを押します。
        ${km.IS_MAC ? "⌘ は Cmd です。" : "Mac で開くと Ctrl の所は ⌘（Cmd）になります。"}</p>
      ${st.why ? html`<div class="note need">${icon("triangle-alert")}<span>${st.why}</span></div>` : nothing}
      ${S.error ? html`<div class="note bad" role="alert">${icon("circle-alert")}<span>${S.error}</span></div>` : nothing}
      ${conflicts.length ? html`<div class="note bad" id="v3-ks-conflicts">${icon("triangle-alert")}<span>重なっているキーがあります：
        ${conflicts.map(([a, b, s], i) => html`${i ? "、" : ""}<kbd>${km.keyLabel(s)}</kbd>（${a.label}／${b.label}）`)}。先に結ばれた方（道具 → 画面 → どの画面でも）が効きます</span></div>` : nothing}
      <div class="acts">
        <label class="v3-search grow">${icon("search")}<input class="field" type="search" id="v3-ks-q" placeholder="すること・キー・画面で探す" aria-label="操作を探す"
          .value=${live(S.query)} @input=${(e) => { S.query = e.target.value; draw(); }}></label>
        <button class="btn sm" id="v3-ks-import" ?disabled=${S.busy || !imp.length} @click=${() => { S.importing = !S.importing; draw(); }}>${icon("import")}今のアプリのキーを読み込む</button>
        <button class="btn sm" id="v3-ks-reset" ?disabled=${S.busy} @click=${() => { if (confirm("全部の操作のキーを初めの割り当てに戻します。よろしいですか")) act(() => km.resetAll()); }}>${icon("rotate-ccw")}全部を初めに戻す</button>
      </div>
      ${S.importing ? html`<div class="card v3-import" id="v3-ks-import-list"><div class="lbl">今のアプリ（manga-editor-desu の画面）で違うキー</div>
        <table class="keys-t">${imp.map((k) => html`<tr><th>${k.current.map((c) => html`<kbd>${km.keyLabel(c)}</kbd> `)}</th><td>${k.label}（${km.SCOPES[k.scope]}）。今は ${km.keyLabels(k.id).join("・") || "キーなし"}。読み込むと足します</td></tr>`)}</table>
        <div class="meta">${CURRENT_APP_NOT_MAPPED.map((t) => html`<div>${t}</div>`)}</div>
        <div class="acts"><button class="btn primary sm" id="v3-ks-import-go" @click=${doImport}>読み込む</button>
          <button class="btn ghost sm" @click=${() => { S.importing = false; draw(); }}>やめる</button></div></div>` : nothing}
      ${scopeOrder().map((s) => {
        const list = km.KEYS.filter((k) => k.scope === s && match(k));
        return list.length ? html`<section class="v3-keys-g" data-scope=${s}><div class="lbl">${km.SCOPES[s]}</div>
          <table class="keys-t v3-ks">${list.map(row)}</table></section>` : nothing;
      })}
    </div>`, dlg);
}

export function openKeySettings() {
  if (!dlg) {
    dlg = document.createElement("dialog");
    dlg.className = "v3-dlg wide"; dlg.id = "v3-keys"; dlg.setAttribute("aria-labelledby", "v3-ks-title");
    document.body.append(dlg);
    dlg.addEventListener("close", () => { if (S.rec) stopRec(); S.conflict = null; });
    // キーを拾っている間の Esc は、窓を閉じずに「やめる」にする
    dlg.addEventListener("cancel", (e) => { if (S.rec) e.preventDefault(); });
    km.onChange(() => { if (dlg.open) draw(); });
  }
  S.query = ""; S.importing = false; S.error = null;
  draw();
  dlg.showModal();
}
