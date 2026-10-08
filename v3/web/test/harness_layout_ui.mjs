// AIハーネスの図の読みやすさを、Cytoscape が描いた箱で確かめる（偽のサーバー。page.route で口を横取りして答える。本物ではない）。
// 画面が出しうる状態（工程の図の開いた・たたんだ、作業の図の段を開いた・戻りが多い、実行中・判断待ち・止めた・失敗・古い・取り消し中）を、
// 広い窓（1920×1080）と 1280×800 で開き、次を数える。1つでもあれば落ちる。
//   - ノードどうしの重なり（枠の中の子は除く。子は枠からはみ出さない）
//   - ラベルどうし・ラベルとノード・ラベルと辺の重なり（自分の物は除く）
//   - 辺が端のノード以外を通る
//   - 辺どうしが同じ線を通る（並んだ線が 6px より近い）
//   - 戻りの辺・飛ばす辺が、前へ進む辺と交わる
//   - 全体を見たときの文字が 12px より小さい・図が箱からはみ出す・ラベルがノードからはみ出す
//   - 状態が変わったとき・窓の大きさが変わったときにノードが動く
//   SIZES=1920x1080 のように窓を絞れる。SHOTS=<フォルダ> で写しを撮る（ui_common.mjs）
import zlib from "node:zlib";
import { makeShot, openBrowser, serveWeb, SHOTS } from "./ui_common.mjs";

const ORIGIN = "http://harness-layout.test";
const USER = "layout-author";
const SIZES = (process.env.SIZES || "1920x1080,1280x800").split(",").map((s) => s.split("x").map(Number));

// ---------------------------------------------------------------- 試験の絵（作品の絵ではない）
function png(w, h, px) {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    for (let x = 0; x < w; x++) raw.set(px(x, y), y * (w * 3 + 1) + 1 + x * 3);
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
const ART = png(160, 120, (x, y) => (Math.abs(Math.hypot(x - 80, y - 60) - 36) < 2 || (x > 110 && (x + y) % 9 < 2) ? [30, 30, 30] : [250, 248, 240]));
const PREVIEW = `data:image/png;base64,${ART.toString("base64")}`;

// ---------------------------------------------------------------- 偽の作品と作業
const PAGES = { p1: 4, p2: 3 };
function work(pages = PAGES) {
  const ps = Object.keys(pages);
  return {
    work: { id: "w1", title: "砂の街（試験）", reading_direction: "rtl", text_direction: "vertical", medium: "paper" },
    volumes: [], episodes: [{ id: "e1", volume_id: null, number: 1, title: "一話", removed: false }],
    pages: ps.map((id, i) => ({ id, episode_id: "e1", number: i + 1, removed: false })),
    panels: ps.flatMap((pid) => Array.from({ length: pages[pid] }, (_, k) => ({ id: `${pid}-${k + 1}`, page_id: pid, order: k + 1, removed: false }))),
    text_items: [], panel_layers: [], page_items: [], spreads: [],
  };
}
const T0 = Date.parse("2026-10-08T10:00:00Z");
const at = (s) => new Date(T0 + s * 1000).toISOString();
const LIMITS = { max_attempts: 3, candidates_per_attempt: 2, budget_cost: 1000, budget_seconds: 600, max_fix_rounds: 1 };
function unit(id, status, step, extra = {}) {
  const [pid] = id.split("-");
  return { unit_id: id, stage_run_id: "r-S4", kind: "panel_drawing", status, step, page_id: pid, target_id: id, attempt: 1,
           max_attempts: 3, candidates: 2, cost_used: 2, seconds_used: 30, budget_cost: 1000, budget_seconds: 600,
           stop_reason: null, limits: LIMITS, ...extra };
}
const RUNS = [...["S0", "S1", "S2", "S3"].map((s) => ({ id: `r-${s}`, stage: s, episode_id: "e1", status: "done" })),
              { id: "r-S4", stage: "S4", episode_id: "e1", status: "running" }];
const S3_UNIT = { unit_id: "name-1", stage_run_id: "r-S3", kind: "name_draft", status: "done", step: "end", page_id: null, target_id: "e1",
                  attempt: 1, max_attempts: 3, candidates: 2, cost_used: 3, seconds_used: 40, limits: LIMITS };
const prog = (uid, k, value, state = "running", preview = null) =>
  ({ candidate_id: `${uid}:c${k}`, unit_id: uid, attempt: 1, k_index: k, state, value, max: 10, preview, updated_at: at(60 + value) });

// 段の行を時間の順に作る（names の順に始まって終わる。最後の段は status のまま）
function steps(names, last = "running", attemptOf = () => 1) {
  return names.map((step, i) => ({ id: `st${i}`, step, attempt: attemptOf(i), status: i === names.length - 1 ? last : "done",
                                   started_at: at(i * 10), finished_at: i === names.length - 1 && last === "running" ? null : at(i * 10 + 8),
                                   detail: step === "evaluate" ? { rounds: [{ repeat: 0, verdict: "a" }, { repeat: 1, verdict: "tie" }], tops: { 0: "c1", 1: null } } : null }));
}
const cands = (attempt) => [0, 1].map((k) => ({ id: `c${k + 1}`, k_index: k, attempt, status: "generated", image_id: `c${k + 1}`, check_verdict: "pass",
  check: { findings: [{ name: "人物の位置", ok: true }, { name: "顔と吹き出しの重なり", ok: k === 0 }, { name: "手", ok: null }] } }));
const jobs = (attempt) => [
  { id: "j1", harness_key: `u:a${attempt}:gen0`, service_id: "s1", service_name: "手元の ComfyUI", status: "done", failure_kind: null },
  { id: "j2", harness_key: `u:a${attempt}:gen1`, service_id: "s1", service_name: "手元の ComfyUI", status: "running", failure_kind: null },
  { id: "j3", harness_key: `u:a${attempt}:comp0`, service_id: "s2", service_name: "外の API", status: "failed", failure_kind: "timeout" },
  { id: "j4", harness_key: `u:a${attempt}:fix0`, service_id: "s1", service_name: "手元の ComfyUI", status: "done", failure_kind: null },
];
const detail = (u, names, last, extra = {}) => ({ ...u, steps: steps(names, last, extra.attemptOf), candidates: extra.candidates || cands(u.attempt),
                                                   decisions: extra.decisions || [], jobs: jobs(u.attempt), limits: LIMITS });

// 戻りを全部通った作業（3回目。却下・選べない・作り直す・直させる・直した絵から）
const MANY = ["cut_out", "context", "generate", "check", "fix", "check", "context", "generate", "check", "evaluate", "context",
              "generate", "check", "evaluate", "review", "context", "generate", "check", "evaluate", "review", "generate", "check"];
const MANY_ATT = (i) => (i < 6 ? 1 : i < 15 ? 2 : 3);
const MANY_DEC = [{ at: at(14 * 10 + 9), action: "reject", by: USER, reason: "表情が硬い" }, { at: at(19 * 10 + 9), action: "edit", by: USER, reason: null }];

function stageUnits(kind) {
  if (kind === "running") {
    return { units: [unit("p1-1", "running", "generate"), unit("p1-2", "queued", "cut_out"), unit("p1-3", "running", "check"),
                     unit("p1-4", "queued", "cut_out"), unit("p2-1", "queued", "cut_out"), unit("p2-2", "queued", "cut_out"), unit("p2-3", "queued", "cut_out")],
             progress: [prog("p1-1", 0, 6), prog("p1-1", 1, 3)], stale: [] };
  }
  return { units: [S3_UNIT, unit("p1-1", "running", "generate", { attempt: 2 }), unit("p1-2", "running", "evaluate"), unit("p1-3", "awaiting_review", "review"),
                   unit("p1-4", "paused", "generate"), unit("p2-1", "cancelling", "generate"), unit("p2-2", "failed", "check", { stop_reason: "続けて失敗した" }),
                   unit("p2-3", "blocked", "context", { stop_reason: "閾値が未設定" })],
           progress: [prog("p1-1", 0, 8), prog("p1-1", 1, 4), prog("p2-1", 0, 2, "pending")],
           stale: [{ id: "m1", unit_id: "p1-3", reason: "ネームのコマが変わった", effect: "作り直しが要る", status: "open" }] };
}

// 状態ごとの偽の答え。unit があれば作業の図を開く
const SCENARIOS = [
  { name: "01_stage_running", what: "工程の図。S4 の作業7つ（実行中2・順番待ち5）。実行中の作業の下に候補ごとの棒", ...stageUnits("running") },
  { name: "05_stage_mixed", what: "工程の図。実行中・判断待ち（古い）・止めた・取り消し中・失敗・決めるまで進めない、S3 の作業の枠も", ...stageUnits("mixed") },
  { name: "06_disconnected", what: "工程の図。流れが切れた（上の帯と図の斜線。つなぎ直しを待つ）", ...stageUnits("mixed"), stream: "down" },
  { name: "07_page_panel_table", what: "工程の図と、ページとコマの表（コマごとの状態・何回目/上限・古い印、ページごとのまとめ）。ページ全体を撮る",
    ...stageUnits("mixed"), fullPage: true },
  { name: "08_stage_folded", what: "工程の図。作業をページごとにたたんだ（内訳と一番急ぐ状態の色）", ...stageUnits("mixed"), act: "fold" },
  { name: "10_stage_many_pages", what: "工程の図。6ページ・30の作業（枠が折り返す）", pages: { p1: 5, p2: 5, p3: 5, p4: 5, p5: 5, p6: 5 },
    units: Object.entries({ p1: 5, p2: 5, p3: 5, p4: 5, p5: 5, p6: 5 }).flatMap(([p, n]) => Array.from({ length: n }, (_, k) =>
      unit(`${p}-${k + 1}`, ["running", "queued", "done", "awaiting_review", "paused"][(k + p.length) % 5], "generate"))),
    progress: [prog("p1-1", 0, 4)], stale: [] },
  { name: "03_unit_generate", what: "作業の図。生成の段（帯に候補ごとの棒、図の下に段数と途中の絵）",
    unit: () => { const u = unit("p1-1", "running", "generate"); return { u, d: detail(u, ["cut_out", "context", "generate"]) }; },
    progress: [prog("p1-1", 0, 6, "running", PREVIEW), prog("p1-1", 1, 3, "running", PREVIEW)] },
  { name: "09_unit_generate_open", what: "作業の図。生成の段を開いた（送り先ごとの依頼の数・失敗の数）",
    unit: () => { const u = unit("p1-1", "running", "generate"); return { u, d: detail(u, ["cut_out", "context", "generate"]) }; },
    progress: [prog("p1-1", 0, 6, "running", PREVIEW), prog("p1-1", 1, 3, "running", PREVIEW)], open: ["generate"] },
  { name: "11_unit_all_open", what: "作業の図。生成・検査・直させる・評価を全部開いた（送り先ごと・項目ごと・評価の回ごと）",
    unit: () => { const u = unit("p1-1", "running", "evaluate"); return { u, d: detail(u, ["cut_out", "context", "generate", "check", "fix", "check", "evaluate"]) }; },
    open: ["generate", "check", "fix", "evaluate"] },
  { name: "04_unit_review", what: "作業の図。人の判断待ち（脈打つ）。横の欄に候補と採用・却下",
    unit: () => { const u = unit("p1-1", "awaiting_review", "review"); return { u, d: detail(u, ["cut_out", "context", "generate", "check", "evaluate"], "done") }; } },
  { name: "02_unit_many_retries", what: "作業の図。3回目。戻りの辺を全部通った（段の回数と、横の欄の戻った回数）。却下で戻る印が動いている途中",
    unit: () => { const u = unit("p1-1", "running", "check", { attempt: 3 }); return { u, d: detail(u, MANY, "running", { attemptOf: MANY_ATT, decisions: MANY_DEC, candidates: cands(3) }) }; },
    marker: ["review", "context"] },
  { name: "12_unit_failed", what: "作業の図。検査で失敗して止まった",
    unit: () => { const u = unit("p1-1", "failed", "check", { stop_reason: "続けて失敗した（3回）" }); return { u, d: detail(u, ["cut_out", "context", "generate", "check"], "failed") }; } },
  { name: "13_unit_paused_stale", what: "作業の図。生成の途中で止めた・上流が変わった（古い）",
    unit: () => { const u = unit("p1-4", "paused", "generate"); return { u, d: detail(u, ["cut_out", "context", "generate"], "paused") }; },
    stale: [{ id: "m2", unit_id: "p1-4", reason: "ネームのコマが変わった", effect: "作り直しが要る", status: "open" }] },
  { name: "14_unit_cancelling", what: "作業の図。取り消し中",
    unit: () => { const u = unit("p2-1", "cancelling", "generate"); return { u, d: detail(u, ["cut_out", "context", "generate"]) }; } },
  { name: "15_unit_done", what: "作業の図。確定して完了",
    unit: () => { const u = unit("p1-2", "done", "end"); return { u, d: detail(u, ["cut_out", "context", "generate", "check", "evaluate", "review", "finalize"], "done", { decisions: [{ at: at(59), action: "approve", by: USER }] }) }; } },
];

function answerFor(sc) {
  const u0 = sc.unit ? sc.unit() : null;
  const units = sc.units || [...stageUnits("running").units.filter((u) => u.unit_id !== u0.u.unit_id), u0.u];
  return (method, url) => {
    const p = url.pathname;
    const j = (json, status = 200) => ({ status, body: JSON.stringify(json), contentType: "application/json" });
    if (method === "GET" && p === "/auth/mode") return j({ mode: "dev_header" });
    if (p === "/me/settings") return j({ user_id: USER, language: null, autosave: null, autosave_interval_seconds: null, other: {}, updated_at: null });
    if (method === "GET" && p === "/works") return j([{ id: "w1", title: "砂の街（試験）" }]);
    if (method === "GET" && p === "/works/w1") return j(work(sc.pages));
    if (method === "GET" && p === "/works/w1/harness/snapshot") {
      return j({ last_event_id: 0, stage_runs: RUNS, units, stale: sc.stale || [], progress: sc.progress || [],
                 ...(u0 && url.searchParams.get("unit_id") ? { unit: u0.d } : {}) });
    }
    if (method === "GET" && u0 && p === `/works/w1/harness/units/${u0.u.unit_id}`) return j(u0.d);
    if (method === "GET" && p === "/works/w1/harness/review-items") return j({ items: [] });
    if (method === "GET" && p === "/works/w1/harness/thresholds") return j({ thresholds: [] });
    if (method === "GET" && p === "/works/w1/harness/notifications") return j({ notifications: [] });
    if (method === "GET" && p === "/works/w1/harness/notification-settings") return j({ kinds: [], settings: null });
    if (method === "GET" && /^\/works\/w1\/images\/\w+\/(file|thumbnail)$/.test(p)) return { status: 200, body: ART, contentType: "image/png" };
    return j({ detail: `偽のサーバーに無い口：${method} ${p}` }, 404);
  };
}

// ---------------------------------------------------------------- 図の箱を読んで数える（ブラウザの中で動く）
function measure() {
  const g = window.__harness.graph();
  const cy = g.cy;
  const z = cy.zoom();
  const TOL = 0.5;
  const box = (b) => ({ x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2 });
  const hit = (a, b, t = TOL) => a.x1 < b.x2 - t && b.x1 < a.x2 - t && a.y1 < b.y2 - t && b.y1 < a.y2 - t;
  const inside = (a, b, t = TOL) => a.x1 >= b.x1 - t && a.y1 >= b.y1 - t && a.x2 <= b.x2 + t && a.y2 <= b.y2 + t;
  const name = (el) => (el.isNode() ? el.data("label") || el.id() : el.id()).split("\n")[0];
  // 枠の中の子：data.box をたどった先の枠は、その子の親
  const ancestors = (n) => { const out = new Set(); let b = n.data("box") || n.data("parent"); while (b) { out.add(b); const x = cy.getElementById(b); b = x.data("box") || x.data("parent"); } return out; };
  const nodes = cy.nodes().map((n) => ({ n, id: n.id(), anc: ancestors(n), frame: n.hasClass("frame") || n.isParent(),
    body: box(n.boundingBox({ includeLabels: false, includeOverlays: false, includeUnderlays: false })),
    label: n.data("label") ? box(n.boundingBox({ includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false, includeUnderlays: false })) : null,
    font: n.numericStyle("font-size") }));
  const byId = new Map(nodes.map((x) => [x.id, x]));
  // 辺の線：折れ線は折れ点、曲線（前の dagre の版の弧）は 2次ベジェを 16 に分けた点
  const polyline = (e) => {
    const a = e.sourceEndpoint(), b = e.targetEndpoint();
    const seg = e.segmentPoints();
    if (seg && seg.length) return [a, ...seg, b];
    const c = e.controlPoints();
    if (c && c.length === 1) {
      return Array.from({ length: 17 }, (_, i) => { const t = i / 16, u = 1 - t;
        return { x: u * u * a.x + 2 * u * t * c[0].x + t * t * b.x, y: u * u * a.y + 2 * u * t * c[0].y + t * t * b.y }; });
    }
    return [a, b];
  };
  const edges = cy.edges().map((e) => ({ e, id: e.id(), kind: e.data("kind") || "forward", s: e.source().id(), t: e.target().id(), pts: polyline(e),
    label: e.data("label") ? box(e.boundingBox({ includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false })) : null,
    font: e.numericStyle("font-size") }));
  const segs = (pts) => pts.slice(1).map((p, i) => [pts[i], p]);
  // 線分と箱（内側に少し縮めた箱）が交わるか
  const segHitsBox = ([a, b], r, shrink = 1) => {
    const x1 = r.x1 + shrink, y1 = r.y1 + shrink, x2 = r.x2 - shrink, y2 = r.y2 - shrink;
    if (x2 <= x1 || y2 <= y1) return false;
    let t0 = 0, t1 = 1;
    const dx = b.x - a.x, dy = b.y - a.y;
    for (const [p, q] of [[-dx, a.x - x1], [dx, x2 - a.x], [-dy, a.y - y1], [dy, y2 - a.y]]) {
      if (p === 0) { if (q < 0) return false; continue; }
      const r_ = q / p;
      if (p < 0) { if (r_ > t1) return false; if (r_ > t0) t0 = r_; } else { if (r_ < t0) return false; if (r_ < t1) t1 = r_; }
    }
    return t0 < t1;
  };
  const cross = ([a, b], [c, d]) => {
    const o = (p, q, r) => Math.sign((q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x));
    return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
  };
  const bad = { nodeNode: [], childOutside: [], labelLabel: [], labelNode: [], labelEdge: [], edgeNode: [], sharedSegment: [],
                backCrossesForward: [], smallFont: [], outside: [], labelClipped: [] };
  // 1. ノードどうし
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (const anc of a.anc) if (!inside(a.body, byId.get(anc).body)) bad.childOutside.push(`${name(a.n)} が ${name(byId.get(anc).n)} の外`);
    for (let k = i + 1; k < nodes.length; k++) {
      const b = nodes[k];
      if (a.anc.has(b.id) || b.anc.has(a.id)) continue;
      if (hit(a.body, b.body)) bad.nodeNode.push(`${name(a.n)} × ${name(b.n)}`);
    }
  }
  // 2. ラベル
  const labels = [...nodes.filter((x) => x.label).map((x) => ({ who: name(x.n), node: x, b: x.label, font: x.font })),
                  ...edges.filter((x) => x.label).map((x) => ({ who: x.id, edge: x, b: x.label, font: x.font }))];
  for (let i = 0; i < labels.length; i++) {
    for (let k = i + 1; k < labels.length; k++) if (hit(labels[i].b, labels[k].b)) bad.labelLabel.push(`${labels[i].who} × ${labels[k].who}`);
  }
  for (const l of labels) {
    for (const x of nodes) {
      if (l.node && (x.id === l.node.id || l.node.anc.has(x.id))) continue;
      if (hit(l.b, x.body)) bad.labelNode.push(`${l.who} × ${name(x.n)}`);
    }
    for (const e of edges) {
      if (l.edge && e.id === l.edge.id) continue;
      if (segs(e.pts).some((s) => segHitsBox(s, l.b))) bad.labelEdge.push(`${l.who} × ${e.id}`);
    }
    if (l.node && !l.node.frame && !inside(l.b, l.node.body)) bad.labelClipped.push(l.who);
    if (l.font * z < 12 - 1e-6) bad.smallFont.push(`${l.who} ${(l.font * z).toFixed(1)}px`);
  }
  // 3. 辺が端以外のノードを通る（端のノードの親の枠も除く）
  for (const e of edges) {
    const ends = new Set([e.s, e.t, ...byId.get(e.s).anc, ...byId.get(e.t).anc]);
    for (const x of nodes) {
      if (ends.has(x.id)) continue;
      if (segs(e.pts).some((s) => segHitsBox(s, x.body))) bad.edgeNode.push(`${e.id} → ${name(x.n)}`);
    }
  }
  // 4. 辺どうしが同じ線を通る（同じ向きの線分が 6px より近く、長さ 2px を超えて並ぶ）
  const axis = (a, b) => (Math.abs(a.y - b.y) < 0.5 ? "h" : Math.abs(a.x - b.x) < 0.5 ? "v" : null);
  for (let i = 0; i < edges.length; i++) {
    for (let k = i + 1; k < edges.length; k++) {
      for (const s1 of segs(edges[i].pts)) for (const s2 of segs(edges[k].pts)) {
        const A = axis(...s1), B = axis(...s2);
        if (!A || A !== B) continue;
        const [p, q] = A === "h" ? ["x", "y"] : ["y", "x"];
        const lo = Math.max(Math.min(s1[0][p], s1[1][p]), Math.min(s2[0][p], s2[1][p]));
        const hi = Math.min(Math.max(s1[0][p], s1[1][p]), Math.max(s2[0][p], s2[1][p]));
        if (hi - lo > 2 && Math.abs(s1[0][q] - s2[0][q]) < 6) bad.sharedSegment.push(`${edges[i].id} = ${edges[k].id}`);
      }
    }
  }
  // 5. 戻りの辺・飛ばす辺は、前へ進む辺と交わらない（外の通り道を通る）
  for (const e of edges.filter((x) => x.kind !== "forward")) {
    for (const f of edges.filter((x) => x.kind === "forward")) {
      if (segs(e.pts).some((s1) => segs(f.pts).some((s2) => cross(s1, s2)))) bad.backCrossesForward.push(`${e.id} × ${f.id}`);
    }
  }
  // 6. 図が箱に収まる
  const rb = cy.elements().renderedBoundingBox({ includeOverlays: false });
  const cw = cy.width(), ch = cy.height();
  if (rb.x1 < -1 || rb.y1 < -1 || rb.x2 > cw + 1 || rb.y2 > ch + 1) bad.outside.push(`図 ${rb.x1.toFixed(0)},${rb.y1.toFixed(0)}–${rb.x2.toFixed(0)},${rb.y2.toFixed(0)} 箱 ${cw}×${ch}`);
  // 図の上の HTML（進み具合の帯）はノードの中
  for (const el of document.querySelectorAll(".hz-progress[data-pnode]")) {
    const n = cy.getElementById(el.dataset.pnode);
    if (!n.length) continue;
    const nb = n.renderedBoundingBox({ includeLabels: false, includeOverlays: false, includeUnderlays: false });
    const r = el.getBoundingClientRect(), c = cy.container().getBoundingClientRect();
    const eb = { x1: r.left - c.left, y1: r.top - c.top, x2: r.right - c.left, y2: r.bottom - c.top };
    if (!inside(eb, nb, 1)) bad.outside.push(`進み具合の帯 ${el.dataset.pnode}`);
  }
  let crossings = 0;
  for (let i = 0; i < edges.length; i++) for (let k = i + 1; k < edges.length; k++) {
    for (const s1 of segs(edges[i].pts)) for (const s2 of segs(edges[k].pts)) if (cross(s1, s2)) crossings += 1;
  }
  const minFont = Math.min(...labels.map((l) => l.font * z));
  const pos = Object.fromEntries(cy.nodes().map((n) => [n.id(), [Math.round(n.position("x")), Math.round(n.position("y"))]]));
  return { bad, zoom: z, minFont, crossings, nodes: nodes.length, edges: edges.length, pos };
}

// ---------------------------------------------------------------- 流す
const browser = await openBrowser();
const results = [];
let failures = 0;
const total = (bad) => Object.values(bad).reduce((a, b) => a + b.length, 0);

async function settle(page) {
  // 並べ直しは非同期（ELK）。描き終えて、続けて並べ直しが起きなくなるまで待つ
  await page.waitForFunction(() => window.__harness?.graph && window.__harness.graph()?.cy.nodes().length > 0, null, { timeout: 15000 });
  for (let i = 0; i < 5; i++) {
    const same = await page.evaluate(async () => {
      const g = window.__harness.graph();
      const p = g.layoutDone;
      await p;
      await new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));
      return g.layoutDone === p;
    });
    if (same) return;
  }
  throw new Error("並べ直しが止まらない");
}

for (const [W, H] of SIZES) {
  const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await context.addInitScript((u) => localStorage.setItem("v3.user", u), USER);
  for (const sc of SCENARIOS) {
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
    // 切断の場面では、流れを断った 503 がブラウザの読み込みの失敗として出る（それだけは場面どおり）
    page.on("console", (m) => { if (m.type() === "error" && !(sc.stream === "down" && /status of 503/.test(m.text()))) errors.push(`console: ${m.text()}`); });
    const answer = answerFor(sc);
    await serveWeb(page, ORIGIN, async (route, u) => {
      // 流れは開いたまま何も送らない。切断の場面では断る
      if (u.pathname.endsWith("/harness/stream")) return sc.stream === "down" ? route.fulfill({ status: 503, body: "" }) : undefined;
      return route.fulfill(answer(route.request().method(), u));
    });
    const u0 = sc.unit ? sc.unit() : null;
    await page.goto(`${ORIGIN}/web/harness/?work=w1${u0 ? `&unit=${u0.u.unit_id}` : ""}`);
    await settle(page);
    if (sc.act === "fold") { await page.click("#fold"); await settle(page); }
    for (const st of sc.open || []) { await page.evaluate((s) => window.__harness.toggleStep(s), st); await settle(page); }
    const m = await page.evaluate(measure);
    // 状態が変わっただけでは動かない：作業の状態の出来事を当てて、ノードの位置を比べる
    const target = u0 ? u0.u : sc.units[sc.units.length - 1];
    await page.evaluate((u) => window.__harness.applyEvent({ id: null, event: "unit", data: { ...u, cost_used: u.cost_used + 1, at: new Date().toISOString() } }), target);
    await settle(page);
    const m2 = await page.evaluate(measure);
    const moved = Object.keys(m.pos).filter((k) => m2.pos[k] && (m2.pos[k][0] !== m.pos[k][0] || m2.pos[k][1] !== m.pos[k][1]));
    if (moved.length) m.bad.movedOnUpdate = moved;
    // 窓の大きさを少し変えても、並べ直さない（倍率と位置だけ）
    await page.setViewportSize({ width: W - 40, height: H });
    await page.waitForTimeout(250);
    await settle(page);
    const m3 = await page.evaluate(measure);
    const moved3 = Object.keys(m.pos).filter((k) => m3.pos[k] && (m3.pos[k][0] !== m.pos[k][0] || m3.pos[k][1] !== m.pos[k][1]));
    if (moved3.length) m.bad.movedOnResize = moved3;
    if (total(m3.bad)) m.bad.afterResize = Object.entries(m3.bad).filter(([, v]) => v.length).map(([k, v]) => `${k}: ${v.slice(0, 3).join(" / ")}`);
    await page.setViewportSize({ width: W, height: H });
    await page.waitForTimeout(250);
    await settle(page);
    if (sc.marker) {
      await page.evaluate(([a, b]) => window.__harness.graph().traverse(a, b), sc.marker);
      await page.waitForTimeout(600);
    }
    if (errors.length) m.bad.pageErrors = errors;
    const n = total(m.bad);
    failures += n ? 1 : 0;
    const tag = `${W}x${H} ${sc.name}`;
    console.log(`${n ? "NG" : "ok"} ${tag}  倍率 ${m.zoom.toFixed(2)}  最小の文字 ${m.minFont.toFixed(1)}px  辺の交わり ${m.crossings}`);
    for (const [k, v] of Object.entries(m.bad)) if (v.length) console.log(`   ${k} ${v.length}: ${v.slice(0, 6).join(" / ")}`);
    results.push({ size: `${W}x${H}`, name: sc.name, count: n, bad: m.bad, zoom: m.zoom, minFont: m.minFont, crossings: m.crossings });
    if (SHOTS) await makeShot(page, { prefix: W === 1920 ? "" : `${W}x${H}_` })(sc.name, sc.fullPage ? { fullPage: true } : {});
    await page.close();
  }
  await context.close();
}
await browser.close();
if (process.env.RESULT) (await import("node:fs")).writeFileSync(process.env.RESULT, JSON.stringify(results, null, 2));
console.log(`\n図の読みやすさ：${results.length - failures}/${results.length} が通った`);
if (failures) process.exitCode = 1;
