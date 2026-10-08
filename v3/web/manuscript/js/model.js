// 原稿の画面が持つ正本の写し（GET /works/{id} の中身）と、操作を先に画面へ当てる所。
// 先に当てるのは見た目のためだけで、保存が済んだらサーバーの答え（読み直した中身）で置き換える。
// 操作の形はサーバーの operations/ と同じ。ここに無い操作は先に当てず、保存の後の読み直しで出す。
import { area, centroid, convexHull, lineNormal, pointInPolygon, splitPolygon } from "./geometry.js";

export function newId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

const TABLES = { panel: "panels", text_item: "text_items", panel_layer: "panel_layers", page_item: "page_items",
                 page: "pages", spread: "spreads" };

export class Model {
  constructor(data) {
    this.data = data;
    // 原稿として出す形（見開き・ページの種類・色と解像度・ノンブル・文字の一部の書式・組版・入稿前の確かめ）を
    // サーバーが持っているか。持っていない版のサーバーでは、その欄を出さずに「このサーバーにはありません」と出す
    this.caps = { print: Array.isArray(data.spreads) };
  }

  get work() { return this.data.work; }
  rows(table) { return this.data[table] || []; }
  find(table, id) { return this.rows(table).find((r) => r.id === id) || null; }

  episodes() { return this.rows("episodes").filter((e) => !e.removed).sort((a, b) => a.number - b.number); }
  pages(episodeId) {
    return this.rows("pages").filter((p) => p.episode_id === episodeId && !p.removed)
      .sort((a, b) => a.number - b.number || (a.id < b.id ? -1 : 1));
  }
  panels(pageId) { return this.rows("panels").filter((p) => p.page_id === pageId && !p.removed).sort((a, b) => a.order - b.order); }
  texts(pageId) { return this.rows("text_items").filter((t) => t.page_id === pageId && !t.removed); }
  items(pageId) { return this.rows("page_items").filter((t) => t.page_id === pageId && !t.removed).sort((a, b) => a.stack_order - b.stack_order); }
  layers(panelId) { return this.rows("panel_layers").filter((l) => l.panel_id === panelId && !l.removed).sort((a, b) => a.stack_order - b.stack_order); }
  spreads(episodeId) { return this.rows("spreads").filter((s) => s.episode_id === episodeId && !s.removed); }
  spreadOf(pageId) { return this.rows("spreads").find((s) => !s.removed && (s.first_page_id === pageId || s.second_page_id === pageId)) || null; }

  // ページの左右（サーバーの print_export/book_layout.py の page_sides と同じ）。決まっていなければ null
  sides(episodeId) {
    const fl = this.work.first_page_is_left;
    if (fl === null || fl === undefined) return null;
    return this.pages(episodeId).map((_, i) => ((i % 2 === 0) === fl ? "left" : "right"));
  }

  // 見開きの組：めくらずに見える2ページ。読む向きで前のページが右（右から）か左（左から）に来る並び。
  // 返すのは [{ left, right }]（ページの行。片方が無いこともある）
  units(episodeId) {
    const pages = this.pages(episodeId), sides = this.sides(episodeId);
    if (!sides) return null;
    const rtl = this.work.reading_direction === "rtl";
    const out = [];
    for (let i = 0; i < pages.length; i++) {
      const p = pages[i], s = sides[i];
      const firstSide = rtl ? "right" : "left";
      const next = pages[i + 1];
      if (s === firstSide && next) { out.push(rtl ? { right: p, left: next } : { left: p, right: next }); i++; }
      else out.push(s === "left" ? { left: p, right: null } : { left: null, right: p });
    }
    return out;
  }

  spec() { return this.work.page_spec; }

  // 人の手の印を付ける（サーバーの human_hand_guard.change_with_human_hand と同じく、人が変えた項目に付く）
  mark(row, fields) {
    if (!row.human_hand_fields) row.human_hand_fields = [];
    for (const f of fields) if (!row.human_hand_fields.includes(f)) row.human_hand_fields.push(f);
  }

  // ---------------------------------------------------------------- 操作を先に当てる
  // 当てられたら true。当てられない操作（サーバーだけが計算できるもの）は false を返し、保存の後の読み直しに任せる
  applyLocal(op) {
    const fn = LOCAL[op.type];
    if (!fn) return false;
    fn(this, op);
    return true;
  }
}

function changes(op) {
  const out = {};
  for (const [k, v] of Object.entries(op)) if (k !== "type" && k !== "id" && k !== "human_hand_fields") out[k] = v;
  return out;
}

function update(m, table, op) {
  const row = m.find(table, op.id);
  if (!row) return;
  const ch = changes(op);
  Object.assign(row, ch);
  m.mark(row, Object.keys(ch));
}

const LOCAL = {
  update_panel: (m, op) => update(m, "panels", op),
  update_text_item: (m, op) => update(m, "text_items", op),
  update_page_item: (m, op) => update(m, "page_items", op),
  update_panel_layer: (m, op) => update(m, "panel_layers", op),
  update_page: (m, op) => update(m, "pages", op),
  set_fixed: (m, op) => { const r = m.find(TABLES[op.target_kind], op.id); if (r) r.fixed = op.fixed; },
  set_removed: (m, op) => { const r = m.find(TABLES[op.target_kind], op.id); if (r) r.removed = op.removed; },
  set_work_settings: (m, op) => Object.assign(m.work, changes(op)),
  add_text_item: (m, op) => {
    const panel = m.find("panels", op.panel_id);
    m.data.text_items.push({ ruby: [], spans: [], transform: {}, opacity: 1, adjustments: [], fixed: false, removed: false,
                             ...changes(op), id: op.id, page_id: panel.page_id, human_hand_fields: Object.keys(changes(op)) });
  },
  add_page_item: (m, op) => {
    if (!m.data.page_items) m.data.page_items = [];
    m.data.page_items.push({ transform: {}, visible: true, opacity: 1, adjustments: [], fixed: false, removed: false,
                             ...changes(op), id: op.id, human_hand_fields: Object.keys(changes(op)) });
  },
  add_panel: (m, op) => {
    m.data.panels.push({ role: null, content: {}, image_id: null, image_placement: null, frame_style: null, adjustments: [],
                         fixed: false, human_confirmed: false, removed: false, ...changes(op), id: op.id,
                         human_hand_fields: ["frame"] });
  },
  add_shape_panel: (m, op) => {
    const [x0, y0, x1, y1] = op.box_mm;
    LOCAL.add_panel(m, { type: "add_panel", id: op.id, page_id: op.page_id, order: op.order,
                         frame: { polygon_mm: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], bleeds: op.bleeds },
                         frame_style: op.frame_style || null });
  },
  // ナイフ：サーバーと同じ式で分けて見せる（読む順の番号は読み直しで直る）
  split_panel: (m, op) => {
    const panel = m.find("panels", op.panel_id);
    const [a, b] = splitPolygon(panel.frame.polygon_mm, op.through_mm, lineNormal(op.direction, op.angle_deg), op.gap_mm);
    const [big, small] = area(a) >= area(b) ? [a, b] : [b, a];
    panel.frame = { ...panel.frame, polygon_mm: big };
    m.mark(panel, ["frame"]);
    m.data.panels.push({ ...panel, id: op.new_panel_id, frame: { ...panel.frame, polygon_mm: small }, image_id: null,
                         image_placement: null, human_hand_fields: ["frame"], order: panel.order + 0.5 });
    for (const t of m.rows("text_items")) {
      if (t.panel_id === panel.id && t.box_mm && pointInPolygon(centroid([[t.box_mm[0], t.box_mm[1]], [t.box_mm[2], t.box_mm[3]]]), small)) t.panel_id = op.new_panel_id;
    }
  },
  merge_panels: (m, op) => {
    const [a, b] = op.panel_ids.map((id) => m.find("panels", id));
    const [keep, drop] = area(a.frame.polygon_mm) >= area(b.frame.polygon_mm) ? [a, b] : [b, a];
    keep.frame = { ...keep.frame, polygon_mm: convexHull([...a.frame.polygon_mm, ...b.frame.polygon_mm]) };
    m.mark(keep, ["frame"]);
    drop.removed = true;
  },
  reorder_pages: (m, op) => {
    op.page_ids.forEach((id, i) => { const p = m.find("pages", id); if (p) p.number = op.numbers ? op.numbers[i] : i + 1; });
  },
  add_spread: (m, op) => {
    m.data.spreads.push({ id: op.id, work_id: m.work.id, first_page_id: op.first_page_id, second_page_id: op.second_page_id,
                          episode_id: m.find("pages", op.first_page_id).episode_id, image_id: null, image_placement: null,
                          adjustments: [], human_hand_fields: [], removed: false });
  },
  resolve_held_change: () => {},
};
