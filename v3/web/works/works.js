// 作品と話：作品の一覧と作成、話（巻・話・締切）、参加者と役、話ごとの進み具合（V3細部の決めごと 15・16・19章）。
// 口：GET/POST /works、GET /works/{id}、GET /works/{id}/members、GET /works/{id}/progress、
//     操作 add_volume・add_episode・update_episode・set_member
import { t } from "../common/i18n.js";
import { html, render, nothing, api, icon, toast, fail, op, startShell, emptyNote, screenHref,
         ROLE, MEDIUM, READING, TEXT_DIR, REVIEW, episodeName, fmtDate } from "../common/shell.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const dot = (list) => list.join("・");  // i18n:data（区切りの記号）
const S = { workId: null, work: null, members: [], progress: null, why: null, busy: false };
let shell;

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null; S.members = []; S.progress = null;
  if (id) {
    try {
      [S.work, S.members, S.progress] = await Promise.all([
        api.get(`/works/${id}`), api.get(`/works/${id}/members`), api.get(`/works/${id}/progress`)]);
    } catch (e) { fail(e, t("作品を読み込めませんでした")); S.why = api.errorText(e); }
  }
  draw();
}
const reload = () => loadWork(S.workId);

async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; draw(); }
}

// ---------------------------------------------------------------- 作品を作る
function createWork(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = {
    title: f.get("title").trim(), reading_direction: f.get("reading_direction"), text_direction: f.get("text_direction"),
    medium: f.get("medium"), trim_size: f.get("trim_size").trim() || null,
    default_page_count: f.get("default_page_count") ? Number(f.get("default_page_count")) : null,
  };
  if (!body.title) { toast(t("題を入れてください"), "need"); return; }
  run(t("作品を作れませんでした"), async () => {
    const r = await api.post("/works", body);
    e.target.reset();
    toast(t("「{{title}}」を作りました。作った人が作者になります", { title: body.title }));
    shell.setWorks(await api.get("/works"), r.id);
  });
}

const radios = (name, map, cur) => html`<div class="seg" role="radiogroup">${Object.entries(map).map(([v, l]) => html`
  <label class="seg-r"><input type="radio" name=${name} value=${v} ?checked=${v === cur}><span>${l}</span></label>`)}</div>`;

function createCard() {
  return html`<section class="card" aria-label=${t("作品を作る")}>
    <div class="card-h"><span class="h2">${t("作品を作る")}</span></div>
    <form class="form" @submit=${createWork}>
      <span class="k">${t("題")}</span><input class="field" name="title" required>
      <span class="k">${t("媒体")}</span>${radios("medium", MEDIUM, "paper")}
      <span class="k">${t("読む向き")}</span>${radios("reading_direction", READING, "rtl")}
      <span class="k">${t("文字の向き")}</span>${radios("text_direction", TEXT_DIR, "vertical")}
      <span class="k">${t("判型")}</span><input class="field" name="trim_size" placeholder=${t("例：B5")}>
      <span class="k">${t("1話のページ数")}</span><input class="field" name="default_page_count" type="number" min="1">
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("plus")}${t("作る")}</button>
        <span class="meta">${t("ページの寸法・入稿の設定は「企画」で決めます")}</span></div>
    </form></section>`;
}

// ---------------------------------------------------------------- 話
function addVolume() {
  const n = Math.max(0, ...S.work.volumes.map((v) => v.number)) + 1;
  run(t("巻を足せませんでした"), async () => { await op(S.workId, { type: "add_volume", number: n }); await reload(); });
}
function addEpisode(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const deadline = f.get("deadline");
  run(t("話を足せませんでした"), async () => {
    await op(S.workId, { type: "add_episode", volume_id: f.get("volume_id"), number: Number(f.get("number")),
                         title: f.get("title").trim() || null, deadline: deadline ? new Date(deadline).toISOString() : null });
    e.target.reset();
    await reload();
  });
}
function setDeadline(ep, value) {
  run(t("締切を変えられませんでした"), async () => {
    await op(S.workId, { type: "update_episode", id: ep.id, deadline: value ? new Date(value).toISOString() : null });
    await reload();
  });
}
const localInput = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};

function progressOf(ep) { return S.progress && S.progress.episodes.find((x) => x.episode_id === ep.id); }

function statusBar(p) {
  const order = ["approved", "in_review", "needs_changes", "draft"];
  const total = p.page_count || 0;
  if (!total) return html`<span class="meta">${t("ページがまだありません")}</span>`;
  return html`<div class="bar" role="img" aria-label=${dot(order.map((s) => `${REVIEW[s]} ${p.pages_by_status[s] || 0}`))}>
    ${order.map((s) => (p.pages_by_status[s] ? html`<span class="s-${s}" style="width:${(p.pages_by_status[s] / total) * 100}%"></span>` : nothing))}</div>`;
}

function episodeRow(ep) {
  const p = progressOf(ep);
  const est = p && p.estimate;
  return html`<div class="card ep" data-episode=${ep.id}>
    <div class="card-h"><span class="h2">${episodeName(ep)}</span>
      ${p && p.overdue ? html`<span class="flag bad">${t("締切を過ぎた")}</span>` : nothing}
      ${est && est.on_track === false ? html`<span class="flag warn">${t("間に合わない見込み")}</span>` : nothing}
      <a class="btn ghost sm" href=${screenHref("structure")}>${icon("layout-grid")}${t("構成")}</a></div>
    <div class="form">
      <span class="k">${t("締切")}</span>
      <input class="field" type="datetime-local" .value=${localInput(ep.deadline)} @change=${(e) => setDeadline(ep, e.target.value)} aria-label=${t("{{name}}の締切", { name: episodeName(ep) })}>
      ${p ? html`
      <span class="k">${t("ページ")}</span>
      <div class="row wrap">${statusBar(p)}<span class="meta num">${t("{{count}} ページ", { count: p.page_count })}　${dot(Object.entries(REVIEW).map(([s, l]) => `${l} ${p.pages_by_status[s] || 0}`))}</span></div>
      <span class="k">${t("確認待ち")}</span>
      <div class="row wrap"><span class="num">${p.pending_review_page_ids.length}</span><span class="meta">${t("ページ")}</span>
        ${p.needs_changes_page_ids.length ? html`<span class="flag warn">${t("直しが要る {{n}}", { n: p.needs_changes_page_ids.length })}</span>` : nothing}
        ${p.pending_review_page_ids.length ? html`<a class="btn ghost sm" href=${screenHref("review")}>${icon("badge-check")}${t("確認する")}</a>` : nothing}</div>
      <span class="k">${t("見込み")}</span>
      <div class="meta">${est.projected_finish ? html`${t("終わる見込み {{date}}（1枚 {{hours}} 時間）", { date: fmtDate(est.projected_finish), hours: Math.round(est.per_page_seconds / 3600 * 10) / 10 })}` : est.reason}
        <br>${est.note}</div>` : nothing}
    </div></div>`;
}

function episodesCard() {
  const w = S.work;
  const vols = [...w.volumes].filter((v) => !v.removed).sort((a, b) => a.number - b.number);
  const eps = w.episodes.filter((e) => !e.removed);
  const nextNo = Math.max(0, ...eps.map((e) => e.number)) + 1;
  return html`<section class="sec" aria-label=${t("話")}>
    <div class="sec-h"><span class="lbl">${t("話")}</span><button class="btn ghost sm" @click=${addVolume} ?disabled=${S.busy}>${icon("plus")}${t("巻を足す")}</button></div>
    ${vols.length ? vols.map((v) => html`<div class="lbl grp">${v.title ? t("第{{number}}巻「{{title}}」", { number: v.number, title: v.title }) : t("第{{number}}巻", { number: v.number })}</div>
      ${eps.filter((e) => e.volume_id === v.id).sort((a, b) => a.number - b.number).map(episodeRow)}`)
      : emptyNote(t("巻がまだありません。話は巻の下に足します。先に「巻を足す」を押してください"))}
    ${vols.length ? html`<form class="card" @submit=${addEpisode} aria-label=${t("話を足す")}>
      <div class="card-h"><span class="h2">${t("話を足す")}</span></div>
      <div class="form">
        <span class="k">${t("巻")}</span><select class="field" name="volume_id">${vols.map((v) => html`<option value=${v.id}>${t("第{{number}}巻", { number: v.number })}</option>`)}</select>
        <span class="k">${t("番号")}</span><input class="field" name="number" type="number" min="1" .value=${String(nextNo)} required>
        <span class="k">${t("題")}</span><input class="field" name="title">
        <span class="k">${t("締切")}</span><input class="field" name="deadline" type="datetime-local">
        <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("plus")}${t("足す")}</button>
          <span class="meta">${t("人物・設定資料の引き継ぎ（決めごと 15章）はサーバーにまだ無いので、この画面ではしません")}</span></div>
      </div></form>` : nothing}
  </section>`;
}

// ---------------------------------------------------------------- 参加者
function setMember(user, role, granted) {
  run(granted ? t("参加者を招待できませんでした") : t("参加者を外せませんでした"), async () => {
    await op(S.workId, { type: "set_member", user, role, granted });
    S.members = await api.get(`/works/${S.workId}/members`);
    toast(granted ? t("{{user}} を{{role}}として招待しました", { user, role: ROLE[role] }) : t("{{user}} の{{role}}を外しました", { user, role: ROLE[role] }));
  });
}
function invite(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const user = f.get("user").trim();
  if (!user) { toast(t("招待する人の名前を入れてください"), "need"); return; }
  setMember(user, f.get("role"), true);
  e.target.reset();
}
function membersCard() {
  return html`<section class="card" aria-label=${t("参加者")}>
    <div class="card-h"><span class="h2">${t("参加者と役")}</span></div>
    <div class="list">${S.members.map((m) => html`<div class="item member"><span class="nm">${m.user}</span>
      <span class="flag mut">${ROLE[m.role] || m.role}</span>
      <button class="ibtn" title=${t("外す")} aria-label=${t("{{user}} の{{role}}を外す", { user: m.user, role: ROLE[m.role] })} @click=${() => setMember(m.user, m.role, false)}>${icon("x")}</button></div>`)}</div>
    <form class="form" @submit=${invite}>
      <span class="k">${t("名前")}</span><input class="field" name="user" autocomplete="off">
      <span class="k">${t("役")}</span><select class="field" name="role">${Object.entries(ROLE).map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select>
      <div class="full acts"><button class="btn" ?disabled=${S.busy}>${icon("user-plus")}${t("招待")}</button>
        <span class="meta">${t("アシスタントが描けるのは、割り当てたページだけです（割り当ては「構成」）")}</span></div>
    </form></section>`;
}

function workCard() {
  const w = S.work.work;
  return html`<section class="card" aria-label=${t("作品")}>
    <div class="card-h"><span class="h1">${w.title}</span>
      ${S.progress ? html`<span class="flag ${S.progress.work_status === "approved" ? "on" : "mut"}">${t("作品 {{status}}", { status: REVIEW[S.progress.work_status] })}</span>` : nothing}
      <a class="btn ghost sm" href=${screenHref("plan")}>${icon("file-text")}${t("企画")}</a></div>
    <div class="meta">${dot([MEDIUM[w.medium], READING[w.reading_direction], TEXT_DIR[w.text_direction], w.trim_size || null,
      w.default_page_count ? t("1話 {{count}} ページ", { count: w.default_page_count }) : null].filter(Boolean))}</div>
    ${episodesCard()}
  </section>`;
}

function draw() {
  render(html`
    <div class="col">${S.work ? workCard() : emptyNote(S.why || t("作品を選んでください"), S.why ? "need" : "")}</div>
    <div class="col">${createCard()}${S.work ? membersCard() : nothing}</div>`, main);
}

shell = await startShell({ screen: "works", onWork: loadWork });
