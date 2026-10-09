// 構成：話ごとのページの並び（台割り）。ページを足す・削除する・戻す・並べ替える、見開きにする・解く、
// ページの種類・色の種類・解像度・ノンブルの出し方、ページの割り当て、締切と見込みの1行（V3細部の決めごと 8・15・19章）。
// API：GET /works/{id}、GET /works/{id}/progress、GET /works/{id}/review-records、
//     操作 add_page・set_removed・assign_page、
//     worktree-agent-a4222899f5500b610 の reorder_pages・add_spread・update_page（page_kind・color_mode・dpi・nombre_display）
import { t } from "../common/i18n.js";
import { html, render, nothing, api, icon, toast, fail, op, startShell, emptyNote, screenHref,
         REVIEW, REVIEW_FLAG, PAGE_KIND, COLOR_MODE, NOMBRE, episodeName, fmtDate,
         reviewStates, episodePages, storedEpisode, rememberEpisode, episodePicker } from "../common/shell.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const S = { workId: null, work: null, progress: null, status: null, episodeId: null, pageId: null, why: null, busy: false };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null;
  if (id) {
    try {
      const [work, progress, records] = await Promise.all([
        api.get(`/works/${id}`), api.get(`/works/${id}/progress`), api.get(`/works/${id}/review-records`)]);
      S.work = work; S.progress = progress; S.status = reviewStates(records);
      S.episodeId = storedEpisode(work);
      rememberEpisode(S.episodeId);
      if (!S.work.pages.some((p) => p.id === S.pageId)) S.pageId = null;
    } catch (e) { fail(e, t("作品を読み込めませんでした")); S.why = api.errorText(e); }
  }
  draw();
}
async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; await loadWork(S.workId); }
}

const pages = () => episodePages(S.work, S.episodeId);
const spreads = () => (S.work.spreads || []).filter((s) => s.episode_id === S.episodeId && !s.removed);
const spreadOf = (pid) => spreads().find((s) => s.first_page_id === pid || s.second_page_id === pid);

function addPage() {
  const n = Math.max(0, ...S.work.pages.filter((p) => p.episode_id === S.episodeId).map((p) => p.number)) + 1;
  run(t("ページを足せませんでした"), async () => { const r = await op(S.workId, { type: "add_page", episode_id: S.episodeId, number: n }); toast(t("{{n}} ページ目を足しました", { n })); return r; });
}
function setRemoved(kind, id, removed, failed, done) {
  run(failed, async () => { await op(S.workId, { type: "set_removed", target_kind: kind, id, removed }); toast(done); });
}
function move(pid, d) {
  const ids = pages().map((p) => p.id);
  const i = ids.indexOf(pid), j = i + d;
  if (j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  run(t("ページを並べ替えられませんでした"), async () => { await op(S.workId, { type: "reorder_pages", episode_id: S.episodeId, page_ids: ids }); });
}
function makeSpread(pid) {
  const ps = pages();
  const i = ps.findIndex((p) => p.id === pid);
  if (i < 0 || i + 1 >= ps.length) { toast(t("次のページがありません"), "need"); return; }
  run(t("見開きにできませんでした"), async () => { await op(S.workId, { type: "add_spread", first_page_id: pid, second_page_id: ps[i + 1].id }); toast(t("見開きにしました")); });
}
function savePage(e, page) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { type: "update_page", id: page.id };
  for (const k of ["page_kind", "color_mode", "nombre_display"]) {
    const v = f.get(k) || null;
    if (v !== (page[k] ?? null)) body[k] = v;
  }
  const dpi = f.get("dpi") ? Number(f.get("dpi")) : null;
  if (dpi !== (page.dpi ?? null)) body.dpi = dpi;
  if (Object.keys(body).length === 2) { toast(t("変わった所がありません")); return; }
  run(t("ページの設定を保存できませんでした"), async () => { await op(S.workId, body); toast(t("ページの設定を保存しました")); });
}
function assign(e, page) {
  e.preventDefault();
  const f = new FormData(e.target);
  const user = f.get("user").trim();
  if (!user) { toast(t("割り当てる人の名前を入れてください"), "need"); return; }
  const assigned = e.submitter && e.submitter.value === "off" ? false : true;
  run(assigned ? t("割り当てられませんでした") : t("割り当てを外せませんでした"), async () => {
    await op(S.workId, { type: "assign_page", page_id: page.id, user, assigned });
    toast(assigned ? t("{{user}} に割り当てました", { user }) : t("{{user}} の割り当てを外しました", { user }));
  });
}

function pageTile(p) {
  const st = S.status("page", p.id);
  const sp = spreadOf(p.id);
  const ep = S.progress.episodes.find((x) => x.episode_id === S.episodeId);
  const late = ep && ep.estimate.late_page_ids.includes(p.id);
  return html`<button class="pg paper" data-page=${p.id} aria-pressed=${String(S.pageId === p.id)} @click=${() => { S.pageId = p.id; draw(); }}>
    <span class="n num">${p.number}</span>
    <span class="tags">
      <span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span>
      ${p.page_kind ? html`<span class="flag mut">${PAGE_KIND[p.page_kind]}</span>` : nothing}
      ${p.color_mode ? html`<span class="flag mut">${COLOR_MODE[p.color_mode]}</span>` : nothing}
      ${sp ? html`<span class="flag ai">${t("見開き")}</span>` : nothing}
      ${late ? html`<span class="flag bad">${t("遅れる見込み")}</span>` : nothing}
    </span></button>`;
}

function headLine() {
  const ep = S.work.episodes.find((e) => e.id === S.episodeId);
  const p = S.progress.episodes.find((x) => x.episode_id === S.episodeId);
  const est = p && p.estimate;
  return html`<div class="row wrap" id="deadline-line">${icon("calendar-clock")}
    <span>${ep.deadline ? t("締切 {{date}}", { date: fmtDate(ep.deadline) }) : t("締切 決めていない")}</span><span class="vsep"></span>
    <span>${est && est.projected_finish ? t("見込み {{date}}", { date: fmtDate(est.projected_finish) }) : (est ? t("見込み {{reason}}", { reason: est.reason }) : t("見込み"))}</span>
    ${est && est.on_track === false ? html`<span class="flag warn">${t("間に合わない見込み")}</span>` : nothing}
    ${p && p.overdue ? html`<span class="flag bad">${t("締切を過ぎた")}</span>` : nothing}
    <span class="meta">${t("見込みの出し方は未検証です")}</span></div>`;
}

function lineup() {
  const ps = pages();
  const removed = episodePages(S.work, S.episodeId, true);
  return html`<section class="card" aria-label=${t("ページの並び")}>
    <div class="card-h"><span class="h2">${t("ページの並び")}</span><span class="meta num">${t("{{count}} ページ", { count: ps.length })}</span>
      ${S.work.work.default_page_count ? html`<span class="meta">${t("（1話の既定 {{n}}）", { n: S.work.work.default_page_count })}</span>` : nothing}
      <button class="btn sm" @click=${addPage} ?disabled=${S.busy}>${icon("plus")}${t("ページを足す")}</button></div>
    ${headLine()}
    ${ps.length ? html`<div class="pages">${ps.map(pageTile)}</div>` : emptyNote(t("この話にはページがまだありません"))}
    ${removed.length ? html`<details class="more"><summary>${icon("chevron-right")}${t("削除したページ {{n}}", { n: removed.length })}</summary>
      <div class="list">${removed.map((p) => html`<div class="item"><span class="nm">${t("{{number}} ページ目", { number: p.number })}</span>
        <button class="btn sm" @click=${() => setRemoved("page", p.id, false, t("ページを戻せませんでした"), t("ページを戻しました"))}>${icon("undo-2")}${t("戻す")}</button></div>`)}</div></details>` : nothing}
  </section>`;
}

function pagePanel() {
  const p = S.work.pages.find((x) => x.id === S.pageId);
  if (!p) return html`<section class="card">${emptyNote(t("ページを押すと、そのページの設定がここに出ます"))}</section>`;
  const ps = pages();
  const i = ps.findIndex((x) => x.id === p.id);
  const sp = spreadOf(p.id);
  const opt = (map, cur) => html`<option value="" ?selected=${cur == null}>${t("（作品の既定）")}</option>${Object.entries(map).map(([k, l]) => html`<option value=${k} ?selected=${cur === k}>${l}</option>`)}`;
  return html`<section class="card" aria-label=${t("ページ {{number}}", { number: p.number })}>
    <div class="card-h"><span class="h2">${t("{{number}} ページ目", { number: p.number })}</span>
      <span class="flag ${REVIEW_FLAG[S.status("page", p.id)]}">${REVIEW[S.status("page", p.id)]}</span></div>
    <div class="acts">
      <button class="btn sm" @click=${() => move(p.id, -1)} ?disabled=${S.busy || i <= 0}>${icon("arrow-left")}${t("前へ")}</button>
      <button class="btn sm" @click=${() => move(p.id, 1)} ?disabled=${S.busy || i < 0 || i >= ps.length - 1}>${icon("arrow-right")}${t("後ろへ")}</button>
      ${sp ? html`<button class="btn sm" @click=${() => setRemoved("spread", sp.id, true, t("見開きを解けませんでした"), t("見開きを解きました"))}>${icon("columns-2")}${t("見開きを解く")}</button>`
           : html`<button class="btn sm" @click=${() => makeSpread(p.id)} ?disabled=${S.busy || i >= ps.length - 1}>${icon("book-open")}${t("次のページと見開きにする")}</button>`}
      <button class="btn ghost sm" @click=${() => setRemoved("page", p.id, true, t("ページを削除できませんでした"), t("ページを削除しました"))} ?disabled=${S.busy}>${icon("trash-2")}${t("削除")}</button>
    </div>
    <form class="form" @submit=${(e) => savePage(e, p)}>
      <span class="sub-h">${t("入稿の形")}</span>
      <label class="k" for="pg-kind">${t("種類")}</label><select class="field" id="pg-kind" name="page_kind">${opt(PAGE_KIND, p.page_kind)}</select>
      <label class="k" for="pg-color">${t("色の種類")}</label><select class="field" id="pg-color" name="color_mode">${opt(COLOR_MODE, p.color_mode)}</select>
      <label class="k" for="pg-dpi">${t("解像度")}</label><input class="field" id="pg-dpi" name="dpi" type="number" min="1" max="2400" .value=${p.dpi ? String(p.dpi) : ""} placeholder=${t("作品の既定")}>
      <label class="k" for="pg-nombre">${t("ノンブル")}</label><select class="field" id="pg-nombre" name="nombre_display">${opt(NOMBRE, p.nombre_display)}</select>
      <div class="full acts"><button class="btn primary sm" ?disabled=${S.busy}>${icon("save")}${t("保存")}</button></div>
    </form>
    <form class="form" @submit=${(e) => assign(e, p)}>
      <span class="sub-h">${t("割り当て（アシスタントが描けるページ）")}</span>
      <label class="k" for="pg-user">${t("名前")}</label><input class="field" id="pg-user" name="user" autocomplete="off">
      <div class="full acts"><button class="btn sm" value="on" ?disabled=${S.busy}>${icon("user-plus")}${t("割り当てる")}</button>
        <button class="btn ghost sm" value="off" ?disabled=${S.busy}>${t("外す")}</button>
        <span class="meta">${t("今の割り当ての一覧を返すAPIがサーバーに無いので、ここには出せません")}</span></div>
    </form>
    <a class="btn ghost sm" href=${`${screenHref("manuscript")}&page=${p.id}`}>${icon("book-open")}${t("原稿で開く")}</a>
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || t("作品を選んでください"), S.why ? "need" : ""), main); return; }
  if (!S.episodeId) {
    render(html`<div class="col">${emptyNote(t("話がまだありません。「作品と話」で巻と話を足してください"))}
      <a class="btn" href=${screenHref("works")}>${icon("library")}${t("作品と話へ")}</a></div>`, main);
    return;
  }
  render(html`<div class="col"><div class="row wrap">${episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; S.pageId = null; rememberEpisode(id); draw(); })}</div>
    ${lineup()}</div><div class="col">${pagePanel()}</div>`, main);
}

await startShell({ screen: "structure", onWork: loadWork });
