// ハーネスの図（Cytoscape.js + cytoscape-dagre。v3/web/vendor に置いた物を index.html の script で読む）。
// - 工程の図：S0〜S7 を左から右へ。作業を切り出す工程（S3・S4）は、その下に作業のノードを並べる
// - 作業の図：1回の作業の段（切り出し→文脈→生成→検査→評価→人の判断→確定）と、直させる段、作り直しの戻りの辺。
//   生成・直させる・検査・評価は、押すと中を開く（送り先ごと・項目ごと・くり返しの回ごと。cytoscape-expand-collapse）
// - 工程の図の作業は、工程 > ページ の入れ子のまとまりにし、まとまりを押すとたたむ・開く
// 状態が変わってもノードを作り直さない（クラスとラベルだけ変える）。並べ直すのは図を切り替えたときと、作業が増えたときだけ。
// 図の上の HTML（進み具合・途中の絵・辺を動く印）は、ノードの画面上の位置に合わせて置き直す（render のたび）。

/* global cytoscape, cytoscapeDagre */
// cytoscape-expand-collapse は読まれたときに cytoscape へ自分を足す（window.cytoscape があれば）
cytoscape.use(cytoscapeDagre);

export const STATUS_JA = {
  queued: "順番待ち", running: "実行中", waiting_limit: "上限で待つ", waiting_budget: "予算で待つ",
  awaiting_review: "判断待ち", paused: "止めた", cancelling: "取り消し中", retrying: "やり直し中",
  stopped: "止まった", failed: "失敗", cancelled: "取り消した", done: "完了", blocked: "決めるまで進めない",
};
export const STEP_JA = {
  cut_out: "切り出し", context: "文脈", generate: "生成", check: "検査", evaluate: "評価",
  review: "人の判断", finalize: "確定", end: "完了", discard_round: "却下", fix: "直させる",
};
// harness_states.py の STEPS と RETRY_EDGES と同じ並び
export const STEPS = ["cut_out", "context", "generate", "check", "fix", "evaluate", "review", "finalize"];
const FORWARD = [
  ["cut_out", "context"], ["context", "generate"], ["generate", "check"], ["check", "evaluate"],
  ["evaluate", "review"], ["review", "finalize"], ["finalize", "end"],
];
const SKIPS = [["check", "review", "評価なし"], ["evaluate", "end", "人の判断なし"]];
export const RETRY_EDGES = [
  ["check", "fix", "落ちた所だけ直す"],
  ["fix", "check", "直した候補だけ検査し直す"],
  ["check", "context", "直せない・直す上限で全部を作り直す"],
  ["evaluate", "context", "評価で選べない・割れた"],
  ["review", "context", "却下（理由つき）"],
  ["review", "generate", "人が直した絵から続ける"],
];
const RETRY_BEND = { "check>fix": 22, "fix>check": 22, "check>context": 60, "evaluate>context": 105, "review>context": -125, "review>generate": -80 };
const SKIP_BEND = { "check>review": -45, "evaluate>end": 60 };

const UNIT_DX = 112;  // 工程の図の作業のノードの間隔
const PAGE_GAP = 34;  // ページのまとまりどうしの間（まとまりの枠の余白と名前の分）
// たたむ・開くで、ほかのノードを動かさない（置き直しは _layoutUnits が1か所でする）。印の絵は使わず、まとまりを押して切り替える
const EC_OPTS = { layoutBy: null, fisheye: false, animate: false, undoable: false };
// たたんだまとまりの色に使う、状態の急ぐ順（人を待つ・止まった が先）
const URGENT = ["blocked", "stopped", "failed", "awaiting_review", "paused", "cancelling", "running", "retrying",
                "queued", "waiting_limit", "waiting_budget", "done", "cancelled"];
const urgency = (s) => (URGENT.includes(s) ? URGENT.indexOf(s) : URGENT.length);
// いくつかの状態のうち一番急ぐもの（たたんだまとまり・段の中の子の色）
export const urgentStatus = (list) => [...list].sort((a, b) => urgency(a) - urgency(b))[0];
const PART_W = 128;  // 段の中の子のノードの幅
const PART_DY = 46;  // 段の中の子のノードの縦の間隔

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
  { selector: "node.group.collapsed", style: {
    "background-color": C.node, "background-opacity": 1, "border-style": "solid", "text-valign": "center",
    "text-halign": "center", "text-margin-x": 0, "text-margin-y": 0, "font-size": 11, color: C.ink,
  } },
  { selector: "node.step-node:parent", style: {
    "background-color": C.groupBg, "background-opacity": 0.6, "border-style": "dashed", "text-valign": "top",
    "text-halign": "center", "text-margin-y": -4, "font-size": 10.5, padding: 10,
  } },
  { selector: "node.part", style: { "font-size": 10.5 } },
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
    this.ec = this.cy.expandCollapse({ ...EC_OPTS, cueEnabled: false });
    this.collapsed = new Set();
    this.cy.on("tap", "node", (e) => {
      const d = e.target.data();
      if (d.kind === "group") return this.toggleGroup(e.target.id());
      if (d.kind === "step" && this.stepParts?.[d.step]?.length) this.toggleStep(d.step);
      return this.handlers.onTap(e.target.id(), d);
    });
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
    this.groups = [];
    this.unitData = {};
    this.where = new Map();
    this.cy.fit(undefined, 24);
  }

  updateStage(s) {
    const n = this.cy.getElementById(`stage:${s.stage}`);
    if (!n.length) return;
    n.data({ label: s.label, h: 30 + 14 * s.lines });
    n.classes(`stage ${s.cls}`);
  }

  // 作業のノードを工程の下に、入れ子のまとまり（工程の作業 > ページ > 作業）で並べる。
  // まとまりを押すとたたむ・開く（cytoscape-expand-collapse）。たたんだまとまりは1つのノードになり、中の作業の数と
  // 状態の内訳を出す。色は中で一番急ぐ状態（人を待つ・止まった を先）に合わせる。
  // groupOf(u) は { key, label }（作業が入るページ。ページを持たない作業は呼ぶ側が別の key にする）
  setUnits(stage, units, labelOf, groupOf) {
    if (this.view !== "stage") return;
    this.unitData[stage] = { units, labelOf, groupOf };
    const sid = `group:${stage}`;
    let added = false;
    if (!this.cy.getElementById(sid).length) {
      this.cy.add([{ group: "nodes", data: { id: sid, label: "", kind: "group", stage, w: UNIT_DX - 10, h: 58 }, classes: "group" },
                   { group: "edges", data: { id: `ge:${stage}`, source: `stage:${stage}`, target: sid, label: "" },
                     classes: "to-group" }]);
      if (!this.groups.includes(stage)) this.groups.push(stage);
      added = true;
    }
    if (!this.collapsed.has(sid)) {
      for (const u of units) {
        const g = groupOf(u);
        const pid = `group:${stage}:${g.key}`;
        this.where.set(u.unit_id, [sid, pid]);
        if (!this.cy.getElementById(pid).length) {
          this.cy.add({ group: "nodes", data: { id: pid, parent: sid, label: g.label, kind: "group", stage, page: g.label,
                                                w: UNIT_DX - 10, h: 58 }, classes: "group page" });
          added = true;
        }
        if (this.collapsed.has(pid)) continue;
        const id = `unit:${u.unit_id}`;
        if (!this.cy.getElementById(id).length) {
          this.cy.add({ group: "nodes", data: { id, parent: pid, kind: "unit", unit_id: u.unit_id, w: UNIT_DX - 10, h: 58,
                                                label: labelOf(u) } });
          added = true;
        }
        this.updateUnit(u, labelOf);
      }
    }
    this._summarize(stage);
    if (added) { this._layoutUnits(); this.cy.fit(undefined, 24); }
  }

  // まとまりをたたむ・開く。開いたあとは、たたんでいる間に増えた作業も足す
  toggleGroup(gid) {
    const n = this.cy.getElementById(gid);
    if (!n.length) return;
    if (this.collapsed.has(gid)) {
      this.collapsed.delete(gid);
      this.ec.expand(n, EC_OPTS);
    } else {
      this.collapsed.add(gid);
      this.ec.collapse(n, EC_OPTS);
    }
    const st = n.data("stage");
    const d = this.unitData[st];
    if (d) this.setUnits(st, d.units, d.labelOf, d.groupOf);
    this._layoutUnits();
  }

  // ページのまとまりを全部たたむ（pages=true）・全部開く（false）
  setAllCollapsed(pages) {
    for (const st of this.groups) {
      const sid = `group:${st}`;
      if (this.collapsed.has(sid)) this.toggleGroup(sid);
      for (const p of this.cy.nodes(".page").filter((x) => x.data("stage") === st)) {
        if (this.collapsed.has(p.id()) !== pages) this.toggleGroup(p.id());
      }
    }
    this.cy.fit(undefined, 24);
  }

  // 作業の数と状態の内訳を、まとまりのラベルにする。たたんだまとまりは一番急ぐ状態の色にする
  _summarize(stage) {
    const d = this.unitData[stage];
    if (!d) return;
    const sid = `group:${stage}`;
    const byGroup = new Map([[sid, []]]);
    for (const u of d.units) {
      const pid = `group:${stage}:${d.groupOf(u).key}`;
      byGroup.get(sid).push(u);
      if (!byGroup.has(pid)) byGroup.set(pid, []);
      byGroup.get(pid).push(u);
    }
    for (const [gid, us] of byGroup) {
      const n = this.cy.getElementById(gid);
      if (!n.length) continue;
      const name = gid === sid ? `${stage} の作業` : n.data("page");
      const shut = this.collapsed.has(gid);
      if (!shut) {
        n.data("label", `${name}（${us.length}）`);
        n.classes(gid === sid ? "group" : "group page");
        continue;
      }
      const count = new Map();
      for (const u of us) count.set(u.status, (count.get(u.status) || 0) + 1);
      const parts = [...count].sort((a, b) => urgency(a[0]) - urgency(b[0])).map(([s, k]) => `${STATUS_JA[s] || s} ${k}`);
      const top = [...count.keys()].sort((a, b) => urgency(a) - urgency(b))[0];
      const stale = us.some((u) => u.stale);
      n.data({ label: `${name}（${us.length}）\n${parts.slice(0, 2).join("\n")}${parts.length > 2 ? "\n…" : ""}`,
               h: 30 + 14 * Math.min(parts.length, 3) });
      n.classes(`group collapsed${gid === sid ? "" : " page"} ${statusClass(top)}${stale ? " stale" : ""}`);
    }
  }

  // 工程ごとのまとまりを上から順に、ページのまとまりを工程の列の幅で左から詰めて置く（たたんだ物は1つ分）
  _layoutUnits() {
    const box = this.cy.nodes(".stage").boundingBox();
    const width = Math.max(4 * UNIT_DX, box.w);
    let top = box.y2 + 74;
    for (const st of this.groups) {
      const sid = `group:${st}`;
      const s = this.cy.getElementById(sid);
      if (!s.length) continue;
      const x0 = box.x1 + (UNIT_DX - 10) / 2;
      if (this.collapsed.has(sid)) {
        s.position({ x: x0, y: top });
        top = s.boundingBox().y2 + 74;
        continue;
      }
      let x = 0;
      let y = top;
      let rowH = 0;
      for (const p of s.children()) {
        const kids = this.collapsed.has(p.id()) ? null : p.children();
        const n = kids ? kids.length : 1;
        const cols = Math.max(1, Math.min(n, Math.floor((width + 10) / UNIT_DX)));
        const rows = Math.ceil(n / cols);
        const w = cols * UNIT_DX + PAGE_GAP;
        if (x > 0 && x + w > width + PAGE_GAP) { x = 0; y += rowH; rowH = 0; }
        if (kids) kids.forEach((k, i) => k.position({ x: x0 + x + (i % cols) * UNIT_DX, y: y + Math.floor(i / cols) * 86 }));
        else p.position({ x: x0 + x, y });
        x += w;
        rowH = Math.max(rowH, rows * 86 + PAGE_GAP);
      }
      top = s.boundingBox().y2 + 74;
    }
  }

  updateUnit(u, labelOf) {
    const n = this.cy.getElementById(this.view === "stage" ? `unit:${u.unit_id}` : "");
    if (!n.length) return;
    n.data("label", labelOf(u));
    n.classes(`${statusClass(u.status)}${u.stale ? " stale" : ""}`);
  }

  // 作業のノードが見えていなければ、それをたたんだまとまり（工程、なければページ）のノード
  _visible(id) {
    const n = this.cy.getElementById(id);
    if (n.length || !id.startsWith("unit:")) return n;
    for (const g of this.where.get(id.slice(5)) || []) if (this.collapsed.has(g)) return this.cy.getElementById(g);
    return n;
  }

  // ------------------------------------------------------------------ 作業の図

  showUnit() {
    this.view = "unit";
    this.cy.elements().remove();
    this.edgeCounts = {};
    const els = [...STEPS, "end"].map((s) => ({ group: "nodes", data: { id: `step:${s}`, kind: "step", step: s,
      label: STEP_JA[s], w: s === "end" ? 56 : 84, h: s === "end" ? 40 : 50 }, classes: s === "end" ? "step-node end" : "step-node" }));
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
    // 直させる段は前へ進む線の外（検査との行き来だけ）なので、検査の下に置く
    const chk = this.cy.getElementById("step:check").position();
    this.cy.getElementById("step:fix").position({ x: chk.x, y: chk.y + 110 });
    this.stepPos = Object.fromEntries(this.cy.nodes(".step-node").map((n) => [n.data("step"), { ...n.position() }]));
    this.openSteps = new Set();
    this.stepParts = {};
    this.cy.fit(undefined, 40);
  }

  // 段の中の子：parts は {段: [{ id, label, status }]}。開いている段だけ子のノードを持つ。
  // たたむと子は cytoscape-expand-collapse が預かり、開くと戻してから今の中身に当て直す（増えた・減った子も）
  setStepParts(parts) {
    if (this.view !== "unit") return;
    this.stepParts = parts;
    for (const step of this.openSteps) this._syncParts(step);
  }

  toggleStep(step) {
    const n = this.cy.getElementById(`step:${step}`);
    if (this.openSteps.has(step)) {
      this.openSteps.delete(step);
      this.ec.collapse(n, EC_OPTS);
      n.position(this.stepPos[step]);
    } else {
      this.openSteps.add(step);
      if (this.ec.isExpandable(n)) this.ec.expand(n, EC_OPTS);
      this._syncParts(step);
    }
    this.handlers.onStepsChanged?.();
  }

  _syncParts(step) {
    const sid = `step:${step}`;
    const items = this.stepParts[step] || [];
    const want = new Set(items.map((p) => `part:${step}:${p.id}`));
    this.cy.nodes(".part").filter((x) => x.data("parent") === sid && !want.has(x.id())).remove();
    const base = this.stepPos[step];
    const cols = items.length > 4 ? 2 : 1;
    const rows = Math.ceil(items.length / cols);
    items.forEach((p, i) => {
      const id = `part:${step}:${p.id}`;
      let n = this.cy.getElementById(id);
      if (!n.length) n = this.cy.add({ group: "nodes", data: { id, parent: sid, kind: "part", step, w: PART_W - 8, h: 40 }, classes: "part" });
      n.data("label", p.label);
      n.classes(`part ${p.status ? statusClass(p.status) : ""}`);
      const col = i % cols;
      const row = Math.floor(i / cols);
      n.position({ x: base.x + (col - (cols - 1) / 2) * PART_W, y: base.y + (row - (rows - 1) / 2) * PART_DY });
    });
  }

  // 段ごとの回数・状態。states: {step: {count, status}}
  setSteps(states, current, unitStatus) {
    for (const s of [...STEPS, "end"]) {
      const n = this.cy.getElementById(`step:${s}`);
      const st = states[s] || {};
      const count = st.count ? ` ×${st.count}` : "";
      // 中を開ける段には印を付ける（＋ は開ける、－ はたためる）
      const mark = this.stepParts[s]?.length ? (this.openSteps.has(s) ? " －" : " ＋") : "";
      n.data("label", `${STEP_JA[s]}${count}${mark}${st.note ? `\n${st.note}` : ""}`);
      let cls = s === "end" ? "step-node end " : "step-node ";
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
      const n = this._visible(g.node);
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
