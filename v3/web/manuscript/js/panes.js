// 右のパネル（判断・ツール・レイヤー・確かめ）と、下のページの一覧。
// どの欄も今の正本（S.m）から作り直す。値を変えたら main.js の change で操作を送る（ここで正本を直に書き換えない）。
import * as api from "../../js/api.js";
import { S, change, draw, reload, selectPage, setTool, setFrameMode, removeSelected, selectedRow, workbenchUrl, openWorkbench, TOOLS } from "./main.js";
import { newId } from "./model.js";
import { BALLOON_FORMS, balloonOutline, bbox, r2 } from "./geometry.js";
import { TONE_KINDS } from "./tone_draw.js";
import { $, $$, h, icons, note, toast, fail, seg, num, color, range, kv, sec, flag } from "./ui.js";
import { PRINT_INK, PRINT_PAPER } from "./print_colors.js";
import { t } from "../../common/i18n.js";

const TABS = [["held", t("判断"), "scale"], ["tools", t("ツール"), "sliders-horizontal"], ["layers", t("レイヤー"), "layers"], ["check", t("確かめ"), "list-checks"]];
const PAGE_KINDS = [["cover", t("表紙")], ["color_page", t("カラー")], ["body", t("本文")], ["blank", t("白")]];
const COLOR_MODES = [["bilevel", t("2階調")], ["grayscale", t("グレー")], ["color", t("カラー")]];
const NOMBRE = [["visible", t("見せる")], ["hidden", t("隠しノンブル")], ["none", t("入れない")]];
const TEXT_KINDS = [["balloon", t("セリフ")], ["caption", t("ナレーション")], ["drawn_sfx", t("描き文字")]];
const FIELD_NAMES = { frame: t("コマ枠"), image_id: t("絵"), image_placement: t("絵の置き場"), frame_style: t("枠の線"), text: t("文字"), box_mm: t("文字の箱"),
  balloon_shape: t("フキダシの形"), tail_target_mm: t("しっぽ"), font_size_pt: t("文字の大きさ"), writing_direction: t("縦横"), spec: t("中身"),
  order: t("順"), typesetting: t("組版"), spans: t("一部の書式"), ruby: t("ルビ"), decoration: t("飾り"), font_family: t("書体"), opacity: t("不透明度"),
  visible: t("見せる"), stack_order: t("重なり"), placement: t("置き場"), page_kind: t("ページの種類"), color_mode: t("色"), dpi: t("解像度"),
  nombre_display: t("ノンブル"), joined_to_previous: t("つなぐ"), item_kind: t("種類") };
const fieldName = (f) => FIELD_NAMES[f] || f;
const noPrint = () => note(t("このサーバーには、この項目の値がありません（見開き・ページの種類・色と解像度・ノンブル・組版・入稿前の確かめが入った版のサーバーで使えます）"), "need");

let heldFocus = 0;

export function init() {
  const tabs = $("#itabs");
  tabs.replaceChildren(...TABS.map(([k, label, icon]) => h("button", { class: "itab", role: "tab", "data-tab": k, onclick: () => openTab(k) },
    h("i", { "data-lucide": icon }), label, k === "held" ? h("span", { class: "count", id: "held-count" }) : null)));
  const tb = $("#tools");
  const undo = $("#undo");
  for (const [k, label, icon, key] of TOOLS) {
    tb.insertBefore(h("button", { class: "tool", "data-tool": k, "aria-pressed": String(k === "select"), "data-key": key, title: label },
      h("i", { "data-lucide": icon }), label, h("kbd", { text: "" })), undo.previousElementSibling);
  }
  $("#page-add").addEventListener("click", addPage);
  icons();
}

export function openTab(k) { S.tab = k; render(); }
export function cycleTab() { const i = TABS.findIndex((t) => t[0] === S.tab); openTab(TABS[(i + 1) % TABS.length][0]); }

export function render() {
  if (!S.m) return;
  for (const b of $$(".itab")) b.setAttribute("aria-selected", String(b.dataset.tab === S.tab));
  const body = $("#pane");
  body.replaceChildren(...({ held: heldPane, tools: toolsPane, layers: layersPane, check: checkPane }[S.tab])());
  renderHeldCount();
  renderDock();
  renderZoom();
  icons();
}

export function renderHeldCount() {
  const c = $("#held-count");
  if (c) c.textContent = S.held.length ? String(S.held.length) : "";
}

export function renderZoom() {
  if (!S.view) return;
  const z = S.view.zoom();
  // 100% は、96dpi の画面で紙と同じ大きさ
  $("#zoom-v").textContent = `${Math.round((z / (96 / 25.4)) * 100)}%`;
}

// ---------------------------------------------------------------- 判断
function heldPane() {
  if (!S.held.length) return [note(t("判断待ちはありません。AIの案が手動編集した所を変えようとすると、ここに並びます"))];
  heldFocus = Math.min(heldFocus, S.held.length - 1);
  return [note(t("J・K で選び、A で受け入れ、X で断ります。行を押すと、その場所を出します")),
    h("div", { class: "list" }, S.held.map((x, i) => {
      const page = S.m.find("pages", x.page_id);
      return h("div", { class: `held-row${i === heldFocus ? " cur" : ""}`, "data-i": i, onclick: () => { heldFocus = i; jump({ page_id: x.page_id, location: { table: x.target_table, id: x.target_id } }); render(); } },
        h("div", { class: "row wrap" }, flag(t("判断待ち"), "warn"), h("span", { class: "meta", text: [page ? t("{{number}} ページ", { number: page.number }) : null, tableName(x.target_table), fieldName(x.field)].filter(Boolean).join(t("・")) })),
        h("div", { class: "kv held-kv" }, h("span", { class: "k", text: t("今") }), h("div", { class: "v mono", text: short(x.current_value) }),
          h("span", { class: "k", text: t("AIの案") }), h("div", { class: "v mono", text: short(x.proposed_value) })),
        h("div", { class: "row" },
          h("button", { class: "btn sm", onclick: (e) => { e.stopPropagation(); decide(x, "accept"); } }, h("i", { "data-lucide": "check" }), t("受け入れる"), h("kbd", { text: "A" })),
          h("button", { class: "btn sm", onclick: (e) => { e.stopPropagation(); decide(x, "reject"); } }, h("i", { "data-lucide": "x" }), t("断る"), h("kbd", { text: "X" }))));
    }))];
}

const tableName = (name) => ({ panels: t("コマ"), text_items: t("文字"), page_items: t("トーン・図形"), panel_layers: t("レイヤー"), pages: t("ページ") }[name] || name);
function short(v) { const s = typeof v === "string" ? v : JSON.stringify(v); return s && s.length > 80 ? `${s.slice(0, 80)}…` : s ?? t("（無し）"); }

function decide(x, decision) {
  change(decision === "accept" ? t("判断：受け入れる") : t("判断：断る"), [{ type: "resolve_held_change", id: x.id, decision }], { pages: [x.page_id || S.pageId], reload: true });
}
export function heldStep(d) { if (!S.held.length) return; openTab("held"); heldFocus = (heldFocus + d + S.held.length) % S.held.length; const x = S.held[heldFocus]; jump({ page_id: x.page_id, location: { table: x.target_table, id: x.target_id } }); render(); }
export function heldDecide(d) { if (S.tab !== "held" || !S.held[heldFocus]) return; decide(S.held[heldFocus], d); }

// ---------------------------------------------------------------- ツール
function toolsPane() {
  const out = [];
  const r = selectedRow();
  if (r && S.sel.kind === "panel") out.push(...panelPane(r));
  else if (r && S.sel.kind === "text") out.push(...textPane(r));
  else if (r && S.sel.kind === "tone") out.push(...tonePane(r));
  else out.push(...toolOptions());
  if (S.pageId) out.push(...pagePane(S.m.find("pages", S.pageId)));
  return out;
}

function toolOptions() {
  const tool = S.tool, spec = S.m.spec(), prefs = S.m.work.preferences || {};
  if (tool === "select") return [sec(t("選ぶ"), note(t("コマ・フキダシ・文字を押すと選べます。コマを2回押すとコマの絵を動かせます。文字は2回押すとその場で打てます")))];
  if (tool === "hand") return [sec(t("手のひら"), note(t("ドラッグで動かします。スペースを押している間と、真ん中のボタンでも動かせます。Ctrl とホイールで広げる・縮める")))];
  if (tool === "frame") {
    const fs = prefs.frame_style;
    return [sec(t("コマ枠"),
      seg([["move", t("動かす"), "move"], ["edit", t("角を直す"), "spline"], ["add", t("足す"), "square-plus"], ["join", t("合わせる"), "merge"]], S.frameMode, setFrameMode, t("コマ枠の操作")),
      note({ move: t("コマを押して動かす・角の掴みで大きさを変える"), edit: t("コマを押すと角ごとの掴みが出ます"), add: t("ページの空いた所を押すとコマを足します"), join: t("合わせる2つのコマを順に押します") }[S.frameMode]),
      kv([t("コマの間（横）"), num(spec.gutter_x_mm, (v) => setSpec({ gutter_x_mm: v }), { min: 0, step: 0.5, unit: "mm", label: t("コマの間（横）") })],
         [t("コマの間（縦）"), num(spec.gutter_y_mm, (v) => setSpec({ gutter_y_mm: v }), { min: 0, step: 0.5, unit: "mm", label: t("コマの間（縦）") })],
         [t("枠の線の太さ"), num(fs ? fs.line_width_mm : null, (v) => setFrameDefault({ line_width_mm: v }), { min: 0, step: 0.05, unit: "mm", label: t("枠の線の太さ") })],
         [t("枠の線の色"), color(fs ? fs.line_color : PRINT_INK, (v) => setFrameDefault({ line_color: v }), t("枠の線の色"))]),
      fs ? h("p", { class: "meta", text: t("作品の標準の枠です。自分の線を持つコマ（右のパネルで変えたコマ）は変わりません") })
         : note(t("作品の標準の枠の線が決まっていません。書き出しで止まります。太さを入れると決まります"), "need"))];
  }
  if (tool === "knife") {
    const k = S.knife;
    const auto = k.direction === "vertical" ? spec.gutter_x_mm : spec.gutter_y_mm;
    return [sec(t("ナイフ"),
      seg([["horizontal", t("横"), "minus"], ["vertical", t("縦"), "grip-vertical"], ["slanted", t("斜め"), "slash"]], k.direction, (v) => { k.direction = v; S.view.knife = k; render(); }, t("切る向き")),
      kv(k.direction === "slanted" ? [t("角度"), num(k.angle, (v) => { k.angle = v; }, { min: -89, max: 89, step: 1, unit: t("度"), label: t("角度") })] : [null, ""],
         [t("間"), h("span", { class: "row" }, num(k.gap ?? auto, (v) => { k.gap = v; render(); }, { min: 0, step: 0.5, unit: "mm", label: t("分けた間") }),
           k.gap !== null ? h("button", { class: "btn sm ghost", onclick: () => { k.gap = null; render(); } }, t("コマの間に合わせる")) : h("span", { class: "meta", text: t("コマの間と同じ") }))]),
      note(t("コマの上で線の位置を見て、押すと分けます。分けた小さい方が新しいコマです")),
      S.m.rows("thresholds").some((x) => x.key === "panel_short_side_min_mm" && !x.removed && x.value) ? null
        : note(t("コマの最小の大きさ（閾値 panel_short_side_min_mm）が決まっていないので、サーバーは分けません。閾値は作品の設定で決めます"), "need"))];
  }
  if (tool === "balloon" || tool === "text") {
    const b = S.balloon;
    return [sec(tool === "balloon" ? t("フキダシ") : t("文字"),
      tool === "balloon" ? seg(BALLOON_FORMS.map(([v, l, i]) => [v, l, i]), b.form, (v) => { b.form = v; render(); }, t("フキダシの形")) : null,
      kv([t("文字の大きさ"), num(b.font_size_pt, (v) => { b.font_size_pt = v; }, { min: 1, step: 0.5, unit: "pt", label: t("文字の大きさ") })],
         ...(tool === "balloon" ? [[t("線の太さ"), num(b.line_width_mm, (v) => { b.line_width_mm = v; }, { min: 0, step: 0.05, unit: "mm", label: t("線の太さ") })],
           [t("線の色"), color(b.line_color, (v) => { b.line_color = v; }, t("線の色"))], [t("塗り"), color(b.fill_color, (v) => { b.fill_color = v; }, t("塗り"))],
           ...(S.m.caps.print ? [[t("しっぽの根元"), num(b.tail_base_width_mm, (v) => { b.tail_base_width_mm = v; }, { min: 0.1, step: 0.5, unit: "mm", label: t("しっぽの根元の幅") })]] : [])] : [])),
      note(tool === "balloon" ? t("コマの中を押すとフキダシを足し、そのまま打てます。縦書きか横書きかは作品の文字の向きに従います") : t("コマの中を押すと文字を足し、そのまま打てます。縦書きか横書きかは作品の文字の向きに従います")))];
  }
  if (tool === "tone") {
    const tn = S.tone;
    return [sec(t("トーン"),
      seg(TONE_KINDS, tn.kind, (v) => { tn.kind = v; render(); }, t("トーンの種類")),
      kv([t("濃さ"), range(tn.density, null, (v) => { tn.density = v; }, { label: t("濃さ") })],
         ...(["dots", "lines", "gradient"].includes(tn.kind) ? [[t("線数"), num(tn.lines_per_inch, (v) => { tn.lines_per_inch = v; }, { min: 1, step: 5, unit: t("線"), label: t("線数") })]] : [])),
      note(t("コマを押すと、そのコマいっぱいに貼ります（トーンはコマの形で切り抜きます）")))];
  }
  return [];
}

function setSpec(ch) { change(t("ページの寸法"), [{ type: "set_work_settings", page_spec: { ...S.m.spec(), ...ch } }], { pages: S.m.pages(S.episodeId).map((p) => p.id) }); }
function setPrefs(ch, label) { change(label, [{ type: "set_work_settings", preferences: { ...(S.m.work.preferences || {}), ...ch } }], { pages: S.m.pages(S.episodeId).map((p) => p.id) }); }
function setFrameDefault(ch) {
  const fs = (S.m.work.preferences || {}).frame_style;
  const next = { line_width_mm: 0.5, line_color: PRINT_INK, ...(fs || {}), ...ch };
  if (!fs && ch.line_width_mm === undefined) { toast(t("先に線の太さを入れてください"), "need"); render(); return; }
  setPrefs({ frame_style: next }, t("標準の枠の線"));
}

function common(r, kind) {
  const hand = (r.human_hand_fields || []);
  const held = S.held.filter((x) => x.target_id === r.id);
  return [
    h("div", { class: "row wrap" },
      hand.length ? flag(t("手動編集：{{fields}}", { fields: hand.map(fieldName).join(t("・")) }), "warn", t("手動で変更した所。AIの案はここを直接は変えず、判断待ちになります")) : flag(t("手動編集の印なし"), "mut"),
      held.length ? h("button", { class: "flag warn", onclick: () => openTab("held") }, t("判断待ち {{count}} 件", { count: held.length })) : null),
    h("div", { class: "row wrap" },
      h("button", { class: "btn sm", "aria-pressed": String(!!r.fixed), onclick: () => change(r.fixed ? t("動かさない印を外す") : t("動かさない印を付ける"), [{ type: "set_fixed", target_kind: kind, id: r.id, fixed: !r.fixed }], { pages: [r.page_id] }) },
        h("i", { "data-lucide": r.fixed ? "lock" : "lock-open" }), r.fixed ? t("動かさない（外す）") : t("動かさない印を付ける")),
      h("button", { class: "btn sm ghost", onclick: removeSelected, disabled: !!r.fixed }, h("i", { "data-lucide": "trash-2" }), t("消す"))),
  ];
}

function panelPane(p) {
  const prefs = S.m.work.preferences || {};
  const fs = p.frame_style;
  const setStyle = (ch) => change(t("コマの枠の線"), [{ type: "update_panel", id: p.id, frame_style: { ...(fs || prefs.frame_style || { line_width_mm: 0.5, line_color: PRINT_INK }), ...ch } }], { pages: [p.page_id] });
  const layers = S.m.layers(p.id);
  return [sec(t("コマ {{order}}", { order: p.order }), ...common(p, "panel"),
    kv([t("枠の線"), h("span", { class: "row" }, num(fs ? fs.line_width_mm : prefs.frame_style ? prefs.frame_style.line_width_mm : null, (v) => setStyle({ line_width_mm: v }), { min: 0, step: 0.05, unit: "mm", label: t("このコマの枠の線の太さ") }),
         fs ? h("button", { class: "btn sm ghost", onclick: () => change(t("コマの枠の線を標準に戻す"), [{ type: "update_panel", id: p.id, frame_style: null }], { pages: [p.page_id] }) }, t("標準に戻す")) : h("span", { class: "meta", text: t("作品の標準") }))],
       [t("線の色"), color((fs || prefs.frame_style || {}).line_color, (v) => setStyle({ line_color: v }), t("このコマの枠の線の色"))],
       [t("地の色"), h("span", { class: "row" }, color((fs || {}).fill_color || PRINT_PAPER, (v) => setStyle({ fill_color: v }), t("このコマの地の色")),
         fs && fs.fill_color ? h("button", { class: "btn sm ghost", onclick: () => setStyle({ fill_color: null }) }, t("塗らない")) : h("span", { class: "meta", text: t("塗らない") }))])),
  sec(t("コマの絵"),
    p.image_id ? h("div", { class: "row wrap" }, flag(p.image_placement ? t("置いてある") : t("置き場が決まっていない"), p.image_placement ? "mut" : "warn"), h("span", { class: "meta", text: t("重ねたレイヤー {{count}} 枚", { count: layers.length }) })) : note(t("このコマには絵がありません")),
    h("div", { class: "row wrap" },
      h("a", { class: "btn sm ai-o", href: workbenchUrl(p.id), onclick: (e) => { e.preventDefault(); openWorkbench(p.id); } }, h("i", { "data-lucide": "sparkles" }), t("このコマの絵を生成"), h("kbd", { text: "L" })),
      p.image_id && p.image_placement ? h("button", { class: "btn sm", onclick: () => S.view.hooks.onImageEdit(p.id) }, h("i", { "data-lucide": "move" }), t("絵を動かす")) : null),
    placeImageForm(p))];
}

// 絵を置く：ローカルのファイルを上げてコマの絵にし、コマの外接の四角を覆う大きさで置く
function placeImageForm(p) {
  const origin = h("select", { class: "field", "aria-label": t("絵の出どころ") }, h("option", { value: "human_drawn", text: t("自分で描いた絵") }), h("option", { value: "imported", text: t("持ち込んだ絵") }));
  const src = h("input", { class: "field", placeholder: t("出どころ（持ち込んだ絵のとき。例：撮った写真の元）"), "aria-label": t("出どころの説明") });
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", class: "field file", "aria-label": t("置く絵のファイル") });
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    if (origin.value === "imported" && !src.value.trim()) { toast(t("持ち込んだ絵には出どころを書いてください"), "need"); file.value = ""; return; }
    let bmp;
    try { bmp = await createImageBitmap(f); } catch (e) { fail(e, t("絵を読み込めませんでした")); return; }
    const [x0, y0, x1, y1] = bbox(p.frame.polygon_mm);
    const k = Math.max((x1 - x0) / bmp.width, (y1 - y0) / bmp.height);
    const w = bmp.width * k, hh = bmp.height * k, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const placement = { crop_px: [0, 0, bmp.width, bmp.height], dest_box_mm: [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2].map(r2), rotation_deg: 0, skew_x_deg: 0, skew_y_deg: 0, flip_h: false, flip_v: false };
    change(t("絵を置く"), [], { pages: [p.page_id], reload: true, send: async () => {
      const fd = new FormData();
      fd.append("image", f);
      fd.append("origin", origin.value);
      if (src.value.trim()) fd.append("source_note", src.value.trim());
      const up = await api.postForm(`/works/${S.workId}/panels/${p.id}/image`, fd);
      const ev = await api.op(S.workId, { type: "update_panel", id: p.id, image_placement: placement });
      return [up.select_event_id, ev.event_id];
    } });
  });
  return h("details", { class: "disc" }, h("summary", { text: t("絵を置く") }), kv([t("出どころ"), origin], [null, src], [null, file]));
}

function textPane(item) {
  const m = S.m, prefs = m.work.preferences || {};
  const bs = item.balloon_shape && item.balloon_shape.kind !== "none" ? item.balloon_shape : null;
  const up = (ch, label = t("文字の設定")) => change(label, [{ type: "update_text_item", id: item.id, ...ch }], { pages: [item.page_id] });
  const ta = h("textarea", { class: "field area", rows: 3, "aria-label": t("文字"), value: item.text });
  ta.value = item.text;
  // 打っている間は画面だけ書き換えて見せ、欄を出たときに送る
  ta.addEventListener("input", () => { item.text = ta.value; S.view.rebuild(); });
  ta.addEventListener("change", () => { item.text = ta.__orig ?? item.text; S.view.hooks.onEditDone(item.id, ta.value); });
  ta.__orig = item.text;
  ta.addEventListener("focus", () => { ta.__orig = item.text; });
  const ts = item.typesetting;
  const tsBase = ts || prefs.typesetting || null;
  const setTs = (ch) => up({ typesetting: { line_spacing_ratio: 0.2, line_break: "phrase", tate_chu_yoko_max_digits: 2, tate_chu_yoko_marks: true, align: "start", ...(tsBase || {}), ...ch } }, t("組版"));
  const out = [sec(TEXT_KINDS.find((k) => k[0] === item.item_kind)?.[1] || t("文字"), ...common(item, "text_item"),
    seg(TEXT_KINDS, item.item_kind, (v) => up({ item_kind: v }, t("文字の種類")), t("文字の種類")),
    ta,
    kv([t("縦横"), seg([["vertical", t("縦"), "arrow-down"], ["horizontal", t("横"), "arrow-right"]], item.writing_direction, (v) => up({ writing_direction: v }, t("縦横")), t("縦書き・横書き"))],
       [t("大きさ"), num(item.font_size_pt, (v) => up({ font_size_pt: v }, t("文字の大きさ")), { min: 1, step: 0.5, unit: "pt", label: t("文字の大きさ") })],
       [t("書体"), h("input", { class: "field", value: item.font_family || "", placeholder: (prefs.fonts_by_kind || {})[item.item_kind] ? t("作品の標準：{{font}}", { font: prefs.fonts_by_kind[item.item_kind] }) : t("未設定（書き出しで止まります）"), "aria-label": t("書体"),
         onchange: (e) => up({ font_family: e.target.value.trim() || null }, t("書体")) })],
       [t("文字の色"), h("span", { class: "row" }, color((item.decoration || {}).fill, (v) => up({ decoration: { ...(item.decoration || {}), fill: v } }, t("文字の色")), t("文字の色")),
         (item.decoration || {}).fill ? null : flag(t("未設定（書き出しで止まります）"), "warn"))],
       [t("不透明度"), range(item.opacity ?? 1, null, (v) => up({ opacity: v }, t("不透明度")), { label: t("不透明度") })]),
    h("p", { class: "meta", text: t("画面の縦組みはブラウザの組み方で、書き出し（サーバーの組版）と同じ所で改行するかは未検証です。入りきるかは「確かめ」で測ります") }))];
  if (m.caps.print) {
    out.push(sec(t("組版"), ts ? null : note(prefs.typesetting ? t("作品の標準の組版を使っています") : t("組版が決まっていません。値を変えるとこの文字の組版になります"), prefs.typesetting ? "" : "need"),
      kv([t("行間"), num(tsBase ? tsBase.line_spacing_ratio : null, (v) => setTs({ line_spacing_ratio: v }), { min: 0, step: 0.05, label: t("行間（文字の大きさとの比）") })],
         [t("改行"), seg([["phrase", t("文節")], ["character", t("字")], ["none", t("しない")]], tsBase ? tsBase.line_break : null, (v) => setTs({ line_break: v }), t("改行のしかた"))],
         [t("縦中横"), num(tsBase ? tsBase.tate_chu_yoko_max_digits : null, (v) => setTs({ tate_chu_yoko_max_digits: v }), { min: 0, max: 4, step: 1, unit: t("桁まで"), label: t("縦中横にする数字の桁") })],
         [t("!? を縦中横"), seg([["1", t("する")], ["0", t("しない")]], tsBase ? (tsBase.tate_chu_yoko_marks ? "1" : "0") : null, (v) => setTs({ tate_chu_yoko_marks: v === "1" }), t("感嘆符・疑問符の縦中横"))],
         [t("揃え"), seg([["start", t("頭")], ["center", t("真ん中")]], tsBase ? tsBase.align : null, (v) => setTs({ align: v }), t("揃え"))]),
      ts ? h("button", { class: "btn sm ghost", onclick: () => up({ typesetting: null }, t("組版を標準に戻す")) }, t("作品の標準に戻す")) : null));
  } else out.push(sec(t("組版"), noPrint()));
  if (bs) {
    const box = item.box_mm;
    out.push(sec(t("フキダシの形"),
      seg(BALLOON_FORMS.map(([v, l, i]) => [v, l, i]), null, (v) => up({ balloon_shape: { ...bs, outline_mm: balloonOutline(v, box, 3) } }, t("フキダシの形")), t("形を作り直す")),
      kv([t("線の太さ"), num(bs.line_width_mm, (v) => up({ balloon_shape: { ...bs, line_width_mm: v } }, t("フキダシの線")), { min: 0, step: 0.05, unit: "mm", label: t("線の太さ") })],
         [t("線の色"), color(bs.line_color, (v) => up({ balloon_shape: { ...bs, line_color: v } }, t("フキダシの線の色")), t("線の色"))],
         [t("塗り"), color(bs.fill_color || PRINT_PAPER, (v) => up({ balloon_shape: { ...bs, fill_color: v } }, t("フキダシの塗り")), t("塗り"))],
         ...(m.caps.print ? [[t("しっぽの根元"), num(bs.tail_base_width_mm, (v) => up({ balloon_shape: { ...bs, tail_base_width_mm: v, tail_bend_ratio: bs.tail_bend_ratio ?? 0 } }, t("しっぽ")), { min: 0.1, step: 0.5, unit: "mm", label: t("しっぽの根元の幅") })],
           [t("しっぽの曲がり"), num(bs.tail_bend_ratio, (v) => up({ balloon_shape: { ...bs, tail_bend_ratio: v, tail_base_width_mm: bs.tail_base_width_mm ?? 4 } }, t("しっぽ")), { min: -1, max: 1, step: 0.1, label: t("しっぽの曲がり") })]] : []),
         [t("しっぽ"), item.tail_target_mm ? h("button", { class: "btn sm ghost", onclick: () => up({ tail_target_mm: null }, t("しっぽを消す")) }, t("しっぽを消す")) : h("span", { class: "meta", text: t("白い丸の掴みを引くと出ます") })],
         [t("前とつなぐ"), seg([["1", t("つなぐ")], ["0", t("つながない")]], item.joined_to_previous ? "1" : "0", (v) => up({ joined_to_previous: v === "1" }, t("フキダシをつなぐ")), t("前のフキダシとつなぐ"))]),
      m.caps.print && item.tail_target_mm && (bs.tail_base_width_mm == null || bs.tail_bend_ratio == null) ? note(t("しっぽの根元の幅・曲がりが決まっていません。書き出しで止まります"), "need") : null,
      h("p", { class: "meta", text: t("形を押すと、今の文字の箱に合わせて外形を作り直します。つないだフキダシは、同じコマの前（順が1つ前）のフキダシと線を消して1つに見せます") })));
  }
  return out;
}

function tonePane(item) {
  const up = (ch, label = t("トーン")) => change(label, [{ type: "update_page_item", id: item.id, ...ch }], { pages: [item.page_id] });
  const sp = item.spec;
  const setSpec = (ch) => up({ spec: { ...sp, ...ch } });
  if (item.item_kind !== "tone") return [sec(t("図形"), ...common(item, "page_item"), note(t("図形の中身を描く・直すのは、この画面にまだありません"), "need"))];
  return [sec(t("トーン：{{kind}}", { kind: (TONE_KINDS.find((k) => k[0] === sp.kind) || [])[1] || sp.kind }), ...common(item, "page_item"),
    kv([t("濃さ"), range(sp.density, null, (v) => setSpec({ density: v }), { label: t("濃さ") })],
       ...(sp.lines_per_inch != null ? [[t("線数"), num(sp.lines_per_inch, (v) => setSpec({ lines_per_inch: v }), { min: 1, step: 5, unit: t("線"), label: t("線数") })]] : []),
       [t("角度"), num(sp.angle_deg, (v) => setSpec({ angle_deg: v }), { step: 1, unit: t("度"), label: t("角度") })],
       ...(sp.line_count != null ? [[t("本数"), num(sp.line_count, (v) => setSpec({ line_count: Math.round(v) }), { min: 1, step: 10, label: t("本数") })]] : []),
       ...(sp.density_end != null ? [[t("終わりの濃さ"), range(sp.density_end, null, (v) => setSpec({ density_end: v }), { label: t("終わりの濃さ") })]] : []),
       [t("不透明度"), range(item.opacity, null, (v) => up({ opacity: v }), { label: t("不透明度") })],
       [t("切り抜き"), h("span", { class: "meta", text: sp.target.kind === "panel" ? t("コマの形") : sp.target.kind === "polygon" ? t("囲んだ形") : t("絵の形（未対応の表示）") })]),
    h("p", { class: "meta", text: t("画面の網点は目安です。書き出しの網点はサーバーが描きます。細かすぎて縞が出る倍率では灰色で見せています") }))];
}

// ---------------------------------------------------------------- ページ
function pagePane(page) {
  const m = S.m, w = m.work;
  const up = (ch, label) => change(label, [{ type: "update_page", id: page.id, ...ch }], { pages: [page.id] });
  const sides = m.sides(S.episodeId);
  const pages = m.pages(S.episodeId);
  const i = pages.findIndex((p) => p.id === page.id);
  const side = sides ? sides[i] : null;
  const out = [];
  const fl = w.first_page_is_left;
  out.push(sec(side === "left" ? t("このページ（{{number}} ページ・左）", { number: page.number }) : side ? t("このページ（{{number}} ページ・右）", { number: page.number }) : t("このページ（{{number}} ページ）", { number: page.number }),
    kv([t("1ページ目"), seg([["left", t("左に置く")], ["right", t("右に置く")]], fl === true ? "left" : fl === false ? "right" : null,
      (v) => change(t("1ページ目の左右"), [{ type: "set_work_settings", first_page_is_left: v === "left" }], { pages: pages.map((p) => p.id) }), t("1ページ目の左右"))]),
    fl === null || fl === undefined ? note(t("1ページ目を左右どちらに置くかが決まっていません。見開きで並べられず、書き出しでも止まります"), "need") : null));
  if (!m.caps.print) { out.push(noPrint()); return out; }
  const prefs = w.preferences || {};
  const pr = prefs.print;
  const nb = prefs.nombre;
  out.push(kv(
    [t("種類"), seg(PAGE_KINDS, page.page_kind, (v) => up({ page_kind: v }, t("ページの種類")), t("ページの種類"))],
    [t("色"), seg(COLOR_MODES, page.color_mode, (v) => up({ color_mode: v }, t("ページの色")), t("ページの色"))],
    [t("解像度"), h("span", { class: "row" }, num(page.dpi, (v) => up({ dpi: Math.round(v) }, t("解像度")), { min: 1, max: 2400, step: 1, unit: "dpi", label: t("解像度") }),
      h("span", { class: "meta", text: page.dpi ? "" : pr ? t("入稿の設定：{{value}}", { value: pr.dpi_by_color_mode[page.color_mode || pr.color_mode] ?? t("未設定") }) : t("入稿の設定が無い") }))],
    [t("ノンブル"), seg(NOMBRE, page.nombre_display, (v) => up({ nombre_display: v }, t("ノンブル")), t("ノンブルの出し方"))]));
  if (!page.page_kind || !page.color_mode || !page.nombre_display) {
    out.push(h("p", { class: "meta", text: t("空いている項目は作品の入稿の設定に従います（{{detail}}）", { detail: [pr ? t("色") : t("入稿の設定が無い"), nb ? t("ノンブルはページの種類ごとの設定") : t("ノンブルの設定が無い")].join(t("・")) }) }));
  }
  // 見開き
  const sp = m.spreadOf(page.id);
  const units = sides ? m.units(S.episodeId) : null;
  const u = units ? units.find((x) => (x.left && x.left.id === page.id) || (x.right && x.right.id === page.id)) : null;
  if (sp) {
    out.push(h("div", { class: "row wrap" }, flag(t("見開き"), "on"), h("span", { class: "meta", text: t("{{first}}–{{second}} ページ", { first: m.find("pages", sp.first_page_id).number, second: m.find("pages", sp.second_page_id).number }) }),
      h("button", { class: "btn sm ghost", onclick: () => change(t("見開きを解く"), [{ type: "set_removed", target_kind: "spread", id: sp.id, removed: true }], { pages: [sp.first_page_id, sp.second_page_id], reload: true }) }, t("見開きを解く"))));
  } else if (u && u.left && u.right) {
    const rtl = w.reading_direction === "rtl";
    const [a, b] = rtl ? [u.right, u.left] : [u.left, u.right];
    out.push(h("button", { class: "btn sm", onclick: () => change(t("見開きにする"), [{ type: "add_spread", id: newId(), first_page_id: a.id, second_page_id: b.id }], { pages: [a.id, b.id], reload: true }) },
      h("i", { "data-lucide": "book-open" }), t("{{first}}–{{second}} ページを見開きにする", { first: a.number, second: b.number })));
  } else if (sides) out.push(h("p", { class: "meta", text: t("向かいのページが無いので見開きにできません") }));
  out.push(h("div", { class: "row wrap" }, h("button", { class: "btn sm ghost", onclick: () => removePage(page) }, h("i", { "data-lucide": "trash-2" }), t("このページを削除"))));
  return out;
}

function removePage(page) {
  change(t("ページを削除"), [{ type: "set_removed", target_kind: "page", id: page.id, removed: true }], { pages: [page.id], reload: true });
}

async function addPage() {
  if (!S.episodeId) return;
  const pages = S.m.pages(S.episodeId);
  const id = newId();
  const ids = change(t("ページを足す"), [{ type: "add_page", id, episode_id: S.episodeId, number: Math.max(0, ...pages.map((p) => p.number)) + 1 }], { pages: [id, ...(S.pageId ? [S.pageId] : [])], reload: true });
  if (ids) { await ids.catch(() => {}); await S.saver.idle().catch(() => {}); selectPage(id); }
}

// ---------------------------------------------------------------- レイヤー・見せる物
function layersPane() {
  const out = [];
  const sh = S.show, lk = S.lock;
  const tog = (obj, k, label, lock) => h("button", { class: "chip", "aria-pressed": String(lock ? !!obj[k] : obj[k] !== false), onclick: () => { obj[k] = lock ? !obj[k] : obj[k] === false; draw(); } },
    h("i", { "data-lucide": lock ? (obj[k] ? "lock" : "lock-open") : obj[k] !== false ? "eye" : "eye-off" }), label);
  out.push(sec(t("見せるもの（W）"),
    h("div", { class: "chips" }, tog(sh.cat, "art", t("コマの絵")), tog(sh.cat, "frame", t("コマ枠")), tog(sh.cat, "tone", t("トーン")), tog(sh.cat, "balloon", t("フキダシ")), tog(sh.cat, "type", t("文字")), tog(sh.cat, "sfx", t("描き文字"))),
    h("div", { class: "chips" }, tog(sh, "guide", t("基本枠")), tog(sh, "safe", t("安全線")), tog(sh, "grid", t("方眼")), tog(sh, "boxes", t("文字の箱")), tog(sh, "hand", t("手動編集の印")), tog(sh, "held", t("判断待ちの印"))),
    h("p", { class: "meta", text: t("見せる・隠すは画面だけで、原稿の値は変えません") })));
  out.push(sec(t("触らない（画面だけ）"),
    h("div", { class: "chips" }, tog(lk, "frame", t("コマ枠"), true), tog(lk, "balloon", t("フキダシ・文字"), true), tog(lk, "sfx", t("描き文字"), true), tog(lk, "tone", t("トーン"), true))));
  if (!S.pageId) return out;
  // トーン・図形（ページのレイヤー）
  const items = S.m.items(S.pageId);
  const itemRow = (row, i) => {
    const up = (ch, label) => change(label, [{ type: "update_page_item", id: row.id, ...ch }], { pages: [row.page_id] });
    const swap = (d) => {
      const o = items[i + d];
      if (!o) return;
      change(t("重なりの順"), [{ type: "update_page_item", id: row.id, stack_order: o.stack_order }, { type: "update_page_item", id: o.id, stack_order: row.stack_order }], { pages: [row.page_id] });
    };
    return h("div", { class: `lrow${S.sel && S.sel.id === row.id ? " cur" : ""}` },
      h("button", { class: "ibtn", title: row.visible ? t("隠す") : t("見せる"), "aria-label": row.visible ? t("隠す") : t("見せる"), onclick: () => up({ visible: !row.visible }, row.visible ? t("隠す") : t("見せる")) }, h("i", { "data-lucide": row.visible ? "eye" : "eye-off" })),
      h("button", { class: "grow lname", onclick: () => { S.tool !== "tone" && setTool("tone"); S.sel = { kind: "tone", id: row.id, pageId: row.page_id }; draw(); } },
        row.item_kind === "tone" ? t("トーン：{{kind}}", { kind: (TONE_KINDS.find((k) => k[0] === row.spec.kind) || [])[1] || row.spec.kind }) : t("図形"), (row.human_hand_fields || []).length ? flag(t("手動編集"), "warn") : null),
      range(row.opacity, null, (v) => up({ opacity: v }, t("不透明度")), { label: t("不透明度") }),
      h("button", { class: "ibtn", title: row.fixed ? t("動かさない印を外す") : t("動かさない印を付ける"), "aria-label": t("動かさない印"), "aria-pressed": String(!!row.fixed), onclick: () => change(t("動かさない印"), [{ type: "set_fixed", target_kind: "page_item", id: row.id, fixed: !row.fixed }], { pages: [row.page_id] }) }, h("i", { "data-lucide": row.fixed ? "lock" : "lock-open" })),
      h("button", { class: "ibtn", title: t("上へ"), "aria-label": t("上へ"), disabled: i === items.length - 1, onclick: () => swap(1) }, h("i", { "data-lucide": "chevron-up" })),
      h("button", { class: "ibtn", title: t("下へ"), "aria-label": t("下へ"), disabled: i === 0, onclick: () => swap(-1) }, h("i", { "data-lucide": "chevron-down" })));
  };
  out.push(sec(t("トーン・図形（上ほど手前）"), items.length ? h("div", { class: "list" }, [...items].map(itemRow).reverse()) : h("p", { class: "meta", text: t("このページにトーン・図形はありません") })));
  // コマのレイヤー
  const rows = [];
  for (const p of S.m.panels(S.pageId)) {
    const ls = S.m.layers(p.id);
    if (!ls.length) continue;
    rows.push(h("div", { class: "lbl", text: t("コマ {{order}}", { order: p.order }) }));
    ls.forEach((l, i) => {
      const up = (ch, label) => change(label, [{ type: "update_panel_layer", id: l.id, ...ch }], { pages: [p.page_id] });
      const swap = (d) => { const o = ls[i + d]; if (o) change(t("レイヤーの順"), [{ type: "update_panel_layer", id: l.id, stack_order: o.stack_order }, { type: "update_panel_layer", id: o.id, stack_order: l.stack_order }], { pages: [p.page_id] }); };
      rows.push(h("div", { class: "lrow" },
        h("button", { class: "ibtn", "aria-label": l.visible ? t("隠す") : t("見せる"), title: l.visible ? t("隠す") : t("見せる"), onclick: () => up({ visible: !l.visible }, l.visible ? t("レイヤーを隠す") : t("レイヤーを見せる")) }, h("i", { "data-lucide": l.visible ? "eye" : "eye-off" })),
        h("span", { class: "grow lname" }, l.role, l.placement ? null : flag(t("置き場なし"), "warn", t("置き場が無いレイヤーは描きません"))),
        range(l.opacity, null, (v) => up({ opacity: v }, t("レイヤーの不透明度")), { label: t("不透明度") }),
        h("button", { class: "ibtn", "aria-label": t("動かさない印"), title: t("動かさない印"), "aria-pressed": String(!!l.fixed), onclick: () => change(t("動かさない印"), [{ type: "set_fixed", target_kind: "panel_layer", id: l.id, fixed: !l.fixed }], { pages: [p.page_id] }) }, h("i", { "data-lucide": l.fixed ? "lock" : "lock-open" })),
        h("button", { class: "ibtn", "aria-label": t("上へ"), title: t("上へ"), disabled: i === ls.length - 1, onclick: () => swap(1) }, h("i", { "data-lucide": "chevron-up" })),
        h("button", { class: "ibtn", "aria-label": t("下へ"), title: t("下へ"), disabled: i === 0, onclick: () => swap(-1) }, h("i", { "data-lucide": "chevron-down" }))));
    });
  }
  out.push(sec(t("コマの絵のレイヤー"), rows.length ? h("div", { class: "list" }, rows) : h("p", { class: "meta", text: t("このページのコマに重ねたレイヤーはありません（レイヤーは画像生成の画面で作ります）") })));
  return out;
}

// ---------------------------------------------------------------- 確かめ（入稿前）
function checkPane() {
  if (!S.m.caps.print) return [noPrint()];
  const pf = S.preflight;
  const out = [h("div", { class: "row wrap" },
    h("button", { class: "btn sm", id: "pf-page", onclick: () => runPreflight([S.pageId]) }, h("i", { "data-lucide": "file-check" }), t("このページを確かめる")),
    h("button", { class: "btn sm", id: "pf-ep", onclick: () => runPreflight(S.m.pages(S.episodeId).map((p) => p.id)) }, h("i", { "data-lucide": "files" }), t("この話を全部確かめる")))];
  if (!pf) { out.push(note(t("書き出しの前に、問題をページと場所ごとに並べます。行を押すとその場所を出します"))); return out; }
  if (pf.running) { out.push(note(t("確かめています"), "", "loader")); return out; }
  out.push(h("div", { class: "row wrap" }, flag(t("止まる {{n}}", { n: pf.errors }), pf.errors ? "bad" : "mut"), flag(t("気を付ける {{n}}", { n: pf.warnings }), pf.warnings ? "warn" : "mut"),
    h("span", { class: "meta", text: t("{{time}} に確かめた結果。直したらもう一度押してください", { time: new Date(pf.at).toLocaleTimeString() }) })));
  if (!pf.issues.length) { out.push(note(t("問題はありません"))); return out; }
  const byPage = new Map();
  for (const x of pf.issues) { const k = x.page_id || ""; if (!byPage.has(k)) byPage.set(k, []); byPage.get(k).push(x); }
  for (const [pid, list] of byPage) {
    const page = pid ? S.m.find("pages", pid) : null;
    out.push(sec(page ? t("{{number}} ページ", { number: page.number }) : t("作品全体"), h("div", { class: "list" }, list.map((x) =>
      h("button", { class: "issue", onclick: () => jump(x) }, flag(x.severity === "error" ? t("止まる") : t("気を付ける"), x.severity === "error" ? "bad" : "warn"),
        h("span", { class: "grow", text: x.message }), x.location ? h("i", { "data-lucide": "crosshair" }) : null)))));
  }
  return out;
}

async function runPreflight(pageIds) {
  try { await S.saver.idle(); } catch (e) { fail(e, t("確かめられませんでした")); return; }
  S.preflight = { running: true };
  render();
  try {
    const r = await api.post(`/works/${S.workId}/preflight`, { page_ids: pageIds });
    S.preflight = { ...r, at: Date.now() };
  } catch (e) { S.preflight = null; fail(e, t("確かめられませんでした")); }
  render();
}

// 問題・判断待ちの場所へ動く：ページを出し、物を選び、見える所まで寄る
export function jump(x) {
  const loc = x.location;
  const pid = x.page_id || (loc && loc.page_id);
  if (pid && pid !== S.pageId && S.m.find("pages", pid)) selectPage(pid);
  if (!loc) return;
  const table = loc.table, id = loc.id;
  let box = null, kind = null;
  if (table === "panels") { const p = S.m.find("panels", id); if (p) { box = bbox(p.frame.polygon_mm); kind = "panel"; } }
  if (table === "text_items") { const t = S.m.find("text_items", id); if (t && t.box_mm) { box = t.box_mm; kind = "text"; } }
  if (table === "page_items") { const t = S.m.find("page_items", id); if (t) { box = t.box_mm; kind = "tone"; } }
  if (table === "panel_layers") { const l = S.m.find("panel_layers", id); const p = l && S.m.find("panels", l.panel_id); if (p) { box = bbox(p.frame.polygon_mm); kind = "panel"; } }
  if (!box) return;
  const owner = kind === "panel" ? S.m.find("panels", table === "panel_layers" ? S.m.find("panel_layers", id).panel_id : id) : S.m.find(table, id);
  const pageId = owner.page_id;
  S.view.focusBox(pageId, box);
  if (kind === "tone" && S.tool !== "tone") setTool("tone");
  if (kind !== "tone" && !["select", "frame"].includes(S.tool) && kind === "panel") setTool("select");
  S.sel = { kind, id: owner.id, pageId };
  // 選ぶと右のパネルは「ツール」に替わる（onSelect）。一覧（判断・確かめ）から飛んだときは一覧のまま、次の項目へ進めるようにする
  const tab = S.tab;
  S.view.select(kind, owner.id, false);
  S.view.flash(pageId, box);
  if (S.tab !== tab) { S.tab = tab; render(); }
}

// ---------------------------------------------------------------- 下のページの一覧
let sortable = null;
// 並べ替えたあと、見開きの2ページが隣り合わなくなる組を返す（無ければ null）
function spreadBroken(m, episodeId, ids) {
  for (const sp of m.spreads(episodeId)) {
    const a = ids.indexOf(sp.first_page_id), b = ids.indexOf(sp.second_page_id);
    if (Math.abs(a - b) !== 1) return t("{{first}}ページ目と{{second}}ページ目", { first: a + 1, second: b + 1 });
  }
  return null;
}

export function renderDock() {
  const host = $("#pages");
  if (!S.m || !S.episodeId) { host.replaceChildren(); return; }
  const m = S.m, pages = m.pages(S.episodeId), sides = m.sides(S.episodeId), spec = m.spec();
  const shown = new Set(S.view.slots.map((s) => s.page.id));
  const issues = new Map();
  for (const x of (S.preflight && S.preflight.issues) || []) if (x.page_id) issues.set(x.page_id, (issues.get(x.page_id) || 0) + 1);
  const heldN = new Map();
  for (const x of S.held) if (x.page_id) heldN.set(x.page_id, (heldN.get(x.page_id) || 0) + 1);
  host.replaceChildren(...pages.map((p, i) => {
    const sp = m.caps.print ? m.spreadOf(p.id) : null;
    const W = spec.frame_width_mm, H = spec.frame_height_mm;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("aria-hidden", "true");
    for (const pn of m.panels(p.id)) {
      const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      poly.setAttribute("points", pn.frame.polygon_mm.map((q) => q.join(",")).join(" "));
      svg.append(poly);
    }
    for (const t of m.texts(p.id)) {
      if (!t.box_mm) continue;
      const e = document.createElementNS("http://www.w3.org/2000/svg", "ellipse");
      e.setAttribute("cx", (t.box_mm[0] + t.box_mm[2]) / 2); e.setAttribute("cy", (t.box_mm[1] + t.box_mm[3]) / 2);
      e.setAttribute("rx", (t.box_mm[2] - t.box_mm[0]) / 2 + 2); e.setAttribute("ry", (t.box_mm[3] - t.box_mm[1]) / 2 + 2);
      e.setAttribute("class", "b");
      svg.append(e);
    }
    const side = sides ? sides[i] : null;
    return h("div", { class: `pcard${p.id === S.pageId ? " cur" : ""}${shown.has(p.id) ? " shown" : ""}${sp ? ` spread ${sp.first_page_id === p.id ? "sp-a" : "sp-b"}` : ""}`, "data-id": p.id, role: "listitem" },
      h("button", { class: "pthumb paper", style: `aspect-ratio:${spec.trim_width_mm}/${spec.trim_height_mm}`, title: t("{{number}} ページを出す", { number: p.number }), onclick: () => selectPage(p.id) }, svg),
      h("div", { class: "pmeta" },
        h("span", { class: "pnum num", text: String(p.number) }),
        side ? h("span", { class: "meta", text: side === "left" ? t("左") : t("右") }) : null,
        sp ? h("i", { "data-lucide": "book-open", title: t("見開き") }) : null,
        heldN.get(p.id) ? flag(t("判断 {{n}}", { n: heldN.get(p.id) }), "warn") : null,
        issues.get(p.id) ? flag(t("問題 {{n}}", { n: issues.get(p.id) }), "bad") : null),
      m.caps.print ? h("div", { class: "pmeta meta" },
        h("span", { text: (PAGE_KINDS.find((k) => k[0] === p.page_kind) || [null, t("種類：標準")])[1] }),
        h("span", { text: (COLOR_MODES.find((k) => k[0] === p.color_mode) || [null, ""])[1] }),
        p.dpi ? h("span", { class: "num", text: `${p.dpi}dpi` }) : null,
        p.nombre_display ? h("span", { text: t("ノンブル：{{style}}", { style: (NOMBRE.find((k) => k[0] === p.nombre_display) || [])[1] }) }) : null) : null);
  }));
  if (sortable) sortable.destroy();
  sortable = null;
  if (m.caps.print && window.Sortable) {
    sortable = new window.Sortable(host, {
      animation: 120, direction: "horizontal", ghostClass: "ghost", filter: ".pmeta", preventOnFilter: false,
      onEnd: (e) => {
        if (e.oldIndex === e.newIndex) return;
        const ids = $$(".pcard", host).map((c) => c.dataset.id);
        const broken = spreadBroken(m, S.episodeId, ids);
        if (broken) {
          // サーバーも同じ理由で断る。送らずに並びを戻す
          toast(t("並べ替えられません：見開きの組が崩れます（{{pages}}）。先に見開きを解いてください", { pages: broken }), "bad");
          renderDock();
          return;
        }
        change(t("ページの並べ替え"), [{ type: "reorder_pages", episode_id: S.episodeId, page_ids: ids }], { pages: ids, reload: true });
      },
    });
  }
  $("#pages-note").textContent = m.caps.print ? t("ドラッグで並べ替え") : t("並べ替えはこのサーバーにはありません");
  icons();
}
