// 取り込み：今のアプリのプロジェクト（.lz4）を話に取り込み、取り込みの報告（入れた物・形を変えて入れた物・入れられなかった物と理由）を出す。
// 口：POST /works/{id}/episodes/{eid}/current-app-imports（作者だけ）、GET /works/{id}/current-app-imports/{report_id}
// 報告の id は ?report= に残す（開き直しても同じ報告を出す）
import { html, render, nothing, api, icon, toast, fail, startShell, emptyNote, screenHref,
         episodeName, storedEpisode, rememberEpisode, episodePicker, fmtDate } from "../common/shell.js";
import { fieldsHtml, readFields, USAGE_TERMS } from "../common/form_fields.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const STATUS = { mapped: ["そのまま入れた", "on"], converted: ["形を変えて入れた", "ai"], unmapped: ["入れられなかった", "bad"], not_needed: ["要らない", "mut"] };
const S = { workId: null, work: null, episodeId: null, origin: "human_drawn", report: null, filter: new Set(["converted", "unmapped"]), why: null, busy: false };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null;
  if (id) {
    try {
      S.work = await api.get(`/works/${id}`);
      S.episodeId = storedEpisode(S.work); rememberEpisode(S.episodeId);
      const rid = new URLSearchParams(location.search).get("report");
      S.report = rid ? await api.get(`/works/${id}/current-app-imports/${rid}`) : null;
    } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
  }
  draw();
}
function keepReport(id) {
  const u = new URL(location.href);
  if (id) u.searchParams.set("report", id); else u.searchParams.delete("report");
  history.replaceState(null, "", u);
}

async function submit(e) {
  e.preventDefault();
  const f = e.target;
  const file = f.elements.project.files[0];
  if (!file) { toast("今のアプリのプロジェクトのファイルを選んでください", "need"); return; }
  const fd = new FormData();
  fd.append("project", file);
  fd.append("image_origin", S.origin);
  if (S.origin === "imported") {
    const t = readFields(f, USAGE_TERMS, "terms.");
    if (!t) { toast("持ち込んだ絵は、利用規約の要点を入れてください", "need"); return; }
    fd.append("usage_terms", JSON.stringify(Object.fromEntries(Object.entries(t).filter(([, v]) => v !== null))));
  }
  S.busy = true; draw();
  try {
    S.report = await api.postForm(`/works/${S.workId}/episodes/${S.episodeId}/current-app-imports`, fd);
    keepReport(S.report.id);
    toast(`${S.report.page_ids.length} ページを取り込みました`);
    f.reset();
  } catch (err) { fail(err, "取り込み"); } finally { S.busy = false; draw(); }
}

function formCard() {
  const ep = S.work.episodes.find((x) => x.id === S.episodeId);
  return html`<form class="card" @submit=${submit} aria-label="取り込む">
    <div class="card-h"><span class="h2">今のアプリのプロジェクトを取り込む</span></div>
    ${S.work.work.page_spec ? nothing : html`<div class="note need">${icon("triangle-alert")}<span>作品のページの寸法が決まっていません。先に「企画」の決めごとで入れてください</span>
      <a class="btn sm" href=${screenHref("plan")}>企画へ</a></div>`}
    <div class="form">
      <span class="k">話</span>${episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; rememberEpisode(id); draw(); })}
      <label class="k" for="project">ファイル</label><div class="v"><input class="field" id="project" name="project" type="file" accept=".lz4">
        <span class="meta">今のアプリで保存したプロジェクト（.lz4）。ページは${ep ? episodeName(ep) : "この話"}の後ろに足されます</span></div>
      <span class="k">絵の出どころ</span><div class="seg" role="radiogroup">${[["human_drawn", "人が描いた"], ["imported", "持ち込んだ"]].map(([k, l]) => html`
        <button type="button" data-origin=${k} aria-pressed=${String(S.origin === k)} @click=${() => { S.origin = k; draw(); }}>${l}</button>`)}</div>
      ${S.origin === "imported" ? html`<span class="sub-h">利用規約の要点（持ち込んだ絵に付けます）</span>${fieldsHtml(USAGE_TERMS, {}, "terms.")}` : nothing}
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy || !S.work.work.page_spec}>${S.busy ? icon("loader", "spin") : icon("upload")}取り込む</button>
        <span class="meta">取り込みは1つの操作です。作品の出来事から取り消せます</span></div>
    </div></form>`;
}

function reportCard() {
  const r = S.report;
  if (!r) return html`<section class="card">${emptyNote("取り込むと、ここに報告が出ます")}</section>`;
  const c = r.counts;
  const shown = r.entries.filter((e) => S.filter.has(e.status));
  const byPage = new Map();
  for (const e of shown) { if (!byPage.has(e.page_index)) byPage.set(e.page_index, []); byPage.get(e.page_index).push(e); }
  return html`<section class="card" aria-label="取り込みの報告" id="report">
    <div class="card-h"><span class="h2">取り込みの報告</span><span class="meta">${r.source_file_name}・${fmtDate(r.created_at)}・${r.created_by}</span>
      <button class="btn ghost sm" @click=${() => { S.report = null; keepReport(null); draw(); }}>${icon("x")}閉じる</button></div>
    <div class="meta mono">sha256 ${r.source_sha256.slice(0, 16)}…・絵の出どころ ${r.image_origin === "imported" ? "持ち込んだ" : "人が描いた"}</div>
    <div class="row wrap"><span class="flag mut">ページ ${c.pages}</span><span class="flag mut">元の物 ${c.source_objects}</span>
      ${Object.entries(STATUS).map(([k, [l, cls]]) => html`<button class="chip" data-status=${k} aria-pressed=${String(S.filter.has(k))}
        @click=${() => { if (S.filter.has(k)) S.filter.delete(k); else S.filter.add(k); draw(); }}><span class="flag ${cls}">${c[k]}</span>${l}</button>`)}</div>
    ${shown.length ? [...byPage].map(([pi, es]) => html`<div class="lbl grp">元の ${pi + 1} ページ目</div>
      <div class="t-wrap"><table class="t"><tr><th>元の物</th><th>結果</th><th>入れた先</th><th>理由・メモ</th></tr>
      ${es.map((e) => html`<tr data-status=${e.status}><td>${e.object_index == null ? "" : `#${e.object_index} `}${e.source_kind}${e.source_name ? `「${e.source_name}」` : ""}</td>
        <td><span class="flag ${STATUS[e.status][1]}">${STATUS[e.status][0]}</span></td>
        <td class="mono">${e.target_table ? `${e.target_table}${e.target_id ? `:${e.target_id.slice(0, 8)}` : ""}` : ""}</td><td>${e.note}</td></tr>`)}</table></div>`)
      : emptyNote("選んだ結果の物はありません")}
    ${r.page_ids ? html`<div class="acts"><a class="btn sm" href=${screenHref("structure")}>${icon("layout-grid")}構成で見る</a></div>` : nothing}
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || "作品を選んでください", S.why ? "need" : ""), main); return; }
  if (!S.episodeId) { render(emptyNote("話がまだありません。「作品と話」で足してください"), main); return; }
  render(html`<div class="col">${reportCard()}</div><div class="col">${formCard()}</div>`, main);
}

await startShell({ screen: "import", onWork: loadWork });
