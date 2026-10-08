// 原稿の画面のはじめと、操作をまとめる所。
// 変更はどれも操作の窓口（POST /works/{id}/ops）へ送る。送る前に画面へ当て（model.applyLocal）、保存は後ろで順に送る。
// 取り消し・やり直しはページごと（saver.js）。キーは決めごと 22.2 に合わせ、この1か所で受ける。
import * as api from "../../js/api.js";
import { Model, newId } from "./model.js";
import { Saver } from "./saver.js";
import { PageView } from "./page_view.js";
import { balloonOutline, bbox, r2, roundPts } from "./geometry.js";
import { $, $$, h, icons, note, toast, fail } from "./ui.js";
import * as panes from "./panes.js";

export const S = {
  works: [], workId: null, m: null, episodeId: null, pageId: null, spread: false,
  tool: "select", frameMode: "move", sel: null, tab: "tools", held: [], preflight: null, imageEdit: null,
  knife: { direction: "horizontal", angle: 12, gap: null },
  balloon: { form: "ellipse", line_width_mm: 0.3, line_color: "#000000", fill_color: "#FFFFFF", font_size_pt: 9, tail_base_width_mm: 4, tail_bend_ratio: 0 },
  tone: { kind: "dots", density: 0.3, lines_per_inch: 60 },
  show: { guide: true, safe: true, grid: false, hand: true, held: true, boxes: true,
          cat: { art: true, frame: true, tone: true, balloon: true, type: true, sfx: true } },
  lock: { frame: false, balloon: false, sfx: false, tone: false },
  saver: null, view: null, reloading: null,
};

// ---------------------------------------------------------------- 選ぶ
async function loadWorks() {
  S.works = await api.get("/works");
  const sel = $("#pick-work");
  sel.replaceChildren(...S.works.map((w) => h("option", { value: w.id, text: w.title })));
  if (!S.works.length) { showEmpty("見てよい作品がありません"); return; }
  const want = asked.get("work") || readPref("work");
  await selectWork(S.works.some((w) => w.id === want) ? want : S.works[0].id);
}

async function selectWork(id) {
  if (S.saver && (S.saver.pending() || S.saver.failed)) { toast("保存が済んでから作品を替えてください", "need"); $("#pick-work").value = S.workId; return; }
  S.workId = id;
  $("#pick-work").value = id;
  writePref("work", id);
  S.saver = new Saver({ workId: id, onState: renderStatus, onSaved, onError: fail });
  S.preflight = null;
  await reload();
  const eps = S.m.episodes();
  $("#pick-episode").replaceChildren(...eps.map((e) => h("option", { value: e.id, text: `${e.number} 話${e.title ? ` ${e.title}` : ""}` })));
  if (!eps.length) { showEmpty("この作品には話がありません"); return; }
  const wantPage = asked.get("page");
  const pageRow = wantPage ? S.m.find("pages", wantPage) : null;
  const wantEp = pageRow ? pageRow.episode_id : asked.get("episode") || readPref("episode");
  selectEpisode(eps.some((e) => e.id === wantEp) ? wantEp : eps[0].id, wantPage);
  asked.delete("page"); asked.delete("episode"); asked.delete("work");
}

function selectEpisode(id, wantPage = null) {
  S.episodeId = id;
  $("#pick-episode").value = id;
  writePref("episode", id);
  const pages = S.m.pages(id);
  if (!pages.length) { S.pageId = null; showEmpty("この話にはページがありません。下のページの一覧から足せます"); draw(); return; }
  const want = wantPage || readPref("page");
  selectPage(pages.some((p) => p.id === want) ? want : pages[0].id);
}

export function selectPage(id) {
  if (!id) return;
  S.view.text.finishEdit();
  S.pageId = id;
  writePref("page", id);
  S.sel = null;
  S.imageEdit = null;
  showEmpty(null);
  draw({ refit: !S.view.slots.some((s) => s.page.id === id) });
}

function showEmpty(text) {
  const e = $("#stage-empty");
  e.hidden = !text;
  e.textContent = text || "";
}

// ---------------------------------------------------------------- 読む・描く
// サーバーから作品を読み直す。動かしている途中なら、離してから読む
export async function reload() {
  if (S.view && S.view.c._currentTransform) {
    await new Promise((r) => S.view.c.once("mouse:up", r));
  }
  const [data, held] = await Promise.all([api.get(`/works/${S.workId}`), api.get(`/works/${S.workId}/held-changes?status=open`)]);
  S.m = new Model(data);
  S.held = held;
  if (S.pageId && !S.m.find("pages", S.pageId)) S.pageId = null;
  if (S.pageId && S.m.find("pages", S.pageId).removed) S.pageId = null;
  if (S.sel && !selectedRow()) S.sel = null;
  if (S.episodeId) draw();
}

// 今出しているページの並び（1ページか見開き）。座標は mm で、左のページの仕上がりの左上が 0
function slots() {
  const m = S.m, spec = m.spec(), page = m.find("pages", S.pageId);
  if (!page) return [];
  const fx = (spec.trim_width_mm - spec.frame_width_mm) / 2, fy = (spec.trim_height_mm - spec.frame_height_mm) / 2;
  const sides = m.sides(S.episodeId), pages = m.pages(S.episodeId);
  const sideOf = (p) => (sides ? sides[pages.indexOf(p)] : null);
  const mk = (p, x, spreadLeft) => ({ page: p, side: sideOf(p), x, ox: x + fx, oy: fy, trimW: spec.trim_width_mm, trimH: spec.trim_height_mm, bleed: spec.bleed_mm, spreadLeft });
  if (!S.spread || !sides) return [mk(page, 0, false)];
  const u = m.units(S.episodeId).find((x) => (x.left && x.left.id === page.id) || (x.right && x.right.id === page.id));
  const sp = m.caps.print && u.left && u.right ? m.spreadOf(u.left.id) : null;
  const joined = !!(sp && (sp.first_page_id === u.right.id || sp.second_page_id === u.right.id));
  // 見開きの組（spreads の行）があるページは、ノドで付けて並べる。無ければ塗り足しの外に少し間を空ける
  const gap = joined ? 0 : spec.bleed_mm * 2 + 6;
  const out = [];
  if (u.left) out.push(mk(u.left, 0, joined));
  if (u.right) out.push(mk(u.right, spec.trim_width_mm + gap, false));
  return out;
}

function viewOpts() {
  const heldBy = new Map();
  for (const x of S.held) { if (!heldBy.has(x.target_id)) heldBy.set(x.target_id, []); heldBy.get(x.target_id).push(x); }
  const prefs = S.m.work.preferences || {};
  return { show: S.show, lock: S.lock, heldBy, safeArea: prefs.print ? prefs.print.safe_area : null };
}

// 画面の全部を今の正本から描き直す
export function draw({ refit = false } = {}) {
  if (!S.m) return;
  const sl = slots();
  if (refit) S.view.fitted = false;
  S.view.imageEdit = S.imageEdit;
  S.view.setScene(sl, S.m, viewOpts());
  if (S.sel && !S.view.select(S.sel.kind, S.sel.id, false)) { /* 道具によっては選べない：右の欄だけ出す */ }
  syncPickers();
  panes.render();
  renderStatus();
  syncUndo();
}

function syncPickers() {
  const pages = S.m.pages(S.episodeId);
  const sel = $("#pick-page");
  sel.replaceChildren(...pages.map((p) => h("option", { value: p.id, text: `${p.number} ページ` })));
  if (S.pageId) sel.value = S.pageId;
  const sides = S.m.sides(S.episodeId);
  const b = $("#view-spread");
  b.setAttribute("aria-pressed", String(S.spread && !!sides));
  b.setAttribute("aria-disabled", String(!sides));
  b.title = sides ? "見開きで見る・1ページで見る" : "1ページ目を左右どちらに置くかが決まっていないので、見開きで並べられません（ページの設定で決めます）";
  $("#reading").textContent = S.m.work.reading_direction === "rtl" ? "右から読む" : S.m.work.reading_direction === "ltr" ? "左から読む" : "読む向きが未設定";
  $("#to-workbench").href = workbenchUrl(S.sel && S.sel.kind === "panel" ? S.sel.id : null);
}

export function workbenchUrl(panelId) {
  const q = new URLSearchParams({ work: S.workId || "", page: S.pageId || "" });
  if (panelId) q.set("panel", panelId);
  return `../index.html?${q}`;
}

// ---------------------------------------------------------------- 変更を送る
// label：状態の所と取り消しに出す名前。ops：操作。pages：取り消しの記録を載せるページ。reload：済んだら読み直す
export function change(label, ops, { pages = [S.pageId], reload: re = false, send = null } = {}) {
  if (S.saver.failed) { toast("保存できていない変更があります。先に「もう一度送る」か「この変更を捨てる」を選んでください", "need"); draw(); return null; }
  let need = re;
  for (const op of ops) if (!S.m.applyLocal(op)) need = true;
  const ids = S.saver.submit({ label, pages, ops, reload: need, send });
  ids.catch(() => {});
  draw();
  return ids;
}

async function onSaved(job, empty) {
  if (!empty) return;
  if (job.reload) await reload();
  else {
    S.held = await api.get(`/works/${S.workId}/held-changes?status=open`);
    panes.renderHeldCount();
  }
}

function renderStatus() {
  const host = $("#stage-msg");
  const sv = S.saver;
  if (!sv) return;
  if (sv.failed) {
    const n = note(`保存できませんでした（${sv.failed.job.label}）：${api.errorText(sv.failed.error)}。変えた所は画面にだけあります`, "bad");
    n.append(h("button", { class: "btn sm", onclick: () => sv.retry() }, "もう一度送る"),
      h("button", { class: "btn sm", onclick: () => { sv.discard(); reload().catch((e) => fail(e, "読み直し")); } }, "この変更を捨てる"));
    host.replaceChildren(n);
  } else {
    const n = sv.pending();
    host.replaceChildren(n ? note(`保存しています（${n} 件）`, "", "loader") : "");
  }
  syncUndo();
}

function syncUndo() {
  if (!S.saver) return;
  for (const [id, dir] of [["#undo", "undo"], ["#redo", "redo"]]) {
    const ok = S.saver.can(S.pageId, dir);
    const b = $(id);
    b.setAttribute("aria-disabled", String(!ok));
    const e = S.saver.peek(S.pageId, dir);
    b.title = `${dir === "undo" ? "取り消す (Ctrl+Z)" : "やり直す (Ctrl+Shift+Z・Ctrl+Y)"}${e ? `：${e.label}` : ""}（このページの操作）`;
  }
}

export async function step(dir) {
  if (!S.saver.can(S.pageId, dir)) return;
  S.view.text.finishEdit();
  try {
    const e = await S.saver.step(S.pageId, dir);
    if (e) toast(`${dir === "undo" ? "取り消しました" : "やり直しました"}：${e.label}`);
  } catch (e) { fail(e, dir === "undo" ? "取り消し" : "やり直し"); }
  await reload().catch((e) => fail(e, "読み直し"));
}

// ---------------------------------------------------------------- ページの上の手の動き → 操作
const fixedRefuse = () => toast("動かさない印が付いています。右の欄で印を外すと直せます", "need");

function nextPanelOrder(pageId) {
  const page = S.m.find("pages", pageId);
  const pages = S.m.pages(page.episode_id).filter((p) => p.number <= page.number);
  let max = 0;
  for (const p of pages) for (const x of S.m.panels(p.id)) max = Math.max(max, x.order);
  return max + 1;
}

const hooks = {
  onError: fail,
  onRefuse: (msg) => toast(msg, "need"),
  onView: () => panes.renderZoom(),
  onPageFocus: (pageId) => { if (pageId !== S.pageId) { S.pageId = pageId; writePref("page", pageId); syncPickers(); syncUndo(); panes.renderDock(); } },
  onSelect: (sel) => {
    S.sel = sel;
    if (sel) { S.pageId = sel.pageId; S.tab = "tools"; }
    syncPickers();
    panes.render();
    syncUndo();
  },
  onEditing: () => {},
  onEditDone: (id, text) => {
    const t = S.m.find("text_items", id);
    if (!t || t.text === text) return;
    const op = { type: "update_text_item", id, text };
    const len = Array.from(text).length;
    const keep = (l) => (l || []).filter((r) => r.end <= len);
    const dropped = (t.spans || []).length + (t.ruby || []).length - keep(t.spans).length - keep(t.ruby).length;
    if (dropped) {
      if (S.m.caps.print) op.spans = keep(t.spans);
      op.ruby = keep(t.ruby);
      toast(`文字が短くなり、はみ出した一部の書式・ルビを ${dropped} 件外しました（取り消せます）`, "need");
    }
    change("文字", [op], { pages: [t.page_id] });
  },
  onKnife: (panel, through, pageId) => {
    if (panel.fixed) return fixedRefuse();
    const k = S.knife, spec = S.m.spec();
    const gap = k.gap ?? (k.direction === "vertical" ? spec.gutter_x_mm : spec.gutter_y_mm);
    const op = { type: "split_panel", panel_id: panel.id, through_mm: [r2(through[0]), r2(through[1])], direction: k.direction,
                 gap_mm: gap, new_panel_id: newId() };
    if (k.direction === "slanted") op.angle_deg = k.angle;
    change("ナイフで分ける", [op], { pages: [pageId], reload: true });
  },
  onJoinPick: (a, b) => {
    if (!b) { toast("合わせるもう1つのコマを押してください"); return; }
    const pa = S.m.find("panels", a), pb = S.m.find("panels", b);
    if (pa.fixed || pb.fixed) return fixedRefuse();
    if (pa.page_id !== pb.page_id) { toast("合わせられるのは同じページのコマだけです", "need"); return; }
    change("コマを合わせる", [{ type: "merge_panels", panel_ids: [a, b] }], { pages: [pa.page_id], reload: true });
  },
  onAdd: (tool, hit, pt) => addAt(tool, hit),
  onImageEdit: (panelId) => {
    const p = S.m.find("panels", panelId);
    if (!p.image_id || !p.image_placement) { toast("このコマには置いた絵がありません。右の欄の「絵を置く」から置けます", "need"); return; }
    if (p.fixed) return fixedRefuse();
    S.imageEdit = panelId;
    S.sel = { kind: "panel", id: panelId, pageId: p.page_id };
    draw();
    S.view.select("image", panelId, false);
    toast("コマの絵を動かす・大きさを変えられます。Esc で終わります");
  },
  onPanelChange: (id, poly, d) => {
    const p = S.m.find("panels", id);
    const op = { type: "update_panel", id, frame: { ...p.frame, polygon_mm: roundPts(poly) } };
    if (d && p.image_placement) {
      const b = p.image_placement.dest_box_mm;
      op.image_placement = { ...p.image_placement, dest_box_mm: [r2(b[0] + d[0]), r2(b[1] + d[1]), r2(b[2] + d[0]), r2(b[3] + d[1])] };
    }
    change(d ? "コマを動かす" : "コマ枠を直す", [op], { pages: [p.page_id] });
  },
  onTextChange: (id, { box, outline, target }) => {
    const t = S.m.find("text_items", id);
    const op = { type: "update_text_item", id, box_mm: box.map(r2) };
    if (outline) op.balloon_shape = { ...t.balloon_shape, outline_mm: roundPts(outline) };
    if (target) op.tail_target_mm = [r2(target[0]), r2(target[1])];
    change(t.item_kind === "balloon" ? "フキダシを動かす" : "文字を動かす", [op], { pages: [t.page_id] });
  },
  onToneChange: (id, box) => {
    const t = S.m.find("page_items", id);
    const op = { type: "update_page_item", id, box_mm: box.map(r2) };
    const tg = t.spec.target;
    const mp = mapBox(t.box_mm, box);
    if (t.item_kind === "tone" && (tg.kind === "polygon" || t.spec.center_mm)) {
      const spec = { ...t.spec };
      if (tg.kind === "polygon") spec.target = { ...tg, polygon_mm: roundPts(tg.polygon_mm.map(mp)) };
      if (spec.center_mm) spec.center_mm = mp(spec.center_mm).map(r2);
      op.spec = spec;
    }
    change("トーンを動かす", [op], { pages: [t.page_id] });
  },
  onImageChange: (panelId, dest) => {
    const p = S.m.find("panels", panelId);
    change("コマの絵を動かす", [{ type: "update_panel", id: panelId, image_placement: { ...p.image_placement, dest_box_mm: dest.map(r2) } }], { pages: [p.page_id] });
  },
};

// 箱 a を箱 b へ写す関数
function mapBox(a, b) {
  const sx = (b[2] - b[0]) / (a[2] - a[0] || 1), sy = (b[3] - b[1]) / (a[3] - a[1] || 1);
  return ([x, y]) => [b[0] + (x - a[0]) * sx, b[1] + (y - a[1]) * sy];
}

// 押した所に、道具に応じた物を足す
function addAt(tool, hit) {
  const page = hit.slot.page, q = hit.q, m = S.m;
  if (tool === "frame") {
    const box = [q[0] - 25, q[1] - 18, q[0] + 25, q[1] + 18].map(r2);
    const op = { type: "add_panel", id: newId(), page_id: page.id, order: nextPanelOrder(page.id),
                 frame: { polygon_mm: [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]], bleeds: [] } };
    change("コマを足す", [op], { pages: [page.id], reload: true });
    return;
  }
  const panel = hit.panel;
  if (tool === "balloon" || tool === "text") {
    const vertical = (m.work.text_direction || "vertical") === "vertical";
    const [w, hh] = vertical ? [12, 26] : [26, 10];
    const box = [q[0] - w / 2, q[1] - hh / 2, q[0] + w / 2, q[1] + hh / 2].map(r2);
    const order = Math.max(0, ...m.rows("text_items").filter((t) => t.panel_id === panel.id && !t.removed).map((t) => t.order)) + 1;
    const b = S.balloon;
    const op = { type: "add_text_item", id: newId(), panel_id: panel.id, item_kind: tool === "balloon" ? "balloon" : "caption", order, text: "",
                 writing_direction: vertical ? "vertical" : "horizontal", font_size_pt: b.font_size_pt, box_mm: box };
    if (tool === "balloon") {
      const shape = { kind: "custom", outline_mm: balloonOutline(b.form, box, 3), line_width_mm: b.line_width_mm, line_color: b.line_color, fill_color: b.fill_color };
      if (m.caps.print) { shape.tail_base_width_mm = b.tail_base_width_mm; shape.tail_bend_ratio = b.tail_bend_ratio; op.tail_target_mm = [r2(q[0] - 6), r2(box[3] + 9)]; }
      op.balloon_shape = shape;
    } else op.balloon_shape = { kind: "none" };
    change(tool === "balloon" ? "フキダシを足す" : "文字を足す", [op], { pages: [page.id] });
    S.sel = { kind: "text", id: op.id, pageId: page.id };
    draw();
    S.view.editText(op.id);
    return;
  }
  if (tool === "tone") {
    const box = bbox(panel.frame.polygon_mm).map(r2);
    const t = S.tone;
    const spec = { kind: t.kind, target: { kind: "panel", panel_id: panel.id }, color: "#000000", density: t.density, angle_deg: 45 };
    if (["dots", "lines", "gradient"].includes(t.kind)) spec.lines_per_inch = t.lines_per_inch;
    if (t.kind === "gradient") Object.assign(spec, { density_end: 0, screen_angle_deg: 45, dot_shape: "round", angle_deg: 90 });
    if (t.kind === "sand" || t.kind === "snow") Object.assign(spec, { grain_mm: 0.3, seed: Math.floor(Math.random() * 1e6) });
    if (t.kind === "focus_lines") Object.assign(spec, { line_count: 120, center_mm: [r2(q[0]), r2(q[1])], inner_ratio: 0.45, seed: Math.floor(Math.random() * 1e6) });
    if (t.kind === "speed_lines") Object.assign(spec, { line_count: 60, seed: Math.floor(Math.random() * 1e6), angle_deg: 0 });
    const stack = Math.max(0, ...m.items(page.id).map((x) => x.stack_order)) + 1;
    const op = { type: "add_page_item", id: newId(), page_id: page.id, panel_id: panel.id, item_kind: "tone", spec, box_mm: box, stack_order: stack };
    change("トーンを貼る", [op], { pages: [page.id] });
    S.sel = { kind: "tone", id: op.id, pageId: page.id };
    draw();
  }
}

export function selectedRow() {
  if (!S.sel) return null;
  const table = { panel: "panels", text: "text_items", tone: "page_items", image: "panels" }[S.sel.kind];
  const r = table ? S.m.find(table, S.sel.id) : null;
  return r && !r.removed ? r : null;
}

// ---------------------------------------------------------------- 道具
export const TOOLS = [
  ["select", "選ぶ", "mouse-pointer-2", "V"], ["frame", "コマ枠", "square-dashed", "F"], ["knife", "ナイフ", "slice", "C"],
  ["balloon", "フキダシ", "message-circle", "S"], ["text", "文字", "type", "T"], ["tone", "トーン", "grid-3x3", "N"], ["hand", "手のひら", "hand", "H"],
];

export function setTool(tool) {
  S.view.text.finishEdit();
  S.tool = tool;
  S.imageEdit = null;
  S.view.imageEdit = null;
  S.view.setTool(tool, { frameMode: S.frameMode, knife: S.knife });
  for (const b of $$("#tools .tool[data-tool]")) b.setAttribute("aria-pressed", String(b.dataset.tool === tool));
  S.tab = "tools";
  panes.render();
}

export function setFrameMode(mode) {
  S.frameMode = mode;
  S.view.setTool("frame", { frameMode: mode, knife: S.knife });
  panes.render();
}

// ---------------------------------------------------------------- 見開き・ページ送り
function toggleSpread() {
  if (!S.m.sides(S.episodeId)) { toast("1ページ目を左右どちらに置くかが決まっていません。ページの設定で決めると見開きで並べられます", "need"); return; }
  S.spread = !S.spread;
  writePref("spread", S.spread ? "1" : "");
  draw({ refit: true });
}

// 前・次の見開き（1ページで見ているときはページ）
function flip(d) {
  const pages = S.m.pages(S.episodeId);
  if (!pages.length) return;
  if (S.spread && S.m.sides(S.episodeId)) {
    const units = S.m.units(S.episodeId);
    const i = units.findIndex((u) => (u.left && u.left.id === S.pageId) || (u.right && u.right.id === S.pageId));
    const u = units[i + d];
    if (!u) return;
    // 読む向きで前のページを選ぶ
    const rtl = S.m.work.reading_direction === "rtl";
    const first = rtl ? u.right || u.left : u.left || u.right;
    selectPage(first.id);
  } else {
    const i = pages.findIndex((p) => p.id === S.pageId);
    const p = pages[i + d];
    if (p) selectPage(p.id);
  }
}

// ---------------------------------------------------------------- 消す・動かさない印
export function removeSelected() {
  const r = selectedRow();
  if (!r) return;
  if (r.fixed) return fixedRefuse();
  const kind = { panel: "panel", text: "text_item", tone: "page_item" }[S.sel.kind];
  if (!kind) return;
  const pageId = r.page_id;
  S.view.c.discardActiveObject();
  S.sel = null;
  change("消す", [{ type: "set_removed", target_kind: kind, id: r.id, removed: true }], { pages: [pageId], reload: kind === "panel" });
}

// ---------------------------------------------------------------- キー（決めごと 22.2）
const KEYS = {
  v: () => setTool("select"), f: () => setTool("frame"), c: () => setTool("knife"), s: () => setTool("balloon"),
  t: () => setTool("text"), n: () => setTool("tone"), h: () => setTool("hand"),
  l: () => openWorkbench(),
  r: () => notHere("赤入れ"), b: () => notHere("ペン"), e: () => notHere("消しゴム"), u: () => notHere("図形"), o: () => notHere("読む順"),
  d: () => panes.cycleTab(), w: () => panes.openTab("layers"), q: () => notHere("順番待ち"),
  j: () => panes.heldStep(1), k: () => panes.heldStep(-1), a: () => panes.heldDecide("accept"), x: () => panes.heldDecide("reject"),
  "+": () => S.view.zoomBy(1.25), "=": () => S.view.zoomBy(1.25), "-": () => S.view.zoomBy(0.8), "0": () => S.view.fit(),
  "?": () => $("#keys").showModal(),
  pageup: () => flip(-1), pagedown: () => flip(1),
  delete: () => removeSelected(), backspace: () => removeSelected(),
};

function notHere(name) { toast(`「${name}」はこの画面にまだありません（キーは決めごと 22.2 のまま空けています）`, "need"); }

export function openWorkbench(panelId = S.sel && S.sel.kind === "panel" ? S.sel.id : null) {
  if (!panelId) { toast("絵を頼むコマを選んでください（選ぶ道具でコマを押す）", "need"); return; }
  if (S.saver.pending()) { toast("保存が済んでから開きます"); S.saver.idle().then(() => openWorkbench(panelId), () => {}); return; }
  location.href = workbenchUrl(panelId);
}

function typing(e) {
  const t = e.target;
  return t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
}

function onKey(e) {
  if (e.key === "Escape") {
    if ($("#keys").open) return;
    if (S.imageEdit) { S.imageEdit = null; draw(); return; }
    if (S.tool === "knife" || S.tool === "frame") S.view.setTool(S.tool, { frameMode: S.frameMode, knife: S.knife });
    S.view.c.discardActiveObject(); S.view.c.requestRenderAll();
    return;
  }
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.altKey) {
    const k = e.key.toLowerCase();
    if (typing(e) && (k === "z" || k === "y")) return; // 打っている所の取り消しはブラウザに任せる
    if (k === "z") { e.preventDefault(); step(e.shiftKey ? "redo" : "undo"); return; }
    if (k === "y") { e.preventDefault(); step("redo"); return; }
    return;
  }
  if (typing(e) || e.altKey) return;
  if (e.key === " ") { if (!S.view.space) { S.view.space = true; $("#stage").classList.add("space"); } e.preventDefault(); return; }
  const fn = KEYS[e.key.toLowerCase()];
  if (fn) { e.preventDefault(); fn(); }
}

// ---------------------------------------------------------------- 覚えておく
const asked = new URLSearchParams(location.search);
function readPref(k) { try { return localStorage.getItem(`v3.ms.${k}`); } catch { return null; } }
function writePref(k, v) { try { localStorage.setItem(`v3.ms.${k}`, v); } catch { /* 覚えられない環境では毎回初めから選ぶ */ } }

// ---------------------------------------------------------------- はじめ
function boot() {
  const user = $("#user");
  user.value = api.currentUser();
  user.addEventListener("change", () => { api.setUser(user.value.trim()); location.reload(); });
  S.spread = readPref("spread") === "1";
  S.view = new PageView($("#stage"), hooks);
  window.__ms = S; // 試験と測定のため（tests/manuscript_ui.mjs が読む）
  $("#pick-work").addEventListener("change", (e) => selectWork(e.target.value).catch((x) => fail(x, "作品を読むこと")));
  $("#pick-episode").addEventListener("change", (e) => selectEpisode(e.target.value));
  $("#pick-page").addEventListener("change", (e) => selectPage(e.target.value));
  $("#view-spread").addEventListener("click", toggleSpread);
  $("#prev-page").addEventListener("click", () => flip(-1));
  $("#next-page").addEventListener("click", () => flip(1));
  $("#undo").addEventListener("click", () => step("undo"));
  $("#redo").addEventListener("click", () => step("redo"));
  $("#zoom-in").addEventListener("click", () => S.view.zoomBy(1.25));
  $("#zoom-out").addEventListener("click", () => S.view.zoomBy(0.8));
  $("#zoom-fit").addEventListener("click", () => S.view.fit());
  $("#keys-open").addEventListener("click", () => $("#keys").showModal());
  $("#keys-close").addEventListener("click", () => $("#keys").close());
  for (const b of $$("#tools .tool[data-tool]")) b.addEventListener("click", () => setTool(b.dataset.tool));
  document.addEventListener("keydown", onKey);
  document.addEventListener("keyup", (e) => { if (e.key === " ") { S.view.space = false; $("#stage").classList.remove("space"); } });
  window.addEventListener("beforeunload", (e) => {
    if (S.saver && (S.saver.pending() || S.saver.failed)) { e.preventDefault(); e.returnValue = ""; }
  });
  panes.init();
  icons();
  if (!api.currentUser()) { showEmpty("右上の「利用者」に名前を入れてください"); return; }
  loadWorks().catch((e) => { fail(e, "作品を読むこと"); showEmpty(`作品を読めませんでした：${api.errorText(e)}`); });
}

boot();
