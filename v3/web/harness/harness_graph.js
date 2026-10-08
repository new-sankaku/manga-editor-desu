// ハーネスの図。並べるのは ELK（elkjs の layered・box。v3/web/vendor に置いた物を index.html の script で読む）、
// 描くのは Cytoscape.js。ELK が出したノードの位置・大きさと、辺の折れ点・辺のラベルの位置を、そのまま Cytoscape に当てる。
// - 工程の図：S0〜S7 を左から右へ1列。作業を切り出す工程（S3・S4）は、その下に「工程の作業 > ページ > 作業」の枠を置く
// - 作業の図：1回の作業の段（切り出し→文脈→生成→検査→評価→人の判断→確定→完了）を1列に。
//   戻りの辺は上の通り道、飛ばす辺は下の通り道を通す（ELK のポートの辺を決める）。直させる段は検査との行き来だけ
// - 枠（まとまり・開いた段）は Cytoscape の入れ子にしない。ELK が決めた大きさの、下に敷くノードにする（data.box が親の枠）
// - ノードの大きさはラベルの文字の大きさから決める（決め打ちの幅を持たない）。文字は 12px で、全体を見たときに縮めない
// 並べ直すのは、ノードや辺が増減したとき・ノードの大きさが変わったときだけ（_relayout の1か所）。
// 状態が変わっただけならクラスとラベルを変えるだけで、ノードは動かない。

/* global cytoscape, ELK */
const elk = new ELK();

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
// 図の段の並び（直させるは評価の後ろに置く。ELK は同じ列の中をこの順に上から置く）
const ORDER = ["cut_out", "context", "generate", "check", "evaluate", "fix", "review", "finalize", "end"];
const FORWARD = [
  ["cut_out", "context"], ["context", "generate"], ["generate", "check"], ["check", "evaluate"],
  ["evaluate", "review"], ["review", "finalize"], ["finalize", "end"],
];
// 辺のラベルは短く（図の上）。全文は辺に指を置いたときの説明と、横の欄の「戻った回数」に出す。
// 検査→直させるは隣の列へ入る短い線で、ラベルを置く長さが無い。行き先の「直させる」が中身を言うので、図にはラベルを出さない
const SKIPS = [["check", "review", "評価なし", "評価の段を使わない"], ["evaluate", "end", "判断なし", "人の判断を使わない"]];
export const RETRY_EDGES = [
  ["check", "fix", "", "落ちた所だけ直す"],
  ["fix", "check", "検査し直す", "直した候補だけ検査し直す"],
  ["check", "context", "作り直す", "直せない・直す上限で全部を作り直す"],
  ["evaluate", "context", "選べない", "評価で選べない・割れた"],
  ["review", "context", "却下", "却下（理由つき）"],
  ["review", "generate", "直した絵から", "人が直した絵から続ける"],
];
export const EDGE_TEXT = Object.fromEntries([...SKIPS, ...RETRY_EDGES].map(([a, b, , full]) => [`${a}>${b}`, full]));

// たたんだまとまりの色に使う、状態の急ぐ順（人を待つ・止まった が先）
const URGENT = ["blocked", "stopped", "failed", "awaiting_review", "paused", "cancelling", "running", "retrying",
                "queued", "waiting_limit", "waiting_budget", "done", "cancelled"];
const urgency = (s) => (URGENT.includes(s) ? URGENT.indexOf(s) : URGENT.length);
// いくつかの状態のうち一番急ぐもの（たたんだまとまり・段の中の子の色）
export const urgentStatus = (list) => [...list].sort((a, b) => urgency(a) - urgency(b))[0];

const HUMAN = new Set(["awaiting_review", "paused", "stopped", "blocked"]);
const SERVICE = new Set(["queued", "waiting_limit", "waiting_budget", "retrying"]);
export function statusClass(s) {
  if (s === "awaiting_review") return "st-review";
  if (HUMAN.has(s)) return s === "paused" ? "st-paused" : "st-blocked";
  if (SERVICE.has(s)) return "st-waiting";
  return `st-${s || "none"}`;
}
export const isHumanWait = (s) => HUMAN.has(s);

// ------------------------------------------------------------------ 色と文字

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
// 文字の形は theme.css の --font-mono。図の文字の大きさの計り（canvas）と Cytoscape に同じ物を渡す
const MONO = getComputedStyle(document.documentElement).getPropertyValue("--font-mono").trim();
if (!MONO) throw new Error("文字の変数 --font-mono がありません");

export const FONT = 12;        // 図の文字（ノード・辺・枠）。全体を見たときもこれより小さくしない（fit の下限が 1 倍）
const LH = 1.35;               // 行の高さ（文字の大きさの倍）
const PAD_X = 12, PAD_Y = 8;   // ノードの中の余白
const BAND = 10;               // 工程の図の作業のノードの下の、進み具合の棒の帯
const LABEL_PAD = 3;           // 辺のラベルの下地の余白
const FRAME_PAD = 12;          // 枠の中の余白
const MARGIN = 24;             // 全体を見るときの、図のまわりの余白
const MAX_ZOOM = 1.25;
const measureCtx = document.createElement("canvas").getContext("2d");
function textSize(label) {
  measureCtx.font = `${FONT}px ${MONO}`;
  const lines = String(label).split("\n");
  return { w: Math.ceil(Math.max(...lines.map((l) => measureCtx.measureText(l).width))), h: Math.ceil(lines.length * FONT * LH), lines: lines.length };
}
const HEADER = Math.ceil(FONT * LH) + 8;  // 枠の名前の行

const STYLE = [
  { selector: "node", style: {
    shape: "round-rectangle", "background-color": C.node, "border-width": 1, "border-color": C.line,
    label: "data(label)", "font-family": MONO, "font-size": FONT, "line-height": LH, color: C.ink, "text-wrap": "wrap",
    "text-max-width": 2000, "text-valign": "center", "text-halign": "center", width: "data(w)", height: "data(h)",
    "text-margin-y": "data(lmy)", "z-index": 10, "z-index-compare": "manual",
    "transition-property": "border-width, border-color, background-color", "transition-duration": "0.4s",
  } },
  { selector: "node.frame", style: {
    "background-color": C.groupBg, "background-opacity": 0.55, "border-style": "dashed", "border-color": C.wait,
    "text-margin-x": "data(lmx)", "text-justification": "left", color: C.ink2, "z-index": 1,
  } },
  { selector: "node.frame.page", style: { "z-index": 2 } },
  { selector: "node.folded", style: { "background-color": C.node, "background-opacity": 1, "border-style": "solid", color: C.ink } },
  { selector: "node.end", style: { shape: "ellipse" } },
  // 使っていない段：線と下地を薄くし、文字は読める濃さのまま
  { selector: "node.unused", style: { "background-opacity": 0.45, "border-opacity": 0.5, color: C.ink2, "border-style": "dashed" } },
  { selector: ".st-running", style: { "border-color": C.run, "border-width": 2, "background-color": C.runBg } },
  { selector: ".st-waiting", style: { "border-color": C.wait, "border-style": "dashed", "border-width": 1.5 } },
  { selector: ".st-review", style: { "border-color": C.review, "border-width": 2, "background-color": C.reviewBg } },
  { selector: ".st-review.pulse-on", style: { "border-width": 5 } },
  { selector: ".st-blocked, .st-stopped, .st-failed", style: { "border-color": C.bad, "border-width": 2, "background-color": C.badBg } },
  { selector: ".st-blocked.pulse-on, .st-stopped.pulse-on", style: { "border-width": 4 } },
  { selector: ".st-paused", style: { "border-color": C.pause, "border-width": 2, "background-color": C.pauseBg } },
  { selector: ".st-paused.pulse-on", style: { "border-width": 4 } },
  { selector: ".st-cancelling", style: { "border-color": C.bad, "border-style": "dashed", "border-width": 2 } },
  { selector: ".st-cancelled", style: { "background-opacity": 0.45, "border-style": "dotted", color: C.ink2 } },
  { selector: ".st-done", style: { "background-color": C.doneBg, "border-color": C.done, color: C.ink2 } },
  { selector: "node.frame.st-running, node.frame.st-waiting, node.frame.st-done", style: { "background-color": C.groupBg } },
  { selector: "node.stale", style: {
    "underlay-color": C.stale, "underlay-opacity": 0.45, "underlay-padding": 5, "underlay-shape": "round-rectangle",
  } },
  { selector: "node.current", style: { "border-width": 3 } },
  { selector: "node:selected", style: { "overlay-color": C.hot, "overlay-opacity": 0.12, "overlay-padding": 3 } },
  { selector: "edge", style: {
    width: 1.3, "line-color": C.edge, "target-arrow-color": C.edge, "target-arrow-shape": "triangle", "arrow-scale": 0.8,
    "curve-style": "straight", "edge-distances": "endpoints", label: "data(label)", "font-family": MONO, "font-size": FONT,
    "text-wrap": "wrap", "line-height": LH,
    color: C.ink2, "text-background-color": C.bg, "text-background-opacity": 1, "text-background-padding": LABEL_PAD,
    "text-background-shape": "round-rectangle", "z-index": 5, "z-index-compare": "manual",
    "transition-property": "line-color, target-arrow-color, width", "transition-duration": "0.4s",
  } },
  { selector: "edge.bent", style: { "curve-style": "segments", "segment-radius": 6, "radius-type": "arc-radius" } },
  { selector: "edge.skip", style: { "line-style": "dotted" } },
  { selector: "edge.retry", style: { "line-style": "dashed", "line-dash-pattern": [6, 4], "line-color": C.retry, "target-arrow-color": C.retry, color: C.retry } },
  { selector: "edge.retry.used", style: { width: 2 } },
  { selector: "edge.traversed", style: { "line-color": C.hot, "target-arrow-color": C.hot, width: 3 } },
];

// ------------------------------------------------------------------ ELK の決まり

const LAYERED = {
  "elk.algorithm": "layered",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.json.edgeCoords": "ROOT",
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
  "elk.layered.cycleBreaking.strategy": "MODEL_ORDER",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.spacing.nodeNodeBetweenLayers": "32",
  "elk.layered.spacing.edgeNodeBetweenLayers": "18",
  "elk.layered.spacing.edgeEdgeBetweenLayers": "14",
  "elk.spacing.nodeNode": "28",
  "elk.spacing.edgeNode": "18",
  // 並んだ線の間は、辺のラベル（文字の高さ＋下地）が隣の線にかからない広さにする（ラベルは線の上に置く）
  "elk.spacing.edgeEdge": String(Math.ceil(FONT * LH + 2 * LABEL_PAD + 6)),
};
const BOX = (aspect) => ({
  "elk.algorithm": "box", "elk.box.packingMode": "SIMPLE", "elk.aspectRatio": String(aspect),
  "elk.spacing.nodeNode": "16", "elk.padding": `[top=${HEADER + 4},left=${FRAME_PAD},bottom=${FRAME_PAD},right=${FRAME_PAD}]`,
});

export class HarnessGraph {
  constructor(container, overlay, handlers) {
    this.container = container;
    this.overlay = overlay;
    this.handlers = handlers;
    this.cy = cytoscape({ container, style: STYLE, minZoom: 0.3, maxZoom: 2, wheelSensitivity: 0.25,
                          boxSelectionEnabled: false, autoungrabify: true });
    this.view = null;
    this.edgeCounts = {};
    this.collapsed = new Set();
    this.cy.on("tap", "node", (e) => {
      const d = e.target.data();
      if (d.kind === "group") return this.toggleGroup(e.target.id());
      if (d.kind === "step" && this.stepParts?.[d.step]?.length) this.toggleStep(d.step);
      return this.handlers.onTap(e.target.id(), d);
    });
    // 辺に指を置くと、短いラベルの全文とたどった回数を出す
    this.cy.on("mouseover", "edge", (e) => this.handlers.onHover?.(e.target.data("note") || ""));
    this.cy.on("mouseout", "edge", () => this.handlers.onHover?.(""));
    this.cy.on("render", () => this._queueOverlay());
    // 箱の大きさが変わったら（右の欄の高さが変わって左の列が伸びた・縮んだなど）合わせ直す。fit が自分で変えた大きさでは呼ばない
    new ResizeObserver(() => {
      const wrap = this.container.parentElement;
      if (this._fitSize && this._fitSize !== `${wrap.clientWidth}x${wrap.clientHeight}`) this.fit();
    }).observe(this.container.parentElement);
    // 人を待つノードを脈打たせる（スタイルの transition で太さを行き来させる）
    this._pulse = setInterval(() => this.cy.nodes(".st-review, .st-blocked, .st-stopped, .st-paused").not(".frame").toggleClass("pulse-on"), 650);
    this.progress = [];
    this.markers = [];
    this._gen = 0;
    this.layoutDone = Promise.resolve();
  }

  // ------------------------------------------------------------------ 並べる（1か所）

  // 今の要素から ELK の図を作って並べ、位置・大きさ・辺の折れ点を当てる。続けて呼ばれたら最後の1回だけ当てる
  // 並べ方の案が複数あるとき（工程の図の段の列の折り返しとページと作業の詰め方、作業の図の横向き・縦向き）は全部を並べ、図の箱の幅に倍率 1 で入る物のうち一番低い物を取る。
  // 幅に入る物が無ければ一番細い物を取り、fit が図の幅を広げて箱の中で横に動かせるようにする（狭い窓）
  _relayout() {
    const gen = ++this._gen;
    const graphs = this.view === "unit" ? [this._unitElk("RIGHT"), this._unitElk("DOWN")] : this._stageCandidates();
    const room = this.container.parentElement.clientWidth - 2 * MARGIN;
    this.layoutDone = Promise.all(graphs.map((g) => elk.layout(g))).then((all) => {
      if (gen !== this._gen) return;
      const fits = all.filter((r) => r.width <= room);
      const res = fits.length ? fits.reduce((a, b) => (b.height < a.height ? b : a)) : all.reduce((a, b) => (b.width < a.width ? b : a));
      this.layoutWidth = room;
      if (this.view === "unit") this._labelDir(graphs[all.indexOf(res)].layoutOptions["elk.direction"]);
      if (this.view === "stage") centerGroups(res);
      this._apply(res);
      this.fit();
      this.handlers.onLayout?.();
    });
    return this.layoutDone;
  }

  // 窓の大きさが変わったとき。今の並びが箱の幅に入るなら倍率だけ合わせ（ノードは動かない）。
  // 並べ直すのは、箱の幅より 8% を超えてはみ出すようになったときと、並べたときより広くなって並べ方を選び直せるときだけ。
  // 少しだけはみ出すときは並びを変えず、fit が図の幅を広げて箱の中で横に動かせるようにする（少し狭めただけで図が組み替わらないように）
  resized() {
    const room = this.container.parentElement.clientWidth - 2 * MARGIN;
    const bb = this.cy.elements().boundingBox({ includeOverlays: false });
    if (bb.w > room * 1.08 || room > this.layoutWidth * 1.25) return this._relayout();
    this.fit();
    return Promise.resolve();
  }

  _apply(res) {
    const cy = this.cy;
    cy.batch(() => {
      // ノードの座標は親からの相対（ポートの辺を ELK に正しく読ませるため shapeCoords は既定のまま）。辺は図の座標（edgeCoords ROOT）
      const walk = (n, ox, oy) => {
        for (const c of n.children || []) {
          const el = cy.getElementById(c.id);
          const x = ox + c.x, y = oy + c.y;
          if (el.length) {
            el.position({ x: x + c.width / 2, y: y + c.height / 2 });
            if (el.hasClass("frame")) {
              el.data({ w: c.width, h: c.height });
              const t = textSize(el.data("label"));
              el.data({ lmx: -c.width / 2 + FRAME_PAD + t.w / 2, lmy: -c.height / 2 + 6 + t.h / 2 });
            }
          }
          walk(c, x, y);
        }
      };
      walk(res, 0, 0);
    });
    const edges = [];
    const collect = (n) => { for (const e of n.edges || []) edges.push(e); for (const c of n.children || []) collect(c); };
    collect(res);
    for (const e of edges) {
      const el = cy.getElementById(e.id);
      if (!el.length || !e.sections?.length) continue;
      const s = e.sections[0];
      const pts = [s.startPoint, ...(s.bendPoints || []), s.endPoint];
      setEdgeGeometry(el, pts);
    }
    placeEdgeLabels(cy);
    this._crossings = findCrossings(cy);
  }

  // 全体を見る。文字が 12px より小さくならないよう、倍率は 1 倍を下限にする。高さが足りなければ図の箱を伸ばす
  fit() {
    const cy = this.cy;
    if (!cy.elements().length) return;
    const wrap = this.container.parentElement;
    const focus = document.documentElement.hasAttribute("data-focus") && !document.documentElement.hasAttribute("data-peek");
    wrap.style.minHeight = "";
    const base = wrap.clientHeight;
    const bb = cy.elements().boundingBox({ includeOverlays: false });
    // 図が倍率 1 でも箱の幅に入らないとき（狭い窓）は、図の幅を広げて箱の中で横に動かして見る。文字を小さくも、切りもしない
    const wide = Math.ceil(bb.w + 2 * MARGIN);
    const over = wide > wrap.clientWidth ? `${wide}px` : "";
    for (const el of [this.container, this.overlay]) if (el.style.width !== over) el.style.width = over;
    const cw = this.container.clientWidth;
    const zw = (cw - 2 * MARGIN) / bb.w;
    const zh = (base - 2 * MARGIN) / bb.h;
    let z = Math.min(MAX_ZOOM, zw, Math.max(1, zh));
    if (z < 1) z = 1;
    // 図が箱より高いときは箱を高くする（切らない）。低いときは箱を埋めたまま真ん中に置く。絵だけの画面では箱は画面いっぱいのまま
    const need = Math.ceil(bb.h * z + 2 * MARGIN);
    if (!focus && need > base) wrap.style.minHeight = `${need}px`;
    cy.resize();
    const ch = this.container.clientHeight;
    cy.viewport({ zoom: z, pan: { x: (cw - bb.w * z) / 2 - bb.x1 * z, y: Math.max(MARGIN, (ch - bb.h * z) / 2) - bb.y1 * z } });
    this._fitSize = `${wrap.clientWidth}x${wrap.clientHeight}`;
  }

  // ------------------------------------------------------------------ 工程の図

  showStages(stages) {
    this.view = "stage";
    this.cy.elements().remove();
    const els = stages.map((s) => ({ group: "nodes", data: { id: `stage:${s.stage}`, kind: "stage", stage: s.stage, label: s.label, lmy: 0 },
                                      classes: `stage ${s.cls}` }));
    for (let i = 1; i < stages.length; i++) {
      els.push({ group: "edges", data: { id: `se:${i}`, source: `stage:${stages[i - 1].stage}`,
                                         target: `stage:${stages[i].stage}`, label: "" } });
    }
    this.cy.add(els);
    this._sizeStages();
    this.groups = [];
    this.unitData = {};
    this.where = new Map();
    this._relayout();
  }

  // 工程のノードは同じ大きさにそろえる（一番長いラベルに合わせる。行の数は今の一番多いもの、3行を下限）
  _sizeStages() {
    const ns = this.cy.nodes(".stage");
    const t = ns.map((n) => textSize(n.data("label")));
    const w = Math.max(textSize("送り先を待つ 99").w, ...t.map((x) => x.w)) + 2 * PAD_X;
    const lines = Math.max(3, ...t.map((x) => x.lines));
    const h = Math.ceil(lines * FONT * LH) + 2 * PAD_Y;
    let changed = false;
    ns.forEach((n) => { if (n.data("w") !== w || n.data("h") !== h) { n.data({ w, h }); changed = true; } });
    return changed;
  }

  updateStage(s) {
    const n = this.cy.getElementById(`stage:${s.stage}`);
    if (!n.length) return;
    n.data({ label: s.label });
    n.classes(`stage ${s.cls}`);
    if (this._sizeStages()) this._relayout();
  }

  // 作業のノードを工程の下に、入れ子の枠（工程の作業 > ページ > 作業）で並べる。
  // 枠を押すとたたむ・開く。たたんだ枠は1つのノードになり、中の作業の数と状態の内訳を出す。
  // 色は中で一番急ぐ状態（人を待つ・止まった を先）に合わせる。
  // groupOf(u) は { key, label }（作業が入るページ。ページを持たない作業は呼ぶ側が別の key にする）
  setUnits(stage, units, labelOf, groupOf) {
    if (this.view !== "stage") return;
    this.unitData[stage] = { units, labelOf, groupOf };
    const sid = `group:${stage}`;
    let added = false;
    if (!this.cy.getElementById(sid).length) {
      this.cy.add({ group: "nodes", data: { id: sid, label: "", kind: "group", stage, w: 10, h: 10, lmx: 0, lmy: 0 }, classes: "frame group" });
      if (!this.groups.includes(stage)) this.groups.push(stage);
      added = true;
    }
    const want = new Set();
    const seen = new Set();
    if (!this.collapsed.has(sid)) {
      for (const [ord, u] of units.entries()) {
        const g = groupOf(u);
        const pid = `group:${stage}:${g.key}`;
        this.where.set(u.unit_id, [sid, pid]);
        want.add(pid);
        if (!this.cy.getElementById(pid).length) {
          this.cy.add({ group: "nodes", data: { id: pid, box: sid, label: g.label, kind: "group", stage, page: g.label, w: 10, h: 10, lmx: 0, lmy: 0 },
                        classes: "frame group page" });
          added = true;
        }
        // 並びは渡された作業の順（ページはその中で最初に出た所）
        if (!seen.has(pid)) { this.cy.getElementById(pid).data("ord", ord); seen.add(pid); }
        if (this.collapsed.has(pid)) continue;
        const id = `unit:${u.unit_id}`;
        want.add(id);
        if (!this.cy.getElementById(id).length) {
          this.cy.add({ group: "nodes", data: { id, box: pid, kind: "unit", stage, unit_id: u.unit_id, label: labelOf(u), w: 10, h: 10, lmy: -BAND / 2 } });
          added = true;
        }
        this.cy.getElementById(id).data("ord", ord);
        this.updateUnit(u, labelOf);
      }
    }
    // たたんだ枠の中の物は消す（開いたらまた足す）
    const gone = this.cy.nodes('[kind="unit"], [kind="group"]').filter((n) => n.data("stage") === stage && n.id() !== sid && !want.has(n.id()));
    if (gone.length) { gone.remove(); added = true; }
    this._summarize(stage);
    if (this._sizeUnits(stage) || added) this._relayout();
  }

  // 1つの工程の作業のノードは同じ大きさにそろえる（3行。下に進み具合の帯）
  _sizeUnits(stage) {
    const ns = this.cy.nodes('[kind="unit"]').filter((n) => this.where.get(n.data("unit_id"))?.[0] === `group:${stage}`);
    const folded = this.cy.nodes(".folded").filter((n) => n.data("stage") === stage);
    const t = [...ns, ...folded].map((n) => textSize(n.data("label")));
    const w = Math.max(textSize("p99-99 99/99").w, textSize("判断待ち・古い").w, ...t.map((x) => x.w)) + 2 * PAD_X;
    const h = Math.ceil(Math.max(3, ...t.map((x) => x.lines)) * FONT * LH) + 2 * PAD_Y + BAND;
    let changed = false;
    for (const n of [...ns, ...folded]) if (n.data("w") !== w || n.data("h") !== h) { n.data({ w, h }); changed = true; }
    return changed;
  }

  // 枠をたたむ・開く
  toggleGroup(gid) {
    const n = this.cy.getElementById(gid);
    if (!n.length) return;
    if (this.collapsed.has(gid)) this.collapsed.delete(gid); else this.collapsed.add(gid);
    const st = n.data("stage");
    const d = this.unitData[st];
    if (d) this.setUnits(st, d.units, d.labelOf, d.groupOf);
    this._relayout();
  }

  // ページの枠を全部たたむ（pages=true）・全部開く（false）
  setAllCollapsed(pages) {
    for (const st of this.groups) {
      this.collapsed.delete(`group:${st}`);
      for (const k of [...this.collapsed]) if (k.startsWith(`group:${st}:`)) this.collapsed.delete(k);
      const d = this.unitData[st];
      if (!d) continue;
      if (pages) for (const u of d.units) this.collapsed.add(`group:${st}:${d.groupOf(u).key}`);
      this.setUnits(st, d.units, d.labelOf, d.groupOf);
    }
    this._relayout();
  }

  // 作業の数と状態の内訳を、枠のラベルにする。たたんだ枠は一番急ぐ状態の色にする
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
        n.classes(gid === sid ? "frame group" : "frame group page");
        continue;
      }
      const count = new Map();
      for (const u of us) count.set(u.status, (count.get(u.status) || 0) + 1);
      const parts = [...count].sort((a, b) => urgency(a[0]) - urgency(b[0])).map(([s, k]) => `${STATUS_JA[s] || s} ${k}`);
      const top = [...count.keys()].sort((a, b) => urgency(a) - urgency(b))[0];
      const stale = us.some((u) => u.stale);
      // 内訳は全部出す（隠さない）。行が増えれば、ノードを高くする
      n.data({ label: `${name}（${us.length}）\n${parts.join("\n")}`, lmy: -BAND / 2 });
      n.classes(`group folded${gid === sid ? "" : " page"} ${statusClass(top)}${stale ? " stale" : ""}`);
    }
  }

  updateUnit(u, labelOf) {
    const n = this.cy.getElementById(this.view === "stage" ? `unit:${u.unit_id}` : "");
    if (!n.length) return;
    n.data("label", labelOf(u));
    n.classes(`${statusClass(u.status)}${u.stale ? " stale" : ""}`);
  }

  // 作業のノードが見えていなければ、それをたたんだ枠（工程、なければページ）のノード
  _visible(id) {
    const n = this.cy.getElementById(id);
    if (n.length || !id.startsWith("unit:")) return n;
    for (const g of this.where.get(id.slice(5)) || []) if (this.collapsed.has(g)) return this.cy.getElementById(g);
    return n;
  }

  // 段の列の折り返し（しない・2・1・0.3・縦に1列）、ページの中の作業の詰め方（横長〜縦長）、工程の作業の枠の中のページの詰め方の組を案にする
  _stageCandidates() {
    const out = [];
    for (const wrap of [0, 2, 1, 0.3]) for (const page of [40, 4, 1.5, 0.3]) for (const group of [1, 3, 8]) out.push(this._stageElk(page, group, wrap));
    // 電話の幅：折り返しても2つ並ぶと入らないので、段を縦に1列に並べ、ページも縦に積む案
    for (const group of [0.3, 1]) out.push(this._stageElk(0.3, group, "down"));
    return out;
  }

  // wrap が 0 なら段の列を1行に、数ならその縦横の比で折り返す（ELK の layered の折り返し）。"down" なら縦に1列
  _stageElk(pageAspect, groupAspect, wrap) {
    const cy = this.cy;
    const size = (n) => ({ id: n.id(), width: n.data("w"), height: n.data("h") });
    // box は大きい物から詰めるので、ページ・作業の順を優先度で残す（先の物ほど高い）
    const ordered = (x, i, n) => ({ ...x, layoutOptions: { ...(x.layoutOptions || {}), "elk.priority": String(n - i) } });
    const fold = wrap && wrap !== "down" ? { "elk.layered.wrapping.strategy": "MULTI_EDGE", "elk.aspectRatio": String(wrap) } : {};
    const row = { id: "wrap:stages", layoutOptions: { ...LAYERED, ...fold, "elk.direction": wrap === "down" ? "DOWN" : "RIGHT", "elk.padding": "[top=0,left=0,bottom=0,right=0]" },
                  children: cy.nodes(".stage").map(size),
                  edges: cy.edges().map((e) => ({ id: e.id(), sources: [e.source().id()], targets: [e.target().id()] })) };
    const groups = this.groups.map((st) => {
      const g = cy.getElementById(`group:${st}`);
      if (g.hasClass("folded")) return size(g);
      const byOrd = (a, b) => a.data("ord") - b.data("ord");
      const pages = cy.nodes(".page").filter((p) => p.data("box") === g.id()).sort(byOrd);
      return { id: g.id(), layoutOptions: BOX(groupAspect),
               children: pages.map((p, i) => (p.hasClass("folded") ? ordered(size(p), i, pages.length)
                 : ordered({ id: p.id(), layoutOptions: BOX(pageAspect),
                             children: cy.nodes('[kind="unit"]').filter((u) => u.data("box") === p.id()).sort(byOrd).map((u, k, all) => ordered(size(u), k, all.length)) }, i, pages.length))) };
    });
    return { id: "root", layoutOptions: { ...LAYERED, "elk.direction": "DOWN", "elk.hierarchyHandling": "SEPARATE_CHILDREN",
                                          "elk.layered.spacing.nodeNodeBetweenLayers": "40", "elk.spacing.nodeNode": "32" },
             children: [row, ...groups],
             edges: groups.map((g) => ({ id: `wrap:${g.id}`, sources: ["wrap:stages"], targets: [g.id] })) };
  }

  // ------------------------------------------------------------------ 作業の図

  showUnit() {
    this.view = "unit";
    this.cy.elements().remove();
    this.edgeCounts = {};
    const els = ORDER.map((s) => ({ group: "nodes", data: { id: `step:${s}`, kind: "step", step: s, label: STEP_JA[s], lmx: 0, lmy: 0 },
                                    classes: s === "end" ? "step-node end" : "step-node" }));
    for (const [a, b] of FORWARD) els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: "", kind: "forward" } });
    for (const [a, b, why, full] of SKIPS) {
      els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: why, full, kind: "skip", note: full }, classes: "skip" });
    }
    for (const [a, b, why, full] of RETRY_EDGES) {
      els.push({ group: "edges", data: { id: `e:${a}>${b}`, source: `step:${a}`, target: `step:${b}`, label: why, full, kind: "retry", note: full }, classes: "retry" });
    }
    this.cy.add(els);
    this.openSteps = new Set();
    this.stepParts = {};
    this._sizeSteps();
    this._relayout();
  }

  // 段のノードは同じ大きさにそろえる（2行。1行目は名前と回数、2行目は候補の数・却下の数）
  _sizeSteps() {
    const ns = this.cy.nodes(".step-node").not(".frame");
    const t = ns.map((n) => textSize(n.data("label")));
    const w = Math.max(textSize("人の判断 ×99 ＋").w, ...t.map((x) => x.w)) + 2 * PAD_X;
    const h = Math.ceil(Math.max(2, ...t.map((x) => x.lines)) * FONT * LH) + 2 * PAD_Y;
    let changed = false;
    ns.forEach((n) => {
      const end = n.data("step") === "end";
      const ww = end ? textSize("完了 ×9").w + 2 * PAD_X : w;
      const hh = end ? Math.ceil(2 * FONT * LH) + 2 * PAD_Y : h;
      if (n.data("w") !== ww || n.data("h") !== hh) { n.data({ w: ww, h: hh }); changed = true; }
    });
    // 中の子は、開いた段ごとに同じ大きさにそろえる（段どうしでそろえると、いちばん長い文の段に引きずられて図が横に延びる）
    const byBox = new Map();
    this.cy.nodes(".part").forEach((n) => { const k = n.data("box"); if (!byBox.has(k)) byBox.set(k, []); byBox.get(k).push(n); });
    for (const parts of byBox.values()) {
      const pt = parts.map((n) => textSize(n.data("label")));
      const pw = Math.max(w - 2 * PAD_X, ...pt.map((x) => x.w)) + 2 * PAD_X;
      const ph = Math.ceil(Math.max(2, ...pt.map((x) => x.lines)) * FONT * LH) + 2 * PAD_Y;
      for (const n of parts) if (n.data("w") !== pw || n.data("h") !== ph) { n.data({ w: pw, h: ph }); changed = true; }
    }
    return changed;
  }

  // 段の中の子：parts は {段: [{ id, label, status }]}。開いている段だけ子のノードを持つ
  setStepParts(parts) {
    if (this.view !== "unit") return;
    this.stepParts = parts;
    let changed = false;
    for (const step of this.openSteps) changed = this._syncParts(step) || changed;
    if (changed) this._relayout();
  }

  toggleStep(step) {
    const n = this.cy.getElementById(`step:${step}`);
    if (this.openSteps.has(step)) {
      this.openSteps.delete(step);
      this.cy.nodes(".part").filter((x) => x.data("box") === n.id()).remove();
      n.removeClass("frame");
    } else {
      this.openSteps.add(step);
      n.addClass("frame");
      this._syncParts(step);
    }
    this._sizeSteps();
    this._relayout();
    this.handlers.onStepsChanged?.();
  }

  _syncParts(step) {
    const sid = `step:${step}`;
    const items = this.stepParts[step] || [];
    const want = new Set(items.map((p) => `part:${step}:${p.id}`));
    const gone = this.cy.nodes(".part").filter((x) => x.data("box") === sid && !want.has(x.id()));
    let changed = gone.length > 0;
    gone.remove();
    for (const p of items) {
      const id = `part:${step}:${p.id}`;
      let n = this.cy.getElementById(id);
      if (!n.length) {
        n = this.cy.add({ group: "nodes", data: { id, box: sid, kind: "part", step, w: 10, h: 10, lmy: 0 }, classes: "part" });
        changed = true;
      }
      n.data("label", p.label);
      n.classes(`part ${p.status ? statusClass(p.status) : ""}`);
    }
    return this._sizeSteps() || changed;
  }

  // 段ごとの回数・状態。states: {step: {count, status, note}}
  setSteps(states, current, unitStatus) {
    for (const s of ORDER) {
      const n = this.cy.getElementById(`step:${s}`);
      const st = states[s] || {};
      const count = st.count ? ` ×${st.count}` : "";
      // 中を開ける段には印を付ける（＋ は開ける、－ はたためる）
      const mark = this.stepParts[s]?.length ? (this.openSteps.has(s) ? " －" : " ＋") : "";
      n.data("label", `${STEP_JA[s]}${count}${mark}${st.note ? `\n${st.note}` : ""}`);
      let cls = s === "end" ? "step-node end " : "step-node ";
      if (this.openSteps.has(s)) cls += "frame ";
      if (s === current) cls += `${statusClass(unitStatus)} current`;
      else if (st.status) cls += statusClass(st.status);
      if (!st.count && s !== current) cls += " unused";
      n.classes(cls);
    }
    if (this._sizeSteps()) this._relayout();
    else this._frameLabels();
  }

  // 開いた段の名前は枠の左上。ラベルの長さが変わったら、ずらしを当て直す（並べ直さない）
  _frameLabels() {
    for (const n of this.cy.nodes(".frame")) {
      const t = textSize(n.data("label"));
      n.data({ lmx: -n.data("w") / 2 + FRAME_PAD + t.w / 2, lmy: -n.data("h") / 2 + 6 + t.h / 2 });
    }
    for (const n of this.cy.nodes(".step-node").not(".frame")) n.data({ lmx: 0, lmy: 0 });
  }

  // 辺をたどった回数。ラベルは短いまま、回数は辺の説明（指を置く）と段の回数に出す
  setEdgeCounts(counts) {
    this.edgeCounts = counts;
    this.cy.edges().forEach((e) => {
      const n = counts[e.id().slice(2)] || 0;
      const full = e.data("full");
      if (full) e.data("note", `${full}${n ? `（${n}回）` : ""}`);
      e.toggleClass("used", n > 0);
    });
  }

  // 辺のラベルの向き：段を縦に並べたときは、戻りの線と飛ばす線が縦に走るので、ラベルも縦書き（1字ずつ改行）にする。
  // 横書きのままだと、縦の線どうしの間をラベルの幅だけ空けることになり、図が箱の幅に入らない
  _labelDir(dir) {
    this.cy.batch(() => {
      for (const e of this.cy.edges()) {
        const short = e.data("short") ?? e.data("label");
        e.data({ short, tate: dir === "DOWN", label: dir === "DOWN" ? tate(short) : short });
      }
    });
  }

  // dir は "RIGHT"（段を横に並べる）か "DOWN"（縦に並べる。箱の幅に横向きが入らないとき）。
  // 縦のときは辺を全部 x と y を入れ替えた向きにする（上→左、下→右、右→下、左→上）。並び順の決まりはそのまま効く
  _unitElk(dir) {
    const cy = this.cy;
    const TURN = dir === "DOWN" ? { NORTH: "WEST", SOUTH: "EAST", EAST: "SOUTH", WEST: "NORTH" } : null;
    // 辺ごとにポートを作り、出る辺・入る辺を決める：前へ進む辺は右から左へ、戻りの辺は上から上へ、飛ばす辺は下から下へ。
    // 同じ辺に並ぶポートの順は自分で決める（ELK に任せると、上・下の辺で戻りの線どうしが入れ子にならずに交わる）。
    // 上・下の辺では、左へ行く線を左に、右へ行く線を右に置き、遠くへ行く線ほど外側（左へ行く線は右、右へ行く線は左）にする。
    // こうすると遠くへ行く線が外側の道を通り、近くへ行く線の内側に入らない
    const COL = { cut_out: 0, context: 1, generate: 2, check: 3, evaluate: 4, fix: 4.5, review: 5, finalize: 6, end: 7 };
    const SIDE = { forward: ["EAST", "WEST"], retry: ["NORTH", "NORTH"], skip: ["SOUTH", "SOUTH"] };
    const ports = new Map();
    const port = (node, id, side, other, self) => {
      if (!ports.has(node)) ports.set(node, []);
      const d = COL[other] - COL[self];
      const key = side === "NORTH" || side === "SOUTH" ? (d < 0 ? -100 - d : 100 - d) : (side === "EAST" ? Math.abs(d) : 0);
      ports.get(node).push({ id, side: TURN ? TURN[side] : side, key });
      return id;
    };
    const edges = cy.edges().map((e) => {
      let [ss, ts] = SIDE[e.data("kind")];
      const [a, b] = e.id().slice(2).split(">");
      // 直させる段は評価と同じ列の下。検査の右から行き、戻りは直させるの下から検査の下へ
      if (a === "check" && b === "fix") { ss = "EAST"; ts = "WEST"; }
      if (a === "fix" && b === "check") { ss = "SOUTH"; ts = "SOUTH"; }
      return { id: e.id(), sources: [port(e.source().id(), `${e.id()}:s`, ss, b, a)], targets: [port(e.target().id(), `${e.id()}:t`, ts, a, b)] };
    });
    // ELK のポートの順は、上の辺の左から時計回り（上は左→右、右は上→下、下は右→左、左は下→上）
    const RANK = { NORTH: 0, EAST: 1, SOUTH: 2, WEST: 3 };
    for (const [node, list] of ports) {
      list.sort((p, q) => RANK[p.side] - RANK[q.side] || (p.side === "SOUTH" || p.side === "WEST" ? q.key - p.key : p.key - q.key));
      ports.set(node, list.map((p, i) => ({ id: p.id, width: 1, height: 1, layoutOptions: { "elk.port.side": p.side, "elk.port.index": String(i) } })));
    }
    const children = ORDER.map((s) => {
      const n = cy.getElementById(`step:${s}`);
      const node = { id: n.id(), ports: ports.get(n.id()) || [], layoutOptions: { "elk.portConstraints": "FIXED_ORDER" } };
      if (n.hasClass("frame")) {
        const head = textSize(n.data("label")).h + 12;
        node.layoutOptions = { ...node.layoutOptions, "elk.padding": `[top=${head},left=${FRAME_PAD},bottom=${FRAME_PAD},right=${FRAME_PAD}]` };
        node.children = cy.nodes(".part").filter((p) => p.data("box") === n.id()).map((p, i, all) => ({ id: p.id(), width: p.data("w"), height: p.data("h"),
                                                 layoutOptions: { "elk.priority": String(all.length - i) } }));  // box は大きい物から詰めるので順を残す
        // 開いた段は、名前の行が入る幅を下限にする
        node.layoutOptions["elk.nodeSize.constraints"] = "MINIMUM_SIZE";
        node.layoutOptions["elk.nodeSize.minimum"] = `(${textSize(n.data("label")).w + 2 * FRAME_PAD}, 0)`;
        // 縦のときは中の子も縦に積む（layered のままだと子が同じ列に横に並び、図が箱の幅を超える）。線は枠にだけつながるので、
        // 枠の中は別に並べてよい
        if (dir === "DOWN") Object.assign(node.layoutOptions, { "elk.hierarchyHandling": "SEPARATE_CHILDREN", "elk.algorithm": "box",
                                                                "elk.box.packingMode": "SIMPLE", "elk.aspectRatio": "0.2", "elk.spacing.nodeNode": "16" });
      } else {
        node.width = n.data("w");
        node.height = n.data("h");
      }
      return node;
    });
    // 縦のときは戻りの線と飛ばす線が縦に並ぶ。ラベルは線の上に縦書きで置くので、隣の線との間を1字の幅より広くする
    // 縦書きのラベルは、隣の段へ入る横の線の間（段の高さ＋段の間）に収まらないと線に重なる。段の間をその分だけ広げる
    const tall = Math.max(...cy.edges().map((e) => textSize(tate(e.data("short") ?? e.data("label"))).h)) + 2 * LABEL_PAD + 16;
    const low = Math.min(...cy.nodes('[id ^= "step:"]').map((n) => n.data("h")));
    const lane = dir === "DOWN"
      ? { "elk.spacing.edgeEdge": String(Math.ceil(Math.max(...cy.edges().map((e) => textSize(tate(e.data("short") ?? e.data("label"))).w))) + 2 * LABEL_PAD + 12),
          "elk.layered.spacing.nodeNodeBetweenLayers": String(Math.max(32, Math.ceil(tall - low))) }
      : { "elk.layered.spacing.nodeNodeBetweenLayers": "24" };
    return { id: "root", layoutOptions: { ...LAYERED, ...lane, "elk.direction": dir, "elk.hierarchyHandling": "INCLUDE_CHILDREN" }, children, edges };
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

  // 線どうしが交わる所に橋を描く：横の線が縦の線を小さな半円でまたぐ（どちらの線が上を通るかを見分けられるように）。
  // 下地の色で横の線の交わる所を消し、縦の線をつなぎ直してから、横の線の色で半円を描く
  _drawBridges(ov) {
    let svg = ov.querySelector("svg.hz-bridges");
    if (!svg) {
      svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "hz-bridges");
      ov.appendChild(svg);
    }
    const z = this.cy.zoom(), pan = this.cy.pan();
    const R = 6 * z;
    // 下地の色は、図の後ろで最初に色を持つ要素から読む（色の値は書かない）
    let gap = "";
    for (let el = this.container; el && !gap; el = el.parentElement) {
      const c = getComputedStyle(el).backgroundColor;
      if (c && c !== "transparent" && !/rgba\(.*,\s*0\)$/.test(c)) gap = c;
    }
    const parts = [];
    for (const c of this._crossings || []) {
      const h = this.cy.getElementById(c.h), v = this.cy.getElementById(c.v);
      if (!h.length || !v.length) continue;
      const x = c.x * z + pan.x, y = c.y * z + pan.y;
      const hw = parseFloat(h.style("width")) * z, vw = parseFloat(v.style("width")) * z;
      parts.push(`<rect fill="${gap}" x="${x - R - 1}" y="${y - hw}" width="${2 * R + 2}" height="${2 * hw}"/>`,
                 `<line x1="${x}" y1="${y - hw - 1}" x2="${x}" y2="${y + hw + 1}" stroke="${v.style("line-color")}" stroke-width="${vw}"/>`,
                 `<path d="M ${x - R} ${y} A ${R} ${R} 0 0 1 ${x + R} ${y}" fill="none" stroke="${h.style("line-color")}" stroke-width="${hw}"/>`);
    }
    const html = parts.join("");
    if (svg.dataset.html !== html) { svg.dataset.html = html; svg.innerHTML = html; }
  }

  _queueOverlay() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => { this._raf = null; this._drawOverlay(); });
  }

  _drawOverlay() {
    const ov = this.overlay;
    const keep = new Set();
    this._drawBridges(ov);
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
    // 工程の図：作業のノードの下の帯に、候補ごとの棒を横に並べる（ノードの中に収める）
    if (this.view === "stage") {
      for (const g of groupProgress(this.progress)) {
        const n = this._visible(g.node);
        if (!n.length) continue;
        const bb = n.renderedBoundingBox({ includeLabels: false, includeOverlays: false, includeUnderlays: false });
        const z = this.cy.zoom();
        let box = ov.querySelector(`[data-pnode="${CSS.escape(g.node)}"]`);
        if (!box) {
          box = document.createElement("div");
          box.dataset.pnode = g.node;
          box.className = "hz-progress stage";
          ov.appendChild(box);
        }
        keep.add(box);
        const inset = 8 * z;
        box.style.transform = `translate(${bb.x1 + inset}px, ${bb.y2 - (BAND + 2) * z}px)`;
        box.style.width = `${Math.max(0, bb.w - 2 * inset)}px`;
        box.style.height = `${(BAND - 4) * z}px`;
        renderBars(box, g.rows);
      }
    } else {
      // 作業の図：生成の段の中の帯（候補ごとの棒）。数と途中の絵は図の下の箱に出す
      const n = this.cy.getElementById("step:generate");
      if (this.progress.length && n.length) {
        const bb = n.renderedBoundingBox({ includeLabels: false, includeOverlays: false, includeUnderlays: false });
        const z = this.cy.zoom();
        let box = ov.querySelector('[data-pnode="step:generate"]');
        if (!box) {
          box = document.createElement("div");
          box.dataset.pnode = "step:generate";
          box.className = "hz-progress in-step";
          ov.appendChild(box);
        }
        keep.add(box);
        const inset = 8 * z;
        box.style.transform = `translate(${bb.x1 + inset}px, ${bb.y2 - 6 * z}px)`;
        box.style.width = `${Math.max(0, bb.w - 2 * inset)}px`;
        box.style.height = `${3 * z}px`;
        renderBars(box, this.progress);
      }
    }
    for (const el of ov.querySelectorAll(".hz-progress")) if (!keep.has(el)) el.remove();
    if (this.handlers.detailBox) renderProgressDetail(this.handlers.detailBox, this.view === "unit" ? this.progress : []);
  }

  destroy() { clearInterval(this._pulse); this.cy.destroy(); }
}

// 工程の図：工程の作業の枠を、その工程の段の真下に寄せる。重なるときは右へずらし、段の列の幅に収める。
// ELK の layered は下の列を左に詰めるので、作業の枠が段から離れて見えるため
function centerGroups(res) {
  const row = res.children.find((c) => c.id === "wrap:stages");
  const groups = res.children.filter((c) => c !== row).sort((a, b) => a.x - b.x);
  if (!row || !groups.length) return;
  const GAP = 32;
  const want = groups.map((g) => {
    const st = row.children.find((c) => c.id === `stage:${g.id.slice(6)}`);
    return st ? row.x + st.x + st.width / 2 - g.width / 2 : g.x;
  });
  let right = -Infinity;
  const left = want.map((x, i) => { const l = Math.max(x, right + GAP); right = l + groups[i].width; return l; });
  const lo = Math.min(row.x, groups[0].x), hi = Math.max(row.x + row.width, res.width);
  let shift = Math.min(0, hi - right);
  shift = Math.max(shift, lo - left[0]);
  groups.forEach((g, i) => { g.x = left[i] + shift; });
}

// 縦書きのラベル（1字ずつ改行）
function tate(text) {
  return [...(text || "")].join("\n");
}

// 線どうしの交わり（横の区間と縦の区間が、どちらの端でもない所で交わる）。橋を描く所
function findCrossings(cy) {
  const segs = [];
  for (const e of cy.edges()) {
    const pts = e.scratch("_pts") || [];
    for (let i = 1; i < pts.length; i++) {
      const p = pts[i - 1], q = pts[i];
      if (Math.abs(p.y - q.y) < 0.5) segs.push({ id: e.id(), h: true, a: Math.min(p.x, q.x), b: Math.max(p.x, q.x), at: p.y });
      else if (Math.abs(p.x - q.x) < 0.5) segs.push({ id: e.id(), h: false, a: Math.min(p.y, q.y), b: Math.max(p.y, q.y), at: p.x });
    }
  }
  const out = [];
  const END = 4;
  for (const h of segs.filter((s) => s.h)) {
    for (const v of segs.filter((s) => !s.h && s.id !== h.id)) {
      if (v.at > h.a + END && v.at < h.b - END && h.at > v.a + END && h.at < v.b - END) out.push({ h: h.id, v: v.id, x: v.at, y: h.at });
    }
  }
  return out;
}

// 辺のラベルを、その辺の線の上に置く（ELK はラベルを列の中のノードとして置くので、上・下のポートから縦に入る辺と重なる。
// そこでラベルは ELK に渡さず、並べ終えた線の上で空いている所を探す）。
// 長い横の線から順に、真ん中から左右へずらして、ほかのノード・ほかの辺の線・置いたラベルにかからない所に置く。
// 置ける所が無ければ線の真ん中に置く（重なりは図の試験 harness_layout_ui.mjs が落とす）
function placeEdgeLabels(cy) {
  const GAP = 3;
  const bodies = cy.nodes().map((n) => n.boundingBox({ includeLabels: false, includeOverlays: false, includeUnderlays: false }));
  // ノードのラベル（枠の名前）もよける
  const nodeLabels = cy.nodes(".frame").map((n) => n.boundingBox({ includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false }));
  const lines = cy.edges().map((e) => ({ id: e.id(), pts: e.scratch("_pts") || [] }));
  const placed = [];
  const hitBox = (a, b) => a.x1 < b.x2 + GAP && b.x1 < a.x2 + GAP && a.y1 < b.y2 + GAP && b.y1 < a.y2 + GAP;
  const segHit = (p, q, r) => {
    const x1 = Math.min(p.x, q.x), x2 = Math.max(p.x, q.x), y1 = Math.min(p.y, q.y), y2 = Math.max(p.y, q.y);
    return x1 < r.x2 + GAP && r.x1 - GAP < x2 && y1 < r.y2 + GAP && r.y1 - GAP < y2;
  };
  const free = (r, own) => !bodies.some((b) => hitBox(r, b)) && !nodeLabels.some((b) => hitBox(r, b)) && !placed.some((b) => hitBox(r, b)) &&
    !lines.some((l) => l.id !== own && l.pts.slice(1).some((q, i) => segHit(l.pts[i], q, r)));
  // ラベルの長い辺から置く（短い物ほど入る所が多い）
  const withLabel = cy.edges().filter((e) => e.data("label")).sort((a, b) => textSize(b.data("label")).w - textSize(a.data("label")).w);
  for (const e of cy.edges()) e.style({ "text-margin-x": 0, "text-margin-y": 0 });
  for (const e of withLabel) {
    // 縦書きのとき（段を縦に並べた図）は、横の区間に置くなら横書きに戻す。線の向きとラベルの向きをそろえる
    const short = e.data("short") ?? e.data("label");
    const vertical = !!e.data("tate");
    const box = (horizontal) => {
      const text = vertical && !horizontal ? tate(short) : (vertical ? short : e.data("label"));
      const t = textSize(text);
      return { text, w: t.w + 2 * LABEL_PAD, h: t.h + 2 * LABEL_PAD };
    };
    const pts = e.scratch("_pts");
    const segs = pts.slice(1).map((q, i) => [pts[i], q]).sort((a, b) => Math.hypot(b[1].x - b[0].x, b[1].y - b[0].y) - Math.hypot(a[1].x - a[0].x, a[1].y - a[0].y));
    let at = null;
    for (const [p, q] of segs) {
      const len = Math.hypot(q.x - p.x, q.y - p.y);
      const horizontal = Math.abs(q.y - p.y) < 0.5;
      const { text, w, h } = box(horizontal);
      const room = (horizontal ? w : h) + 8;
      if (len < room) continue;
      const mid = len / 2;
      for (let d = 0; d <= len / 2 - room / 2 && !at; d += 4) {
        for (const off of d ? [d, -d] : [0]) {
          const f = (mid + off) / len;
          const c = { x: p.x + (q.x - p.x) * f, y: p.y + (q.y - p.y) * f };
          const r = { x1: c.x - w / 2, y1: c.y - h / 2, x2: c.x + w / 2, y2: c.y + h / 2 };
          if (free(r, e.id())) { at = { c, r, text }; break; }
        }
      }
      if (at) break;
    }
    if (!at) {
      const [p, q] = segs[0];
      const { text, w, h } = box(Math.abs(q.y - p.y) < 0.5);
      const c = { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 };
      at = { c, r: { x1: c.x - w / 2, y1: c.y - h / 2, x2: c.x + w / 2, y2: c.y + h / 2 }, text };
    }
    if (at.text !== e.data("label")) e.data("label", at.text);
    placed.push(at.r);
    // Cytoscape は辺のラベルを辺の真ん中に描くので、そこからのずらしにする
    const mid = e.midpoint();
    e.style({ "text-margin-x": at.c.x - mid.x, "text-margin-y": at.c.y - mid.y });
  }
}

// ELK の折れ線（始点・折れ点・終点。図の座標）を Cytoscape の辺に当てる。
// 始点・終点はノードの真ん中からのずらし（source-endpoint・target-endpoint）、折れ点は始点→終点の線に対する割合と離れ（segments）
function setEdgeGeometry(el, pts) {
  const s = el.source().position(), t = el.target().position();
  const a = pts[0], b = pts.at(-1);
  const bends = pts.slice(1, -1);
  const style = { "source-endpoint": `${a.x - s.x}px ${a.y - s.y}px`, "target-endpoint": `${b.x - t.x}px ${b.y - t.y}px` };
  if (!bends.length) {
    el.removeClass("bent");
    el.style(style);
    el.scratch("_pts", pts);
    return;
  }
  const dx = b.x - a.x, dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const len = Math.sqrt(len2);
  const ws = bends.map((p) => ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2);
  const ds = bends.map((p) => (dx * (p.y - a.y) - dy * (p.x - a.x)) / len);
  el.addClass("bent");
  // Cytoscape は2つのノードの間の辺を向きをそろえて計ることがある（逆向きの辺は割合と離れが裏返る）。
  // 4通りを当てて、読み返した折れ点が ELK の折れ点に合うものを残す
  const tries = [[ws, ds], [ws, ds.map((d) => -d)], [ws.map((w) => 1 - w), ds], [ws.map((w) => 1 - w), ds.map((d) => -d)]];
  for (const [w, d] of tries) {
    el.style({ ...style, "segment-weights": w, "segment-distances": d });
    const got = el.segmentPoints() || [];
    if (got.length === bends.length && got.every((p, i) => Math.hypot(p.x - bends[i].x, p.y - bends[i].y) < 1)) { el.scratch("_pts", pts); return; }
  }
  throw new Error(`辺 ${el.id()} の折れ点を当てられない`);
}

function groupProgress(rows) {
  const by = new Map();
  for (const r of rows) {
    const node = `unit:${r.unit_id}`;
    if (!by.has(node)) by.set(node, { node, rows: [] });
    by.get(node).rows.push(r);
  }
  return [...by.values()];
}

const PSTATE_JA = { pending: "送った", running: "描いている", finished: "描き終えた", unavailable: "進み具合を受け取れない",
                    interrupted: "止めた", error: "止まった" };
const pctOf = (r) => (r.max ? Math.round((100 * (r.value || 0)) / r.max) : 0);

// ノードの中の帯：候補ごとの棒を横に並べる
function renderBars(box, rows) {
  const list = [...rows].sort((a, b) => a.k_index - b.k_index);
  const key = list.map((r) => `${r.candidate_id}:${r.state}:${r.value}`).join("|");
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.replaceChildren(...list.map((r) => {
    const line = document.createElement("div");
    line.className = `hz-bar s-${r.state}`;
    const fill = document.createElement("span");
    fill.style.width = `${pctOf(r)}%`;
    line.appendChild(fill);
    return line;
  }));
}

// 図の下の箱：候補ごとの段数（n/max）と途中の絵
function renderProgressDetail(box, rows) {
  const list = [...rows].sort((a, b) => a.k_index - b.k_index);
  box.hidden = !list.length;
  const key = list.map((r) => `${r.candidate_id}:${r.state}:${r.value}:${r.preview ? r.updated_at : ""}`).join("|");
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.replaceChildren();
  if (!list.length) return;
  const rowsEl = document.createElement("div");
  rowsEl.className = "hz-progress unit";
  for (const r of list) {
    const line = document.createElement("div");
    line.className = `hz-bar s-${r.state}`;
    const fill = document.createElement("span");
    fill.style.width = `${pctOf(r)}%`;
    const t = document.createElement("em");
    t.textContent = `#${r.k_index + 1} ${PSTATE_JA[r.state] || r.state}${r.max ? ` ${r.value || 0}/${r.max}` : ""}`;
    line.append(fill, t);
    rowsEl.appendChild(line);
  }
  const withPreview = list.filter((r) => r.preview);
  if (withPreview.length) {
    const strip = document.createElement("div");
    strip.className = "hz-previews";
    for (const r of withPreview) {
      const im = document.createElement("img");
      im.src = r.preview;
      im.alt = `候補 ${r.k_index + 1} の途中の絵`;
      strip.appendChild(im);
    }
    rowsEl.appendChild(strip);
  }
  box.appendChild(rowsEl);
}

function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2; }

// 辺の上の点（画面の座標）。辺は折れ線なので、始点・折れ点・終点を長さの割合でたどる
function pointOnEdge(cy, e, t) {
  if (e.removed()) return null;
  const z = cy.zoom(), pan = cy.pan();
  const pts = [e.sourceEndpoint(), ...(e.hasClass("bent") ? e.segmentPoints() || [] : []), e.targetEndpoint()]
    .map((p) => ({ x: p.x * z + pan.x, y: p.y * z + pan.y }));
  const seg = pts.slice(1).map((p, i) => Math.hypot(p.x - pts[i].x, p.y - pts[i].y));
  let left = t * seg.reduce((a, b) => a + b, 0);
  for (let i = 0; i < seg.length; i++) {
    if (left <= seg[i] || i === seg.length - 1) {
      const f = seg[i] ? Math.min(1, left / seg[i]) : 0;
      return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * f, y: pts[i].y + (pts[i + 1].y - pts[i].y) * f };
    }
    left -= seg[i];
  }
  return pts.at(-1);
}
