// 作品をまたぐ画面（作品と話・企画・構成・設定資料・書き出し・生成サービス・取り込み・翻訳・確認）で共通の部品。
// - 上の帯：画面の名前・作品を選ぶ欄・利用者の欄（利用者は画像生成の画面と同じ localStorage の v3.user。js/api.js）
// - 描き方は lit-html（vendor/lit-html-3.2.1）。画面ごとに状態を持ち、変わったら draw() で全体を描き直す
// - 正本を変えるのは操作の窓口（POST /works/{id}/ops）だけ。op() はその薄い包み
import { html, render, nothing } from "../vendor/lit-html-3.2.1/lit-html.js";
import { live } from "../vendor/lit-html-3.2.1/directives/live.js";
import { repeat } from "../vendor/lit-html-3.2.1/directives/repeat.js";
import * as api from "../js/api.js";
import { SCREENS, storedWork, rememberWork, screenHref } from "./nav.js";

export { html, render, nothing, live, repeat, api, screenHref };

// lucide の印を1つ作る（lit-html の中に置く）。名前は lucide の名前（file-text など）
export function icon(name, cls = "") {
  const key = name.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase());
  const node = window.lucide.icons[key];
  if (!node) throw new Error(`lucide に ${name} が無い`);
  const svg = window.lucide.createElement(node);
  svg.classList.add("lucide");
  if (cls) for (const c of cls.split(" ")) svg.classList.add(c);
  svg.setAttribute("aria-hidden", "true");
  return svg;
}

// ---------------------------------------------------------------- 知らせ（画像生成の画面の toast と同じ見た目）
export function toast(msg, kind = "") {
  const t = document.getElementById("toast");
  const ic = kind === "bad" ? "circle-alert" : kind === "need" ? "triangle-alert" : "info";
  render(html`<div class="note ${kind}" role="status">${icon(ic)}<span>${msg}</span></div>`, t);
  clearTimeout(toast.h);
  toast.h = setTimeout(() => render(nothing, t), kind === "bad" ? 9000 : 4000);
}
// what：何をしようとして失敗したか。理由と一緒に出す
export function fail(e, what = "") {
  console.error(e);
  toast(what ? `${what}できませんでした：${api.errorText(e)}` : api.errorText(e), "bad");
}

// js/api.js に無い PUT・PATCH（つなぎ先と送り先）と、ファイルを取る GET。失敗の形は api.js と同じ（ApiError・NetworkError）
export async function send(method, path, json) {
  const r = await raw(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(json) });
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}
export async function raw(path, init = {}) {
  const user = api.currentUser();
  if (!user) throw new api.ApiError(401, "利用者の名前を入れてください");
  let r;
  try {
    r = await fetch(path, { ...init, headers: { ...(init.headers || {}), "X-V3-User": user } });
  } catch {
    throw new api.NetworkError("サーバーにつながりません。サーバーが止まっているか、回線が切れています");
  }
  if (!r.ok) {
    const text = await r.text();
    let detail = `${r.status} ${text}`;
    try { const d = JSON.parse(text); if (d.detail !== undefined) detail = d.detail; } catch { /* JSON でない答えは文のまま出す */ }
    throw new api.ApiError(r.status, detail);
  }
  return r;
}

// 正本を変える操作。返り値は { event_id, seq, held_changes }
export function op(workId, body) { return api.op(workId, body); }

// ---------------------------------------------------------------- 言葉
export const ROLE = { author: "作者", editor: "編集者", assistant: "アシスタント", client: "依頼主", translator: "翻訳者", viewer: "見るだけ" };
export const MEDIUM = { paper: "紙", web_page: "Webのページ型", vertical_scroll: "縦読み" };
export const READING = { rtl: "右から左", ltr: "左から右" };
export const TEXT_DIR = { vertical: "縦書き", horizontal: "横書き" };
export const REVIEW = { draft: "下書き", in_review: "確認待ち", approved: "承認", needs_changes: "直しが要る" };
export const REVIEW_FLAG = { draft: "mut", in_review: "ai", approved: "on", needs_changes: "warn" };
export const PAGE_KIND = { cover: "表紙", color_page: "カラー", body: "本文", blank: "白ページ" };
export const COLOR_MODE = { bilevel: "白黒2階調", grayscale: "グレー", color: "カラー" };
export const NOMBRE = { visible: "見せる", hidden: "隠し", none: "出さない" };
export const YNU = { yes: "はい", no: "いいえ", unknown: "未確認" };

export function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
// 話の名前（第3話「霧の夜」）
export function episodeName(ep) { return `第${ep.number}話${ep.title ? `「${ep.title}」` : ""}`; }

// ---------------------------------------------------------------- 上の帯
// opts.screen：nav.js の SCREENS の id。opts.needsWork：作品を選ぶ欄を出すか。
// opts.onWork(workId)：作品・利用者が変わったら呼ぶ。workId が無いとき（作品が無い・選べない）は null
export async function startShell({ screen, needsWork = true, onWork }) {
  const s = SCREENS.find((x) => x.id === screen);
  document.title = `V3 ${s.label}`;
  const top = document.getElementById("top");
  const state = { works: [], workId: null, error: null };
  const drawTop = () => render(html`
    <div class="brand"><span class="mark">${icon(s.icon)}</span><span>${s.label}</span></div>
    ${needsWork ? html`<nav class="pickers" aria-label="作品">
      <select id="pick-work" class="field" aria-label="作品" @change=${(e) => pick(e.target.value)}>
        ${state.works.length ? nothing : html`<option value="">作品がありません</option>`}
        ${state.works.map((w) => html`<option value=${w.id} ?selected=${w.id === state.workId}>${w.title}</option>`)}
      </select>
      <a class="btn ghost sm" href=${screenHref("works", "")}>${icon("plus")}作品を作る</a></nav>` : html`<span class="grow"></span>`}
    <label class="who">利用者 <input id="user" class="field" autocomplete="username" .value=${live(api.currentUser())}
      @change=${(e) => { api.setUser(e.target.value.trim()); load(); }}></label>`, top);

  async function pick(id) {
    state.workId = id || null;
    rememberWork(state.workId);
    drawTop();
    await onWork(state.workId);
  }
  async function load() {
    drawTop();
    if (!api.currentUser()) { await onWork(null, "利用者の名前を入れてください（右上の欄）"); return; }
    if (!needsWork) { await onWork(null); return; }
    try {
      state.works = await api.get("/works");
    } catch (e) { fail(e, "作品の一覧を読む"); await onWork(null, api.errorText(e)); return; }
    const want = storedWork();
    state.workId = state.works.some((w) => w.id === want) ? want : (state.works[0] ? state.works[0].id : null);
    rememberWork(state.workId);
    drawTop();
    await onWork(state.workId, state.works.length ? null : "見てよい作品がありません。「作品と話」で作るか、作者に招いてもらってください");
  }
  await load();
  return { reload: load, setWorks: (works, id) => { state.works = works; pick(id); } };
}

// 確認の記録（GET /works/{id}/review-records。古い順）から、対象ごとの今の状態を出す。記録の無い対象は下書き
export function reviewStates(records) {
  const m = new Map();
  for (const r of records) m.set(`${r.target_kind}:${r.target_id}`, r.to_status);
  return (kind, id) => m.get(`${kind}:${id}`) || "draft";
}
// 話の抜いていないページ（番号の順）
export function episodePages(work, episodeId, removed = false) {
  return work.pages.filter((p) => p.episode_id === episodeId && p.removed === removed).sort((a, b) => a.number - b.number);
}
// 話を選ぶ欄の値（?episode= と localStorage の v3.episode）
export function storedEpisode(work) {
  const eps = work.episodes.filter((e) => !e.removed).sort((a, b) => a.number - b.number);
  let want = new URLSearchParams(location.search).get("episode");
  if (!want) { try { want = localStorage.getItem("v3.episode"); } catch { want = null; } }
  return (eps.find((e) => e.id === want) || eps[0] || null)?.id || null;
}
export function rememberEpisode(id) {
  try { localStorage.setItem("v3.episode", id || ""); } catch { /* 残せない環境では URL だけ */ }
  const u = new URL(location.href);
  if (id) u.searchParams.set("episode", id); else u.searchParams.delete("episode");
  history.replaceState(null, "", u);
}
export function episodePicker(work, current, onPick) {
  const eps = work.episodes.filter((e) => !e.removed).sort((a, b) => a.number - b.number);
  return html`<select class="field" id="pick-episode" aria-label="話" @change=${(e) => onPick(e.target.value)}>
    ${eps.map((e) => html`<option value=${e.id} ?selected=${e.id === current}>${episodeName(e)}</option>`)}</select>`;
}

// <img data-thumb="/works/…/thumbnail?size=…"> を、利用者の見出しつきで取って出す（js/api.js の showIn）。描いた後に呼ぶ
export function loadThumbs(root = document) {
  for (const img of root.querySelectorAll("img[data-thumb]")) {
    if (img.dataset.loaded === img.dataset.thumb) continue;
    img.dataset.loaded = img.dataset.thumb;
    api.showIn(img, img.dataset.thumb).catch((e) => { img.alt = `読めませんでした：${api.errorText(e)}`; });
  }
}

// 中身が無いとき・読めないときの1枚
export function emptyNote(text, kind = "") {
  return html`<div class="note ${kind}">${icon(kind === "bad" ? "circle-alert" : "info")}<span>${text}</span></div>`;
}
