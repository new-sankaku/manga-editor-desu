// 右の欄（判断・道具・層・確かめ）と、下のページの一覧。
// どの欄も今の正本（S.m）から作り直す。値を変えたら main.js の change で操作を送る（ここで正本を直に書き換えない）。
import * as api from "../../js/api.js";
import { S, change, draw, reload, selectPage, setTool, setFrameMode, removeSelected, selectedRow, workbenchUrl, openWorkbench, TOOLS } from "./main.js";
import { newId } from "./model.js";
import { BALLOON_FORMS, balloonOutline, bbox, r2 } from "./geometry.js";
import { TONE_KINDS } from "./tone_draw.js";
import { $, $$, h, icons, note, toast, fail, seg, num, color, range, kv, sec, flag } from "./ui.js";

const TABS = [["held", "判断", "scale"], ["tools", "道具", "sliders-horizontal"], ["layers", "層", "layers"], ["check", "確かめ", "list-checks"]];
const PAGE_KINDS = [["cover", "表紙"], ["color_page", "カラー"], ["body", "本文"], ["blank", "白"]];
const COLOR_MODES = [["bilevel", "2階調"], ["grayscale", "グレー"], ["color", "カラー"]];
const NOMBRE = [["visible", "見せる"], ["hidden", "隠しノンブル"], ["none", "入れない"]];
const TEXT_KINDS = [["balloon", "セリフ"], ["caption", "ナレーション"], ["drawn_sfx", "描き文字"]];
const FIELD_NAMES = { frame: "コマ枠", image_id: "絵", image_placement: "絵の置き場", frame_style: "枠の線", text: "文字", box_mm: "文字の箱",
  balloon_shape: "フキダシの形", tail_target_mm: "しっぽ", font_size_pt: "文字の大きさ", writing_direction: "縦横", spec: "中身",
  order: "順", typesetting: "組版", spans: "一部の書式", ruby: "ルビ", decoration: "飾り", font_family: "書体", opacity: "不透明度",
  visible: "見せる", stack_order: "重なり", placement: "置き場", page_kind: "ページの種類", color_mode: "色", dpi: "解像度",
  nombre_display: "ノンブル", joined_to_previous: "つなぐ", item_kind: "種類" };
const fieldName = (f) => FIELD_NAMES[f] || f;
const noPrint = () => note("このサーバーには、この欄の値がありません（見開き・ページの種類・色と解像度・ノンブル・組版・入稿前の確かめが入った版のサーバーで使えます）", "need");

let heldFocus = 0;

export function init() {
  const tabs = $("#itabs");
  tabs.replaceChildren(...TABS.map(([k, label, icon]) => h("button", { class: "itab", role: "tab", "data-tab": k, onclick: () => openTab(k) },
    h("i", { "data-lucide": icon }), label, k === "held" ? h("span", { class: "count", id: "held-count" }) : null)));
  const tb = $("#tools");
  const undo = $("#undo");
  for (const [k, label, icon, key] of TOOLS) {
    tb.insertBefore(h("button", { class: "tool", "data-tool": k, "aria-pressed": String(k === "select"), title: `${label} (${key})` },
      h("i", { "data-lucide": icon }), label, h("kbd", { text: key })), undo.previousElementSibling);
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
  const z = S.view.zoom();
  // 100% は、96dpi の画面で紙と同じ大きさ
  $("#zoom-v").textContent = `${Math.round((z / (96 / 25.4)) * 100)}%`;
}

// ---------------------------------------------------------------- 判断
function heldPane() {
  if (!S.held.length) return [note("判断待ちはありません。AIの案が人の手の所を変えようとすると、ここに並びます")];
  heldFocus = Math.min(heldFocus, S.held.length - 1);
  return [note("J・K で選び、A で受け入れ、X で断ります。行を押すと、その場所を出します"),
    h("div", { class: "list" }, S.held.map((x, i) => {
      const page = S.m.find("pages", x.page_id);
      return h("div", { class: `held-row${i === heldFocus ? " cur" : ""}`, "data-i": i, onclick: () => { heldFocus = i; jump({ page_id: x.page_id, location: { table: x.target_table, id: x.target_id } }); render(); } },
        h("div", { class: "row wrap" }, flag("判断待ち", "warn"), h("span", { class: "meta", text: `${page ? `${page.number} ページ・` : ""}${tableName(x.target_table)}・${fieldName(x.field)}` })),
        h("div", { class: "kv held-kv" }, h("span", { class: "k", text: "今" }), h("div", { class: "v mono", text: short(x.current_value) }),
          h("span", { class: "k", text: "AIの案" }), h("div", { class: "v mono", text: short(x.proposed_value) })),
        h("div", { class: "row" },
          h("button", { class: "btn sm", onclick: (e) => { e.stopPropagation(); decide(x, "accept"); } }, h("i", { "data-lucide": "check" }), "受け入れる", h("kbd", { text: "A" })),
          h("button", { class: "btn sm", onclick: (e) => { e.stopPropagation(); decide(x, "reject"); } }, h("i", { "data-lucide": "x" }), "断る", h("kbd", { text: "X" }))));
    }))];
}

const tableName = (t) => ({ panels: "コマ", text_items: "文字", page_items: "トーン・図形", panel_layers: "層", pages: "ページ" }[t] || t);
function short(v) { const s = typeof v === "string" ? v : JSON.stringify(v); return s && s.length > 80 ? `${s.slice(0, 80)}…` : s ?? "（無し）"; }

function decide(x, decision) {
  change(decision === "accept" ? "判断：受け入れる" : "判断：断る", [{ type: "resolve_held_change", id: x.id, decision }], { pages: [x.page_id || S.pageId], reload: true });
}
export function heldStep(d) { if (!S.held.length) return; openTab("held"); heldFocus = (heldFocus + d + S.held.length) % S.held.length; const x = S.held[heldFocus]; jump({ page_id: x.page_id, location: { table: x.target_table, id: x.target_id } }); render(); }
export function heldDecide(d) { if (S.tab !== "held" || !S.held[heldFocus]) return; decide(S.held[heldFocus], d); }

// ---------------------------------------------------------------- 道具
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
  const t = S.tool, spec = S.m.spec(), prefs = S.m.work.preferences || {};
  if (t === "select") return [sec("選ぶ", note("コマ・フキダシ・文字を押すと選べます。コマを2回押すとコマの絵を動かせます。文字は2回押すとその場で打てます"))];
  if (t === "hand") return [sec("手のひら", note("ドラッグで動かします。スペースを押している間と、真ん中のボタンでも動かせます。Ctrl とホイールで広げる・縮める"))];
  if (t === "frame") {
    const fs = prefs.frame_style;
    return [sec("コマ枠",
      seg([["move", "動かす", "move"], ["edit", "角を直す", "spline"], ["add", "足す", "square-plus"], ["join", "合わせる", "merge"]], S.frameMode, setFrameMode, "コマ枠の操作"),
      note({ move: "コマを押して動かす・角の掴みで大きさを変える", edit: "コマを押すと角ごとの掴みが出ます", add: "ページの空いた所を押すとコマを足します", join: "合わせる2つのコマを順に押します" }[S.frameMode]),
      kv(["コマの間（横）", num(spec.gutter_x_mm, (v) => setSpec({ gutter_x_mm: v }), { min: 0, step: 0.5, unit: "mm", label: "コマの間（横）" })],
         ["コマの間（縦）", num(spec.gutter_y_mm, (v) => setSpec({ gutter_y_mm: v }), { min: 0, step: 0.5, unit: "mm", label: "コマの間（縦）" })],
         ["枠の線の太さ", num(fs ? fs.line_width_mm : null, (v) => setFrameDefault({ line_width_mm: v }), { min: 0, step: 0.05, unit: "mm", label: "枠の線の太さ" })],
         ["枠の線の色", color(fs ? fs.line_color : "#000000", (v) => setFrameDefault({ line_color: v }), "枠の線の色")]),
      fs ? h("p", { class: "meta", text: "作品の標準の枠です。自分の線を持つコマ（右の欄で変えたコマ）は変わりません" })
         : note("作品の標準の枠の線が決まっていません。書き出しで止まります。太さを入れると決まります", "need"))];
  }
  if (t === "knife") {
    const k = S.knife;
    const auto = k.direction === "vertical" ? spec.gutter_x_mm : spec.gutter_y_mm;
    return [sec("ナイフ",
      seg([["horizontal", "横", "minus"], ["vertical", "縦", "grip-vertical"], ["slanted", "斜め", "slash"]], k.direction, (v) => { k.direction = v; S.view.knife = k; render(); }, "切る向き"),
      kv(k.direction === "slanted" ? ["角度", num(k.angle, (v) => { k.angle = v; }, { min: -89, max: 89, step: 1, unit: "度", label: "角度" })] : [null, ""],
         ["間", h("span", { class: "row" }, num(k.gap ?? auto, (v) => { k.gap = v; render(); }, { min: 0, step: 0.5, unit: "mm", label: "分けた間" }),
           k.gap !== null ? h("button", { class: "btn sm ghost", onclick: () => { k.gap = null; render(); } }, "コマの間に合わせる") : h("span", { class: "meta", text: "コマの間と同じ" }))]),
      note("コマの上で線の位置を見て、押すと分けます。分けた小さい方が新しいコマです"))];
  }
  if (t === "balloon" || t === "text") {
    const b = S.balloon;
    return [sec(t === "balloon" ? "フキダシ" : "文字",
      t === "balloon" ? seg(BALLOON_FORMS.map(([v, l, i]) => [v, l, i]), b.form, (v) => { b.form = v; render(); }, "フキダシの形") : null,
      kv(["文字の大きさ", num(b.font_size_pt, (v) => { b.font_size_pt = v; }, { min: 1, step: 0.5, unit: "pt", label: "文字の大きさ" })],
         ...(t === "balloon" ? [["線の太さ", num(b.line_width_mm, (v) => { b.line_width_mm = v; }, { min: 0, step: 0.05, unit: "mm", label: "線の太さ" })],
           ["線の色", color(b.line_color, (v) => { b.line_color = v; }, "線の色")], ["塗り", color(b.fill_color, (v) => { b.fill_color = v; }, "塗り")],
           ...(S.m.caps.print ? [["しっぽの根元", num(b.tail_base_width_mm, (v) => { b.tail_base_width_mm = v; }, { min: 0.1, step: 0.5, unit: "mm", label: "しっぽの根元の幅" })]] : [])] : [])),
      note(`コマの中を押すと${t === "balloon" ? "フキダシ" : "文字"}を足し、そのまま打てます。縦書きか横書きかは作品の文字の向きに従います`))];
  }
  if (t === "tone") {
    const tn = S.tone;
    return [sec("トーン",
      seg(TONE_KINDS, tn.kind, (v) => { tn.kind = v; render(); }, "トーンの種類"),
      kv(["濃さ", range(tn.density, null, (v) => { tn.density = v; }, { label: "濃さ" })],
         ...(["dots", "lines", "gradient"].includes(tn.kind) ? [["線数", num(tn.lines_per_inch, (v) => { tn.lines_per_inch = v; }, { min: 1, step: 5, unit: "線", label: "線数" })]] : [])),
      note("コマを押すと、そのコマいっぱいに貼ります（トーンはコマの形で切り抜きます）"))];
  }
  return [];
}

function setSpec(ch) { change("ページの寸法", [{ type: "set_work_settings", page_spec: { ...S.m.spec(), ...ch } }], { pages: S.m.pages(S.episodeId).map((p) => p.id) }); }
function setPrefs(ch, label) { change(label, [{ type: "set_work_settings", preferences: { ...(S.m.work.preferences || {}), ...ch } }], { pages: S.m.pages(S.episodeId).map((p) => p.id) }); }
function setFrameDefault(ch) {
  const fs = (S.m.work.preferences || {}).frame_style;
  const next = { line_width_mm: 0.5, line_color: "#000000", ...(fs || {}), ...ch };
  if (!fs && ch.line_width_mm === undefined) { toast("先に線の太さを入れてください", "need"); render(); return; }
  setPrefs({ frame_style: next }, "標準の枠の線");
}

function common(r, kind) {
  const hand = (r.human_hand_fields || []);
  const held = S.held.filter((x) => x.target_id === r.id);
  return [
    h("div", { class: "row wrap" },
      hand.length ? flag(`人の手：${hand.map(fieldName).join("・")}`, "warn", "人が変えた所。AIの案はここを直接は変えず、判断待ちになります") : flag("人の手の印なし", "mut"),
      held.length ? h("button", { class: "flag warn", onclick: () => openTab("held") }, `判断待ち ${held.length} 件`) : null),
    h("div", { class: "row wrap" },
      h("button", { class: "btn sm", "aria-pressed": String(!!r.fixed), onclick: () => change(r.fixed ? "動かさない印を外す" : "動かさない印を付ける", [{ type: "set_fixed", target_kind: kind, id: r.id, fixed: !r.fixed }], { pages: [r.page_id] }) },
        h("i", { "data-lucide": r.fixed ? "lock" : "lock-open" }), r.fixed ? "動かさない（外す）" : "動かさない印を付ける"),
      h("button", { class: "btn sm ghost", onclick: removeSelected, disabled: !!r.fixed }, h("i", { "data-lucide": "trash-2" }), "消す")),
  ];
}

function panelPane(p) {
  const prefs = S.m.work.preferences || {};
  const fs = p.frame_style;
  const setStyle = (ch) => change("コマの枠の線", [{ type: "update_panel", id: p.id, frame_style: { ...(fs || prefs.frame_style || { line_width_mm: 0.5, line_color: "#000000" }), ...ch } }], { pages: [p.page_id] });
  const layers = S.m.layers(p.id);
  return [sec(`コマ ${p.order}`, ...common(p, "panel"),
    kv(["枠の線", h("span", { class: "row" }, num(fs ? fs.line_width_mm : prefs.frame_style ? prefs.frame_style.line_width_mm : null, (v) => setStyle({ line_width_mm: v }), { min: 0, step: 0.05, unit: "mm", label: "このコマの枠の線の太さ" }),
         fs ? h("button", { class: "btn sm ghost", onclick: () => change("コマの枠の線を標準に戻す", [{ type: "update_panel", id: p.id, frame_style: null }], { pages: [p.page_id] }) }, "標準に戻す") : h("span", { class: "meta", text: "作品の標準" }))],
       ["線の色", color((fs || prefs.frame_style || {}).line_color, (v) => setStyle({ line_color: v }), "このコマの枠の線の色")],
       ["地の色", h("span", { class: "row" }, color((fs || {}).fill_color || "#FFFFFF", (v) => setStyle({ fill_color: v }), "このコマの地の色"),
         fs && fs.fill_color ? h("button", { class: "btn sm ghost", onclick: () => setStyle({ fill_color: null }) }, "塗らない") : h("span", { class: "meta", text: "塗らない" }))])),
  sec("コマの絵",
    p.image_id ? h("div", { class: "row wrap" }, flag(p.image_placement ? "置いてある" : "置き場が決まっていない", p.image_placement ? "mut" : "warn"), h("span", { class: "meta", text: `重ねた層 ${layers.length} 枚` })) : note("このコマには絵がありません"),
    h("div", { class: "row wrap" },
      h("a", { class: "btn sm ai-o", href: workbenchUrl(p.id), onclick: (e) => { e.preventDefault(); openWorkbench(p.id); } }, h("i", { "data-lucide": "sparkles" }), "このコマの絵を頼む", h("kbd", { text: "L" })),
      p.image_id && p.image_placement ? h("button", { class: "btn sm", onclick: () => S.view.hooks.onImageEdit(p.id) }, h("i", { "data-lucide": "move" }), "絵を動かす") : null),
    placeImageForm(p))];
}

// 絵を置く：手元のファイルを上げてコマの絵にし、コマの外接の四角を覆う大きさで置く
function placeImageForm(p) {
  const origin = h("select", { class: "field", "aria-label": "絵の出どころ" }, h("option", { value: "human_drawn", text: "自分で描いた絵" }), h("option", { value: "imported", text: "持ち込んだ絵" }));
  const src = h("input", { class: "field", placeholder: "出どころ（持ち込んだ絵のとき。例：撮った写真の元）", "aria-label": "出どころの書き付け" });
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", class: "field file", "aria-label": "置く絵のファイル" });
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    if (origin.value === "imported" && !src.value.trim()) { toast("持ち込んだ絵には出どころを書いてください", "need"); file.value = ""; return; }
    let bmp;
    try { bmp = await createImageBitmap(f); } catch (e) { fail(e, "絵を読むこと"); return; }
    const [x0, y0, x1, y1] = bbox(p.frame.polygon_mm);
    const k = Math.max((x1 - x0) / bmp.width, (y1 - y0) / bmp.height);
    const w = bmp.width * k, hh = bmp.height * k, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const placement = { crop_px: [0, 0, bmp.width, bmp.height], dest_box_mm: [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2].map(r2), rotation_deg: 0, skew_x_deg: 0, skew_y_deg: 0, flip_h: false, flip_v: false };
    change("絵を置く", [], { pages: [p.page_id], reload: true, send: async () => {
      const fd = new FormData();
      fd.append("image", f);
      fd.append("origin", origin.value);
      if (src.value.trim()) fd.append("source_note", src.value.trim());
      const up = await api.postForm(`/works/${S.workId}/panels/${p.id}/image`, fd);
      const ev = await api.op(S.workId, { type: "update_panel", id: p.id, image_placement: placement });
      return [up.select_event_id, ev.event_id];
    } });
  });
  return h("details", { class: "disc" }, h("summary", { text: "絵を置く" }), kv(["出どころ", origin], [null, src], [null, file]));
}

function textPane(t) {
  const m = S.m, prefs = m.work.preferences || {};
  const bs = t.balloon_shape && t.balloon_shape.kind !== "none" ? t.balloon_shape : null;
  const up = (ch, label = "文字の設定") => change(label, [{ type: "update_text_item", id: t.id, ...ch }], { pages: [t.page_id] });
  const ta = h("textarea", { class: "field area", rows: 3, "aria-label": "文字", value: t.text });
  ta.value = t.text;
  // 打っている間は画面だけ書き換えて見せ、欄を出たときに送る
  ta.addEventListener("input", () => { t.text = ta.value; S.view.rebuild(); });
  ta.addEventListener("change", () => { t.text = ta.__orig ?? t.text; S.view.hooks.onEditDone(t.id, ta.value); });
  ta.__orig = t.text;
  ta.addEventListener("focus", () => { ta.__orig = t.text; });
  const ts = t.typesetting;
  const tsBase = ts || prefs.typesetting || null;
  const setTs = (ch) => up({ typesetting: { line_spacing_ratio: 0.2, line_break: "phrase", tate_chu_yoko_max_digits: 2, tate_chu_yoko_marks: true, align: "start", ...(tsBase || {}), ...ch } }, "組版");
  const out = [sec(TEXT_KINDS.find((k) => k[0] === t.item_kind)?.[1] || "文字", ...common(t, "text_item"),
    seg(TEXT_KINDS, t.item_kind, (v) => up({ item_kind: v }, "文字の種類"), "文字の種類"),
    ta,
    kv(["縦横", seg([["vertical", "縦", "arrow-down"], ["horizontal", "横", "arrow-right"]], t.writing_direction, (v) => up({ writing_direction: v }, "縦横"), "縦書き・横書き")],
       ["大きさ", num(t.font_size_pt, (v) => up({ font_size_pt: v }, "文字の大きさ"), { min: 1, step: 0.5, unit: "pt", label: "文字の大きさ" })],
       ["書体", h("input", { class: "field", value: t.font_family || "", placeholder: (prefs.fonts_by_kind || {})[t.item_kind] ? `作品の標準：${prefs.fonts_by_kind[t.item_kind]}` : "未設定（書き出しで止まります）", "aria-label": "書体",
         onchange: (e) => up({ font_family: e.target.value.trim() || null }, "書体") })],
       ["不透明度", range(t.opacity ?? 1, null, (v) => up({ opacity: v }, "不透明度"), { label: "不透明度" })]),
    h("p", { class: "meta", text: "画面の縦組みはブラウザの組み方で、書き出し（サーバーの組版）と同じ所で改行するかは未検証です。入りきるかは「確かめ」で測ります" }))];
  if (m.caps.print) {
    out.push(sec("組版", ts ? null : note(prefs.typesetting ? "作品の標準の組版を使っています" : "組版が決まっていません。値を変えるとこの文字の組版になります", prefs.typesetting ? "" : "need"),
      kv(["行間", num(tsBase ? tsBase.line_spacing_ratio : null, (v) => setTs({ line_spacing_ratio: v }), { min: 0, step: 0.05, label: "行間（文字の大きさとの比）" })],
         ["改行", seg([["phrase", "文節"], ["character", "字"], ["none", "しない"]], tsBase ? tsBase.line_break : null, (v) => setTs({ line_break: v }), "改行のしかた")],
         ["縦中横", num(tsBase ? tsBase.tate_chu_yoko_max_digits : null, (v) => setTs({ tate_chu_yoko_max_digits: v }), { min: 0, max: 4, step: 1, unit: "桁まで", label: "縦中横にする数字の桁" })],
         ["!? を縦中横", seg([["1", "する"], ["0", "しない"]], tsBase ? (tsBase.tate_chu_yoko_marks ? "1" : "0") : null, (v) => setTs({ tate_chu_yoko_marks: v === "1" }), "感嘆符・疑問符の縦中横")],
         ["揃え", seg([["start", "頭"], ["center", "真ん中"]], tsBase ? tsBase.align : null, (v) => setTs({ align: v }), "揃え")]),
      ts ? h("button", { class: "btn sm ghost", onclick: () => up({ typesetting: null }, "組版を標準に戻す") }, "作品の標準に戻す") : null));
  } else out.push(sec("組版", noPrint()));
  if (bs) {
    const box = t.box_mm;
    out.push(sec("フキダシの形",
      seg(BALLOON_FORMS.map(([v, l, i]) => [v, l, i]), null, (v) => up({ balloon_shape: { ...bs, outline_mm: balloonOutline(v, box, 3) } }, "フキダシの形"), "形を作り直す"),
      kv(["線の太さ", num(bs.line_width_mm, (v) => up({ balloon_shape: { ...bs, line_width_mm: v } }, "フキダシの線"), { min: 0, step: 0.05, unit: "mm", label: "線の太さ" })],
         ["線の色", color(bs.line_color, (v) => up({ balloon_shape: { ...bs, line_color: v } }, "フキダシの線の色"), "線の色")],
         ["塗り", color(bs.fill_color || "#FFFFFF", (v) => up({ balloon_shape: { ...bs, fill_color: v } }, "フキダシの塗り"), "塗り")],
         ...(m.caps.print ? [["しっぽの根元", num(bs.tail_base_width_mm, (v) => up({ balloon_shape: { ...bs, tail_base_width_mm: v, tail_bend_ratio: bs.tail_bend_ratio ?? 0 } }, "しっぽ"), { min: 0.1, step: 0.5, unit: "mm", label: "しっぽの根元の幅" })],
           ["しっぽの曲がり", num(bs.tail_bend_ratio, (v) => up({ balloon_shape: { ...bs, tail_bend_ratio: v, tail_base_width_mm: bs.tail_base_width_mm ?? 4 } }, "しっぽ"), { min: -1, max: 1, step: 0.1, label: "しっぽの曲がり" })]] : []),
         ["しっぽ", t.tail_target_mm ? h("button", { class: "btn sm ghost", onclick: () => up({ tail_target_mm: null }, "しっぽを消す") }, "しっぽを消す") : h("span", { class: "meta", text: "白い丸の掴みを引くと出ます" })],
         ["前とつなぐ", seg([["1", "つなぐ"], ["0", "つながない"]], t.joined_to_previous ? "1" : "0", (v) => up({ joined_to_previous: v === "1" }, "フキダシをつなぐ"), "前のフキダシとつなぐ")]),
      m.caps.print && t.tail_target_mm && (bs.tail_base_width_mm == null || bs.tail_bend_ratio == null) ? note("しっぽの根元の幅・曲がりが決まっていません。書き出しで止まります", "need") : null,
      h("p", { class: "meta", text: "形を押すと、今の文字の箱に合わせて外形を作り直します。つないだフキダシは、同じコマの前（順が1つ前）のフキダシと線を消して1つに見せます" })));
  }
  return out;
}

function tonePane(t) {
  const up = (ch, label = "トーン") => change(label, [{ type: "update_page_item", id: t.id, ...ch }], { pages: [t.page_id] });
  const sp = t.spec;
  const setSpec = (ch) => up({ spec: { ...sp, ...ch } });
  if (t.item_kind !== "tone") return [sec("図形", ...common(t, "page_item"), note("図形の中身を描く・直すのは、この画面にまだありません", "need"))];
  return [sec(`トーン：${(TONE_KINDS.find((k) => k[0] === sp.kind) || [])[1] || sp.kind}`, ...common(t, "page_item"),
    kv(["濃さ", range(sp.density, null, (v) => setSpec({ density: v }), { label: "濃さ" })],
       ...(sp.lines_per_inch != null ? [["線数", num(sp.lines_per_inch, (v) => setSpec({ lines_per_inch: v }), { min: 1, step: 5, unit: "線", label: "線数" })]] : []),
       ["角度", num(sp.angle_deg, (v) => setSpec({ angle_deg: v }), { step: 1, unit: "度", label: "角度" })],
       ...(sp.line_count != null ? [["本数", num(sp.line_count, (v) => setSpec({ line_count: Math.round(v) }), { min: 1, step: 10, label: "本数" })]] : []),
       ...(sp.density_end != null ? [["終わりの濃さ", range(sp.density_end, null, (v) => setSpec({ density_end: v }), { label: "終わりの濃さ" })]] : []),
       ["不透明度", range(t.opacity, null, (v) => up({ opacity: v }), { label: "不透明度" })],
       ["切り抜き", h("span", { class: "meta", text: sp.target.kind === "panel" ? "コマの形" : sp.target.kind === "polygon" ? "囲んだ形" : "絵の形（未対応の表示）" })]),
    h("p", { class: "meta", text: "画面の網点は目安です。書き出しの網点はサーバーが描きます。細かすぎて縞が出る倍率では灰色で見せています" }))];
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
  out.push(sec(`このページ（${page.number} ページ${side ? `・${side === "left" ? "左" : "右"}` : ""}）`,
    kv(["1ページ目", seg([["left", "左に置く"], ["right", "右に置く"]], fl === true ? "left" : fl === false ? "right" : null,
      (v) => change("1ページ目の左右", [{ type: "set_work_settings", first_page_is_left: v === "left" }], { pages: pages.map((p) => p.id) }), "1ページ目の左右")]),
    fl === null || fl === undefined ? note("1ページ目を左右どちらに置くかが決まっていません。見開きで並べられず、書き出しでも止まります", "need") : null));
  if (!m.caps.print) { out.push(noPrint()); return out; }
  const prefs = w.preferences || {};
  const pr = prefs.print;
  const nb = prefs.nombre;
  out.push(kv(
    ["種類", seg(PAGE_KINDS, page.page_kind, (v) => up({ page_kind: v }, "ページの種類"), "ページの種類")],
    ["色", seg(COLOR_MODES, page.color_mode, (v) => up({ color_mode: v }, "ページの色"), "ページの色")],
    ["解像度", h("span", { class: "row" }, num(page.dpi, (v) => up({ dpi: Math.round(v) }, "解像度"), { min: 1, max: 2400, step: 1, unit: "dpi", label: "解像度" }),
      h("span", { class: "meta", text: page.dpi ? "" : pr ? `入稿の設定：${pr.dpi_by_color_mode[page.color_mode || pr.color_mode] ?? "未設定"}` : "入稿の設定が無い" }))],
    ["ノンブル", seg(NOMBRE, page.nombre_display, (v) => up({ nombre_display: v }, "ノンブル"), "ノンブルの出し方")]));
  if (!page.page_kind || !page.color_mode || !page.nombre_display) {
    out.push(h("p", { class: "meta", text: `空いている項目は作品の入稿の設定に従います（${pr ? "色" : "入稿の設定が無い"}${nb ? "・ノンブルはページの種類ごとの設定" : "・ノンブルの設定が無い"}）` }));
  }
  // 見開き
  const sp = m.spreadOf(page.id);
  const units = sides ? m.units(S.episodeId) : null;
  const u = units ? units.find((x) => (x.left && x.left.id === page.id) || (x.right && x.right.id === page.id)) : null;
  if (sp) {
    out.push(h("div", { class: "row wrap" }, flag("見開き", "on"), h("span", { class: "meta", text: `${m.find("pages", sp.first_page_id).number}–${m.find("pages", sp.second_page_id).number} ページ` }),
      h("button", { class: "btn sm ghost", onclick: () => change("見開きを解く", [{ type: "set_removed", target_kind: "spread", id: sp.id, removed: true }], { pages: [sp.first_page_id, sp.second_page_id], reload: true }) }, "見開きを解く")));
  } else if (u && u.left && u.right) {
    const rtl = w.reading_direction === "rtl";
    const [a, b] = rtl ? [u.right, u.left] : [u.left, u.right];
    out.push(h("button", { class: "btn sm", onclick: () => change("見開きにする", [{ type: "add_spread", id: newId(), first_page_id: a.id, second_page_id: b.id }], { pages: [a.id, b.id], reload: true }) },
      h("i", { "data-lucide": "book-open" }), `${a.number}–${b.number} ページを見開きにする`));
  } else if (sides) out.push(h("p", { class: "meta", text: "向かいのページが無いので見開きにできません" }));
  out.push(h("div", { class: "row wrap" }, h("button", { class: "btn sm ghost", onclick: () => removePage(page) }, h("i", { "data-lucide": "trash-2" }), "このページを抜く")));
  return out;
}

function removePage(page) {
  change("ページを抜く", [{ type: "set_removed", target_kind: "page", id: page.id, removed: true }], { pages: [page.id], reload: true });
}

async function addPage() {
  if (!S.episodeId) return;
  const pages = S.m.pages(S.episodeId);
  const id = newId();
  const ids = change("ページを足す", [{ type: "add_page", id, episode_id: S.episodeId, number: Math.max(0, ...pages.map((p) => p.number)) + 1 }], { pages: [id, ...(S.pageId ? [S.pageId] : [])], reload: true });
  if (ids) { await ids.catch(() => {}); await S.saver.idle().catch(() => {}); selectPage(id); }
}

// ---------------------------------------------------------------- 層・見せる物
function layersPane() {
  const out = [];
  const sh = S.show, lk = S.lock;
  const tog = (obj, k, label, lock) => h("button", { class: "chip", "aria-pressed": String(lock ? !!obj[k] : obj[k] !== false), onclick: () => { obj[k] = lock ? !obj[k] : obj[k] === false; draw(); } },
    h("i", { "data-lucide": lock ? (obj[k] ? "lock" : "lock-open") : obj[k] !== false ? "eye" : "eye-off" }), label);
  out.push(sec("見せるもの（W）",
    h("div", { class: "chips" }, tog(sh.cat, "art", "コマの絵"), tog(sh.cat, "frame", "コマ枠"), tog(sh.cat, "tone", "トーン"), tog(sh.cat, "balloon", "フキダシ"), tog(sh.cat, "type", "文字"), tog(sh.cat, "sfx", "描き文字")),
    h("div", { class: "chips" }, tog(sh, "guide", "基本枠"), tog(sh, "safe", "安全線"), tog(sh, "grid", "方眼"), tog(sh, "boxes", "文字の箱"), tog(sh, "hand", "人の手の印"), tog(sh, "held", "判断待ちの印")),
    h("p", { class: "meta", text: "見せる・隠すは画面だけで、原稿の値は変えません" })));
  out.push(sec("触らない（画面だけ）",
    h("div", { class: "chips" }, tog(lk, "frame", "コマ枠", true), tog(lk, "balloon", "フキダシ・文字", true), tog(lk, "sfx", "描き文字", true), tog(lk, "tone", "トーン", true))));
  if (!S.pageId) return out;
  // トーン・図形（ページの層）
  const items = S.m.items(S.pageId);
  const itemRow = (t, i) => {
    const up = (ch, label) => change(label, [{ type: "update_page_item", id: t.id, ...ch }], { pages: [t.page_id] });
    const swap = (d) => {
      const o = items[i + d];
      if (!o) return;
      change("重なりの順", [{ type: "update_page_item", id: t.id, stack_order: o.stack_order }, { type: "update_page_item", id: o.id, stack_order: t.stack_order }], { pages: [t.page_id] });
    };
    return h("div", { class: `lrow${S.sel && S.sel.id === t.id ? " cur" : ""}` },
      h("button", { class: "ibtn", title: t.visible ? "隠す" : "見せる", "aria-label": t.visible ? "隠す" : "見せる", onclick: () => up({ visible: !t.visible }, t.visible ? "隠す" : "見せる") }, h("i", { "data-lucide": t.visible ? "eye" : "eye-off" })),
      h("button", { class: "grow lname", onclick: () => { S.tool !== "tone" && setTool("tone"); S.sel = { kind: "tone", id: t.id, pageId: t.page_id }; draw(); } },
        t.item_kind === "tone" ? `トーン：${(TONE_KINDS.find((k) => k[0] === t.spec.kind) || [])[1] || t.spec.kind}` : "図形", (t.human_hand_fields || []).length ? flag("人の手", "warn") : null),
      range(t.opacity, null, (v) => up({ opacity: v }, "不透明度"), { label: "不透明度" }),
      h("button", { class: "ibtn", title: t.fixed ? "動かさない印を外す" : "動かさない印を付ける", "aria-label": "動かさない印", "aria-pressed": String(!!t.fixed), onclick: () => change("動かさない印", [{ type: "set_fixed", target_kind: "page_item", id: t.id, fixed: !t.fixed }], { pages: [t.page_id] }) }, h("i", { "data-lucide": t.fixed ? "lock" : "lock-open" })),
      h("button", { class: "ibtn", title: "上へ", "aria-label": "上へ", disabled: i === items.length - 1, onclick: () => swap(1) }, h("i", { "data-lucide": "chevron-up" })),
      h("button", { class: "ibtn", title: "下へ", "aria-label": "下へ", disabled: i === 0, onclick: () => swap(-1) }, h("i", { "data-lucide": "chevron-down" })));
  };
  out.push(sec("トーン・図形（上ほど手前）", items.length ? h("div", { class: "list" }, [...items].map(itemRow).reverse()) : h("p", { class: "meta", text: "このページにトーン・図形はありません" })));
  // コマの層
  const rows = [];
  for (const p of S.m.panels(S.pageId)) {
    const ls = S.m.layers(p.id);
    if (!ls.length) continue;
    rows.push(h("div", { class: "lbl", text: `コマ ${p.order}` }));
    ls.forEach((l, i) => {
      const up = (ch, label) => change(label, [{ type: "update_panel_layer", id: l.id, ...ch }], { pages: [p.page_id] });
      const swap = (d) => { const o = ls[i + d]; if (o) change("層の順", [{ type: "update_panel_layer", id: l.id, stack_order: o.stack_order }, { type: "update_panel_layer", id: o.id, stack_order: l.stack_order }], { pages: [p.page_id] }); };
      rows.push(h("div", { class: "lrow" },
        h("button", { class: "ibtn", "aria-label": l.visible ? "隠す" : "見せる", title: l.visible ? "隠す" : "見せる", onclick: () => up({ visible: !l.visible }, l.visible ? "層を隠す" : "層を見せる") }, h("i", { "data-lucide": l.visible ? "eye" : "eye-off" })),
        h("span", { class: "grow lname" }, l.role, l.placement ? null : flag("置き場なし", "warn", "置き場が無い層は描きません")),
        range(l.opacity, null, (v) => up({ opacity: v }, "層の不透明度"), { label: "不透明度" }),
        h("button", { class: "ibtn", "aria-label": "動かさない印", title: "動かさない印", "aria-pressed": String(!!l.fixed), onclick: () => change("動かさない印", [{ type: "set_fixed", target_kind: "panel_layer", id: l.id, fixed: !l.fixed }], { pages: [p.page_id] }) }, h("i", { "data-lucide": l.fixed ? "lock" : "lock-open" })),
        h("button", { class: "ibtn", "aria-label": "上へ", title: "上へ", disabled: i === ls.length - 1, onclick: () => swap(1) }, h("i", { "data-lucide": "chevron-up" })),
        h("button", { class: "ibtn", "aria-label": "下へ", title: "下へ", disabled: i === 0, onclick: () => swap(-1) }, h("i", { "data-lucide": "chevron-down" }))));
    });
  }
  out.push(sec("コマの絵の層", rows.length ? h("div", { class: "list" }, rows) : h("p", { class: "meta", text: "このページのコマに重ねた層はありません（層は画像生成の画面で作ります）" })));
  return out;
}

// ---------------------------------------------------------------- 確かめ（入稿前）
function checkPane() {
  if (!S.m.caps.print) return [noPrint()];
  const pf = S.preflight;
  const out = [h("div", { class: "row wrap" },
    h("button", { class: "btn sm", id: "pf-page", onclick: () => runPreflight([S.pageId]) }, h("i", { "data-lucide": "file-check" }), "このページを確かめる"),
    h("button", { class: "btn sm", id: "pf-ep", onclick: () => runPreflight(S.m.pages(S.episodeId).map((p) => p.id)) }, h("i", { "data-lucide": "files" }), "この話を全部確かめる"))];
  if (!pf) { out.push(note("書き出しの前に、問題をページと場所ごとに並べます。行を押すとその場所を出します")); return out; }
  if (pf.running) { out.push(note("確かめています", "", "loader")); return out; }
  out.push(h("div", { class: "row wrap" }, flag(`止まる ${pf.errors}`, pf.errors ? "bad" : "mut"), flag(`気を付ける ${pf.warnings}`, pf.warnings ? "warn" : "mut"),
    h("span", { class: "meta", text: `${new Date(pf.at).toLocaleTimeString()} に確かめた結果。直したらもう一度押してください` })));
  if (!pf.issues.length) { out.push(note("問題はありません")); return out; }
  const byPage = new Map();
  for (const x of pf.issues) { const k = x.page_id || ""; if (!byPage.has(k)) byPage.set(k, []); byPage.get(k).push(x); }
  for (const [pid, list] of byPage) {
    const page = pid ? S.m.find("pages", pid) : null;
    out.push(sec(page ? `${page.number} ページ` : "作品全体", h("div", { class: "list" }, list.map((x) =>
      h("button", { class: "issue", onclick: () => jump(x) }, flag(x.severity === "error" ? "止まる" : "気を付ける", x.severity === "error" ? "bad" : "warn"),
        h("span", { class: "grow", text: x.message }), x.location ? h("i", { "data-lucide": "crosshair" }) : null)))));
  }
  return out;
}

async function runPreflight(pageIds) {
  try { await S.saver.idle(); } catch (e) { fail(e, "確かめ"); return; }
  S.preflight = { running: true };
  render();
  try {
    const r = await api.post(`/works/${S.workId}/preflight`, { page_ids: pageIds });
    S.preflight = { ...r, at: Date.now() };
  } catch (e) { S.preflight = null; fail(e, "確かめ"); }
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
  if (!S.view.select(kind, owner.id, false)) S.view.flash(pageId, box);
  else S.view.flash(pageId, box);
}

// ---------------------------------------------------------------- 下のページの一覧
let sortable = null;
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
      h("button", { class: "pthumb", style: `aspect-ratio:${spec.trim_width_mm}/${spec.trim_height_mm}`, title: `${p.number} ページを出す`, onclick: () => selectPage(p.id) }, svg),
      h("div", { class: "pmeta" },
        h("span", { class: "pnum num", text: String(p.number) }),
        side ? h("span", { class: "meta", text: side === "left" ? "左" : "右" }) : null,
        sp ? h("i", { "data-lucide": "book-open", title: "見開き" }) : null,
        heldN.get(p.id) ? flag(`判断 ${heldN.get(p.id)}`, "warn") : null,
        issues.get(p.id) ? flag(`問題 ${issues.get(p.id)}`, "bad") : null),
      m.caps.print ? h("div", { class: "pmeta meta" },
        h("span", { text: (PAGE_KINDS.find((k) => k[0] === p.page_kind) || [null, "種類：標準"])[1] }),
        h("span", { text: (COLOR_MODES.find((k) => k[0] === p.color_mode) || [null, ""])[1] }),
        p.dpi ? h("span", { class: "num", text: `${p.dpi}dpi` }) : null,
        p.nombre_display ? h("span", { text: `ノンブル：${(NOMBRE.find((k) => k[0] === p.nombre_display) || [])[1]}` }) : null) : null);
  }));
  if (sortable) sortable.destroy();
  sortable = null;
  if (m.caps.print && window.Sortable) {
    sortable = new window.Sortable(host, {
      animation: 120, direction: "horizontal", ghostClass: "ghost", filter: ".pmeta", preventOnFilter: false,
      onEnd: (e) => {
        if (e.oldIndex === e.newIndex) return;
        const ids = $$(".pcard", host).map((c) => c.dataset.id);
        change("ページの並べ替え", [{ type: "reorder_pages", episode_id: S.episodeId, page_ids: ids }], { pages: ids, reload: true });
      },
    });
  }
  $("#pages-note").textContent = m.caps.print ? "ドラッグで並べ替え" : "並べ替えはこのサーバーにはありません";
  icons();
}
