// 書き出し：ページを選び、形式（PNG・PDF・PSD）・見開きの出し方・言語・解像度を決め、色の種類をページに決める。
// 先に入稿前の確かめを走らせて問題を出し、そのあと書き出しの進行状況とファイルを出す（V3細部の決めごと 7・13章）。
// API：GET /works/{id}、GET /works/{id}/review-records、POST /works/{id}/exports、GET /works/{id}/exports/{run}、
//     GET /works/{id}/exports/{run}/files/{name}、POST /works/{id}/preflight、操作 update_page（color_mode）
import { t } from "../common/i18n.js";
import { pollMs } from "../common/poll_interval.js";
import { html, render, nothing, api, icon, toast, fail, op, raw, startShell, emptyNote, screenHref,
         REVIEW, REVIEW_FLAG, COLOR_MODE, episodeName, reviewStates, episodePages, storedEpisode, rememberEpisode,
         episodePicker } from "../common/shell.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const FORMAT = { png: "PNG", pdf: "PDF", psd: t("PSD（レイヤーを分ける）") };
const SPREAD = { split: t("1ページずつ"), joined: t("見開きを1枚に"), both: t("両方") };
const RUN = { queued: t("順番待ち"), running: t("書き出している"), done: t("できた"), failed: t("止まった") };
const KIND = { settings: t("作品の設定"), page_kind: t("ページの種類"), color_mode: t("色の種類"), dpi: t("解像度"), image_resolution: t("絵の解像度"),
               color_image: t("色のある絵"), spread: t("見開き"), safe_area: t("安全線"), text_overflow: t("文字があふれる"), font: t("書体と組版"),
               held_change: t("判断待ち"), ai_candidate: t("選んでいない候補"), job: t("終わっていない生成"), page_count: t("ページ数") };
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
    } catch (e) { fail(e, t("作品を読み込めませんでした")); S.why = api.errorText(e); }
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
  if (!ids.length) { toast(t("書き出すページを選んでください"), "need"); return; }
  S.busy = true; draw();
  try {
    S.preflight = await api.post(`/works/${S.workId}/preflight`, { page_ids: ids });
    S.checkedKey = requestKey();
  } catch (e) { fail(e, t("入稿前の確かめができませんでした")); } finally { S.busy = false; draw(); }
}

async function setColor(mode) {
  const ids = pickedIds();
  if (!ids.length) { toast(t("ページを選んでください"), "need"); return; }
  S.busy = true; draw();
  try {
    for (const id of ids) await op(S.workId, { type: "update_page", id, color_mode: mode || null });
    toast(mode ? t("{{count}} ページの色の種類を{{mode}}にしました", { count: ids.length, mode: COLOR_MODE[mode] }) : t("{{count}} ページの色の種類を作品の既定にしました", { count: ids.length }));
  } catch (e) { fail(e, t("色の種類を変えられませんでした")); } finally { S.busy = false; await loadWork(S.workId); }
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
  } catch (e) { fail(e, t("書き出せませんでした")); } finally { S.busy = false; draw(); }
}
async function poll() {
  const r = S.run;
  if (!r || r.status === "done" || r.status === "failed") return;
  await new Promise((ok) => setTimeout(ok, POLL_MS));
  if (S.run !== r) return;
  try { S.run = await api.get(`/works/${S.workId}/exports/${r.id}`); } catch (e) { fail(e, t("書き出しの進行状況を読み込めませんでした")); return; }
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
  } catch (e) { fail(e, t("ファイルを取得できませんでした")); }
}
// ---------------------------------------------------------------- 描く
function pageGrid() {
  const ps = pages();
  const sp = spreadPages();
  return html`<section class="card" aria-label=${t("書き出すページ")}>
    <div class="card-h"><span class="h2">${t("書き出すページ")}</span><span class="meta num">${t("選んだ {{picked}} / {{total}}", { picked: pickedIds().length, total: ps.length })}</span>
      <button class="btn ghost sm" @click=${() => { ps.forEach((p) => S.picked.add(p.id)); draw(); }}>${t("全部")}</button>
      <button class="btn ghost sm" @click=${() => { S.picked.clear(); draw(); }}>${t("選ばない")}</button></div>
    ${ps.length ? html`<div class="pages">${ps.map((p) => {
      const st = S.status("page", p.id);
      const issues = S.preflight ? S.preflight.issues.filter((i) => i.page_id === p.id) : [];
      const errs = issues.filter((i) => i.severity === "error").length;
      return html`<button class="pg paper" role="checkbox" data-page=${p.id} aria-checked=${String(S.picked.has(p.id))} aria-pressed=${String(S.picked.has(p.id))} @click=${() => toggle(p.id)}>
        <span class="n num">${p.number}</span>
        <span class="tags"><span class="flag ${REVIEW_FLAG[st]}">${REVIEW[st]}</span>
          <span class="flag mut">${p.color_mode ? COLOR_MODE[p.color_mode] : t("色：既定")}</span>
          ${sp.has(p.id) ? html`<span class="flag ai">${t("見開き")}</span>` : nothing}
          ${errs ? html`<span class="flag bad">× ${errs}</span>` : nothing}</span></button>`;
    })}</div>` : emptyNote(t("この話にはページがありません"))}
  </section>`;
}

function seg(name, map, cur, set) {
  return html`<div class="seg" role="radiogroup" aria-label=${name}>${Object.entries(map).map(([v, l]) => html`
    <button type="button" data-v=${v} aria-pressed=${String(cur === v)} @click=${() => { set(v); draw(); }}>${l}</button>`)}</div>`;
}

function issuesList() {
  const p = S.preflight;
  if (!p) return html`<span class="meta">${t("まだ確かめていません。書き出す前に「確かめる」を押してください")}</span>`;
  const stale = S.checkedKey !== requestKey();
  const num = (pid) => (S.work.pages.find((x) => x.id === pid) || {}).number;
  const fix = (i) => (i.kind === "settings" || i.kind === "page_count") ? html`<a class="btn ghost sm" href=${screenHref("plan")}>${t("企画で直す")}</a>`
    : ["page_kind", "color_mode", "dpi", "spread"].includes(i.kind) ? html`<a class="btn ghost sm" href=${screenHref("structure")}>${t("構成で直す")}</a>` : nothing;
  return html`${stale ? html`<div class="note need">${icon("triangle-alert")}<span>${t("確かめた後に選び方を変えました。もう一度確かめてください")}</span></div>` : nothing}
    <div class="row wrap"><span class="flag ${p.ok ? "on" : "bad"}">${p.ok ? t("止まる問題なし") : t("止まる問題 {{n}}", { n: p.errors })}</span>
      <span class="flag ${p.warnings ? "warn" : "mut"}">${t("見る所 {{n}}", { n: p.warnings })}</span></div>
    <div class="issues">${p.issues.map((i) => html`<div class="issue" data-kind=${i.kind}>
      <span class="flag ${i.severity === "error" ? "bad" : "warn"}">${i.severity === "error" ? "×" : "△"} ${KIND[i.kind] || i.kind}</span>
      <div><div>${i.page_id ? html`<b class="num">p.${num(i.page_id)}</b>　` : nothing}${i.message}</div>
        <div class="acts">${i.location ? html`<span class="meta mono">${i.location.table}:${i.location.id}</span>` : nothing}${fix(i)}</div></div></div>`)}</div>`;
}

function runCard() {
  const r = S.run;
  if (!r) return nothing;
  const active = r.status === "queued" || r.status === "running";
  return html`<section class="card" aria-label=${t("書き出しの進行状況")} id="run">
    <div class="card-h"><span class="h2">${t("書き出し")}</span><span class="flag ${r.status === "done" ? "on" : r.status === "failed" ? "bad" : "ai"}">${RUN[r.status] || r.status}</span>
      ${active ? icon("loader", "spin") : nothing}</div>
    <div class="meta">${[FORMAT[r.format], t("{{count}} ページ", { count: r.page_ids.length }), r.dpi ? `${r.dpi}dpi` : "", r.language, r.spread_output ? SPREAD[r.spread_output] : ""].filter(Boolean).join(t("・"))}</div>
    ${active ? html`<span class="meta">${t("何ページ目まで進んだかはサーバーが返さないので、状態（順番待ち・書き出している）だけを出しています")}</span>` : nothing}
    ${r.status === "failed" ? html`<div class="note bad">${icon("circle-alert")}<span>${r.detail}</span></div>` : nothing}
    ${r.note ? html`<div class="note">${icon("info")}<span>${r.note}</span></div>` : nothing}
    ${r.status === "done" ? html`<div class="list">${r.outputs.map((o) => html`<div class="item"><span class="nm mono">${o.file}</span>
      <span class="meta num">${Math.round(o.bytes / 1024).toLocaleString()} KB</span>
      <button class="btn sm" @click=${() => save(o.file)}>${icon("download")}${t("保存")}</button></div>`)}</div>` : nothing}
  </section>`;
}

function settings() {
  const ids = pickedIds();
  const hasSpread = ids.some((id) => spreadPages().has(id));
  const p = S.preflight;
  return html`<section class="card" aria-label=${t("書き出しの設定")}>
    <div class="form">
      <span class="k">${t("ファイル")}</span>${seg(t("ファイル"), FORMAT, S.format, (v) => { S.format = v; })}
      <span class="k">${t("見開き")}</span><div class="v">${seg(t("見開き"), SPREAD, S.spread, (v) => { S.spread = v; })}
        <span class="meta">${hasSpread ? t("選んだページに見開きがあります") : t("選んだページに見開きはありません（送りません）")}</span></div>
      <label class="k" for="lang">${t("言語")}</label><div class="v"><input class="field" id="lang" .value=${S.language} placeholder=${t("空なら元の文字")} @input=${(e) => { S.language = e.target.value; draw(); }}>
        ${S.format === "psd" && S.language.trim() ? html`<span class="meta">${t("PSD は言語ごとに書き出せません（サーバーが断ります）")}</span>` : nothing}</div>
      <label class="k" for="dpi">${t("解像度")}</label><div class="v"><input class="field" id="dpi" type="number" min="1" max="2400" .value=${S.dpi} placeholder=${t("ページごとの解像度")} @input=${(e) => { S.dpi = e.target.value; draw(); }}>
        <span class="meta">${t("入れると全ページをその解像度で出します（下見など）")}</span></div>
      <span class="k">${t("色の種類")}</span><div class="v"><div class="acts">
        ${Object.entries(COLOR_MODE).map(([k, l]) => html`<button class="btn sm" data-color=${k} @click=${() => setColor(k)} ?disabled=${S.busy || !ids.length}>${l}</button>`)}
        <button class="btn ghost sm" @click=${() => setColor(null)} ?disabled=${S.busy || !ids.length}>${t("作品の既定")}</button></div>
        <span class="meta">${t("選んだページの色の種類を変えます（ページの設定。書き出しの依頼には入りません）")}</span></div>
    </div>
    <section class="sec"><div class="sec-h"><span class="lbl">${t("入稿前の確かめ")}</span>
      <button class="btn sm" id="preflight" @click=${preflight} ?disabled=${S.busy || !ids.length}>${icon("list-checks")}${t("確かめる")}</button></div>
      ${issuesList()}</section>
    <div class="acts">
      ${p && !p.ok ? html`<span class="meta">${t("止まる問題が {{n}} 残っています。書き出すと、サーバーが理由を出して止めることがあります", { n: p.errors })}</span>` : nothing}
      <button class="btn primary" id="export" @click=${startExport} ?disabled=${S.busy || !ids.length || !p || S.checkedKey !== requestKey()}>${icon("download")}${t("{{count}} ページを書き出す", { count: ids.length })}</button>
    </div>
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || t("作品を選んでください"), S.why ? "need" : ""), main); return; }
  if (!S.episodeId) { render(emptyNote(t("話がまだありません。「作品と話」で足してください")), main); return; }
  render(html`<div class="col"><div class="row wrap">${episodePicker(S.work, S.episodeId, (id) => { S.episodeId = id; rememberEpisode(id); S.picked.clear(); S.preflight = null; draw(); })}</div>
    ${pageGrid()}</div><div class="col">${settings()}${runCard()}</div>`, main);
}

await startShell({ screen: "export", onWork: loadWork });
