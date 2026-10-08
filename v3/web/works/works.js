// 作品と話：作品の一覧と作成、話（巻・話・締切）、参加者と役、話ごとの進み具合（V3細部の決めごと 15・16・19章）。
// 口：GET/POST /works、GET /works/{id}、GET /works/{id}/members、GET /works/{id}/progress、
//     操作 add_volume・add_episode・update_episode・set_member
import { html, render, nothing, api, icon, toast, fail, op, startShell, emptyNote, screenHref,
         ROLE, MEDIUM, READING, TEXT_DIR, REVIEW, episodeName, fmtDate } from "../common/shell.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const S = { workId: null, work: null, members: [], progress: null, why: null, busy: false };
let shell;

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null; S.members = []; S.progress = null;
  if (id) {
    try {
      [S.work, S.members, S.progress] = await Promise.all([
        api.get(`/works/${id}`), api.get(`/works/${id}/members`), api.get(`/works/${id}/progress`)]);
    } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
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
  if (!body.title) { toast("題を入れてください", "need"); return; }
  run("作品を作る", async () => {
    const r = await api.post("/works", body);
    e.target.reset();
    toast(`「${body.title}」を作りました。作った人が作者になります`);
    shell.setWorks(await api.get("/works"), r.id);
  });
}

const radios = (name, map, cur) => html`<div class="seg" role="radiogroup">${Object.entries(map).map(([v, l]) => html`
  <label class="seg-r"><input type="radio" name=${name} value=${v} ?checked=${v === cur}><span>${l}</span></label>`)}</div>`;

function createCard() {
  return html`<section class="card" aria-label="作品を作る">
    <div class="card-h"><span class="h2">作品を作る</span></div>
    <form class="form" @submit=${createWork}>
      <span class="k">題</span><input class="field" name="title" required>
      <span class="k">媒体</span>${radios("medium", MEDIUM, "paper")}
      <span class="k">読む向き</span>${radios("reading_direction", READING, "rtl")}
      <span class="k">文字の向き</span>${radios("text_direction", TEXT_DIR, "vertical")}
      <span class="k">判型</span><input class="field" name="trim_size" placeholder="例：B5">
      <span class="k">1話のページ数</span><input class="field" name="default_page_count" type="number" min="1">
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("plus")}作る</button>
        <span class="meta">ページの寸法・入稿の設定は「企画」で決めます</span></div>
    </form></section>`;
}

// ---------------------------------------------------------------- 話
function addVolume() {
  const n = Math.max(0, ...S.work.volumes.map((v) => v.number)) + 1;
  run("巻を足す", async () => { await op(S.workId, { type: "add_volume", number: n }); await reload(); });
}
function addEpisode(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const deadline = f.get("deadline");
  run("話を足す", async () => {
    await op(S.workId, { type: "add_episode", volume_id: f.get("volume_id"), number: Number(f.get("number")),
                         title: f.get("title").trim() || null, deadline: deadline ? new Date(deadline).toISOString() : null });
    e.target.reset();
    await reload();
  });
}
function setDeadline(ep, value) {
  run("締切を変える", async () => {
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
  if (!total) return html`<span class="meta">ページがまだありません</span>`;
  return html`<div class="bar" role="img" aria-label=${order.map((s) => `${REVIEW[s]} ${p.pages_by_status[s] || 0}`).join("・")}>
    ${order.map((s) => (p.pages_by_status[s] ? html`<span class="s-${s}" style="width:${(p.pages_by_status[s] / total) * 100}%"></span>` : nothing))}</div>`;
}

function episodeRow(ep) {
  const p = progressOf(ep);
  const est = p && p.estimate;
  return html`<div class="card ep" data-episode=${ep.id}>
    <div class="card-h"><span class="h2">${episodeName(ep)}</span>
      ${p && p.overdue ? html`<span class="flag bad">締切を過ぎた</span>` : nothing}
      ${est && est.on_track === false ? html`<span class="flag warn">間に合わない見込み</span>` : nothing}
      <a class="btn ghost sm" href=${screenHref("structure")}>${icon("layout-grid")}構成</a></div>
    <div class="form">
      <span class="k">締切</span>
      <input class="field" type="datetime-local" .value=${localInput(ep.deadline)} @change=${(e) => setDeadline(ep, e.target.value)} aria-label="${episodeName(ep)}の締切">
      ${p ? html`
      <span class="k">ページ</span>
      <div class="row wrap">${statusBar(p)}<span class="meta num">${p.page_count} ページ　${Object.entries(REVIEW).map(([s, l]) => `${l} ${p.pages_by_status[s] || 0}`).join("・")}</span></div>
      <span class="k">確認待ち</span>
      <div class="row wrap"><span class="num">${p.pending_review_page_ids.length}</span><span class="meta">ページ</span>
        ${p.needs_changes_page_ids.length ? html`<span class="flag warn">直しが要る ${p.needs_changes_page_ids.length}</span>` : nothing}
        ${p.pending_review_page_ids.length ? html`<a class="btn ghost sm" href=${screenHref("review")}>${icon("badge-check")}確認する</a>` : nothing}</div>
      <span class="k">見込み</span>
      <div class="meta">${est.projected_finish ? html`終わる見込み ${fmtDate(est.projected_finish)}（1枚 ${Math.round(est.per_page_seconds / 3600 * 10) / 10} 時間）` : est.reason}
        <br>${est.note}</div>` : nothing}
    </div></div>`;
}

function episodesCard() {
  const w = S.work;
  const vols = [...w.volumes].filter((v) => !v.removed).sort((a, b) => a.number - b.number);
  const eps = w.episodes.filter((e) => !e.removed);
  const nextNo = Math.max(0, ...eps.map((e) => e.number)) + 1;
  return html`<section class="sec" aria-label="話">
    <div class="sec-h"><span class="lbl">話</span><button class="btn ghost sm" @click=${addVolume} ?disabled=${S.busy}>${icon("plus")}巻を足す</button></div>
    ${vols.length ? vols.map((v) => html`<div class="lbl grp">第${v.number}巻${v.title ? `「${v.title}」` : ""}</div>
      ${eps.filter((e) => e.volume_id === v.id).sort((a, b) => a.number - b.number).map(episodeRow)}`)
      : emptyNote("巻がまだありません。話は巻の下に足します。先に「巻を足す」を押してください")}
    ${vols.length ? html`<form class="card" @submit=${addEpisode} aria-label="話を足す">
      <div class="card-h"><span class="h2">話を足す</span></div>
      <div class="form">
        <span class="k">巻</span><select class="field" name="volume_id">${vols.map((v) => html`<option value=${v.id}>第${v.number}巻</option>`)}</select>
        <span class="k">番号</span><input class="field" name="number" type="number" min="1" .value=${String(nextNo)} required>
        <span class="k">題</span><input class="field" name="title">
        <span class="k">締切</span><input class="field" name="deadline" type="datetime-local">
        <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("plus")}足す</button>
          <span class="meta">人物・設定資料の引き継ぎ（決めごと 15章）はサーバーにまだ無いので、この画面ではしません</span></div>
      </div></form>` : nothing}
  </section>`;
}

// ---------------------------------------------------------------- 参加者
function setMember(user, role, granted) {
  run(granted ? "招く" : "外す", async () => {
    await op(S.workId, { type: "set_member", user, role, granted });
    S.members = await api.get(`/works/${S.workId}/members`);
    toast(granted ? `${user} を${ROLE[role]}として招きました` : `${user} の${ROLE[role]}を外しました`);
  });
}
function invite(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const user = f.get("user").trim();
  if (!user) { toast("招く人の名前を入れてください", "need"); return; }
  setMember(user, f.get("role"), true);
  e.target.reset();
}
function membersCard() {
  return html`<section class="card" aria-label="参加者">
    <div class="card-h"><span class="h2">参加者と役</span></div>
    <div class="list">${S.members.map((m) => html`<div class="item member"><span class="nm">${m.user}</span>
      <span class="flag mut">${ROLE[m.role] || m.role}</span>
      <button class="ibtn" title="外す" aria-label="${m.user} の${ROLE[m.role]}を外す" @click=${() => setMember(m.user, m.role, false)}>${icon("x")}</button></div>`)}</div>
    <form class="form" @submit=${invite}>
      <span class="k">名前</span><input class="field" name="user" autocomplete="off">
      <span class="k">役</span><select class="field" name="role">${Object.entries(ROLE).map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select>
      <div class="full acts"><button class="btn" ?disabled=${S.busy}>${icon("user-plus")}招く</button>
        <span class="meta">アシスタントが描けるのは、割り当てたページだけです（割り当ては「構成」）</span></div>
    </form></section>`;
}

function workCard() {
  const w = S.work.work;
  return html`<section class="card" aria-label="作品">
    <div class="card-h"><span class="h1">${w.title}</span>
      ${S.progress ? html`<span class="flag ${S.progress.work_status === "approved" ? "on" : "mut"}">作品 ${REVIEW[S.progress.work_status]}</span>` : nothing}
      <a class="btn ghost sm" href=${screenHref("plan")}>${icon("file-text")}企画</a></div>
    <div class="meta">${MEDIUM[w.medium]}・${READING[w.reading_direction]}・${TEXT_DIR[w.text_direction]}${w.trim_size ? `・${w.trim_size}` : ""}${w.default_page_count ? `・1話 ${w.default_page_count} ページ` : ""}</div>
    ${episodesCard()}
  </section>`;
}

function draw() {
  render(html`
    <div class="col">${S.work ? workCard() : emptyNote(S.why || "作品を選んでください", S.why ? "need" : "")}</div>
    <div class="col">${createCard()}${S.work ? membersCard() : nothing}</div>`, main);
}

shell = await startShell({ screen: "works", onWork: loadWork });
