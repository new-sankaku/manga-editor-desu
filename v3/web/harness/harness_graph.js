// ハーネスの図（Cytoscape.js + cytoscape-dagre。v3/web/vendor に置いた物を index.html の script で読む）。
// - 工程の図：S0〜S7 を左から右へ。作業を切り出す工程（S3・S4）は、その下に作業のノードを並べる
// - 作業の図：1回の作業の段（切り出し→文脈→生成→検査→評価→人の判断→確定）と、作り直しの戻りの辺
// 状態が変わってもノードを作り直さない（クラスとラベルだけ変える）。並べ直すのは図を切り替えたときと、作業が増えたときだけ。
// 図の上の HTML（進み具合・途中の絵・辺を動く印）は、ノードの画面上の位置に合わせて置き直す（render のたび）。

/* global cytoscape, cytoscapeDagre */
cytoscape.use(cytoscapeDagre);

export const STATUS_JA = {
  queued: "順番待ち", running: "実行中", waiting_limit: "上限で待つ", waiting_budget: "予算で待つ",
  awaiting_review: "判断待ち", paused: "止めた", cancelling: "取り消し中", retrying: "やり直し中",
  stopped: "止まった", failed: "失敗", cancelled: "取り消した", done: "完了", blocked: "決めるまで進めない",
};
export const STEP_JA = {
  cut_out: "切り出し", context: "文脈", generate: "生成", check: "検査", evaluate: "評価",
  review: "人の判断", finalize: "確定", end: "完了", discard_round: "却下",
};
// harness_states.py の STEPS と RETRY_EDGES と同じ並び
export const STEPS = ["cut_out", "context", "generate", "check", "evaluate", "review", "finalize"];
const FORWARD = [
  ["cut_out", "context"], ["context", "generate"], ["generate", "check"], ["check", "evaluate"],
  ["evaluate", "review"], ["review", "finalize"], ["finalize", "end"],
];
const SKIPS = [["check", "review", "評価なし"], ["evaluate", "end", "人の判断なし"]];
export const RETRY_EDGES = [
  ["check", "context", "検査で全部落ちた"],
  ["evaluate", "context", "評価で選べない・割れた"],
  ["review", "context", "却下（理由つき）"],
  ["review", "generate", "人が直した絵から続ける"],
];
const RETRY_BEND = { "check>context": 60, "evaluate>context": 105, "review>context": -125, "review>generate": -80 };
const SKIP_BEND = { "check>review": -45, "evaluate>end": 60 };

const UNIT_DX = 112;  // 工程の図の作業のノードの間隔

const HUMAN = new Set(["awaiting_review", "paused", "stopped", "blocked"]);
const SERVICE = new Set(["queued", "waiting_limit", "waiting_budget", "retrying"]);
export function statusClass(s) {
  if (s === "awaiting_review") return "st-review";
  if (HUMAN.has(s)) return s === "paused" ? "st-paused" : "st-blocked";
  if (SERVICE.has(s)) return "st-waiting";
  return `st-${s || "none"}`;
}
export const isHumanWait = (s) => HUMAN.has(s);

// 図の色は harness.css の状態の色の呼び名（theme.css の変数から作る）を読む。色の値はここに書かない。
// Cytoscape は CSS の変数も color-mix() も読めないので、要素の color に当ててブラウザに解かせ、1画素の canvas で rgb にする
const probe = document.createElement("i");
probe.style.display = "none";
document.documentElement.append(probe);
const px = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
function token(name) {
  if (!getComputedStyle(document.documentElement).getPropertyValue(name).trim()) throw new Error(`色の変数 ${name} がありません`);
  probe.style.color = `var(${name})`;
  px.clearRect(0, 0, 1, 1);
  px.fillStyle = getComputedStyle(probe).color;
  px.fillRect(0, 0, 1, 1);
  const [r, g, b] = px.getImageData(0, 0, 1, 1).data;
  return `rgb(${r},${g},${b})`;
}
const C = Object.fromEntries(Object.entries({
  bg: "--h-bg", node: "--h-node", line: "--h-line", ink: "--h-ink", ink2: "--h-ink-2",
  run: "--run", runBg: "--run-bg", wait: "--wait", review: "--review", reviewBg: "--review-bg",
  bad: "--bad", badBg: "--bad-bg", pause: "--pause", pauseBg: "--pause-bg", done: "--done",
  doneBg: "--done-bg", stale: "--stale", edge: "--h-edge", retry: "--retry", hot: "--hot",
  groupBg: "--h-group-bg",
}).map(([k, name]) => [k, token(name)]));
probe.remove();
const MONO = '"SFMono-Regular", "Cascadia Mono", Consolas, "Noto Sans Mono CJK JP", "Noto Sans Mono", monospace';

const STYLE = [
  { selector: "node", style: {
    shape: "round-rectangle", "background-color": C.node, "border-width": 1, "border-color": C.line,
    label: "data(label)", "font-family": MONO, "font-size": 12, color: C.ink, "text-wrap": "wrap",
    "text-valign": "center", "text-halign": "center", width: "data(w)", height: "data(h)",
    "transition-property": "border-width, border-color, background-color", "transition-duration": "0.55s",
  } },
  { selector: "node.stage", style: { "font-size": 11.5 } },
  { selector: "node.group", style: {
    "background-color": C.groupBg, "background-opacity": 0.6, "border-style": "dashed", "border-color": C.wait,
    label: "data(label)", "text-valign": "top", "text-halign": "left", "text-margin-x": 70, "text-margin-y": -4,
    "font-size": 10, color: C.ink2, padding: 12,
  } },
  { selector: "node.end", style: { shape: "ellipse" } },
  { selector: "node.unused", style: { opacity: 0.35 } },
  { selector: ".st-running", style: { "border-color": C.run, "border-width": 2, "background-color": C.runBg } },
  { selector: ".st-waiting", style: { "border-color": C.wait, "border-style": "dashed", "border-width": 1.5 } },
  { selector: ".st-review", style: { "border-color": C.review, "border-width": 2, "background-color": C.reviewBg } },
  { selector: ".st-review.pulse-on", style: { "border-width": 6, "border-color": C.review } },
  { selector: ".st-blocked, .st-stopped, .st-failed", style: { "border-color": C.bad, "border-width": 2, "background-color": C.badBg } },
  { selector: ".st-blocked.pulse-on, .st-stopped.pulse-on", style: { "border-width": 5 } },
  { selector: ".st-paused", style: { "border-color": C.pause, "border-width": 2, "background-color": C.pauseBg } },
  { selector: ".st-paused.pulse-on", style: { "border-width": 5 } },
  { selector: ".st-cancelling", style: { "border-color": C.bad, "border-style": "dashed", "border-width": 2 } },
  { selector: ".st-cancelled", style: { opacity: 0.45, "border-style": "dotted" } },
  { selector: ".st-done", style: { "background-color": C.doneBg, "border-color": C.done, color: C.ink2 } },
  { selector: "node.stale", style: {
    "underlay-color": C.stale, "underlay-opacity": 0.5, "underlay-padding": 7, "underlay-shape": "round-rectangle",
  } },
  { selector: "node.current", style: { "border-width": 3 } },
  { selector: "node:selected", style: { "overlay-color": C.hot, "overlay-opacity": 0.12, "overlay-padding": 4 } },
  { selector: "edge", style: {
    width: 1.2, "line-color": C.edge, "target-arrow-color": C.edge, "target-arrow-shape": "triangle",
    "arrow-scale": 0.8, "curve-style": "bezier", label: "data(label)", "font-family": MONO, "font-size": 9.5,
    color: C.ink2, "text-background-color": C.bg, "text-background-opacity": 1, "text-background-padding": 2,
    "transition-property": "line-color, target-arrow-color, width", "transition-duration": "0.4s",
  } },
  { selector: "edge.skip", style: { "line-style": "dotted", "curve-style": "unbundled-bezier",
                                    "control-point-distances": "data(bend)", "control-point-weights": 0.5 } },
  { selector: "edge.retry", style: {
    "curve-style": "unbundled-bezier", "control-point-distances": "data(bend)", "control-point-weights": 0.5,
    "line-style": "dashed", "line-color": C.retry, "target-arrow-color": C.retry,
  } },
  { selector: "edge.traversed", style: { "line-color": C.hot, "target-arrow-color": C.hot, width: 3 } },
  { selector: "edge.to-group", style: { "line-style": "dotted", "target-arrow-shape": "none" } },
];

export class HarnessGraph {
  constructor(container, overlay, handlers) {
    this.overlay = overlay;
    this.handlers = handlers;
    this.cy = cytoscape({ container, style: STYLE, minZoom: 0.3, maxZoom: 1.5, wheelSensitivity: 0.25,
                          boxSelectionEnabled: false, autoungrabify: true });
    this.view = null;
    this.edgeCounts = {};
    this.cy.on("tap", "node", (e) => this.handlers.onTap(e.target.id(), e.target.data()));
    this.cy.on("render", () => this._queueOverlay());
    // 人を待つノードを脈打たせる（スタイルの transition で太さを行き来させる）
    this._pulse = setInterval(() => this.cy.nodes(".st-review, .st-blocked, .st-stopped, .st-paused").toggleClass("pulse-on"), 650);
    this.progress = [];
    this.markers = [];
  }

  // ------------------------------------------------------------------ 工程の図

  showStages(stages) {
    this.view = "stage";
    this.cy.elements().remove();
    const els = stages.map((s) => ({ group: "nodes", data: { id: `stage:${s.stage}`, kind: "stage", stage: s.stage,
                                                             label: s.label, w: 100, h: 30 + 14 * s.lines }, classes: `stage ${s.cls}` }));
    for (let i = 1; i < stages.length; i++) {
      els.push({ group: "edges", data: { id: `se:${i}`, source: `stage:${stages[i - 1].stage}`,
                                         target: `stage:${stages[i].stage}`, label: "" } });
    }
    this.cy.add(els);
    this.cy.layout({ name: "dagre", rankDir: "LR", nodeSep: 30, rankSep: 16, animate: false }).run();
    this.groups = {};
    this.cy.fit(undefined, 24);
  }

  updateStage(s) {
    const n = this.cy.getElementById(`stage:${s.stage}`);
    if (!n.length) return;
    n.data({ label: s.label, h: 30 + 14 * s.lines });
    n.classes(`stage ${s.cls}`);
  }

  // 作業のノードを工程の下に並べる。並びは作られた順（増えても前からの位置は変えない）
  setUnits(stage, units, labelOf) {
    if (this.view !== "stage") return;
    const gid = `group:${stage}`;
    let added = false;
    if (!this.cy.getElementById(gid).length) {
      this.cy.add([{ group: "nodes", data: { id: gid, label: `${stage} の作業`, kind: "group" }, classes: "group" },
                   { group: "edges", data: { id: `ge:${stage}`, source: `stage:${stage}`, target: gid, label: "" },
                     classes: "to-group" }]);
      added = true;
    }
    // 作業は工程の列と同じ幅に並べる（図の幅は工程の列で決まるので、作業のノードを大きく見せられる）
    const box = this.cy.nodes(".stage").boundingBox();
    const cols = Math.max(4, Math.floor((box.w + 8) / UNIT_DX));
    const origin = this._groupOrigin(stage);
    units.forEach((u, i) => {
      const id = `unit:${u.unit_id}`;
      const pos = { x: origin.x + (i % cols) * UNIT_DX, y: origin.y + Math.floor(i / cols) * 86 };
      let n = this.cy.getElementById(id);
      if (!n.length) {
        n = this.cy.add({ group: "nodes", data: { id, parent: gid, kind: "unit", unit_id: u.unit_id, w: UNIT_DX - 10, h: 58,
                                                  label: labelOf(u) }, position: pos });
        added = true;
      }
      n.position(pos);
      this.updateUnit(u, labelOf);
    });
    if (added) this.cy.fit(undefined, 24);
  }

  _groupOrigin(stage) {
    const box = this.cy.nodes(".stage").boundingBox();
    // 作業の多い工程どうしが重ならないよう、工程ごとに下の段をずらす
    const order = Object.keys(this.groups);
    if (!order.includes(stage)) this.groups[stage] = true;
    const k = Object.keys(this.groups).indexOf(stage);
    return { x: box.x1 + (UNIT_DX - 10) / 2, y: box.y2 + 74 + k * 260 };
  }

  updateUnit(u, labelOf) {
    const n = this.cy.getElementById(this.view === "stage" ? `unit:${u.unit_id}` : "");
    if (!n.length) return;
    n.data("label", labelOf(u));
    n.classes(`${statusClass(u.status)}${u.stale ? " stale" : ""}`);
  }

  // ------------------------------------------------------------------ 作業の図

  showUnit() {
    this.view = "unit";
    this.cy.elements().remove();
    this.edgeCounts = {};
    const els = [...STEPS, "end"].map((s) => ({ group: "nodes", data: { id: `step:${s}`, kind: "step", step: s,
      label: STEP_JA[s], w: s === "end" ? 56 : 84, h: s === "end" ? 40 : 50 }, classes: s === "end" ? "end" : "" }));
    for (const [a, b] of FORWARD) els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: "" } });
    for (const [a, b, why] of SKIPS) els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: why, base: why, bend: SKIP_BEND[`${a}>${b}`] }, classes: "skip" });
    for (const [a, b, why] of RETRY_EDGES) {
      els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: why,
                                         base: why, bend: RETRY_BEND[`${a}>${b}`] }, classes: "retry" });
    }
    this.cy.add(els);
    // 並びは前へ進む辺だけで決める（戻りの辺は弧で描く）
    this.cy.elements().not(".retry, .skip").layout({ name: "dagre", rankDir: "LR", nodeSep: 40, rankSep: 34, animate: false }).run();
    this.cy.getElementById("step:end").position({ x: this.cy.getElementById("step:finalize").position("x") + 96,
                                                  y: this.cy.getElementById("step:finalize").position("y") });
    this.cy.fit(undefined, 40);
  }

  // 段ごとの回数・状態。states: {step: {count, status}}
  setSteps(states, current, unitStatus) {
    for (const s of [...STEPS, "end"]) {
      const n = this.cy.getElementById(`step:${s}`);
      const st = states[s] || {};
      const count = st.count ? ` ×${st.count}` : "";
      n.data("label", `${STEP_JA[s]}${count}${st.note ? `\n${st.note}` : ""}`);
      let cls = s === "end" ? "end " : "";
      if (s === current) cls += `${statusClass(unitStatus)} current`;
      else if (st.status) cls += statusClass(st.status);
      if (!st.count && s !== current) cls += " unused";
      n.classes(cls);
    }
  }

  setEdgeCounts(counts) {
    this.edgeCounts = counts;
    this.cy.edges().forEach((e) => {
      const n = counts[e.id().slice(2)] || 0;
      const base = e.data("base") || "";
      e.data("label", n ? `${base}${base ? " " : ""}×${n}` : base);
    });
  }

  // 辺をたどった。印を辺に沿って動かし、辺をしばらく明るくする
  traverse(from, to) {
    const e = this.cy.getElementById(`e:${from}>${to}`);
    if (!e.length) return false;
    e.addClass("traversed");
    clearTimeout(e.scratch("_t"));
    e.scratch("_t", setTimeout(() => e.removeClass("traversed"), 2600));
    const dot = document.createElement("div");
    dot.className = `hz-marker${e.hasClass("retry") ? " retry" : ""}`;
    this.overlay.appendChild(dot);
    const m = { edge: e, dot, t0: performance.now(), dur: e.hasClass("retry") ? 1400 : 800 };
    this.markers.push(m);
    this._queueOverlay();
    this.lastTraversal = { from, to, retry: e.hasClass("retry"), at: Date.now() };
    return true;
  }

  // ------------------------------------------------------------------ 図の上の HTML

  setProgress(rows) {
    this.progress = rows;
    this._queueOverlay();
  }

  _queueOverlay() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => { this._raf = null; this._drawOverlay(); });
  }

  _drawOverlay() {
    const ov = this.overlay;
    const keep = new Set();
    const now = performance.now();
    for (const m of [...this.markers]) {
      const t = Math.min(1, (now - m.t0) / m.dur);
      const p = pointOnEdge(this.cy, m.edge, easeInOut(t));
      if (p) { m.dot.style.transform = `translate(${p.x}px, ${p.y}px)`; }
      if (t >= 1) {
        m.dot.classList.add("arrived");
        setTimeout(() => m.dot.remove(), 450);
        this.markers.splice(this.markers.indexOf(m), 1);
      }
    }
    if (this.markers.length) this._queueOverlay();
    for (const g of groupProgress(this.view, this.progress)) {
      const n = this.cy.getElementById(g.node);
      if (!n.length) continue;
      const bb = n.renderedBoundingBox({ includeLabels: false });
      let box = ov.querySelector(`[data-pnode="${CSS.escape(g.node)}"]`);
      if (!box) {
        box = document.createElement("div");
        box.dataset.pnode = g.node;
        box.className = `hz-progress ${this.view}`;
        ov.appendChild(box);
      }
      keep.add(box);
      box.style.transform = `translate(${bb.x1}px, ${bb.y2 + 4}px)`;
      box.style.minWidth = `${Math.max(bb.w, 40)}px`;
      renderProgressBox(box, g, this.view);
    }
    for (const el of ov.querySelectorAll(".hz-progress")) if (!keep.has(el)) el.remove();
  }

  destroy() { clearInterval(this._pulse); this.cy.destroy(); }
}

function groupProgress(view, rows) {
  const by = new Map();
  for (const r of rows) {
    const node = view === "unit" ? "step:generate" : `unit:${r.unit_id}`;
    if (!by.has(node)) by.set(node, { node, rows: [] });
    by.get(node).rows.push(r);
  }
  return [...by.values()];
}

const PSTATE_JA = { pending: "送った", running: "描いている", finished: "描き終えた", unavailable: "進み具合を受け取れない",
                    interrupted: "止めた", error: "止まった" };

function renderProgressBox(box, g, view) {
  const rows = [...g.rows].sort((a, b) => a.k_index - b.k_index);
  const key = rows.map((r) => `${r.candidate_id}:${r.state}:${r.value}:${r.preview ? r.updated_at : ""}`).join("|");
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.replaceChildren();
  for (const r of rows) {
    const pct = r.max ? Math.round((100 * (r.value || 0)) / r.max) : 0;
    const line = document.createElement("div");
    line.className = `hz-bar s-${r.state}`;
    const fill = document.createElement("span");
    fill.style.width = `${pct}%`;
    line.appendChild(fill);
    if (view === "unit") {
      const t = document.createElement("em");
      t.textContent = `#${r.k_index + 1} ${PSTATE_JA[r.state] || r.state}${r.max ? ` ${r.value || 0}/${r.max}` : ""}`;
      line.appendChild(t);
    }
    box.appendChild(line);
  }
  if (view === "unit") {
    const withPreview = rows.filter((r) => r.preview);
    if (withPreview.length) {
      const strip = document.createElement("div");
      strip.className = "hz-previews";
      for (const r of withPreview) {
        const im = document.createElement("img");
        im.src = r.preview;
        im.alt = `候補 ${r.k_index + 1} の途中の絵`;
        strip.appendChild(im);
      }
      box.appendChild(strip);
    }
  }
}

function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2; }

// 辺の上の点（画面の座標）。弧の辺は Cytoscape の制御点（1つ）で2次ベジェ、まっすぐな辺は線分
function pointOnEdge(cy, e, t) {
  if (e.removed()) return null;
  const z = cy.zoom(), pan = cy.pan();
  const r = (p) => ({ x: p.x * z + pan.x, y: p.y * z + pan.y });
  const a = r(e.sourceEndpoint()), b = r(e.targetEndpoint());
  const cps = e.controlPoints && e.controlPoints();
  if (cps && cps.length) {
    const c = r(cps[0]);
    const u = 1 - t;
    return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y };
  }
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}
