// V3 の AIハーネスの画面（/web/harness/?work=<作品の id>）。
// 状態の正本はサーバー（harness_* の表）。この画面は snapshot を取り、その last_event_id の続きを SSE で受けて当てる。
// 切れたら「切断中」を出し、つなぎ直すときに snapshot を取り直す（取りこぼしも重なりも無い。live_stream.py）。
// 口は全部 ../js/api.js の authFetch を通す（名乗りの見出しと X-V3-Request を付ける所は api.js の1か所）。
import { loadAuth, mode, myName, currentUser, setUser, authFetch, showIn, get, post as apiPost, put, op } from "../js/api.js";
import { readStream } from "./harness_sse.js";
import { storedWork, rememberWork } from "../common/nav.js";
import { startKeys, km } from "../common/keys.js";
import { HarnessGraph, STATUS_JA, STEP_JA, STEPS, statusClass, isHumanWait, urgentStatus } from "./harness_graph.js";

const STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"];
const STAGE_JA = { S0: "企画", S1: "構成", S2: "設定資料", S3: "ネーム", S4: "作画", S5: "仕上げ", S6: "総合", S7: "書き出し" };
const ITEM_JA = { stopped: "止まった作業", check_failed: "検査で落ちた候補", candidates: "候補の判断待ち",
                  stale: "上流が変わった", held_ai_change: "保留のAIの変更", stage_review: "工程の承認待ち" };
const ACTIVE = new Set(["queued", "running", "waiting_limit", "waiting_budget", "retrying", "cancelling"]);
// 上限の名前（harness_limits.py の UnitLimits の項目）
const LIMIT_JA = { max_attempts: "回の上限", candidates_per_attempt: "1回の候補の数", budget_cost: "費用の上限",
                   budget_seconds: "秒の上限", error_stop: "続けて失敗したら止める", same_failure_restart: "同じ失敗で文脈から",
                   eval_repeats: "評価を繰り返す数", disagreement_stop: "評価が割れたら止める", review_notice_seconds: "判断待ちの知らせ（秒）",
                   resend_limit: "送り直しの上限", max_fix_rounds: "直させる回数の上限", wait_seconds: "順番待ちの上限（秒）",
                   redo_on_reject: "却下したらすぐ作り直す" };
// 作業の種類の名前と、何を対象にするか（作品・話・コマ）
const KIND_JA = { plan_interview: "企画の聞き取り", structure: "構成", settings_sheet: "設定資料", name_draft: "ネームの作業",
                  panel_drawing: "コマの作画", page_finishing: "仕上げ", overall_review: "総合", export: "書き出し" };
const WHOLE = { plan_interview: "作品全体", settings_sheet: "作品全体", structure: "話全体", name_draft: "話全体",
                page_finishing: "話全体", overall_review: "話全体", export: "話全体" };
// 作業役が人へ質問を返す種類（サーバーの TAKES_ANSWERS と同じ。ほかの種類はサーバーが answer を断る）
const ANSWER_KINDS = new Set(["plan_interview"]);
const CAND_JA = { requested: "頼んだ", generated: "描けた", failed: "失敗", cancelled: "取り消した" };
const RUNNING = new Set(["running", "retrying", "cancelling"]);

const $ = (s) => document.querySelector(s);
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "text") el.textContent = v;
    else if (k === "cls") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) el.append(c);
  return el;
}

// ------------------------------------------------------------------ サーバー

// ハーネスの書き込みの口は本体を要るので、空でも {} を送る
const post = (p, body) => apiPost(p, body ?? {});

// ------------------------------------------------------------------ 状態

const S = {
  workId: null, work: null, episodeId: null,
  runs: new Map(), units: new Map(), stale: new Map(), progress: new Map(),
  view: "stage", unitId: null, stageSel: null, detail: null, pos: null,
  conn: "connecting", retries: 0, lastEventId: 0, abort: null,
  reviewItems: [], toast: null, thresholds: null, notes: [], notify: null,
};
// 確かめのための値（Playwright で読む。画面の動きには使わない）
const probe = window.__harness = { latencies: [], events: 0, lastTraversal: null, conn: "connecting", reconnects: 0 };

let graph;

// ------------------------------------------------------------------ 入口

async function main() {
  const params = new URLSearchParams(location.search);
  S.workId = storedWork();
  S.unitId = params.get("unit");
  if (S.unitId) S.view = "unit";
  await loadAuth();
  // キー・キーの一覧・絵だけ（図だけを大きく出す。見張る画面として使う）・全画面（common/keys.js）
  km.bind("harness.fit", () => graph?.cy.fit(undefined, 40));
  km.bind("harness.stageView", () => openStageView());
  await startKeys("harness");
  if (mode() === "oidc") {
    $("#user").value = myName();
    $("#user").readOnly = true;
  } else {
    $("#user").value = currentUser();
    $("#user-form").addEventListener("submit", (e) => { e.preventDefault(); setUser($("#user").value.trim()); location.reload(); });
    if (!currentUser()) { showEmpty("利用者の名前を入れてください"); return; }
  }
  if (!S.workId) {
    const works = await get("/works");
    if (!works.length) { showEmpty("見てよい作品がありません"); return; }
    S.workId = works[0].id;
  }
  rememberWork(S.workId);
  graph = new HarnessGraph($("#graph"), $("#graph-overlay"), { onTap, onStepsChanged: refreshDetail });
  // 画面の試験（harness_ui.mjs）が図の中を見る。たたんだノードの data には中の要素（collapsedChildren）が入り、
  // ブラウザの外へ渡せないので、文字・数・真偽の値だけを渡す
  probe.graphNodes = (sel) => graph.cy.nodes(sel).map((n) =>
    Object.fromEntries(Object.entries(n.data()).filter(([, v]) => v === null || typeof v !== "object")));
  probe.toggleStep = (step) => graph.toggleStep(step);  // 同じく、段を押したのと同じ動き
  $("#tab-stage").addEventListener("click", () => openStageView());
  $("#tab-unit").addEventListener("click", () => S.unitId && openUnit(S.unitId));
  $("#fit").addEventListener("click", () => graph.cy.fit(undefined, 40));
  $("#fold").addEventListener("click", () => graph.setAllCollapsed(true));
  $("#unfold").addEventListener("click", () => graph.setAllCollapsed(false));
  // 絵だけ・Tab でパネルが出入りすると図の箱の大きさが変わる。Cytoscape は箱の大きさを自分では見ないので知らせる
  window.addEventListener("v3-view", () => requestAnimationFrame(() => { graph.cy.resize(); graph.cy.fit(undefined, 40); }));
  setInterval(tick, 500);
  await loadWork();
  connect();
}

async function loadWork() {
  S.work = await get(`/works/${S.workId}`);
  $("#work-title").textContent = S.work.work.title;
}

function showEmpty(msg) { $("#empty").textContent = msg; $("#empty").hidden = false; }

// ------------------------------------------------------------------ つなぐ・切れる・つなぎ直す

async function connect() {
  setConn(S.retries ? "reconnecting" : "connecting");
  try {
    const snap = await get(`/works/${S.workId}/harness/snapshot${S.view === "unit" && S.unitId ? `?unit_id=${S.unitId}` : ""}`);
    applySnapshot(snap);
    S.abort = new AbortController();
    await readStream(authFetch, `/works/${S.workId}/harness/stream?after=${S.lastEventId}`, {
      signal: S.abort.signal,
      onOpen: () => { S.retries = 0; setConn("live"); },
      onEvent: onEvent,
    });
  } catch (e) {
    if (e.name === "AbortError") return;
    console.warn("ハーネスの流れが切れた", e);
  }
  S.retries += 1;
  probe.reconnects += 1;
  setConn("disconnected");
  setTimeout(connect, Math.min(1500 * S.retries, 8000));
}

function setConn(c) {
  S.conn = probe.conn = c;
  const el = $("#conn");
  el.className = `conn conn-${c}`;
  el.textContent = { connecting: "つないでいます", reconnecting: "つなぎ直しています", live: "受信中",
                     disconnected: `切断中（${S.retries}回目のつなぎ直しを待つ）` }[c];
  document.body.classList.toggle("is-disconnected", c === "disconnected" || c === "reconnecting");
}

function applySnapshot(snap) {
  S.lastEventId = snap.last_event_id;
  S.runs = new Map(snap.stage_runs.map((r) => [r.id, r]));
  S.units = new Map(snap.units.map((u) => [u.unit_id, u]));
  S.stale = new Map(snap.stale.map((m) => [m.id, m]));
  S.progress = new Map(snap.progress.map((p) => [p.candidate_id, p]));
  for (const u of S.units.values()) u.stale = false;
  for (const m of S.stale.values()) if (S.units.has(m.unit_id)) S.units.get(m.unit_id).stale = true;
  const latest = [...S.runs.values()].at(-1);
  S.episodeId = latest ? latest.episode_id : (S.work.episodes[0] || {}).id;
  if (snap.unit) { S.detail = normalizeDetail(snap.unit); S.pos = positionOf(S.detail); }
  if (S.view === "unit" && S.detail) { graph.showUnit(); }
  else { S.view = "stage"; buildStageGraph(); }
  render();
  refreshReviewItems();
}

// ------------------------------------------------------------------ 出来事を当てる

function onEvent({ id, event, data }) {
  if (id) S.lastEventId = Math.max(S.lastEventId, Number(id));  // 確定の遅れた出来事は小さい id で後から届く
  probe.events += 1;
  const at = Date.parse(event === "progress" ? data.updated_at : data.at);
  const kind = event;
  if (kind === "progress") {
    S.progress.set(data.candidate_id, data);
  } else if (kind === "stage") {
    const old = S.runs.get(data.stage_run_id) || { id: data.stage_run_id, created_at: data.at };
    S.runs.set(data.stage_run_id, { ...old, id: data.stage_run_id, episode_id: data.episode_id, stage: data.stage,
                                    status: data.status, stop_reason: data.stop_reason, stage_check: data.stage_check,
                                    next_stage_run_id: data.next_stage_run_id, limits: data.limits, updated_at: data.at });
    if (data.episode_id) S.episodeId = data.episode_id;
  } else if (kind === "stale") {
    for (const m of data.marks) S.stale.set(m.mark_id, { id: m.mark_id, unit_id: data.unit_id, ...m, status: "open" });
    markStale(data.unit_id);
  } else if (kind === "stale_resolved") {
    S.stale.delete(data.mark_id);
    markStale(data.unit_id);
  } else if (kind === "step") {
    if (S.detail && data.unit_id === S.detail.unit_id) applyStep(data);
  } else if (data.unit_id && data.status !== undefined) {
    const prev = S.units.get(data.unit_id);
    const u = { ...(prev || {}), ...data, stale: prev ? prev.stale : false };
    S.units.set(data.unit_id, u);
    if (kind === "unit_created" && data.rerun_of) {
      for (const [mid, m] of S.stale) if (m.unit_id === data.rerun_of) S.stale.delete(mid);
      markStale(data.rerun_of);
    }
    if (S.detail && data.unit_id === S.detail.unit_id) applyUnitToDetail(u, kind, data);
    if (kind === "unit_created" && u.page_id && !panelOf(u)) loadWork().then(render);
  }
  scheduleRender(Number.isFinite(at) ? { kind, at } : null);
  if (kind === "notification") browserNotify(data);
  if (kind !== "progress" && kind !== "step") scheduleReviewItems();
}

function markStale(unitId) {
  const u = S.units.get(unitId);
  if (u) u.stale = [...S.stale.values()].some((m) => m.unit_id === unitId);
}

// 作業の図：段の行と人の判断を時間の順に並べ、辺の数と今いる所を出す
function normalizeDetail(d) {
  // 候補の一覧は cands に置く（作業の出来事の candidates は候補の数で、名前がぶつかる）
  return { ...d, cands: d.candidates || [], steps: new Map(d.steps.filter((s) => s.step !== "discard_round").map((s) => [s.id, s])),
           decisions: d.decisions || [] };
}

function sequenceOf(d) {
  const seq = [...d.steps.values()].map((s) => ({ node: s.step, t: Date.parse(s.started_at) }));
  for (const x of d.decisions) seq.push({ node: "review", t: Date.parse(x.at) - 1 });
  seq.sort((a, b) => a.t - b.t);
  const u = S.units.get(d.unit_id) || d;
  if (u.status === "awaiting_review") seq.push({ node: "review", t: Infinity });
  if (u.status === "done") seq.push({ node: "end", t: Infinity });
  return seq;
}

function positionOf(d) {
  const seq = sequenceOf(d);
  return seq.length ? seq.at(-1).node : null;
}

function applyStep(e) {
  const d = S.detail;
  if (e.step === "discard_round") return;
  const row = d.steps.get(e.step_id) || { id: e.step_id, step: e.step, attempt: e.attempt };
  if (e.status === "running") Object.assign(row, { status: "running", started_at: e.started_at, finished_at: null });
  else Object.assign(row, { status: e.status, finished_at: e.finished_at, detail: e.detail });
  d.steps.set(e.step_id, row);
  if (e.status === "running") moveTo(e.step);
  else scheduleDetailReload();
}

function applyUnitToDetail(u, kind, data) {
  Object.assign(S.detail, u);
  if (kind === "review") {
    S.detail.decisions.push({ at: data.at, action: data.action, by: data.by, reason: data.reason });
    scheduleDetailReload();
  }
  if (u.status === "awaiting_review") { moveTo("review"); scheduleDetailReload(); }
  if (u.status === "done") moveTo("end");
}

function moveTo(node) {
  if (S.pos && S.pos !== node && S.view === "unit") {
    if (graph.traverse(S.pos, node)) probe.lastTraversal = graph.lastTraversal;
  }
  S.pos = node;
}

let detailTimer = null;
function scheduleDetailReload() {
  clearTimeout(detailTimer);
  detailTimer = setTimeout(async () => {
    if (!S.detail) return;
    const id = S.detail.unit_id;
    const d = await get(`/works/${S.workId}/harness/units/${id}`).catch(() => null);
    if (!d || !S.detail || S.detail.unit_id !== id) return;
    const pos = S.pos;
    S.detail = normalizeDetail(d);
    S.pos = pos;
    render();
  }, 200);
}

// ------------------------------------------------------------------ 描く

let renderQueued = false;
const pendingLatency = [];
function scheduleRender(lat) {
  if (lat) pendingLatency.push(lat);
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    render();
    const now = Date.now();
    for (const l of pendingLatency.splice(0)) {
      probe.latencies.push({ kind: l.kind, ms: now - l.at });
      if (probe.latencies.length > 2000) probe.latencies.shift();
    }
  });
}

function render() {
  document.body.dataset.view = S.view;
  $("#tab-stage").classList.toggle("on", S.view === "stage");
  $("#tab-unit").classList.toggle("on", S.view === "unit");
  $("#tab-unit").disabled = !S.unitId;
  if (S.view === "stage") renderStageGraph(); else renderUnitGraph();
  renderSide();
  renderTable();
}

function runsOfEpisode() {
  return [...S.runs.values()].filter((r) => r.episode_id === S.episodeId);
}
function latestRun(stage) {
  return runsOfEpisode().filter((r) => r.stage === stage).at(-1) || null;
}
function unitsOfRun(run) {
  return run ? [...S.units.values()].filter((u) => u.stage_run_id === run.id) : [];
}

function stageInfo(stage) {
  const run = latestRun(stage);
  const units = unitsOfRun(run);
  const count = (pred) => units.filter(pred).length;
  const parts = [];
  if (units.length) {
    parts.push(`完了 ${count((u) => u.status === "done")}/${units.length}`);
    const run_ = count((u) => RUNNING.has(u.status));
    const queued = count((u) => ACTIVE.has(u.status) && !RUNNING.has(u.status));
    const wait = count((u) => isHumanWait(u.status));
    if (run_) parts.push(`実行中 ${run_}`);
    if (queued) parts.push(`送り先を待つ ${queued}`);
    if (wait) parts.push(`人を待つ ${wait}`);
  }
  const status = run ? run.status : null;
  return { stage, cls: run ? statusClass(status) : "st-none unused", lines: 2 + parts.length,
           label: `${stage} ${STAGE_JA[stage]}\n${status ? STATUS_JA[status] || status : "まだ"}${parts.length ? `\n${parts.join("\n")}` : ""}` };
}

function buildStageGraph() {
  graph.showStages(STAGES.map(stageInfo));
  renderStageGraph();
}

function unitLabel(u) {
  const p = panelOf(u);
  const page = pageOf(u);
  const where = WHOLE[u.kind] || `p${page ? page.number : "?"}-${p ? p.order : "?"}`;
  const tries = u.max_attempts ? ` ${u.attempt}/${u.max_attempts}` : "";
  const step = u.step && ACTIVE.has(u.status) ? `\n${STEP_JA[u.step] || u.step}` : "";
  return `${where}${tries}\n${STATUS_JA[u.status] || u.status}${u.stale ? "・古い" : ""}${step}`;
}

// 工程の図で作業を入れるまとまり（ページ。ページを持たない作業は、作品・話の全体として1つにまとめる）
function unitGroup(u) {
  if (WHOLE[u.kind]) return { key: "whole", label: WHOLE[u.kind] };
  const page = pageOf(u);
  return { key: u.page_id || "none", label: page ? `p${page.number}` : "ページなし" };
}

function renderStageGraph() {
  for (const s of STAGES) graph.updateStage(stageInfo(s));
  for (const s of STAGES) {
    const units = unitsOfRun(latestRun(s));
    if (units.length) graph.setUnits(s, units, unitLabel, unitGroup);
  }
  graph.setProgress([...S.progress.values()].filter((p) => p.state === "running" || p.state === "pending"));
}

function renderUnitGraph() {
  const d = S.detail;
  if (!d) return;
  const seq = sequenceOf(d);
  const counts = {};
  for (let i = 1; i < seq.length; i++) {
    if (seq[i].node === seq[i - 1].node) continue;
    const k = `${seq[i - 1].node}>${seq[i].node}`;
    counts[k] = (counts[k] || 0) + 1;
  }
  const states = {};
  for (const s of [...d.steps.values()].sort((a, b) => Date.parse(a.started_at) - Date.parse(b.started_at))) {
    const st = states[s.step] || (states[s.step] = { count: 0 });
    st.count += 1;
    st.status = s.status;
  }
  const u = S.units.get(d.unit_id) || d;
  const rejects = d.decisions.filter((x) => x.action === "reject").length;
  states.review = { count: d.decisions.length + (u.status === "awaiting_review" ? 1 : 0),
                    status: d.decisions.length ? "done" : null, note: rejects ? `却下 ${rejects}` : "" };
  if (u.status === "done") states.end = { count: 1, status: "done" };
  if (states.generate) states.generate.note = `候補 ${u.candidates}`;
  const current = u.status === "awaiting_review" ? "review" : u.status === "done" ? "end" : (u.step || S.pos);
  graph.setStepParts(stepParts(d, u));
  graph.setSteps(states, current, u.status);
  graph.setEdgeCounts(counts);
  // 進み具合は生成の段にいる間だけ出す（終わった後は候補の一覧と判断のパネルで見る）
  const generating = u.step === "generate" && ACTIVE.has(u.status);
  graph.setProgress(generating ? [...S.progress.values()].filter((p) => p.unit_id === d.unit_id && p.attempt === u.attempt) : []);
}

// 段の中の子（今の回の分）。生成・直させるは送り先ごと、検査は項目ごと、評価はくり返しの回ごと
// 依頼の段は harness_key（<作業>:a<回>:<種類>…）の種類で分ける：gen・comp は生成、fix は直させる
function stepParts(d, u) {
  const att = `a${u.attempt}`;
  const jobsOf = (re) => (d.jobs || []).filter((j) => {
    const k = (j.harness_key || "").split(":");
    return k[1] === att && re.test(k[2] || "");
  });
  const byService = (jobs) => {
    const by = new Map();
    for (const j of jobs) {
      if (!by.has(j.service_id)) by.set(j.service_id, { name: j.service_name, list: [] });
      by.get(j.service_id).list.push(j);
    }
    return [...by].map(([id, g]) => {
      const bad = g.list.filter((j) => j.failure_kind).length;
      return { id, status: urgentStatus(g.list.map((j) => j.status)),
               label: `${g.name}\n依頼 ${g.list.length}${bad ? `・失敗 ${bad}` : ""}` };
    });
  };
  const checks = new Map();
  for (const c of d.cands.filter((x) => `a${x.attempt}` === att && x.check)) {
    for (const f of c.check.findings || []) {
      if (!checks.has(f.name)) checks.set(f.name, { ok: 0, ng: 0, none: 0 });
      const t = checks.get(f.name);
      if (f.ok === true) t.ok += 1; else if (f.ok === false) t.ng += 1; else t.none += 1;
    }
  }
  const evals = [...d.steps.values()].filter((x) => x.step === "evaluate" && `a${x.attempt}` === att && x.detail?.rounds)
    .sort((a, b) => Date.parse(a.started_at) - Date.parse(b.started_at));
  const ev = evals.at(-1)?.detail;
  const short = (cid) => { const c = d.cands.find((x) => x.id === cid); return c ? `#${c.k_index + 1}` : "?"; };
  const repeats = ev ? [...new Set(ev.rounds.map((r) => r.repeat))] : [];
  return {
    generate: byService(jobsOf(/^(gen|comp)\d/)),
    fix: byService(jobsOf(/^fix\d/)),
    check: [...checks].map(([name, t]) => ({ id: name, status: t.ng ? "failed" : t.none ? "waiting_limit" : "done",
      label: `${name}\n通る ${t.ok}・落ちる ${t.ng}${t.none ? `・測れない ${t.none}` : ""}` })),
    evaluate: repeats.map((r) => {
      const rs = ev.rounds.filter((x) => x.repeat === r);
      const ties = rs.filter((x) => x.verdict === "tie").length;
      const top = ev.tops[r];
      return { id: String(r), status: top ? "done" : "stopped",
               label: `${r + 1}回目 比べた ${rs.length}${ties ? `・同点 ${ties}` : ""}\n1位 ${top ? short(top) : "決まらない"}` };
    }),
  };
}

function tick() {
  if (S.view === "unit" && S.detail) renderTimeline();
  // 判断待ちの経過時間などの表示を進める
  for (const el of document.querySelectorAll("[data-since]")) el.textContent = ago(el.dataset.since);
}

function ago(iso) {
  const s = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
  return s < 60 ? `${s}秒` : s < 3600 ? `${Math.floor(s / 60)}分${s % 60}秒` : `${Math.floor(s / 3600)}時間${Math.floor((s % 3600) / 60)}分`;
}

// ------------------------------------------------------------------ 時間の列（作業の図の下）

function renderTimeline() {
  const d = S.detail;
  const box = $("#timeline");
  const rows = [...d.steps.values()].filter((s) => s.started_at);
  if (!rows.length) { box.replaceChildren(h("p", { cls: "muted", text: "まだ段が始まっていません" })); return; }
  const u = S.units.get(d.unit_id) || d;
  const bars = rows.map((s) => ({ lane: s.step, t0: Date.parse(s.started_at),
                                  t1: s.finished_at ? Date.parse(s.finished_at) : Date.now(), status: s.status,
                                  label: `${STEP_JA[s.step]} ${s.attempt ? `${s.attempt}回目` : ""}` }));
  // 人の判断を待った間：その前に終わった段から、判断の時刻（まだなら今）まで
  const ends = rows.filter((s) => s.finished_at).map((s) => Date.parse(s.finished_at)).sort((a, b) => a - b);
  const waits = d.decisions.map((x) => ({ t1: Date.parse(x.at), action: x.action }));
  if (u.status === "awaiting_review") waits.push({ t1: Date.now(), action: null });
  for (const w of waits) {
    const t0 = ends.filter((t) => t <= w.t1).at(-1);
    if (t0) bars.push({ lane: "review", t0, t1: w.t1, status: w.action ? "done" : "awaiting_review",
                        label: w.action ? { approve: "採用", reject: "却下", edit: "直した絵" }[w.action] : "判断待ち" });
  }
  const tmin = Math.min(...bars.map((b) => b.t0));
  const tmax = Math.max(Date.now() - (ACTIVE.has(u.status) || isHumanWait(u.status) ? 0 : 1e12), ...bars.map((b) => b.t1));
  const span = Math.max(1, tmax - tmin);
  const lanes = STEPS.filter((s) => bars.some((b) => b.lane === s));
  const key = bars.map((b) => `${b.lane}${b.t0}${b.status}`).join() + lanes.join();
  if (box.dataset.key !== key) {
    box.dataset.key = key;
    box.replaceChildren(...lanes.map((lane) => h("div", { cls: "tl-lane", dataset: { lane } },
      h("span", { cls: "tl-name", text: STEP_JA[lane] }), h("div", { cls: "tl-track" }))));
    for (const b of bars) {
      const track = box.querySelector(`[data-lane="${b.lane}"] .tl-track`);
      track.append(h("span", { cls: `tl-bar ${statusClass(b.status)}`, title: b.label, dataset: { t0: b.t0, t1: b.t1, live: b.status === "running" || b.status === "awaiting_review" ? "1" : "" } }));
    }
  }
  for (const el of box.querySelectorAll(".tl-bar")) {
    const t0 = Number(el.dataset.t0);
    const t1 = el.dataset.live ? Date.now() : Number(el.dataset.t1);
    el.style.left = `${(100 * (t0 - tmin)) / span}%`;
    el.style.width = `${Math.max(0.6, (100 * (t1 - t0)) / span)}%`;
  }
  $("#timeline-span").textContent = `${((tmax - tmin) / 1000).toFixed(1)}秒`;
}

// ------------------------------------------------------------------ 横のパネル

function renderSide() {
  const side = $("#side");
  const key = sideKey();
  if (side.dataset.key === key) return;
  const focused = document.activeElement && side.contains(document.activeElement) && document.activeElement.matches("input, textarea");
  if (focused) return;  // 入力の途中は作り直さない（次の出来事で作る）
  side.dataset.key = key;
  side.replaceChildren(...(S.view === "unit" && S.detail ? unitPanel() : stagePanel()));
}

function sideKey() {
  if (S.view === "unit" && S.detail) {
    const u = S.units.get(S.detail.unit_id) || S.detail;
    return JSON.stringify([u.unit_id, u.status, u.step, u.attempt, u.stop_reason, u.cost_used, u.candidates, u.stale,
                           S.detail.cands.map((c) => [c.id, c.status, c.check_verdict, c.picked]),
                           S.detail.decisions.length, u.limits || S.detail.limits]);
  }
  const run = S.stageSel ? S.runs.get(S.stageSel) : runsOfEpisode().at(-1);
  return JSON.stringify(["stage", run && [run.id, run.status, run.stop_reason, run.stage_check], S.reviewItems.length, S.thresholds,
                         S.notes.map((n) => n.id), S.notify,
                         S.reviewItems.map((i) => i.kind + (i.unit_id || i.stage_run_id || ""))]);
}

function chip(status) { return h("span", { cls: `chip ${statusClass(status)}`, text: STATUS_JA[status] || status || "まだ" }); }

function act(label, fn, cls = "") {
  return h("button", { type: "button", cls: `btn ${cls}`, onclick: async (e) => {
    const b = e.currentTarget;
    b.disabled = true;
    try { await fn(); toast(`${label}を送りました`); }
    catch (err) { toast(`${label}できません：${err.message}`, true); }
    finally { b.disabled = false; }
  } }, label);
}

function unitPanel() {
  const d = S.detail;
  const u = S.units.get(d.unit_id) || d;
  const base = `/works/${S.workId}/harness/units/${u.unit_id}`;
  const out = [];
  out.push(h("div", { cls: "side-head" },
    h("span", { cls: "label", text: KIND_JA[u.kind] || u.kind }),
    h("h2", { text: unitLabel(u).split("\n")[0] }), chip(u.status)));
  if (u.stop_reason) out.push(h("p", { cls: `reason ${statusClass(u.status)}`, text: u.stop_reason }));
  out.push(h("dl", { cls: "kv" },
    h("dt", { text: "段" }), h("dd", { text: u.status === "awaiting_review" ? STEP_JA.review : STEP_JA[u.step] || u.step || "—" }),
    h("dt", { text: "回" }), h("dd", { text: `${u.attempt} / ${u.max_attempts ?? "—"}` }),
    h("dt", { text: "費用" }), h("dd", { text: `${u.cost_used} / ${u.budget_cost ?? "—"}` }),
    h("dt", { text: "秒" }), h("dd", { text: `${Math.round(u.seconds_used)} / ${u.budget_seconds ?? "—"}` }),
    h("dt", { text: "候補" }), h("dd", { text: String(u.candidates) })));

  const ctl = (body) => post(`${base}/control`, body);
  const btns = [];
  if (ACTIVE.has(u.status)) {
    btns.push(act("段の切れ目で止める", () => ctl({ action: "pause", mode: "boundary" })),
              act("今すぐ止める", () => ctl({ action: "pause", mode: "now" })),
              act("段を取り消す", () => ctl({ action: "cancel_step" })));
  }
  if (u.status === "paused" || u.status === "blocked" || u.status === "stopped") btns.push(act("再開", () => ctl({ action: "resume" }), "primary"));
  if (!["done", "cancelled", "failed", "cancelling"].includes(u.status)) btns.push(act("作業を取り消す", () => ctl({ action: "cancel_unit" }), "danger"));
  if (btns.length) out.push(h("div", { cls: "actions" }, btns));

  if (u.status === "awaiting_review") out.push(reviewPanel(u, d, base));

  const marks = [...S.stale.values()].filter((m) => m.unit_id === u.unit_id);
  if (marks.length) {
    out.push(h("section", { cls: "box stale-box" }, h("h3", { text: "上流が変わった（自動では作り直さない）" }),
      marks.map((m) => h("div", { cls: "stale-row" }, h("p", { text: `${m.reason}（${m.effect}）` }),
        h("div", { cls: "actions" },
          act("作り直す", () => post(`/works/${S.workId}/harness/stages/${u.stage_run_id}/rerun`, { unit_ids: [u.unit_id] }), "primary"),
          act("このままでよい", () => post(`/works/${S.workId}/harness/stale/${m.id}/dismiss`)))))));
  }

  out.push(limitsForm(u, d, base));
  out.push(candidateList(d));
  return out;
}

function reviewPanel(u, d, base) {
  const attempt = (u.review || d.review || {}).attempt ?? u.attempt;
  const picked = (u.review || d.review || {}).picked;
  const cands = d.cands.filter((c) => c.attempt === attempt);
  const reason = h("textarea", { rows: 2, placeholder: "却下の理由（次の文脈に入ります）", id: "reject-reason" });
  const edited = h("input", { type: "text", placeholder: "人が直した絵の id", id: "edit-image" });
  const answer = h("textarea", { rows: 2, placeholder: "候補が返した質問への答え（これまでの答えと一緒に次の文脈に入ります）", id: "answer-text" });
  const since = (u.review || d.review || {}).since;
  return h("section", { cls: "box review-box" },
    h("h3", {}, "人の判断を待っています", since ? h("span", { cls: "since", dataset: { since }, text: ago(since) }) : null),
    h("div", { cls: "cands" }, cands.map((c) => candidateCard(c, picked, () => post(`${base}/review`, { action: "approve", candidate_id: c.id })))),
    h("label", { cls: "label", text: "却下" }), reason,
    // 却下は止まるだけ（決めごと 5.3）。すぐ作り直すのは上限の redo_on_reject を入れたときだけ
    h("div", { cls: "actions" }, act((u.limits || d.limits || {}).redo_on_reject ? "却下して作り直す" : "却下して止める", () => {
      if (!reason.value.trim()) throw new Error("理由を入れてください");
      return post(`${base}/review`, { action: "reject", reason: reason.value.trim() });
    }, "danger")),
    ...(ANSWER_KINDS.has(u.kind) ? [h("label", { cls: "label", text: "質問に答える" }), answer,
      h("div", { cls: "actions" }, act("答えて作り直す", () => {
        if (!answer.value.trim()) throw new Error("答えを入れてください");
        return post(`${base}/review`, { action: "answer", reason: answer.value.trim() });
      }))] : []),
    h("label", { cls: "label", text: "直した絵から続ける" }), edited,
    h("div", { cls: "actions" }, act("直した絵で生成へ戻す", () => {
      if (!edited.value.trim()) throw new Error("絵の id を入れてください");
      return post(`${base}/review`, { action: "edit", image_id: edited.value.trim() });
    })));
}

function candidateCard(c, picked, approve) {
  const img = h("img", { alt: `候補 ${c.k_index + 1}` });
  if (c.image_id) showIn(img, `/works/${S.workId}/images/${c.image_id}/thumbnail?size=256`).catch((e) => { img.alt = String(e.message || e); });
  const issues = ((c.check || {}).findings || []).filter((f) => f.ok !== true).map((f) => `${f.ok === false ? "外れ" : "人が見る"}：${f.name}`);
  return h("div", { cls: `cand${c.id === picked ? " picked" : ""} v-${c.check_verdict || "none"}` },
    c.image_id ? img : c.content ? contentView(c.content) : h("div", { cls: "noimg", text: c.proposal_id ? "ネームの案" : "絵なし" }),
    h("div", { cls: "cand-meta" },
      h("span", { cls: "label", text: `#${c.k_index + 1} ${{ pass: "通過", flag: "指摘あり", drop: "落ちた" }[c.check_verdict] || "検査前"}${c.id === picked ? "・評価役が選んだ" : ""}` }),
      issues.length ? h("ul", { cls: "issues" }, issues.slice(0, 6).map((t) => h("li", { text: t }))) : null,
      c.evaluation ? h("span", { cls: "muted", text: `票 ${c.evaluation.votes}/${c.evaluation.repeats}` }) : null,
      c.check_verdict !== "drop" && (c.image_id || c.proposal_id || c.content) ? act("これを採用", approve, "primary") : null));
}

// 絵の無い候補（企画・構成・設定資料・仕上げ・総合・書き出し）の中身を、種類を問わず短い行で出す
function contentView(content) {
  const lines = [];
  const walk = (v, path) => {
    if (lines.length >= 12) return;
    if (v && typeof v === "object") {
      for (const [k, x] of Object.entries(v)) if (!["cost", "job_ids"].includes(k)) walk(x, path ? `${path}.${k}` : k);
    } else if (v !== null && v !== "") lines.push(`${path}：${v}`);
  };
  walk(content, "");
  return h("ul", { cls: "noimg content-lines" }, lines.map((t) => h("li", { text: t })));
}

function limitsForm(u, d, base) {
  const limits = u.limits || d.limits || {};
  const inputs = Object.entries(limits).filter(([, v]) => typeof v === "number" || typeof v === "boolean").map(([k, v]) =>
    h("label", { cls: "lim" }, h("span", { cls: "label key", text: LIMIT_JA[k] || k }),
      typeof v === "boolean" ? h("input", { type: "checkbox", name: k, checked: v })
        : h("input", { type: "number", name: k, value: v, step: "any" })));
  const form = h("form", { cls: "box limits", onsubmit: async (e) => {
    e.preventDefault();
    const next = {};
    for (const i of form.querySelectorAll("input")) {
      const v = i.type === "checkbox" ? i.checked : Number(i.value);
      if (v !== limits[i.name]) next[i.name] = v;
    }
    try { await post(`${base}/limits`, { limits: next }); toast("上限を変えました"); }
    catch (err) { toast(`上限を変えられません：${err.message}`, true); }
  } }, h("h3", { text: "上限（動いている作業にも効く）" }), h("div", { cls: "lim-grid" }, inputs),
  h("div", { cls: "actions" }, h("button", { type: "submit", cls: "btn" }, "上限を変える")));
  return form;
}

function candidateList(d) {
  const cands = d.cands;
  if (!cands.length) return h("section", { cls: "box" }, h("h3", { text: "候補" }), h("p", { cls: "muted", text: "まだありません" }));
  return h("section", { cls: "box" }, h("h3", { text: `候補（全 ${cands.length}）` }),
    h("table", { cls: "mini" }, h("tr", {}, ["回", "#", "状態", "検査", "落とした理由"].map((t) => h("th", { text: t }))),
      cands.map((c) => h("tr", {}, h("td", { text: c.attempt }), h("td", { text: c.k_index + 1 }), h("td", { text: CAND_JA[c.status] || c.status }),
                                   h("td", { text: c.check_verdict || "—" }), h("td", { text: c.dropped_reason || "" })))));
}

function stagePanel() {
  const out = [];
  const run = S.stageSel ? S.runs.get(S.stageSel) : runsOfEpisode().at(-1);
  if (run) {
    const base = `/works/${S.workId}/harness/stages/${run.id}`;
    out.push(h("div", { cls: "side-head" }, h("span", { cls: "label", text: "工程" }),
      h("h2", { text: `${run.stage} ${STAGE_JA[run.stage]}` }), chip(run.status)));
    if (run.stop_reason) out.push(h("p", { cls: `reason ${statusClass(run.status)}`, text: run.stop_reason }));
    const btns = [];
    if (run.status === "awaiting_review") btns.push(act("工程を承認して次へ", () => post(`${base}/approve`), "primary"));
    if (ACTIVE.has(run.status)) btns.push(act("止める", () => post(`${base}/control`, { action: "pause" })));
    if (run.status === "paused" || run.status === "blocked" || run.status === "stopped") btns.push(act("再開", () => post(`${base}/control`, { action: "resume" }), "primary"));
    if (!["done", "cancelled", "failed"].includes(run.status)) btns.push(act("工程を取り消す", () => post(`${base}/control`, { action: "cancel" }), "danger"));
    if (btns.length) out.push(h("div", { cls: "actions" }, btns));
    if (run.stage_check) out.push(h("section", { cls: "box" }, h("h3", { text: "工程の検査" }), stageCheckView(run.stage_check)));
  }
  out.push(h("section", { cls: "box" }, h("h3", { text: `判断待ちの一覧（${S.reviewItems.length}）` }),
    S.reviewItems.length ? h("ul", { cls: "items" }, S.reviewItems.map(itemRow)) : h("p", { cls: "muted", text: "ありません" })));
  out.push(noteBox());
  if (S.thresholds) out.push(thresholdBox(S.thresholds));
  if (S.notify) out.push(notifySettingsBox(S.notify));
  return out;
}

const LEVEL_JA = { info: "知らせ", warn: "注意", escalated: "急ぎ" };

// アプリの中の知らせ（未読）。出来事から作るのはサーバーの1か所（harness_notify.py）
function noteBox() {
  return h("section", { cls: "box notes" }, h("h3", { text: `知らせ（未読 ${S.notes.length}）` }),
    S.notes.length ? h("ul", { cls: "items" }, S.notes.map((n) => h("li", { cls: `item note lv-${n.level}` },
      h("span", { cls: "label", text: `${LEVEL_JA[n.level] || n.level} ${ago(n.created_at)}` }),
      h("span", { text: n.title, onclick: () => n.unit_id && openUnit(n.unit_id) }),
      n.deliveries.length ? h("span", { cls: "muted", text: n.deliveries.map((d) => `${d.channel}:${d.status}`).join(" ") }) : null,
      act("既読", () => post(`/works/${S.workId}/harness/notifications/${n.id}/read`).then(refreshReviewItems)))))
      : h("p", { cls: "muted", text: "ありません" }),
    "Notification" in window && Notification.permission === "default"
      ? h("div", { cls: "actions" }, act("ブラウザの知らせを使う", () => Notification.requestPermission())) : null);
}

function browserNotify(data) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  new Notification(`AIハーネス：${LEVEL_JA[data.level] || data.level}`, { body: data.title, tag: data.id });
}

// 作品の知らせの決まり。外（Webhook）へは、ここで入れた先にだけ送る（既定は送らない）
function notifySettingsBox(n) {
  const cur = n.settings || { kinds: Object.keys(n.kinds), webhooks: [], escalate_after_notices: null, budget_near_ratio: null };
  const checks = Object.entries(n.kinds).map(([k, ja]) => h("label", { cls: "chk" },
    h("input", { type: "checkbox", name: k, checked: cur.kinds.includes(k) }), h("span", { text: ja })));
  const hooks = h("textarea", { rows: 2, placeholder: "Webhook の URL（1行に1つ。後ろに空白で区切って送る種類を書けます）",
    "aria-label": "Webhook の URL" });
  hooks.value = cur.webhooks.map((w) => [w.url, ...(w.kinds || [])].join(" ")).join("\n");
  const esc = h("input", { type: "number", min: 1, step: 1, value: cur.escalate_after_notices ?? "", "aria-label": "急ぎに上げる回数" });
  const ratio = h("input", { type: "number", min: 0.01, max: 0.99, step: 0.01, value: cur.budget_near_ratio ?? "", "aria-label": "予算の割合" });
  const save = () => {
    const kinds = checks.map((c) => c.querySelector("input")).filter((i) => i.checked).map((i) => i.name);
    const webhooks = hooks.value.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [url, ...ks] = l.split(/\s+/);
      return ks.length ? { url, kinds: ks } : { url };
    });
    return put(`/works/${S.workId}/harness/notification-settings`, {
      kinds, webhooks, escalate_after_notices: esc.value === "" ? null : Number(esc.value),
      budget_near_ratio: ratio.value === "" ? null : Number(ratio.value) }).then(refreshReviewItems);
  };
  return h("section", { cls: "box notify-settings" }, h("h3", { text: n.settings ? "知らせの決まり" : "知らせの決まり（未設定：一覧にだけ出す）" }),
    h("p", { cls: "muted", text: "チェックした種類を上の一覧に出します。Webhook は入れた先にだけ送ります（既定は送りません）。"
      + "判断待ちの知らせが決めた回数に達すると「急ぎ」に上げ、種類の絞り込みに関係なく全部の送り先へ送ります。"
      + "予算の割合は空なら出しません。署名の鍵は画面では変えません（今の鍵をそのまま使います）。" }),
    h("div", { cls: "chks" }, checks), hooks,
    h("div", { cls: "lim-grid" },
      h("label", { cls: "lim" }, h("span", { cls: "label key", text: "急ぎに上げる回数" }), esc),
      h("label", { cls: "lim" }, h("span", { cls: "label key", text: "予算の割合（0〜1）" }), ratio)),
    h("div", { cls: "actions" }, act("決まりを保存", save, "primary")));
}

// 閾値は作品ごとに人が置く。案は出典つきで並べるだけで、押すまで入れない（黙って決めない）
function thresholdBox(rows) {
  const unset = rows.filter((r) => !r.current || r.current.status === "rejected").length;
  return h("section", { cls: "box thresholds" },
    h("h3", { text: `閾値（未設定 ${unset} / ${rows.length}）` }),
    h("p", { cls: "muted", text: "検査が読む閾値です。作品ごとに置きます。案の値は試作で測った数で、置くと「未検証」になります。"
      + "この作品の絵で確かめたら「確かめた」を押してください。測っていない鍵は案の値がないので、値と出典を入れて置きます。"
      + "閾値が無い検査は止まります（その作業は「閾値未設定」で待ちます）。" }),
    rows.map(thresholdRow));
}

function thresholdRow(r) {
  const cur = r.current;
  const prop = r.proposal;
  const value = h("input", { type: "number", step: "any", value: cur ? cur.value : prop.value ?? "", "aria-label": `${r.key} の値` });
  const source = h("input", { type: "text", value: cur ? cur.source : prop.value !== null ? prop.source : "",
                              placeholder: "出典（何で決めたか）", "aria-label": `${r.key} の出典` });
  const put = (status) => {
    if (value.value === "" || Number.isNaN(Number(value.value))) throw new Error("値を入れてください");
    if (!source.value.trim()) throw new Error("出典を入れてください");
    return op(S.workId, { type: "set_threshold", key: r.key, value: { value: Number(value.value) }, source: source.value.trim(), status })
      .then(refreshReviewItems);
  };
  const state = cur ? `${cur.value}（${{ unverified: "未検証", verified: "確かめた", rejected: "使わない" }[cur.status] || cur.status}）` : "未設定";
  return h("div", { cls: `th-row${cur ? "" : " th-unset"}` },
    h("div", { cls: "kvline" }, h("span", { cls: "label key", text: `${r.stage} ${r.key}` }), h("span", { text: state })),
    h("p", { cls: "muted", text: `${r.meaning}（${r.when}）` }),
    h("p", { cls: "muted", text: `案：${prop.value ?? "値なし"} ／ ${prop.source}` }),
    h("div", { cls: "th-inputs" }, value, source),
    h("div", { cls: "actions" },
      act("置く（未検証）", () => put("unverified")),
      cur && cur.status === "unverified" ? act("確かめた", () => put("verified"), "primary") : null));
}

function stageCheckView(c) {
  const lines = [];
  const walk = (v, path) => {
    if (v && typeof v === "object" && !Array.isArray(v)) for (const [k, x] of Object.entries(v)) walk(x, path ? `${path}.${k}` : k);
    else lines.push(h("div", { cls: "kvline" }, h("span", { cls: "label", text: path }), h("span", { text: Array.isArray(v) ? `${v.length}件` : String(v) })));
  };
  walk(c, "");
  return h("div", {}, lines.slice(0, 30));
}

function itemRow(i) {
  const u = i.unit_id ? S.units.get(i.unit_id) : null;
  const what = u ? unitLabel(u).split("\n")[0] : i.stage_run_id ? "工程" : (i.target_table || "");
  return h("li", { cls: `item k-${i.kind}`, onclick: () => (i.unit_id ? openUnit(i.unit_id) : i.stage_run_id && selectStage(i.stage_run_id)) },
    h("span", { cls: "label", text: `${i.stage || "—"} ${ITEM_JA[i.kind] || i.kind}` }),
    h("span", { text: `${what} ${i.reason || i.dropped_reason || ""}`.trim() }));
}

let reviewTimer = null;
function scheduleReviewItems() { clearTimeout(reviewTimer); reviewTimer = setTimeout(refreshReviewItems, 400); }
async function refreshReviewItems() {
  try {
    S.reviewItems = (await get(`/works/${S.workId}/harness/review-items`)).items;
    S.thresholds = (await get(`/works/${S.workId}/harness/thresholds`)).thresholds;
    S.notes = (await get(`/works/${S.workId}/harness/notifications?unread=true&limit=30`)).notifications;
    S.notify = await get(`/works/${S.workId}/harness/notification-settings`);
    renderSide();
  } catch (e) { console.warn("判断待ちの一覧を取れない", e); }
}

// ------------------------------------------------------------------ ページとコマの表

function pageOf(u) { return S.work && S.work.pages.find((p) => p.id === u.page_id); }
function panelOf(u) { return S.work ? S.work.panels.find((p) => p.id === u.target_id) : null; }

function renderTable() {
  if (!S.work) return;
  const tb = $("#table-body");
  const pages = S.work.pages.filter((p) => p.episode_id === S.episodeId && !p.removed).sort((a, b) => a.number - b.number);
  const latestByTarget = new Map();
  for (const u of S.units.values()) latestByTarget.set(u.target_id, u);  // 作られた順なので、後の物が新しい
  const rows = [];
  const ep = [...S.units.values()].filter((u) => u.kind === "name_draft" && u.target_id === S.episodeId).at(-1);
  if (ep) rows.push(h("tr", {}, h("th", { text: "話全体" }), h("td", {}, unitChip(ep, "ネーム")), h("td", { text: "" })));
  for (const page of pages) {
    const panels = S.work.panels.filter((p) => p.page_id === page.id && !p.removed).sort((a, b) => a.order - b.order);
    const units = panels.map((p) => latestByTarget.get(p.id));
    const sum = {};
    for (const u of units) { const k = u ? u.status : "none"; sum[k] = (sum[k] || 0) + 1; }
    rows.push(h("tr", {}, h("th", { text: `${page.number}ページ` }),
      h("td", {}, h("div", { cls: "chips" }, panels.map((p, i) => units[i] ? unitChip(units[i], `コマ${p.order}`)
        : h("span", { cls: `pchip ${p.image_id ? "st-done" : "st-none"}`, text: `コマ${p.order} ${p.human_confirmed ? "人が確定" : p.image_id ? "絵あり" : "作業なし"}` })))),
      h("td", { cls: "sum" }, Object.entries(sum).map(([k, n]) => h("span", { cls: `chip small ${statusClass(k)}`, text: `${STATUS_JA[k] || "作業なし"} ${n}` })))));
  }
  const key = rows.map((r) => r.textContent + r.innerHTML.length).join("|");
  if (tb.dataset.key === key) return;
  tb.dataset.key = key;
  tb.replaceChildren(...rows);
}

function unitChip(u, name) {
  return h("button", { type: "button", cls: `pchip ${statusClass(u.status)}${u.stale ? " stale" : ""}${u.unit_id === S.unitId ? " sel" : ""}`,
                       onclick: () => openUnit(u.unit_id), title: u.stop_reason || "", dataset: { unit: u.unit_id, status: u.status } },
    h("b", { text: name }), ` ${STATUS_JA[u.status] || u.status}`,
    u.max_attempts ? h("i", { text: ` ${u.attempt}/${u.max_attempts}` }) : null,
    u.stale ? h("i", { cls: "stale-tag", text: " 古い" }) : null);
}

// ------------------------------------------------------------------ 切り替え

function onTap(id, data) {
  if (data.kind === "unit") openUnit(data.unit_id);
  else if (data.kind === "stage") { const r = latestRun(data.stage); if (r) selectStage(r.id); }
  else if (data.kind === "step" && data.step === "review") { $("#side").scrollTop = 0; }
}

// 段の中を開いた・たたんだ。依頼の行（送り先ごとの子）は SSE で届かないので、作業の中身を取り直してから描く
async function refreshDetail() {
  if (S.view !== "unit" || !S.unitId) return;
  S.detail = normalizeDetail(await get(`/works/${S.workId}/harness/units/${S.unitId}`));
  renderUnitGraph();
}

function selectStage(id) {
  S.stageSel = id;
  if (S.view !== "stage") openStageView(); else render();
}

async function openUnit(id) {
  S.unitId = id;
  history.replaceState(null, "", `?work=${encodeURIComponent(S.workId)}&unit=${id}`);
  const d = await get(`/works/${S.workId}/harness/units/${id}`);
  S.detail = normalizeDetail(d);
  S.pos = positionOf(S.detail);
  S.view = "unit";
  graph.showUnit();
  $("#timeline").dataset.key = "";
  render();
  renderTimeline();
}

function openStageView() {
  S.view = "stage";
  S.detail = null;
  history.replaceState(null, "", `?work=${encodeURIComponent(S.workId)}`);
  buildStageGraph();
  render();
}

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast show${bad ? " bad" : ""}`;
  clearTimeout(S.toast);
  S.toast = setTimeout(() => { t.className = "toast"; }, 3500);
}

main().catch((e) => { console.error(e); showEmpty(`開けません：${e.message}`); });
