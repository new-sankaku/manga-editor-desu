// 確認：ページと作品の確認の状態（下書き・確認待ち・承認・直しが要る）を移し、コメントと記録を見る。
// 口：GET /works/{id}、GET /works/{id}/review-records、操作 set_review_status（取り消しは reverts_record_id）
// 移り方と出せる人はサーバー（operations/review_operations.py）が決める。画面は今の状態から移れる先だけボタンにする
import { html, render, nothing, live, api, icon, toast, fail, op, startShell, emptyNote, screenHref, fmtDate,
         REVIEW, REVIEW_FLAG, reviewStates, episodePages, storedEpisode, rememberEpisode, episodePicker, km, READING } from "../common/shell.js";
import * as view from "../common/fullscreen.js";

const main = document.getElementById("main");
main.className = "screen side-r";
// 今の状態 → [移る先, ボタンの文字, 印, 出す側か決める側か]
const MOVES = {
  draft: [["in_review", "確認に出す", "send", "submit"]],
  in_review: [["approved", "承認する", "check", "decide"], ["needs_changes", "直しを頼む", "message-square-warning", "decide"], ["draft", "出したのを引っ込める", "undo-2", "submit"]],
  needs_changes: [["in_review", "直して出し直す", "send", "submit"]],
  approved: [["draft", "承認を開け直す", "lock-open", "decide"]],
};
const S = { workId: null, work: null, records: [], status: () => "draft", episodeId: null, sel: null, comment: "",
            filter: "all", busy: false, why: null };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null;
  if (id) {
    try {
      S.work = await api.get(`/works/${id}`);
      S.episodeId = storedEpisode(S.work); rememberEpisode(S.episodeId);
      await loadRecords();
      const want = new URLSearchParams(location.search).get("page");
      S.sel = S.work.pages.some((p) => p.id === want) ? { kind: "page", id: want } : { kind: "work", id };
    } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
  }
  draw();
}
async function loadRecords() {
  S.records = await api.get(`/works/${S.workId}/review-records`);
  S.status = reviewStates(S.records);
}
function select(kind, id) {
  S.sel = { kind, id }; S.comment = "";
  const u = new URL(location.href); if (kind === "page") u.searchParams.set("page", id); else u.searchParams.delete("page");
  history.replaceState(null, "", u);
  draw();
}

async function move(to, extra = {}) {
  const { kind, id } = S.sel;
  const comment = S.comment.trim();
  if (to === "needs_changes" && !extra.reverts_record_id && !comment) { toast("何を直すかをコメントに書いてください", "need"); document.getElementById("comment")?.focus(); return; }
  S.busy = true; draw();
  try {
    await op(S.workId, { type: "set_review_status", target_kind: kind, target_id: id, status: to, ...(comment ? { comment } : {}), ...extra });
    S.comment = "";
    await loadRecords();
    toast(extra.reverts_record_id ? "取り消しました" : `「${REVIEW[to]}」にしました`);
  } catch (e) { fail(e, "状態を変える"); } finally { S.busy = false; draw(); }
}

function targetName(kind, id) {
  if (kind === "work") return `作品「${S.work.work.title}」`;
  const p = S.work.pages.find((x) => x.id === id);
  const ep = p && S.work.episodes.find((e) => e.id === p.episode_id);
  return p ? `第${ep?.number ?? "?"}話 ${p.number} ページ` : id;
}

function pageGrid() {
  const pages = episodePages(S.work, S.episodeId);
  const counts = {}; for (const p of pages) { const s = S.status("page", p.id); counts[s] = (counts[s] || 0) + 1; }
  const shown = S.filter === "all" ? pages : pages.filter((p) => S.status("page", p.id) === S.filter);
  return html`<section class="card" aria-label="ページ">
    <div class="card-h"><span class="h2">ページ</span>
      ${episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; rememberEpisode(id); draw(); })}
      <button class="btn sm" id="read-through" data-key="view.focus" title="読み通す" ?disabled=${!pages.length} @click=${() => view.setFocus(true)}>${icon("book-open")}読み通す<kbd></kbd></button></div>
    <div class="acts" role="group" aria-label="状態で絞る">
      <button class="chip" data-filter="all" aria-pressed=${String(S.filter === "all")} @click=${() => { S.filter = "all"; draw(); }}>全部 ${pages.length}</button>
      ${Object.entries(REVIEW).map(([k, l]) => html`<button class="chip" data-filter=${k} aria-pressed=${String(S.filter === k)} @click=${() => { S.filter = k; draw(); }}>
        <span class="flag ${REVIEW_FLAG[k]}">${counts[k] || 0}</span>${l}</button>`)}</div>
    ${pages.length ? (shown.length ? html`<div class="pages">${shown.map((p) => {
      const st = S.status("page", p.id);
      const last = [...S.records].reverse().find((r) => r.target_kind === "page" && r.target_id === p.id && r.comment);
      return html`<button class="pg paper" data-page=${p.id} aria-pressed=${String(S.sel?.kind === "page" && S.sel.id === p.id)} @click=${() => select("page", p.id)}>
        <span class="n">${p.number}</span>
        ${last ? html`<span class="meta" title=${last.comment}>${icon("message-square")} ${last.comment.length > 24 ? `${last.comment.slice(0, 24)}…` : last.comment}</span>` : nothing}
        <span class="tags"><span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span></span></button>`;
    })}</div>` : emptyNote("この状態のページはありません")) : emptyNote("この話にページがありません")}
  </section>`;
}

function workCard() {
  const st = S.status("work", S.workId);
  return html`<section class="card" aria-label="作品の状態">
    <div class="card-h"><span class="h2">作品の状態</span><span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span>
      <button class="btn sm" aria-pressed=${String(S.sel?.kind === "work")} @click=${() => select("work", S.workId)}>${icon("book-open")}作品を選ぶ</button></div>
    <span class="meta">作品を出すのは作者、承認と直しの依頼は作者と編集者。ページを出すのは、そのページを描ける人です</span></section>`;
}

function sidePanel() {
  const { kind, id } = S.sel;
  const st = S.status(kind, id);
  const recs = S.records.filter((r) => r.target_kind === kind && r.target_id === id);
  const lastRec = recs[recs.length - 1];
  return html`<section class="card" aria-label="選んだもの" id="target">
    <div class="card-h"><span class="h2">${targetName(kind, id)}</span><span class="flag ${REVIEW_FLAG[st]}" id="cur-status">${REVIEW[st]}</span></div>
    ${kind === "page" ? html`<div class="acts"><a class="btn ghost sm" href=${screenHref("manuscript")}>${icon("pen-tool")}原稿で見る</a>
      <a class="btn ghost sm" href=${screenHref("translation")}>${icon("languages")}翻訳で見る</a></div>` : nothing}
    <label class="lbl" for="comment">コメント（直しを頼むときは要る）</label>
    <textarea class="field" id="comment" rows="3" .value=${live(S.comment)} @input=${(e) => { S.comment = e.target.value; }}></textarea>
    <div class="acts">${MOVES[st].map(([to, label, ic, side]) => html`<button class="btn ${to === "approved" ? "primary" : ""} sm" data-move=${to}
      title=${side === "decide" ? "決める側（作者・編集者）" : "出す側"} ?disabled=${S.busy} @click=${() => move(to)}>${icon(ic)}${label}</button>`)}</div>
    <div class="sub-h lbl">記録</div>
    ${recs.length ? html`<div class="list" id="records">${[...recs].reverse().map((r) => html`<div class="issue" data-record=${r.id}>
      <span class="flag ${REVIEW_FLAG[r.to_status]}">${REVIEW[r.to_status]}</span>
      <div class="v"><span class="meta">${REVIEW[r.from_status]} → ${REVIEW[r.to_status]}・${r.actor_id}${r.actor_kind === "human" ? "" : `（${r.actor_kind}）`}・${fmtDate(r.created_at)}${r.reverts_record_id ? "・取り消し" : ""}</span>
        ${r.comment ? html`<span>${r.comment}</span>` : nothing}
        ${r === lastRec ? html`<div class="acts"><button class="btn ghost sm" data-undo ?disabled=${S.busy}
          @click=${() => move(r.from_status, { reverts_record_id: r.id })}>${icon("undo-2")}この移りを取り消す</button></div>` : nothing}</div></div>`)}</div>`
      : emptyNote("まだ記録はありません（下書き）")}
  </section>`;
}

// ---------------------------------------------------------------- 読み通す（絵だけのとき。V3細部の決めごと 22.5）
// ページを1枚ずつ大きく出す。← → は作品の読む向きに合わせる（右から左の作品では ← が次）。PageDown・PageUp は向きによらず次・前
function readPages() { return S.work && S.episodeId ? episodePages(S.work, S.episodeId) : []; }
function readIndex() {
  const pages = readPages();
  const i = S.sel?.kind === "page" ? pages.findIndex((p) => p.id === S.sel.id) : -1;
  return i < 0 ? 0 : i;
}
function step(d) {
  if (!view.viewState().focus) return false;
  const pages = readPages();
  const p = pages[readIndex() + d];
  if (p) select("page", p.id);
  return true;
}
const rtl = () => S.work?.work.reading_direction === "rtl";
km.bind("review.next", () => step(1));
km.bind("review.prev", () => step(-1));
km.bind("review.left", () => step(rtl() ? 1 : -1));
km.bind("review.right", () => step(rtl() ? -1 : 1));
window.addEventListener("v3-view", () => draw());

function reader() {
  const pages = readPages();
  if (!pages.length) return emptyNote("この話にページがありません");
  const i = readIndex(), p = pages[i];
  const st = S.status("page", p.id);
  const recs = S.records.filter((r) => r.target_kind === "page" && r.target_id === p.id && r.comment);
  const ep = S.work.episodes.find((e) => e.id === p.episode_id);
  const leftD = rtl() ? 1 : -1;
  const side = (d, ic, key) => html`<button class="ibtn reader-go" data-key=${key} title=${d > 0 ? "次のページ" : "前のページ"} aria-label=${d > 0 ? "次のページ" : "前のページ"}
    ?disabled=${!pages[i + d]} @click=${() => step(d)}>${icon(ic)}</button>`;
  return html`<section class="reader" aria-label="読み通す">
    <div class="reader-h"><span class="h2">第${ep?.number ?? "?"}話 ${p.number} ページ</span><span class="meta">${i + 1} / ${pages.length}・${READING[S.work.work.reading_direction]}</span></div>
    <div class="reader-b">
      ${side(leftD, "chevron-left", "review.left")}
      <div class="reader-page paper" data-page=${p.id}>
        <span class="reader-n">${p.number}</span>
        <span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span>
        ${recs.length ? html`<div class="list">${recs.map((r) => html`<div class="issue"><span class="flag ${REVIEW_FLAG[r.to_status]}">${REVIEW[r.to_status]}</span><div class="v"><span>${r.comment}</span><span class="meta">${r.actor_id}・${fmtDate(r.created_at)}</span></div></div>`)}</div>` : html`<span class="meta">コメントはありません</span>`}
      </div>
      ${side(-leftD, "chevron-right", "review.right")}
    </div>
    <span class="meta">ページの絵を返す口がまだ無いので、番号・状態・コメントを出しています。</span>
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || "作品を選んでください", S.why ? "need" : ""), main); return; }
  if (view.viewState().focus) { main.className = "screen"; render(reader(), main); km.applyHints(main); return; }
  main.className = "screen side-r";
  render(html`<div class="col">${workCard()}${S.episodeId ? pageGrid() : emptyNote("話がまだありません。「作品と話」で足してください")}</div>
    <div class="col">${sidePanel()}</div>`, main);
  km.applyHints(main);
}

await startShell({ screen: "review", onWork: loadWork });
