// 生成サービス：つなぎ先と、処理ごとの送り先（全作品で共通。V3細部の決めごと 4.7）。
// 管理者は全部（GET /services）を見て変えられる。作品の参加者は、その作品から見える項目（GET /works/{id}/services）だけを見る。
// 口：GET /services、POST /services、PATCH /services/{id}、PUT /routes/{process}、GET /works/{id}/services
// タブは2つ：「処理ごとの送り先」（行は処理・列はつなぎ先の表）と「つなぎ先」（1つを1枚のカード）。右の欄は置かない（決めごと 4.7）
import { html, render, nothing, api, icon, toast, fail, send, startShell, emptyNote, YNU } from "../common/shell.js";
import { fieldsHtml, readFields, USAGE_TERMS } from "../common/form_fields.js";

const main = document.getElementById("main");
main.className = "screen";
const STATE = { connected: "つながっている", stopped: "止まっている", key_rejected: "キーが通らない", unchecked: "未確認" };
const APT = { good: ["◎", "得意"], normal: ["○", "ふつう"], poor: ["△", "苦手"] };
const KIND = { image: "画像", text: "文章" };
const SEND = { serial: "1件ずつ", parallel: "同時に" };
const GROUPS = { cheap: "安く", good: "得意を優先", local: "手元だけ", api: "APIだけ" };
const S = { workId: null, admin: null, data: null, member: null, tab: "routes", open: null, plan: null, adding: false, why: null, busy: false };

async function load(workId, why = null) {
  S.workId = workId; S.why = why; S.data = null; S.member = null; S.plan = null;
  if (!api.currentUser()) { draw(); return; }
  try {
    S.data = await api.get("/services");
    S.admin = true;
  } catch (e) {
    if (!(e instanceof api.ApiError) || e.status !== 403) { fail(e, "つなぎ先を読む"); S.why = api.errorText(e); draw(); return; }
    S.admin = false;
  }
  if (!S.admin && workId) {
    try { S.member = await api.get(`/works/${workId}/services`); } catch (e) { fail(e, "つなぎ先を読む"); S.why = api.errorText(e); }
  }
  draw();
}
async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; await load(S.workId, S.why); }
}
const sendable = (s) => s.state === "connected" && !s.paused;
const stateLabel = (s) => (s.paused ? "休ませている" : STATE[s.state] || s.state);
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
  if (!r) { toast(`「${process}」はまだ送り先が無く、作業（ai_task）と手（ai_action）が決まっていないので、ここでは選べません`, "need"); return; }
  if (r.service_id === serviceId) return;
  run("送り先を変える", async () => {
    await send("PUT", `/routes/${encodeURIComponent(process)}`, { service_id: serviceId, resend_limit: r.resend_limit,
      regenerate_limit: r.regenerate_limit, ai_task: r.ai_task, ai_action: r.ai_action });
    toast(`${process} を ${S.data.services.find((s) => s.id === serviceId).name} へ送ります（前は ${S.data.services.find((s) => s.id === r.service_id)?.name || r.service_id}）`);
  });
}
function matrix(kind) {
  const cols = S.data.services.filter((s) => s.kind === kind);
  const rows = processesOf(kind);
  if (!cols.length) return emptyNote(`${KIND[kind]}のつなぎ先がありません`);
  return html`<div class="t-wrap"><div class="mx" style="--n:${cols.length}" role="grid" aria-label="${KIND[kind]}の処理ごとの送り先">
    <span class="mh">${KIND[kind]}</span>
    ${cols.map((s) => html`<button class="mh" @click=${() => { S.tab = "cons"; S.open = s.id; draw(); }} title="つなぎ先のカードを開く">
      <span class="row">${dot(s)}<b>${s.name}</b></span><span class="meta">${s.location === "local" ? "手元" : "API"}・${stateLabel(s)}</span></button>`)}
    ${rows.map((p) => html`<span class="mh">${p}${routeOf(p) ? html`<span class="meta">送り直し ${routeOf(p).resend_limit}・作り直し ${routeOf(p).regenerate_limit}</span>` : html`<span class="meta">送り先なし</span>`}</span>
      ${cols.map((s) => {
        const c = sp(s.id, p);
        if (!c) return html`<span class="mc x" title="${s.name} はこの処理を受けられない"></span>`;
        const on = routeOf(p) && routeOf(p).service_id === s.id;
        const a = APT[c.aptitude];
        return html`<button class="mc" data-process=${p} data-service=${s.id} aria-pressed=${String(!!on)} ?disabled=${S.busy}
          aria-label="${p}を${s.name}へ送る ${a ? a[1] : "得意さ未記入"} ${c.cost_per_call ?? "費用未記入"}"
          @click=${() => setRoute(p, s.id)}>${on ? icon("check") : nothing}<span>${a ? a[0] : "－"}</span>
          <span class="num meta">${c.cost_per_call == null ? "費用？" : `¥${c.cost_per_call}`}</span>
          ${on && !sendable(s) ? html`<span class="flag bad">送れない</span>` : nothing}</button>`;
      })}`)}
  </div></div>`;
}

// 組：送り先の全体を1回で切り替える。送れる先だけから選ぶ。選べる先が無い処理は変えない（決めごと 4.7）
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
      if (cands.some((s) => cost(s) == null)) { skipped.push([p, "費用が入っていない先がある"]); continue; }
      cands.sort((a, b) => cost(a) - cost(b));
    } else {
      if (cands.some((s) => !sp(s.id, p).aptitude)) { skipped.push([p, "得意さが入っていない先がある"]); continue; }
      cands.sort((a, b) => rank[sp(a.id, p).aptitude] - rank[sp(b.id, p).aptitude] || (cost(a) ?? Infinity) - (cost(b) ?? Infinity));
    }
    if (!cands.length) { skipped.push([p, "送れる先が無い"]); continue; }
    if (!r) { skipped.push([p, "まだ送り先が無い（作業と手が決まっていない）"]); continue; }
    if (r.service_id !== cands[0].id) changes.push([p, cands[0]]);
  }
  S.plan = { g, changes, skipped };
  draw();
}
function applyPlan() {
  const { changes } = S.plan;
  run("組を切り替える", async () => {
    for (const [p, s] of changes) {
      const r = routeOf(p);
      await send("PUT", `/routes/${encodeURIComponent(p)}`, { service_id: s.id, resend_limit: r.resend_limit,
        regenerate_limit: r.regenerate_limit, ai_task: r.ai_task, ai_action: r.ai_action });
    }
    toast(`${changes.length} 件の送り先を変えました`);
  });
}
function routesTab() {
  return html`<section class="card"><div class="sec-h"><span class="lbl">組</span><span class="meta">送り先の全体を1回で切り替えます。自動では切り替えません</span></div>
    <div class="acts">${Object.entries(GROUPS).map(([k, l]) => html`<button class="chip" data-group=${k} aria-pressed=${String(S.plan && S.plan.g === k)} @click=${() => planGroup(k)}>${l}</button>`)}
      <span class="grow"></span><span class="meta">◎ 得意　○ ふつう　△ 苦手</span></div>
    ${S.plan ? html`<div class="note" id="group-plan">${icon("info")}<div class="grow">
      <div>${GROUPS[S.plan.g]}：変わる処理 ${S.plan.changes.length}${S.plan.changes.map(([p, s]) => html`<br>${p} → ${s.name}`)}</div>
      ${S.plan.skipped.length ? html`<div class="meta">変えない処理：${S.plan.skipped.map(([p, why]) => `${p}（${why}）`).join("、")}</div>` : nothing}
      <div class="acts"><button class="btn sm primary" @click=${applyPlan} ?disabled=${S.busy || !S.plan.changes.length}>切り替える</button>
        <button class="btn sm ghost" @click=${() => { S.plan = null; draw(); }}>やめる</button></div></div></div>` : nothing}
    <span class="meta">いまの並びを組に残す・同じ指示で比べる・得意さと費用をこの表で直すことは、サーバーに口が無いのでできません</span>
    </section>
    <section class="card">${matrix("image")}</section><section class="card">${matrix("text")}</section>`;
}

// ---------------------------------------------------------------- つなぎ先（管理者）
function patch(s, body, what) {
  run(what, async () => { await send("PATCH", `/services/${s.id}`, body); toast(`${s.name}：${what}ました`); });
}
function saveTerms(e, s) {
  e.preventDefault();
  const t = readFields(e.target, USAGE_TERMS, "terms.");
  if (!t) { toast("利用規約の要点を入れてください", "need"); return; }
  patch(s, { usage_terms: Object.fromEntries(Object.entries(t).filter(([, v]) => v !== null)) }, "利用規約の要点を残し");
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
  if (!Object.keys(body).length) { toast("変わった所がありません"); return; }
  patch(s, body, "残し");
}
function card(s) {
  const procs = S.data.processes.filter((p) => p.service_id === s.id);
  const routed = S.data.routes.filter((r) => r.service_id === s.id);
  const t = s.usage_terms;
  return html`<section class="card con" id="con-${s.id}" data-service=${s.id} ?open=${S.open === s.id}>
    <div class="card-h">${dot(s)}<span class="h2">${s.name}</span>
      <span class="meta">${KIND[s.kind]}・${s.location === "local" ? "手元" : "API"}・${s.adapter}・${stateLabel(s)}</span>
      <span class="meta">休ませる</span><button class="sw" role="switch" aria-checked=${String(s.paused)} aria-label="${s.name}を休ませる"
        @click=${() => patch(s, { paused: !s.paused }, s.paused ? "戻し" : "休ませ")} ?disabled=${S.busy}></button></div>
    <div class="meta">${routed.length ? `送り先にしている処理 ${routed.length}：${routed.map((r) => r.process).join("・")}` : "送り先にしていない"}${s.paused ? "。休ませた先へ頼んだものは待ちに入り、戻すと順に送ります" : ""}</div>
    <form class="form" @submit=${(e) => saveConn(e, s)}>
      <label class="k">住所</label><input class="field mono" name="endpoint" .value=${s.endpoint || ""}>
      <span class="k">送り方</span><div class="row wrap">${Object.entries(SEND).map(([k, l]) => html`<button type="button" class="chip" aria-pressed=${String(s.send_mode === k)}
          @click=${() => s.send_mode !== k && patch(s, { send_mode: k }, "送り方を変え")}>${l}</button>`)}
        <input class="field num short" name="max_concurrency" type="number" min="1" .value=${String(s.max_concurrency)} aria-label="同時に送る数"><span class="meta">件まで</span></div>
      <label class="k">月の予算</label><div class="row"><input class="field num" name="monthly_budget" type="number" min="0" .value=${s.monthly_budget == null ? "" : String(s.monthly_budget)}><span class="meta">円</span></div>
      <div class="full acts"><button class="btn sm" ?disabled=${S.busy}>${icon("save")}残す</button>
        <span class="meta">APIキーはサーバー（LiteLLM）だけが持ちます。つながるか試す・いまの走り具合・止まったもの・入っているモデルを読む口はまだありません</span></div>
    </form>
    <details class="more"><summary>${icon("chevron-right")}受けられる処理 ${procs.length}</summary>
      <div class="t-wrap"><table class="t"><tr><th>処理</th><th>得意さ</th><th>1回の費用</th><th>モデル</th></tr>
      ${procs.map((p) => html`<tr><td>${p.process}</td><td>${APT[p.aptitude] ? APT[p.aptitude].join(" ") : "未記入"}</td>
        <td class="num">${p.cost_per_call == null ? "未記入" : `¥${p.cost_per_call}`}</td><td class="mono">${p.model || ""}</td></tr>`)}</table></div></details>
    <details class="more"><summary>${icon("chevron-right")}商用利用の条件 <span class="flag ${t ? "mut" : "warn"}">${t ? `確かめた日 ${t.checked_on}` : "未記録"}</span></summary>
      ${t ? html`<div class="meta">商用 ${YNU[t.commercial_use]}・出力の権利 ${t.rights_holder}・学習に使われる ${YNU[t.training_use]}・クレジット ${YNU[t.credit_required]}</div>` : nothing}
      <form class="form" @submit=${(e) => saveTerms(e, s)}>${fieldsHtml(USAGE_TERMS, t || {}, "terms.")}
        <div class="full acts"><button class="btn sm" ?disabled=${S.busy}>${icon("save")}残す</button></div></form></details>
  </section>`;
}
function addService(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { name: f.get("name").trim(), kind: f.get("kind"), location: f.get("location"), adapter: f.get("adapter"),
                 endpoint: f.get("endpoint").trim() || null, send_mode: f.get("send_mode"), max_concurrency: Number(f.get("max_concurrency")) };
  run("つなぎ先を足す", async () => { await api.post("/services", body); S.adding = false; toast(`${body.name} を足しました`); });
}
function consTab() {
  const sel = (name, map) => html`<select class="field" name=${name}>${Object.entries(map).map(([k, l]) => html`<option value=${k}>${l}</option>`)}</select>`;
  return html`<div class="acts"><button class="btn ghost sm" @click=${() => { S.adding = !S.adding; draw(); }} aria-expanded=${String(S.adding)}>${icon("plus")}つなぎ先を足す</button></div>
    ${S.adding ? html`<form class="card" @submit=${addService} aria-label="つなぎ先を足す"><div class="form">
      <span class="k">名前</span><input class="field" name="name" required>
      <span class="k">種類</span>${sel("kind", KIND)}
      <span class="k">場所</span>${sel("location", { local: "手元", api: "API" })}
      <span class="k">送り手</span>${sel("adapter", { comfyui: "ComfyUI", litellm: "LiteLLM", detector: "検出器" })}
      <span class="k">住所</span><input class="field mono" name="endpoint">
      <span class="k">送り方</span>${sel("send_mode", SEND)}
      <span class="k">同時に送る数</span><input class="field" name="max_concurrency" type="number" min="1" value="1">
      <div class="full acts"><button class="btn primary sm" ?disabled=${S.busy}>足す</button>
        <span class="meta">手元と登録できるのは、この機械の住所へ直接送る先だけです（サーバーが確かめます）</span></div></div></form>` : nothing}
    ${Object.entries(KIND).map(([k, l]) => html`<div class="lbl grp">${l}</div><div class="grid wide">${S.data.services.filter((s) => s.kind === k).map(card)}</div>`)}`;
}

// ---------------------------------------------------------------- 参加者の見え方
function memberView() {
  if (!S.member) return emptyNote(S.why || "作品を選んでください。参加者は、その作品から見えるつなぎ先だけを見られます", S.why ? "need" : "");
  const name = (id) => (S.member.services.find((s) => s.id === id) || {}).name || id;
  return html`<div class="note">${icon("info")}<span>管理者ではないので、この作品から見える項目だけを出しています。送り先を変えるのは管理者です</span></div>
    <section class="card"><div class="card-h"><span class="h2">つなぎ先</span></div>
    <div class="t-wrap"><table class="t" id="member-services"><tr><th>名前</th><th>種類</th><th>場所</th><th>状態</th><th>この作品から</th><th>商用利用の条件</th></tr>
    ${S.member.services.map((s) => html`<tr data-service=${s.id}><td>${s.name}</td><td>${KIND[s.kind]}</td><td>${s.location === "local" ? "手元" : "API"}</td>
      <td><span class="row">${dot(s)}${stateLabel(s)}</span></td><td>${s.allowed ? "送ってよい" : html`<span class="flag warn">送れない</span>`}</td>
      <td>${s.usage_terms ? `商用 ${YNU[s.usage_terms.commercial_use]}（${s.usage_terms.checked_on}）` : html`<span class="flag warn">未記録</span>`}</td></tr>`)}</table></div></section>
    <section class="card"><div class="card-h"><span class="h2">処理ごとの送り先</span></div>
    <div class="t-wrap"><table class="t"><tr><th>処理</th><th>送り先</th></tr>${S.member.routes.map((r) => html`<tr><td>${r.process}</td><td>${name(r.service_id)}</td></tr>`)}</table></div></section>`;
}

function draw() {
  if (S.admin === null) { render(emptyNote(S.why || "読んでいます"), main); return; }
  if (!S.admin) { render(memberView(), main); return; }
  render(html`<div class="row wrap"><span class="flag mut">全作品で共通</span><span class="h1">生成サービス</span></div>
    <div class="tabs" role="tablist">${[["routes", "処理ごとの送り先"], ["cons", "つなぎ先"]].map(([k, l]) => html`
      <button class="tab" role="tab" data-tab=${k} aria-selected=${String(S.tab === k)} @click=${() => { S.tab = k; draw(); }}>${l}</button>`)}</div>
    ${S.tab === "routes" ? routesTab() : consTab()}`, main);
  if (S.tab === "cons" && S.open) {
    const el = document.getElementById(`con-${S.open}`);
    if (el) el.scrollIntoView({ block: "start" });
    S.open = null;
  }
}

await startShell({ screen: "services", onWork: load });
