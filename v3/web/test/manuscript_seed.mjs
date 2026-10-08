// 原稿の画面の試験と測定に使う作品を、操作の窓口から作る（本物のサーバーにも、偽のサーバーにも同じ手順で入れる）。
// B5（仕上がり 182×257mm・基本枠 150×220mm・塗り足し 3mm）・600dpi・右から読む・縦書き。
// 1ページ目：コマ 6・フキダシ 10（うち2つはつなぐ）・トーン 3・コマの絵 2。2〜4ページ目：コマ少し。3–4ページを見開きにする。
import { deflateSync } from "node:zlib";
import { randomBytes } from "node:crypto";

const id = () => randomBytes(16).toString("hex");

export const PAGE_SPEC = { frame_width_mm: 150, frame_height_mm: 220, trim_width_mm: 182, trim_height_mm: 257, bleed_mm: 3, gutter_x_mm: 3, gutter_y_mm: 6 };
export const PRINT = { file_code: "MS", color_mode: "bilevel", dpi_by_color_mode: { bilevel: 600, grayscale: 350, color: 350 },
  bilevel: { threshold: 128, pdf_codec: "ccitt_g4", image_screen: { lines_per_inch: 60, angle_deg: 45, dot_shape: "round" } },
  safe_area: { top_mm: 10, bottom_mm: 10, gutter_mm: 12, outer_mm: 8 }, page_count_multiple: 4, page_count_scope: "episode" };
export const NOMBRE = { font_family: "IPAMincho", font_size_pt: 9, hidden_font_size_pt: 6, color: "#000000", start_number: 1, numbering_scope: "episode",
  position: { vertical: "bottom", horizontal: "outer", edge_mm: 5, side_mm: 5 }, hidden_position: { bottom_mm: 3, gutter_mm: 3 },
  display_by_kind: { cover: "none", color_page: "hidden", body: "visible", blank: "hidden" } };
export const TYPESETTING = { line_spacing_ratio: 0.15, line_break: "phrase", tate_chu_yoko_max_digits: 2, tate_chu_yoko_marks: true, align: "start" };

const rect = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

// 1ページ目のコマ（右から読むので右上が 1）
const P1 = [rect(77, 0, 150, 60), rect(0, 0, 74, 60), rect(0, 66, 150, 140), rect(102, 146, 150, 220), [[52, 146], [99, 146], [99, 220], [45, 220]], [[0, 146], [49, 146], [42, 220], [0, 220]]];
const LINES = ["ここが\n入口か", "誰も\nいない…", "待って！", "足音が\n聞こえる", "気のせい\nだろう", "風の音だ", "いや\n違う", "2人とも\n伏せて！!?", "砂が\n動いた", "来るぞ"];

function ellipse(box, pad = 3, n = 48) {
  const [x0, y0, x1, y1] = box, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, rx = (x1 - x0) / 2 + pad, ry = (y1 - y0) / 2 + pad;
  return Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return [Math.round((cx + rx * Math.cos(a)) * 100) / 100, Math.round((cy + ry * Math.sin(a)) * 100) / 100]; });
}

// 灰色の PNG（模様つき）を作る。w×h 画素
export function makePng(w, h, seed = 1) {
  const raw = Buffer.alloc((w + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w + 1)] = 0;
    for (let x = 0; x < w; x++) {
      const d = Math.hypot(x - w * 0.6, y - h * 0.45) / Math.max(w, h);
      let v = 235 - Math.floor(140 * Math.max(0, 0.5 - d)) - ((((x >> 5) + (y >> 5) + seed) & 7) === 0 ? 60 : 0);
      if (y > h * 0.72) v = 190 - Math.floor(((y - h * 0.72) / h) * 120) + (((x * 7 + y * 13 + seed) % 23) < 2 ? -50 : 0);
      raw[y * (w + 1) + 1 + x] = Math.max(0, Math.min(255, v));
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 0; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw, { level: 6 })), chunk("IEND", Buffer.alloc(0))]);
}
let CRC;
function crc32(buf) {
  if (!CRC) { CRC = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; CRC[n] = c; } }
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = CRC[(c ^ buf[i]) & 255] ^ (c >>> 8);
  return c ^ -1;
}

// call(method, path, body, form?) → JSON。form は { image: Buffer, origin: string }
export async function seed(call, title = "原稿の画面の試験") {
  const { id: wid } = await call("POST", "/works", { title, reading_direction: "rtl", text_direction: "vertical", medium: "paper" });
  const op = (o) => call("POST", `/works/${wid}/ops`, o);
  const vol = id(), ep = id(), pages = [id(), id(), id(), id()];
  await op({ type: "add_volume", id: vol, number: 1 });
  await op({ type: "add_episode", id: ep, volume_id: vol, number: 1, title: "砂の町" });
  for (let i = 0; i < pages.length; i++) await op({ type: "add_page", id: pages[i], episode_id: ep, number: i + 1 });
  await op({ type: "set_work_settings", page_spec: PAGE_SPEC, first_page_is_left: false,
            preferences: { fonts_by_kind: { balloon: "IPAMincho", caption: "IPAMincho", drawn_sfx: "IPAMincho" },
                           frame_style: { line_width_mm: 0.5, line_color: "#000000" }, typesetting: TYPESETTING, print: PRINT, nombre: NOMBRE } });
  // ナイフはコマの最小の大きさ（閾値）が無いと分けない（サーバーの決まり）。試験のための値
  await op({ type: "set_threshold", key: "panel_short_side_min_mm", value: { value: 10 }, source: "原稿の画面の試験", status: "unverified" });
  let order = 0;
  const panels = [];
  for (const poly of P1) {
    const pid = id();
    await op({ type: "add_panel", id: pid, page_id: pages[0], order: ++order, frame: { polygon_mm: poly, bleeds: false } });
    panels.push({ id: pid, poly });
  }
  // コマの絵：1 と 3 に置く（600dpi で置いたときの大きさに近い画素数）
  for (const [k, w, hh] of [[0, 1720, 1420], [2, 3540, 1750]]) {
    const p = panels[k];
    const r = await call("POST", `/works/${wid}/panels/${p.id}/image`, null, { image: makePng(w, hh, k + 1), origin: "human_drawn" });
    const xs = p.poly.map((q) => q[0]), ys = p.poly.map((q) => q[1]);
    await op({ type: "update_panel", id: p.id, image_placement: { crop_px: [0, 0, w, hh], dest_box_mm: [Math.min(...xs), Math.min(...ys), Math.min(...xs) + w * 25.4 / 600, Math.min(...ys) + hh * 25.4 / 600], rotation_deg: 0, skew_x_deg: 0, skew_y_deg: 0, flip_h: false, flip_v: false } });
    void r;
  }
  // フキダシ 10
  const at = [[0, 128, 6], [0, 88, 30], [1, 50, 8], [1, 18, 22], [2, 130, 72], [2, 108, 100], [2, 30, 78], [3, 128, 152], [4, 70, 152], [5, 20, 156]];
  const texts = [];
  for (let i = 0; i < at.length; i++) {
    const [k, x, y] = at[i];
    const lines = LINES[i].split("\n").length;
    const box = [x - lines * 3.3, y, x + lines * 3.3, y + 22];
    const tid = id();
    const joined = i === 5;
    await op({ type: "add_text_item", id: tid, panel_id: panels[k].id, item_kind: "balloon", order: i + 1, text: LINES[i], writing_direction: "vertical", font_size_pt: 9, decoration: { fill: "#000000" },
               box_mm: box, tail_target_mm: joined ? null : [x - 8, y + 34], joined_to_previous: joined,
               balloon_shape: { kind: "custom", outline_mm: ellipse(box), line_width_mm: 0.3, line_color: "#000000", fill_color: "#FFFFFF", tail_base_width_mm: 4, tail_bend_ratio: 0.15 } });
    texts.push(tid);
  }
  // トーン 3
  await op({ type: "add_page_item", id: id(), page_id: pages[0], panel_id: panels[2].id, item_kind: "tone", stack_order: 1, box_mm: [0, 66, 150, 140],
            spec: { kind: "dots", target: { kind: "panel", panel_id: panels[2].id }, color: "#000000", density: 0.25, lines_per_inch: 60, angle_deg: 45 } });
  await op({ type: "add_page_item", id: id(), page_id: pages[0], panel_id: panels[1].id, item_kind: "tone", stack_order: 2, box_mm: [0, 0, 74, 60],
            spec: { kind: "gradient", target: { kind: "panel", panel_id: panels[1].id }, color: "#000000", density: 0.55, density_end: 0, lines_per_inch: 60, angle_deg: 90, screen_angle_deg: 45, dot_shape: "round" } });
  await op({ type: "add_page_item", id: id(), page_id: pages[0], panel_id: panels[4].id, item_kind: "tone", stack_order: 3, box_mm: [45, 146, 99, 220],
            spec: { kind: "focus_lines", target: { kind: "panel", panel_id: panels[4].id }, color: "#000000", density: 0.6, line_count: 90, center_mm: [72, 185], inner_ratio: 0.4, seed: 7, angle_deg: 0 } });
  // 2〜4ページ
  const more = [[rect(0, 0, 150, 100), rect(78, 106, 150, 220), rect(0, 106, 75, 220)], [rect(0, 0, 150, 220)], [rect(0, 0, 150, 120), rect(0, 126, 150, 220)]];
  for (let i = 0; i < more.length; i++) for (const poly of more[i]) await op({ type: "add_panel", id: id(), page_id: pages[i + 1], order: ++order, frame: { polygon_mm: poly, bleeds: false } });
  await op({ type: "add_spread", id: id(), first_page_id: pages[2], second_page_id: pages[3] });
  await op({ type: "update_page", id: pages[0], page_kind: "body", color_mode: "bilevel", dpi: 600, nombre_display: "visible" });
  return { workId: wid, episodeId: ep, pages, panels: panels.map((p) => p.id), texts };
}

// fetch で本物のサーバーへ送る call
export function httpCall(base, user) {
  return async (method, path, body, form) => {
    const headers = { "X-V3-User": user };
    let payload;
    if (form) {
      const fd = new FormData();
      fd.append("image", new Blob([form.image], { type: "image/png" }), "seed.png");
      fd.append("origin", form.origin);
      payload = fd;
    } else if (body !== undefined && body !== null) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    const r = await fetch(base + path, { method, headers, body: payload });
    const text = await r.text();
    if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${text}`);
    return text ? JSON.parse(text) : null;
  };
}
