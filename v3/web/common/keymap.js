// V3 の全部の画面で共通のキーの受け方（V3細部の決めごと 22章）。キーはここ1か所で受ける。
// - 何のキーが何をするかは key_catalog.js。画面は bind(id, 処理) で処理を結ぶだけ
// - キーの書き方と1回の押し方の照合は tinykeys 3.0.0（vendor/tinykeys-3.0.0）の parseKeybinding・matchKeyBindingPress。
//   "$mod" は Windows・Linux で Ctrl、Mac で Cmd（tinykeys が navigator.platform で決める）
// - 効く順：今の道具（"画面:道具"）→ 画面 → どの画面でも。処理が false を返したら次の候補へ回す（Esc の順など）
// - 文字を打っている間（IME の変換中：isComposing か keyCode 229）は何も効かない。入力の欄の中では where が
//   "input"・"any" の物だけが効く
// - 利用者が変えたキーは、サーバーの利用者ごとの設定（GET・PUT /me/settings の other.keymap）に残す
import { parseKeybinding, matchKeyBindingPress } from "../vendor/tinykeys-3.0.0/tinykeys.modern.js";
import { KEYS, SCOPES } from "./key_catalog.js";
import * as api from "../js/api.js";

export { KEYS, SCOPES };
export const IS_MAC = /Mac|iPod|iPhone|iPad/.test(navigator.platform);
const BY_ID = new Map(KEYS.map((k) => [k.id, k]));
const FIELD = "input,textarea,select,[contenteditable]:not([contenteditable=false])";
const MODS = ["Control", "Meta", "Alt", "Shift"];
const SEQ_MS = 1000;

const handlers = new Map();      // id → 処理（hold の物は { down, up }）
let screen = null, tool = null;
let overrides = {};              // id → [キー]（初めの割り当てと違う物だけ）
let userState = { loaded: false, why: "まだ読んでいません" };
let pending = null, pendingTimer = 0;
const held = new Map();          // e.code → 押している間の項目
let suspended = 0;               // キーを変える画面がキーを拾っている間は 1 以上
const watchers = new Set();

export function entry(id) {
  const k = BY_ID.get(id);
  if (!k) throw new Error(`キーの一覧（common/key_catalog.js）に ${id} がありません`);
  return k;
}
export function keysOf(id) { return overrides[id] ?? entry(id).keys; }
export function isCustom(id) { return Object.hasOwn(overrides, id); }
export function isBound(id) { return handlers.has(id); }
export function currentScreen() { return screen; }
export function userKeysState() { return userState; }
export function onChange(fn) { watchers.add(fn); return () => watchers.delete(fn); }
function changed() { applyHints(); for (const fn of watchers) fn(); }

// 今効く所（強い順）
export function activeScopes() {
  return [tool && `${screen}:${tool}`, screen, "global"].filter(Boolean);
}

// ---------------------------------------------------------------- 画面から使う
export function start(screenId) {
  if (screen) throw new Error("keymap.start は1つの画面で1回だけ呼ぶ");
  if (!SCOPES[screenId]) throw new Error(`画面 ${screenId} が SCOPES にありません`);
  screen = screenId;
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", releaseAll);
}
// opts.missing：その画面にまだ機能が無く、押すと「まだ無い」と知らせるだけの物（キーの一覧に「まだ無い」と出す）
const missing = new Set();
export function isMissing(id) { return missing.has(id); }
export function bind(id, fn, opts = {}) {
  const k = entry(id);
  if (opts.missing) missing.add(id);
  if (k.hold && (typeof fn.down !== "function" || typeof fn.up !== "function")) throw new Error(`${id} は押している間の物なので { down, up } で結ぶ`);
  handlers.set(id, fn);
  applyHints();
}
// 道具を選んだら呼ぶ（"画面:道具" の項目が効くようになる）。道具の項目が無い画面は呼ばなくてよい
export function setTool(t) { tool = t || null; }
// キーを変える画面がキーを拾う間、ここで受けない
export function suspend(on) { suspended += on ? 1 : -1; if (on) releaseAll(); }

// ---------------------------------------------------------------- 書き方・見せ方
export function normalize(str) {
  return parseKeybinding(str).map(([mods, key]) =>
    [...MODS.filter((m) => mods.includes(m)), String(key).toLowerCase()].join("+")).join(" ");
}
const NAMES = { escape: "Esc", enter: "Enter", space: "Space", tab: "Tab", arrowleft: "←", arrowright: "→", arrowup: "↑",
                arrowdown: "↓", pageup: "PageUp", pagedown: "PageDown", backspace: "Backspace", delete: "Delete",
                home: "Home", end: "End", "-": "−" };
function modName(m) {
  if (m === "$mod") return IS_MAC ? "⌘" : "Ctrl";
  if (m === "Control") return IS_MAC ? "⌃" : "Ctrl";
  if (m === "Meta") return IS_MAC ? "⌘" : "Win";
  if (m === "Alt") return IS_MAC ? "⌥" : "Alt";
  return m;
}
export function keyLabel(str) {
  return str.trim().split(" ").map((press) => {
    const parts = press.split(/\b\+/);
    let key = parts.pop();
    let mods = parts;
    const code = key.match(/^(Key|Digit)(.)$/);
    if (code) key = code[2];
    // 記号は Shift を押して出す配列が多い（? や +）。記号そのものを見せ、Shift は書かない
    if (key.length === 1 && !/[a-z0-9]/i.test(key)) mods = mods.filter((m) => m !== "Shift");
    const shown = NAMES[key.toLowerCase()] ?? (key.length === 1 ? key.toUpperCase() : key);
    return [...mods.map(modName), shown].join("+");
  }).join(" のあと ");
}
// 見せ方が同じキー（"+" と "Shift++" など、配列で Shift が要るかどうかの違い）は1つにまとめる
export function keyGroups(id) {
  const groups = new Map();
  for (const k of keysOf(id)) {
    const label = keyLabel(k);
    if (!groups.has(label)) groups.set(label, { label, keys: [] });
    groups.get(label).keys.push(k);
  }
  return [...groups.values()];
}
export function keyLabels(id) { return keyGroups(id).map((g) => g.label); }

// 押したキーを書き方にする（キーを変える画面）。修飾キーだけのときは、押している間の項目のためにそのまま返す
export function keyFromEvent(e, allowModifierOnly = false) {
  if (MODS.includes(e.key)) return allowModifierOnly ? e.key : null;
  const mods = [];
  if (IS_MAC ? e.metaKey : e.ctrlKey) mods.push("$mod");
  if (IS_MAC && e.ctrlKey) mods.push("Control");
  if (!IS_MAC && e.metaKey) mods.push("Meta");
  if (e.altKey) mods.push("Alt");
  if (e.shiftKey) mods.push("Shift");
  let key = e.key === " " ? "Space" : e.key.length === 1 ? e.key.toLowerCase() : e.key;
  // Mac の Option は文字を変える（⌥+L が ¬ になる）。位置（e.code）で残す
  if (IS_MAC && e.altKey && /^(Key|Digit)/.test(e.code)) key = e.code;
  return [...mods, key].join("+");
}

// ---------------------------------------------------------------- 重なり
function scopesOverlap(a, b) {
  if (a === b || a === "global" || b === "global") return true;
  return a.startsWith(`${b}:`) || b.startsWith(`${a}:`);
}
function whereOverlap(a, b) {
  const w = (k) => k.where || "outside";
  return w(a) === "any" || w(b) === "any" || w(a) === w(b);
}
function clash(a, b) { return a === b || a.startsWith(`${b} `) || b.startsWith(`${a} `); }
// id にキー str を割り当てたときに重なる項目（同じ時に効き、同じキーか、片方が他方の始まりになる続けて押すキー）
export function conflicts(id, str) {
  const me = entry(id), n = normalize(str);
  return KEYS.filter((o) => o.id !== id && scopesOverlap(o.scope, me.scope) && whereOverlap(o, me) && !(o.chain && me.chain)
    && keysOf(o.id).some((k) => clash(normalize(k), n)));
}
// 今の割り当て全体の重なり（[項目, 相手, キー]）
export function allConflicts() {
  const out = [];
  for (const k of KEYS) for (const s of keysOf(k.id)) for (const o of conflicts(k.id, s)) if (k.id < o.id) out.push([k, o, s]);
  return out;
}

// ---------------------------------------------------------------- 利用者ごとの設定（サーバー）
export async function loadUserKeys() {
  overrides = {};
  if (api.mode() !== "oidc" && !api.currentUser()) {
    userState = { loaded: false, why: "利用者の名前が無いので、変えたキーを読めません。初めの割り当てで動いています" };
  } else {
    try {
      const s = await api.get("/me/settings");
      overrides = clean(s.other?.keymap ?? {});
      userState = { loaded: true, why: null };
    } catch (e) {
      userState = { loaded: false, why: `変えたキーを読めませんでした（${api.errorText(e)}）。初めの割り当てで動いています` };
    }
  }
  changed();
}
function clean(map) {
  const out = {};
  for (const [id, keys] of Object.entries(map)) {
    if (!BY_ID.has(id) || !Array.isArray(keys)) continue;   // 一覧から消えた操作は読まない
    out[id] = keys.filter((k) => typeof k === "string" && parseKeybinding(k).length);
  }
  return out;
}
async function save(next) {
  const cur = await api.get("/me/settings");
  await api.put("/me/settings", { language: cur.language, autosave: cur.autosave,
    autosave_interval_seconds: cur.autosave_interval_seconds, other: { ...cur.other, keymap: next } });
  overrides = next;
  userState = { loaded: true, why: null };
  changed();
}
function same(a, b) { return a.length === b.length && a.every((x, i) => normalize(x) === normalize(b[i])); }
// 1つの操作のキーを決めて残す。初めの割り当てと同じなら、変えた印を消す
export function setKeys(id, keys) {
  const next = { ...overrides };
  if (same(keys, entry(id).keys)) delete next[id]; else next[id] = keys;
  return save(next);
}
// まとめて決める（{ id: [キー] }。重なりの相手から外すときなど）
export function setMany(map) {
  const next = { ...overrides };
  for (const [id, keys] of Object.entries(map)) { if (same(keys, entry(id).keys)) delete next[id]; else next[id] = keys; }
  return save(next);
}
export function resetAll() { return save({}); }

// ---------------------------------------------------------------- ボタンにキーを見せる（22.1：指を置くとキーが出る）
// <button data-key="workbench.pen" title="ペン"><kbd></kbd></button> の kbd と title を、今の割り当てで書き直す
export function applyHints(root = document) {
  for (const el of root.querySelectorAll("[data-key]")) {
    const id = el.dataset.key;
    if (!BY_ID.has(id)) continue;
    el.dataset.titleBase ??= el.title;
    const labels = keyLabels(id);
    el.title = labels.length ? `${el.dataset.titleBase} (${labels.join("・")})` : el.dataset.titleBase;
    const kbd = el.querySelector("kbd");
    if (kbd) { kbd.textContent = labels[0] ?? ""; kbd.hidden = !labels.length; }
  }
}

// ---------------------------------------------------------------- 受ける
function candidates(inField) {
  const order = activeScopes();
  return KEYS.filter((k) => handlers.has(k.id) && order.includes(k.scope)
      && (inField ? k.where === "input" || k.where === "any" : k.where !== "input"))
    .sort((a, b) => order.indexOf(a.scope) - order.indexOf(b.scope));
}
function run(k, e) {
  const r = handlers.get(k.id)(e);
  return r !== false;
}
function onKeyDown(e) {
  if (suspended || e.defaultPrevented) return;
  if (e.isComposing || e.keyCode === 229) return;                 // IME の変換中
  // 開いている窓（dialog）の中のキーは、その窓が受ける
  if (e.target instanceof Element && e.target.closest("dialog[open]")) return;
  if (MODS.includes(e.key) && pending) return;                     // 続けて押す途中の Shift などは途切れにしない
  const inField = e.target instanceof Element && !!e.target.closest(FIELD);
  const list = candidates(inField);

  if (pending) {
    const was = pending; pending = null; clearTimeout(pendingTimer);
    const next = [];
    for (const p of was) {
      if (!matchKeyBindingPress(e, p.rest[0])) continue;
      if (p.rest.length === 1) { if (run(p.k, e)) { e.preventDefault(); return; } } else next.push({ k: p.k, rest: p.rest.slice(1) });
    }
    if (next.length) { pending = next; pendingTimer = setTimeout(() => { pending = null; }, SEQ_MS); e.preventDefault(); return; }
  }

  const starts = [];
  for (const k of list) {
    for (const s of keysOf(k.id)) {
      const presses = parseKeybinding(s);
      if (!matchKeyBindingPress(e, presses[0])) continue;
      if (presses.length > 1) { starts.push({ k, rest: presses.slice(1) }); continue; }
      if (k.hold) {
        e.preventDefault();
        if (!held.has(e.code)) { held.set(e.code, k); handlers.get(k.id).down(e); }
        return;
      }
      if (run(k, e)) { e.preventDefault(); return; }
    }
  }
  if (starts.length) { pending = starts; pendingTimer = setTimeout(() => { pending = null; }, SEQ_MS); e.preventDefault(); }
}
function onKeyUp(e) {
  const k = held.get(e.code);
  if (!k) return;
  held.delete(e.code);
  e.preventDefault();
  handlers.get(k.id).up(e);
}
function releaseAll() {
  for (const [code, k] of held) { held.delete(code); handlers.get(k.id).up(null); }
  pending = null;
}
