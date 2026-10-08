// 書き出し：ページを選び、形式（PNG・PDF・PSD）・見開きの出し方・言語・解像度を決め、色の種類をページに決める。
// 先に入稿前の確かめを走らせて問題を出し、そのあと書き出しの進み具合とファイルを出す（V3細部の決めごと 7・13章）。
// 口：GET /works/{id}、GET /works/{id}/review-records、POST /works/{id}/exports、GET /works/{id}/exports/{run}、
//     GET /works/{id}/exports/{run}/files/{name}、POST /works/{id}/preflight、操作 update_page（color_mode）
import { pollMs } from "../common/poll_interval.js";
import { html, render, nothing, api, icon, toast, fail, op, raw, startShell, emptyNote, screenHref,
         REVIEW, REVIEW_FLAG, COLOR_MODE, episodeName, reviewStates, episodePages, storedEpisode, rememberEpisode,
         episodePicker } from "../common/shell.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const FORMAT = { png: "PNG", pdf: "PDF", psd: "PSD（層を分ける）" };
const SPREAD = { split: "1ページずつ", joined: "見開きを1枚に", both: "両方" };
const RUN = { queued: "順番待ち", running: "書き出している", done: "できた", failed: "止まった" };
const KIND = { settings: "作品の設定", page_kind: "ページの種類", color_mode: "色の種類", dpi: "解像度", image_resolution: "絵の解像度",
               color_image: "色のある絵", spread: "見開き", safe_area: "安全線", text_overflow: "文字があふれる", font: "書体と組版",
               held_change: "判断待ち", ai_candidate: "選んでいない候補", job: "終わっていない生成", page_count: "ページ数" };
const POLL_MS = pollMs(1500);
const S = { workId: null, work: null, status: null, episodeId: null, picked: new Set(), format: "pdf", spread: "split",
            language: "", dpi: "", preflight: null, checkedKey: null, run: null, why: null, busy: false };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null; S.preflight = null; S.run = null;
  if (id) {
    try {
      const [work, records] = await Promise.all([api.get(`/works/${id}`), api.get(`/works/${id}/review-records`)]);
      S.work = work; S.status = reviewStates(records);
      S.episodeId = storedEpisode(work); rememberEpisode(S.episodeId);
      const live = new Set(work.pages.filter((p) => !p.removed).map((p) => p.id));
      S.picked = new Set([...S.picked].filter((p) => live.has(p)));
    } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
  }
  draw();
}

const pages = () => episodePages(S.work, S.episodeId);
const pickedIds = () => pages().filter((p) => S.picked.has(p.id)).map((p) => p.id);
const spreadPages = () => new Set((S.work.spreads || []).filter((s) => !s.removed).flatMap((s) => [s.first_page_id, s.second_page_id]));
// 確かめた後に選び方を変えたら、確かめ直す（古い結果で書き出さない）
const requestKey = () => JSON.stringify([pickedIds(), S.format, S.spread, S.language, S.dpi]);

function toggle(pid) { if (S.picked.has(pid)) S.picked.delete(pid); else S.picked.add(pid); draw(); }

async function preflight() {
  const ids = pickedIds();
  if (!ids.length) { toast("書き出すページを選んでください", "need"); return; }
  S.busy = true; draw();
  try {
    S.preflight = await api.post(`/works/${S.workId}/preflight`, { page_ids: ids });
    S.checkedKey = requestKey();
  } catch (e) { fail(e, "入稿前の確かめ"); } finally { S.busy = false; draw(); }
}

async function setColor(mode) {
  const ids = pickedIds();
  if (!ids.length) { toast("ページを選んでください", "need"); return; }
  S.busy = true; draw();
  try {
    for (const id of ids) await op(S.workId, { type: "update_page", id, color_mode: mode || null });
    toast(`${ids.length} ページの色の種類を${mode ? COLOR_MODE[mode] : "作品の既定"}にしました`);
  } catch (e) { fail(e, "色の種類を変える"); } finally { S.busy = false; await loadWork(S.workId); }
}

async function startExport() {
  const ids = pickedIds();
  const body = { format: S.format, page_ids: ids };
  if (ids.some((id) => spreadPages().has(id))) body.spread_output = S.spread;
  if (S.language.trim()) body.language = S.language.trim();
  if (S.dpi) body.dpi = Number(S.dpi);
  S.busy = true; draw();
  try {
    S.run = await api.post(`/works/${S.workId}/exports`, body);
    poll();
  } catch (e) { fail(e, "書き出し"); } finally { S.busy = false; draw(); }
}
async function poll() {
  const r = S.run;
  if (!r || r.status === "done" || r.status === "failed") return;
  await new Promise((ok) => setTimeout(ok, POLL_MS));
  if (S.run !== r) return;
  try { S.run = await api.get(`/works/${S.workId}/exports/${r.id}`); } catch (e) { fail(e, "書き出しの進み具合を読む"); return; }
  draw();
  poll();
}
// ファイルは X-V3-User が要るので、取ってきて blob の URL にして保存させる
async function save(name) {
  try {
    const r = await raw(`/works/${S.workId}/exports/${S.run.id}/files/${encodeURIComponent(name)}`);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) { fail(e, "ファイルを取る"); }
}
// ---------------------------------------------------------------- 描く
function pageGrid() {
  const ps = pages();
  const sp = spreadPages();
  return html`<section class="card" aria-label="書き出すページ">
    <div class="card-h"><span class="h2">書き出すページ</span><span class="meta num">選んだ ${pickedIds().length} / ${ps.length}</span>
      <button class="btn ghost sm" @click=${() => { ps.forEach((p) => S.picked.add(p.id)); draw(); }}>全部</button>
      <button class="btn ghost sm" @click=${() => { S.picked.clear(); draw(); }}>選ばない</button></div>
    ${ps.length ? html`<div class="pages">${ps.map((p) => {
      const st = S.status("page", p.id);
      const issues = S.preflight ? S.preflight.issues.filter((i) => i.page_id === p.id) : [];
      const errs = issues.filter((i) => i.severity === "error").length;
      return html`<button class="pg paper" role="checkbox" data-page=${p.id} aria-checked=${String(S.picked.has(p.id))} aria-pressed=${String(S.picked.has(p.id))} @click=${() => toggle(p.id)}>
        <span class="n num">${p.number}</span>
        <span class="tags"><span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span>
          <span class="flag mut">${p.color_mode ? COLOR_MODE[p.color_mode] : "色：既定"}</span>
          ${sp.has(p.id) ? html`<span class="flag ai">見開き</span>` : nothing}
          ${errs ? html`<span class="flag bad">× ${errs}</span>` : nothing}</span></button>`;
    })}</div>` : emptyNote("この話にはページがありません")}
  </section>`;
}

function seg(name, map, cur, set) {
  return html`<div class="seg" role="radiogroup" aria-label=${name}>${Object.entries(map).map(([v, l]) => html`
    <button type="button" data-v=${v} aria-pressed=${String(cur === v)} @click=${() => { set(v); draw(); }}>${l}</button>`)}</div>`;
}

function issuesList() {
  const p = S.preflight;
  if (!p) return html`<span class="meta">まだ確かめていません。書き出す前に「確かめる」を押してください</span>`;
  const stale = S.checkedKey !== requestKey();
  const num = (pid) => (S.work.pages.find((x) => x.id === pid) || {}).number;
  const fix = (i) => (i.kind === "settings" || i.kind === "page_count") ? html`<a class="btn ghost sm" href=${screenHref("plan")}>企画で直す</a>`
    : ["page_kind", "color_mode", "dpi", "spread"].includes(i.kind) ? html`<a class="btn ghost sm" href=${screenHref("structure")}>構成で直す</a>` : nothing;
  return html`${stale ? html`<div class="note need">${icon("triangle-alert")}<span>確かめた後に選び方を変えました。もう一度確かめてください</span></div>` : nothing}
    <div class="row wrap"><span class="flag ${p.ok ? "on" : "bad"}">${p.ok ? "止まる問題なし" : `止まる問題 ${p.errors}`}</span>
      <span class="flag ${p.warnings ? "warn" : "mut"}">見る所 ${p.warnings}</span></div>
    <div class="issues">${p.issues.map((i) => html`<div class="issue" data-kind=${i.kind}>
      <span class="flag ${i.severity === "error" ? "bad" : "warn"}">${i.severity === "error" ? "×" : "△"} ${KIND[i.kind] || i.kind}</span>
      <div><div>${i.page_id ? html`<b class="num">p.${num(i.page_id)}</b>　` : nothing}${i.message}</div>
        <div class="acts">${i.location ? html`<span class="meta mono">${i.location.table}:${i.location.id}</span>` : nothing}${fix(i)}</div></div></div>`)}</div>`;
}

function runCard() {
  const r = S.run;
  if (!r) return nothing;
  const active = r.status === "queued" || r.status === "running";
  return html`<section class="card" aria-label="書き出しの進み具合" id="run">
    <div class="card-h"><span class="h2">書き出し</span><span class="flag ${r.status === "done" ? "on" : r.status === "failed" ? "bad" : "ai"}">${RUN[r.status] || r.status}</span>
      ${active ? icon("loader", "spin") : nothing}</div>
    <div class="meta">${FORMAT[r.format]}・${r.page_ids.length} ページ${r.dpi ? `・${r.dpi}dpi` : ""}${r.language ? `・${r.language}` : ""}${r.spread_output ? `・${SPREAD[r.spread_output]}` : ""}</div>
    ${active ? html`<span class="meta">何ページ目まで進んだかはサーバーが返さないので、段（順番待ち・書き出している）だけを出しています</span>` : nothing}
    ${r.status === "failed" ? html`<div class="note bad">${icon("circle-alert")}<span>${r.detail}</span></div>` : nothing}
    ${r.note ? html`<div class="note">${icon("info")}<span>${r.note}</span></div>` : nothing}
    ${r.status === "done" ? html`<div class="list">${r.outputs.map((o) => html`<div class="item"><span class="nm mono">${o.file}</span>
      <span class="meta num">${Math.round(o.bytes / 1024).toLocaleString()} KB</span>
      <button class="btn sm" @click=${() => save(o.file)}>${icon("download")}保存</button></div>`)}</div>` : nothing}
  </section>`;
}

function settings() {
  const ids = pickedIds();
  const hasSpread = ids.some((id) => spreadPages().has(id));
  const p = S.preflight;
  return html`<section class="card" aria-label="書き出しの設定">
    <div class="form">
      <span class="k">ファイル</span>${seg("ファイル", FORMAT, S.format, (v) => { S.format = v; })}
      <span class="k">見開き</span><div class="v">${seg("見開き", SPREAD, S.spread, (v) => { S.spread = v; })}
        <span class="meta">${hasSpread ? "選んだページに見開きがあります" : "選んだページに見開きはありません（送りません）"}</span></div>
      <label class="k" for="lang">言語</label><div class="v"><input class="field" id="lang" .value=${S.language} placeholder="空なら元の文字" @input=${(e) => { S.language = e.target.value; draw(); }}>
        ${S.format === "psd" && S.language.trim() ? html`<span class="meta">PSD は言語ごとに書き出せません（サーバーが断ります）</span>` : nothing}</div>
      <label class="k" for="dpi">解像度</label><div class="v"><input class="field" id="dpi" type="number" min="1" max="2400" .value=${S.dpi} placeholder="ページごとの解像度" @input=${(e) => { S.dpi = e.target.value; draw(); }}>
        <span class="meta">入れると全ページをその解像度で出します（下見など）</span></div>
      <span class="k">色の種類</span><div class="v"><div class="acts">
        ${Object.entries(COLOR_MODE).map(([k, l]) => html`<button class="btn sm" data-color=${k} @click=${() => setColor(k)} ?disabled=${S.busy || !ids.length}>${l}</button>`)}
        <button class="btn ghost sm" @click=${() => setColor(null)} ?disabled=${S.busy || !ids.length}>作品の既定</button></div>
        <span class="meta">選んだページの色の種類を変えます（ページの設定。書き出しの依頼には入りません）</span></div>
    </div>
    <section class="sec"><div class="sec-h"><span class="lbl">入稿前の確かめ</span>
      <button class="btn sm" id="preflight" @click=${preflight} ?disabled=${S.busy || !ids.length}>${icon("list-checks")}確かめる</button></div>
      ${issuesList()}</section>
    <div class="acts">
      ${p && !p.ok ? html`<span class="meta">止まる問題が ${p.errors} 残っています。書き出すと、サーバーが理由を出して止めることがあります</span>` : nothing}
      <button class="btn primary" id="export" @click=${startExport} ?disabled=${S.busy || !ids.length || !p || S.checkedKey !== requestKey()}>${icon("download")}${ids.length} ページを書き出す</button>
    </div>
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || "作品を選んでください", S.why ? "need" : ""), main); return; }
  if (!S.episodeId) { render(emptyNote("話がまだありません。「作品と話」で足してください"), main); return; }
  render(html`<div class="col"><div class="row wrap">${episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; rememberEpisode(id); S.picked.clear(); S.preflight = null; draw(); })}</div>
    ${pageGrid()}</div><div class="col">${settings()}${runCard()}</div>`, main);
}

await startShell({ screen: "export", onWork: loadWork });
