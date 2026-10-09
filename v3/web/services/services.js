// 生成サービス：接続先と、処理ごとの送り先（全作品で共通。V3細部の決めごと 4.7）。
// 管理者は全部（GET /services）を見て変えられる。作品の参加者は、その作品から見える項目（GET /works/{id}/services）だけを見る。
// API：GET /services、POST /services、PATCH /services/{id}、PUT /routes/{process}、GET /works/{id}/services
// タブは2つ：「処理ごとの送り先」（行は処理・列は接続先の表）と「接続先」（1つを1枚のカード）。右のパネルは置かない（決めごと 4.7）
import { t } from "../common/i18n.js";
import { html, render, nothing, api, icon, toast, fail, send, startShell, emptyNote, YNU } from "../common/shell.js";
import { fieldsHtml, readFields, USAGE_TERMS } from "../common/form_fields.js";

const main = document.getElementById("main");
main.className = "screen";
const STATE = { connected: t("接続済み"), stopped: t("停止中"), key_rejected: t("APIキーが無効"), unchecked: t("未確認") };
const APT = { good: ["◎", t("得意")], normal: ["○", t("ふつう")], poor: ["△", t("苦手")] };
const KIND = { image: t("画像"), text: t("文章") };
const SEND = { serial: t("1件ずつ"), parallel: t("同時に") };
const GROUPS = { cheap: t("安く"), good: t("得意を優先"), local: t("ローカルだけ"), api: t("APIだけ") };
const S = { workId: null, admin: null, data: null, member: null, tab: "routes", open: null, plan: null, adding: false, why: null, busy: false };

async function load(workId, why = null) {
  S.workId = workId; S.why = why; S.data = null; S.member = null; S.plan = null;
  if (!api.currentUser()) { draw(); return; }
  try {
    S.data = await api.get("/services");
    S.admin = true;
  } catch (e) {
    if (!(e instanceof api.ApiError) || e.status !== 403) { fail(e, t("接続先を読み込めませんでした")); S.why = api.errorText(e); draw(); return; }
    S.admin = false;
  }
  if (!S.admin && workId) {
    try { S.member = await api.get(`/works/${workId}/services`); } catch (e) { fail(e, t("接続先を読み込めませんでした")); S.why = api.errorText(e); }
  }
  draw();
}
async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; await load(S.workId, S.why); }
}
const sendable = (s) => s.state === "connected" && !s.paused;
const stateLabel = (s) => (s.paused ? t("一時停止中") : STATE[s.state] || s.state);
const locLabel = (s) => (s.location === "local" ? t("ローカル") : "API");
const dot = (s) => html`<span class="dot ${s.paused ? "paused" : s.state}" aria-hidden="true"></span>`;

// ---------------------------------------------------------------- 処理ごとの送り先（管理者）
function sp(svcId, process) { return S.data.processes.find((p) => p.service_id === svcId && p.process === process); }
function routeOf(process) { return S.data.routes.find((r) => r.process === process); }
function processesOf(kind) {
  const ids = new Set(S.data.services.filter((s) => s.kind === kind).map((s) => s.id));
  return [...new Set(S.data.processes.filter((p) => ids.has(p.service_id)).map((p) => p.process))].sort();
}
function setRoute(process, serviceId) {
  const r = routeOf(process);
  if (!r) { toast(t("「{{process}}」はまだ送り先が無く、作業（ai_task）と手（ai_action）が決まっていないので、ここでは選べません", { process }), "need"); return; }
  if (r.service_id === serviceId) return;
  run(t("送り先を変えられませんでした"), async () => {
    await send("PUT", `/routes/${encodeURIComponent(process)}`, { service_id: serviceId, resend_limit: r.resend_limit,
      regenerate_limit: r.regenerate_limit, ai_task: r.ai_task, ai_action: r.ai_action });
    toast(t("{{process}} を {{to}} へ送ります（前は {{from}}）", { process, to: S.data.services.find((s) => s.id === serviceId).name, from: S.data.services.find((s) => s.id === r.service_id)?.name || r.service_id }));
  });
}
function matrix(kind) {
  const cols = S.data.services.filter((s) => s.kind === kind);
  const rows = processesOf(kind);
  if (!cols.length) return emptyNote(t("{{kind}}の接続先がありません", { kind: KIND[kind] }));
  return html`<div class="t-wrap"><div class="mx" style="--n:${cols.length}" role="grid" aria-label=${t("{{kind}}の処理ごとの送り先", { kind: KIND[kind] })}>
    <span class="mh">${KIND[kind]}</span>
    ${cols.map((s) => html`<button class="mh" @click=${() => { S.tab = "cons"; S.open = s.id; draw(); }} title=${t("接続先のカードを開く")}>
      <span class="row">${dot(s)}<b>${s.name}</b></span><span class="meta">${locLabel(s)}${t("・")}${stateLabel(s)}</span></button>`)}
    ${rows.map((p) => html`<span class="mh">${p}${routeOf(p) ? html`<span class="meta">${t("送り直し {{resend}}・作り直し {{regenerate}}", { resend: routeOf(p).resend_limit, regenerate: routeOf(p).regenerate_limit })}</span>` : html`<span class="meta">${t("送り先なし")}</span>`}</span>
      ${cols.map((s) => {
        const c = sp(s.id, p);
        if (!c) return html`<span class="mc x" title=${t("{{name}} はこの処理を受けられない", { name: s.name })}></span>`;
        const on = routeOf(p) && routeOf(p).service_id === s.id;
        const a = APT[c.aptitude];
        const aptText = a ? a[1] : t("得意さ未記入");
        const costText = c.cost_per_call ?? t("費用未記入");
        return html`<button class="mc" data-process=${p} data-service=${s.id} aria-pressed=${String(!!on)} ?disabled=${S.busy}
          aria-label=${t("{{process}}を{{name}}へ送る {{apt}} {{cost}}", { process: p, name: s.name, apt: aptText, cost: costText })}
          @click=${() => setRoute(p, s.id)}>${on ? icon("check") : nothing}<span>${a ? a[0] : "－"}</span>
          <span class="num meta">${c.cost_per_call == null ? t("費用？") : `¥${c.cost_per_call}`}</span>
          ${on && !sendable(s) ? html`<span class="flag bad">${t("送れない")}</span>` : nothing}</button>`;
      })}`)}
  </div></div>`;
}

// プリセット：送り先の全体を1回で切り替える。送れる先だけから選ぶ。選べる先が無い処理は変えない（決めごと 4.7）
function planGroup(g) {
  const changes = [], skipped = [];
  for (const kind of Object.keys(KIND)) for (const p of processesOf(kind)) {
    const r = routeOf(p);
    let cands = S.data.services.filter((s) => s.kind === kind && sendable(s) && sp(s.id, p));
    if (g === "local") cands = cands.filter((s) => s.location === "local");
    if (g === "api") cands = cands.filter((s) => s.location === "api");
    const cost = (s) => sp(s.id, p).cost_per_call;
    const rank = { good: 0, normal: 1, poor: 2 };
    if (g === "cheap" || g === "local" || g === "api") {
      if (cands.some((s) => cost(s) == null)) { skipped.push([p, t("費用が入っていない先がある")]); continue; }
      cands.sort((a, b) => cost(a) - cost(b));
    } else {
      if (cands.some((s) => !sp(s.id, p).aptitude)) { skipped.push([p, t("得意さが入っていない先がある")]); continue; }
      cands.sort((a, b) => rank[sp(a.id, p).aptitude] - rank[sp(b.id, p).aptitude] || (cost(a) ?? Infinity) - (cost(b) ?? Infinity));
    }
    if (!cands.length) { skipped.push([p, t("送れる先が無い")]); continue; }
    if (!r) { skipped.push([p, t("まだ送り先が無い（作業と手が決まっていない）")]); continue; }
    if (r.service_id !== cands[0].id) changes.push([p, cands[0]]);
  }
  S.plan = { g, changes, skipped };
  draw();
}
function applyPlan() {
  const { changes } = S.plan;
  run(t("プリセットを切り替えられませんでした"), async () => {
    for (const [p, s] of changes) {
      const r = routeOf(p);
      await send("PUT", `/routes/${encodeURIComponent(p)}`, { service_id: s.id, resend_limit: r.resend_limit,
        regenerate_limit: r.regenerate_limit, ai_task: r.ai_task, ai_action: r.ai_action });
    }
    toast(t("{{count}} 件の送り先を変えました", { count: changes.length }));
  });
}
function routesTab() {
  return html`<section class="card"><div class="sec-h"><span class="lbl">${t("プリセット")}</span><span class="meta">${t("送り先の全体を1回で切り替えます。自動では切り替えません")}</span></div>
    <div class="acts">${Object.entries(GROUPS).map(([k, l]) => html`<button class="chip" data-group=${k} aria-pressed=${String(S.plan && S.plan.g === k)} @click=${() => planGroup(k)}>${l}</button>`)}
      <span class="grow"></span><span class="meta">${t("◎ 得意　○ ふつう　△ 苦手")}</span></div>
    ${S.plan ? html`<div class="note" id="group-plan">${icon("info")}<div class="grow">
      <div>${t("{{group}}：変わる処理 {{n}}", { group: GROUPS[S.plan.g], n: S.plan.changes.length })}${S.plan.changes.map(([p, s]) => html`<br>${p} → ${s.name}`)}</div>
      ${S.plan.skipped.length ? html`<div class="meta">${t("変えない処理：")}${S.plan.skipped.map(([p, why]) => t("{{process}}（{{reason}}）", { process: p, reason: why })).join(t("、"))}</div>` : nothing}
      <div class="acts"><button class="btn sm primary" @click=${applyPlan} ?disabled=${S.busy || !S.plan.changes.length}>${t("切り替える")}</button>
        <button class="btn sm ghost" @click=${() => { S.plan = null; draw(); }}>${t("やめる")}</button></div></div></div>` : nothing}
    <span class="meta">${t("いまの並びをプリセットに残す・同じ指示で比べる・得意さと費用をこの表で直すことは、サーバーにAPIが無いのでできません")}</span>
    </section>
    <section class="card">${matrix("image")}</section><section class="card">${matrix("text")}</section>`;
}

// ---------------------------------------------------------------- 接続先（管理者）
function patch(s, body, done, failed) {
  run(failed, async () => { await send("PATCH", `/services/${s.id}`, body); toast(done); });
}
function saveTerms(e, s) {
  e.preventDefault();
  const terms = readFields(e.target, USAGE_TERMS, "terms.");
  if (!terms) { toast(t("利用規約の要点を入れてください"), "need"); return; }
  patch(s, { usage_terms: Object.fromEntries(Object.entries(terms).filter(([, v]) => v !== null)) },
        t("{{name}}：利用規約の要点を残しました", { name: s.name }), t("利用規約の要点を残せませんでした"));
}
function saveConn(e, s) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = {};
  const ep = f.get("endpoint").trim() || null;
  if (ep !== s.endpoint) body.endpoint = ep;
  const n = Number(f.get("max_concurrency"));
  if (n !== s.max_concurrency) body.max_concurrency = n;
  const budget = f.get("monthly_budget") === "" ? null : Number(f.get("monthly_budget"));
  if (budget !== s.monthly_budget) body.monthly_budget = budget;
  if (!Object.keys(body).length) { toast(t("変わった所がありません")); return; }
  patch(s, body, t("{{name}}：残しました", { name: s.name }), t("残せませんでした"));
}
function card(s) {
  const procs = S.data.processes.filter((p) => p.service_id === s.id);
  const routed = S.data.routes.filter((r) => r.service_id === s.id);
  const terms = s.usage_terms;
  return html`<section class="card con" id="con-${s.id}" data-service=${s.id} ?open=${S.open === s.id}>
    <div class="card-h">${dot(s)}<span class="h2">${s.name}</span>
      <span class="meta">${[KIND[s.kind], locLabel(s), s.adapter, stateLabel(s)].join(t("・"))}</span>
      <span class="meta">${t("一時停止")}</span><button class="sw" role="switch" aria-checked=${String(s.paused)} aria-label=${t("{{name}}を一時停止", { name: s.name })}
        @click=${() => patch(s, { paused: !s.paused }, s.paused ? t("{{name}}：再開しました", { name: s.name }) : t("{{name}}：一時停止しました", { name: s.name }), s.paused ? t("再開できませんでした") : t("一時停止できませんでした"))} ?disabled=${S.busy}></button></div>
    <div class="meta">${routed.length ? t("送り先にしている処理 {{count}}：{{list}}", { count: routed.length, list: routed.map((r) => r.process).join(t("・")) }) : t("送り先にしていない")}${s.paused ? html` <span>${t("一時停止中の接続先へ送った依頼は待ちに入り、再開すると順に送ります")}</span>` : nothing}</div>
    <form class="form" @submit=${(e) => saveConn(e, s)}>
      <label class="k">URL</label><input class="field mono" name="endpoint" .value=${s.endpoint || ""}>
      <span class="k">${t("送り方")}</span><div class="row wrap">${Object.entries(SEND).map(([k, l]) => html`<button type="button" class="chip" aria-pressed=${String(s.send_mode === k)}
          @click=${() => s.send_mode !== k && patch(s, { send_mode: k }, t("{{name}}：送り方を変えました", { name: s.name }), t("送り方を変えられませんでした"))}>${l}</button>`)}
        <input class="field num short" name="max_concurrency" type="number" min="1" .value=${String(s.max_concurrency)} aria-label=${t("同時に送る数")}><span class="meta">${t("件まで")}</span></div>
      <label class="k">${t("月の予算")}</label><div class="row"><input class="field num" name="monthly_budget" type="number" min="0" .value=${s.monthly_budget == null ? "" : String(s.monthly_budget)}><span class="meta">${t("円")}</span></div>
      <div class="full acts"><button class="btn sm" ?disabled=${S.busy}>${icon("save")}${t("残す")}</button>
        <span class="meta">${t("APIキーはサーバー（LiteLLM）だけが持ちます。接続を試す・いまの実行状況・止まったもの・入っているモデルを読むAPIはまだありません")}</span></div>
    </form>
    <details class="more"><summary>${icon("chevron-right")}${t("受けられる処理 {{n}}", { n: procs.length })}</summary>
      <div class="t-wrap"><table class="t"><tr><th>${t("処理")}</th><th>${t("得意さ")}</th><th>${t("1回の費用")}</th><th>${t("モデル")}</th></tr>
      ${procs.map((p) => html`<tr><td>${p.process}</td><td>${APT[p.aptitude] ? APT[p.aptitude].join(" ") : t("未記入")}</td>
        <td class="num">${p.cost_per_call == null ? t("未記入") : `¥${p.cost_per_call}`}</td><td class="mono">${p.model || ""}</td></tr>`)}</table></div></details>
    <details class="more"><summary>${icon("chevron-right")}${t("商用利用の条件")} <span class="flag ${terms ? "mut" : "warn"}">${terms ? t("確かめた日 {{date}}", { date: terms.checked_on }) : t("未記録")}</span></summary>
      ${terms ? html`<div class="meta">${t("商用 {{commercial}}・出力の権利 {{rights}}・学習に使われる {{training}}・クレジット {{credit}}", { commercial: YNU[terms.commercial_use], rights: terms.rights_holder, training: YNU[terms.training_use], credit: YNU[terms.credit_required] })}</div>` : nothing}
      <form class="form" @submit=${(e) => saveTerms(e, s)}>${fieldsHtml(USAGE_TERMS, terms || {}, "terms.")}
        <div class="full acts"><button class="btn sm" ?disabled=${S.busy}>${icon("save")}${t("残す")}</button></div></form></details>
  </section>`;
}
function addService(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { name: f.get("name").trim(), kind: f.get("kind"), location: f.get("location"), adapter: f.get("adapter"),
                 endpoint: f.get("endpoint").trim() || null, send_mode: f.get("send_mode"), max_concurrency: Number(f.get("max_concurrency")) };
  run(t("接続先を足せませんでした"), async () => { await api.post("/services", body); S.adding = false; toast(t("{{name}} を足しました", { name: body.name })); });
}
function consTab() {
  const sel = (name, map) => html`<select class="field" name=${name}>${Object.entries(map).map(([k, l]) => html`<option value=${k}>${l}</option>`)}</select>`;
  return html`<div class="acts"><button class="btn ghost sm" @click=${() => { S.adding = !S.adding; draw(); }} aria-expanded=${String(S.adding)}>${icon("plus")}${t("接続先を足す")}</button></div>
    ${S.adding ? html`<form class="card" @submit=${addService} aria-label=${t("接続先を足す")}><div class="form">
      <span class="k">${t("名前")}</span><input class="field" name="name" required>
      <span class="k">${t("種類")}</span>${sel("kind", KIND)}
      <span class="k">${t("場所")}</span>${sel("location", { local: t("ローカル"), api: "API" })}
      <span class="k">${t("アダプター")}</span>${sel("adapter", { comfyui: "ComfyUI", litellm: "LiteLLM", detector: t("検出器") })}
      <span class="k">URL</span><input class="field mono" name="endpoint">
      <span class="k">${t("送り方")}</span>${sel("send_mode", SEND)}
      <span class="k">${t("同時に送る数")}</span><input class="field" name="max_concurrency" type="number" min="1" value="1">
      <div class="full acts"><button class="btn primary sm" ?disabled=${S.busy}>${t("足す")}</button>
        <span class="meta">${t("ローカルとして登録できるのは、このPCのURLへ直接送る先だけです（サーバーが確かめます）")}</span></div></div></form>` : nothing}
    ${Object.entries(KIND).map(([k, l]) => html`<div class="lbl grp">${l}</div><div class="grid wide">${S.data.services.filter((s) => s.kind === k).map(card)}</div>`)}`;
}

// ---------------------------------------------------------------- 参加者の見え方
function memberView() {
  if (!S.member) return emptyNote(S.why || t("作品を選んでください。参加者は、その作品から見える接続先だけを見られます"), S.why ? "need" : "");
  const name = (id) => (S.member.services.find((s) => s.id === id) || {}).name || id;
  return html`<div class="note">${icon("info")}<span>${t("管理者ではないので、この作品から見える項目だけを出しています。送り先を変えるのは管理者です")}</span></div>
    <section class="card"><div class="card-h"><span class="h2">${t("接続先")}</span></div>
    <div class="t-wrap"><table class="t" id="member-services"><tr><th>${t("名前")}</th><th>${t("種類")}</th><th>${t("場所")}</th><th>${t("状態")}</th><th>${t("この作品から")}</th><th>${t("商用利用の条件")}</th></tr>
    ${S.member.services.map((s) => html`<tr data-service=${s.id}><td>${s.name}</td><td>${KIND[s.kind]}</td><td>${locLabel(s)}</td>
      <td><span class="row">${dot(s)}${stateLabel(s)}</span></td><td>${s.allowed ? t("送ってよい") : html`<span class="flag warn">${t("送れない")}</span>`}</td>
      <td>${s.usage_terms ? t("商用 {{commercial}}（{{date}}）", { commercial: YNU[s.usage_terms.commercial_use], date: s.usage_terms.checked_on }) : html`<span class="flag warn">${t("未記録")}</span>`}</td></tr>`)}</table></div></section>
    <section class="card"><div class="card-h"><span class="h2">${t("処理ごとの送り先")}</span></div>
    <div class="t-wrap"><table class="t"><tr><th>${t("処理")}</th><th>${t("送り先")}</th></tr>${S.member.routes.map((r) => html`<tr><td>${r.process}</td><td>${name(r.service_id)}</td></tr>`)}</table></div></section>`;
}

function draw() {
  if (S.admin === null) { render(emptyNote(S.why || t("読んでいます")), main); return; }
  if (!S.admin) { render(memberView(), main); return; }
  render(html`<div class="row wrap"><span class="flag mut">${t("全作品で共通")}</span><span class="h1">${t("生成サービス")}</span></div>
    <div class="tabs" role="tablist">${[["routes", t("処理ごとの送り先")], ["cons", t("接続先")]].map(([k, l]) => html`
      <button class="tab" role="tab" data-tab=${k} aria-selected=${String(S.tab === k)} @click=${() => { S.tab = k; draw(); }}>${l}</button>`)}</div>
    ${S.tab === "routes" ? routesTab() : consTab()}`, main);
  if (S.tab === "cons" && S.open) {
    const el = document.getElementById(`con-${S.open}`);
    if (el) el.scrollIntoView({ block: "start" });
    S.open = null;
  }
}

await startShell({ screen: "services", onWork: load });
