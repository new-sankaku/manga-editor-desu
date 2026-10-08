// 翻訳：ページごとに、元の文字（作品の言語）と訳文を左右に並べて直す。
// 口：GET /works/{id}（ページ・コマ・文字の並び）、GET /works/{id}/translations?language=（訳文と訳文の無い文字）
//     操作 set_text_translation（足す・変える）・set_text_translation_removed（抜く）。翻訳者の役でも出せる（決めるのはサーバー）
// 訳す言語は ?lang= と localStorage の v3.lang に残す
import { html, render, nothing, live, api, icon, toast, fail, op, startShell, emptyNote, screenHref,
         TEXT_DIR, REVIEW, REVIEW_FLAG, reviewStates, episodePages, storedEpisode, rememberEpisode, episodePicker } from "../common/shell.js";

const main = document.getElementById("main");
const KIND = { balloon: "吹き出し", caption: "ナレーション", drawn_sfx: "描き文字" };
const KIND_ORDER = ["balloon", "caption", "drawn_sfx"];
// 言語の欄の候補。ここに無い言語も手で入れられる（形はサーバーの LANGUAGE_PATTERN と同じ）
const LANG_HINTS = [["en", "英語"], ["zh-Hans", "中国語（簡体）"], ["zh-Hant", "中国語（繁体）"], ["ko", "韓国語"], ["fr", "フランス語"], ["es", "スペイン語"], ["de", "ドイツ語"]];
const FIELD = { text: "訳文", writing_direction: "向き", font_size_pt: "大きさ" };
const LANG_RE = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;
const S = { workId: null, work: null, episodeId: null, lang: storedLang(), tr: null, review: () => "draft",
            drafts: new Map(), onlyMissing: false, saving: new Set(), why: null };

function storedLang() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q) return q;
  try { return localStorage.getItem("v3.lang") || ""; } catch { return ""; }
}
function keepLang(l) {
  try { localStorage.setItem("v3.lang", l); } catch { /* 残せない環境では URL だけ */ }
  const u = new URL(location.href); if (l) u.searchParams.set("lang", l); else u.searchParams.delete("lang");
  history.replaceState(null, "", u);
}

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null; S.drafts.clear();
  if (id) {
    try {
      const [w, recs] = await Promise.all([api.get(`/works/${id}`), api.get(`/works/${id}/review-records`)]);
      S.work = w; S.review = reviewStates(recs);
      S.episodeId = storedEpisode(w); rememberEpisode(S.episodeId);
      await loadTr();
    } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
  }
  draw();
}
async function loadTr() {
  S.tr = null;
  if (!S.lang || !LANG_RE.test(S.lang)) return;
  S.tr = await api.get(`/works/${S.workId}/translations?language=${encodeURIComponent(S.lang)}`);
}
async function setLang(l) {
  l = l.trim();
  if (l && !LANG_RE.test(l)) { toast(`言語の形が正しくありません：${l}（en・zh-Hans のような形）`, "need"); return; }
  S.lang = l; keepLang(l); S.drafts.clear();
  try { await loadTr(); } catch (e) { fail(e, "訳文を読む"); }
  draw();
}

// ページの文字を、コマの順 → 種類 → コマの中の順に並べる
function pageItems(pageId) {
  const panelOrder = new Map(S.work.panels.filter((p) => p.page_id === pageId).map((p) => [p.id, p.order]));
  return S.work.text_items.filter((t) => t.page_id === pageId && !t.removed && panelOrder.has(t.panel_id))
    .sort((a, b) => (panelOrder.get(a.panel_id) - panelOrder.get(b.panel_id))
      || (KIND_ORDER.indexOf(a.item_kind) - KIND_ORDER.indexOf(b.item_kind)) || (a.order - b.order));
}

async function save(item) {
  const cur = S.tr.translations.find((t) => t.text_item_id === item.id);
  const d = S.drafts.get(item.id) || {};
  const body = { type: "set_text_translation", text_item_id: item.id, language: S.lang };
  if (d.text !== undefined && d.text !== (cur?.text ?? "")) body.text = d.text;
  if (d.writing_direction !== undefined && d.writing_direction !== (cur?.writing_direction ?? null)) body.writing_direction = d.writing_direction;
  if (d.font_size_pt !== undefined && d.font_size_pt !== (cur?.font_size_pt ?? null)) body.font_size_pt = d.font_size_pt;
  if (!cur && !body.text) { toast("新しく訳すときは訳文を入れてください", "need"); return; }
  if (body.text === "") { toast("訳文を空にするときは「抜く」を使ってください", "need"); return; }
  if (Object.keys(body).length === 3) { S.drafts.delete(item.id); draw(); return; }
  S.saving.add(item.id); draw();
  try {
    await op(S.workId, body);
    S.drafts.delete(item.id);
    await loadTr();
  } catch (e) { fail(e, "訳文を残す"); } finally { S.saving.delete(item.id); draw(); }
}
async function removeTr(item) {
  const cur = S.tr.translations.find((t) => t.text_item_id === item.id);
  try {
    await op(S.workId, { type: "set_text_translation_removed", id: cur.id, removed: true });
    S.drafts.delete(item.id); await loadTr(); toast("訳文を抜きました");
  } catch (e) { fail(e, "訳文を抜く"); }
  draw();
}
function edit(item, key, value) {
  const d = S.drafts.get(item.id) || {}; d[key] = value; S.drafts.set(item.id, d); draw();
}

function pairRow(item) {
  const cur = S.tr.translations.find((t) => t.text_item_id === item.id);
  const d = S.drafts.get(item.id) || {};
  const text = d.text ?? cur?.text ?? "";
  const dir = d.writing_direction !== undefined ? d.writing_direction : (cur?.writing_direction ?? null);
  const size = d.font_size_pt !== undefined ? d.font_size_pt : (cur?.font_size_pt ?? null);
  const dirty = S.drafts.has(item.id);
  const human = cur?.human_hand_fields?.length ? html`<span class="flag mut" title="人が直した項目">人が直した：${cur.human_hand_fields.map((f) => FIELD[f] || f).join("・")}</span>` : nothing;
  return html`<div class="pair" data-item=${item.id}>
    <div class="v"><div class="row wrap meta"><span class="flag mut">${KIND[item.item_kind] || item.item_kind}</span>${item.speaker ? html`<span>${item.speaker}</span>` : nothing}</div>
      <div class="src" lang=${S.tr.source_language || ""}>${item.text}</div></div>
    <div class="v"><div class="row wrap meta">${cur ? html`<span class="flag on">訳あり</span>` : html`<span class="flag warn">訳なし</span>`}${human}${dirty ? html`<span class="flag ai">まだ残していない</span>` : nothing}</div>
      <textarea class="field" rows="2" lang=${S.lang} aria-label="訳文" .value=${live(text)} @input=${(e) => edit(item, "text", e.target.value)}></textarea>
      <div class="acts">
        <select class="field auto" aria-label="文字の向き" @change=${(e) => edit(item, "writing_direction", e.target.value || null)}>
          <option value="" ?selected=${!dir}>向きは元のまま</option>
          ${Object.entries(TEXT_DIR).map(([k, l]) => html`<option value=${k} ?selected=${dir === k}>${l}</option>`)}</select>
        <input class="field short" type="number" min="1" step="0.5" aria-label="文字の大きさ（pt）" placeholder="pt" .value=${live(size == null ? "" : String(size))}
          @change=${(e) => edit(item, "font_size_pt", e.target.value === "" ? null : Number(e.target.value))}>
        <button class="btn primary sm" data-save ?disabled=${!dirty || S.saving.has(item.id)} @click=${() => save(item)}>${icon("save")}残す</button>
        ${dirty ? html`<button class="btn ghost sm" @click=${() => { S.drafts.delete(item.id); draw(); }}>戻す</button>` : nothing}
        ${cur ? html`<button class="btn ghost sm" @click=${() => removeTr(item)}>${icon("trash-2")}抜く</button>` : nothing}
      </div></div></div>`;
}

function pageCard(page) {
  const items = pageItems(page.id);
  const missing = new Set(S.tr.missing_text_item_ids);
  const shown = S.onlyMissing ? items.filter((i) => missing.has(i.id)) : items;
  const st = S.review("page", page.id);
  const done = items.filter((i) => !missing.has(i.id)).length;
  return html`<section class="card" data-page=${page.id} aria-label=${`${page.number} ページ`}>
    <div class="card-h"><span class="h2">${page.number} ページ</span>
      <span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span><span class="meta">訳 ${done} / ${items.length}</span>
      <a class="btn ghost sm" href=${screenHref("manuscript")}>${icon("pen-tool")}原稿で見る</a></div>
    ${items.length ? (shown.length ? shown.map(pairRow) : emptyNote("このページは全部訳してあります")) : emptyNote("このページに文字はありません")}
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || "作品を選んでください", S.why ? "need" : ""), main); return; }
  const src = S.work.work.preferences?.language;
  const head = html`<section class="card"><div class="acts">
      ${S.episodeId ? episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; rememberEpisode(id); draw(); }) : nothing}
      <span class="meta">元の言語 ${src || "未設定"}</span>${icon("arrow-right")}
      <input class="field short" id="lang" list="lang-hints" aria-label="訳す言語" placeholder="言語" .value=${live(S.lang)} @change=${(e) => setLang(e.target.value)}>
      <datalist id="lang-hints">${LANG_HINTS.map(([k, l]) => html`<option value=${k}>${l}</option>`)}</datalist>
      <label class="row"><input type="checkbox" .checked=${S.onlyMissing} @change=${(e) => { S.onlyMissing = e.target.checked; draw(); }}>訳の無い文字だけ</label>
      ${S.tr ? html`<span class="meta">この作品で訳の無い文字 ${S.tr.missing_text_item_ids.length}</span>` : nothing}
    </div>
    ${src ? nothing : html`<div class="note need">${icon("triangle-alert")}<span>作品の言語が決まっていません。どれが元の言語か分からないので訳せません。「企画」の決めごとで入れてください</span><a class="btn sm" href=${screenHref("plan")}>企画へ</a></div>`}
    ${src && S.lang === src ? html`<div class="note need">${icon("triangle-alert")}<span>${src} は作品の言語です。元の文字は原稿の画面で直します</span></div>` : nothing}
  </section>`;
  let body = nothing;
  if (!S.episodeId) body = emptyNote("話がまだありません。「作品と話」で足してください");
  else if (!S.lang) body = emptyNote("訳す言語を入れてください");
  else if (S.tr && src && S.lang !== src) {
    const pages = episodePages(S.work, S.episodeId);
    body = pages.length ? pages.map(pageCard) : emptyNote("この話にページがありません");
  }
  render(html`${head}${body}`, main);
}

await startShell({ screen: "translation", onWork: loadWork });
