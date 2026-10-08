// 偽のサーバー（試験だけで使う。本物ではない）。
// 見開き・ページの並べ替え・ページの種類・入稿前の確かめなどの口が、まだ土台の枝（v3-server-plan）に入っていない間に、
// 原稿の画面を Playwright で通すためのもの。Playwright の route で口を横取りして答える。
// 操作は画面と同じ model.js で当て、取り消しは「取り消していない出来事を初めから当て直す」で作る。
// 本物と違う所：権限・人の手の守り（判断待ちを作る）・ナイフの番号の振り方・入稿前の確かめの中身（簡単な検査だけ）。
// 判断待ちは、偽のサーバーが試験のために2件作る（AIの案ではない）。
import { serveWeb } from "./ui_common.mjs";
import { Model } from "../manuscript/js/model.js";
import { bbox } from "../manuscript/js/geometry.js";

const clone = (x) => JSON.parse(JSON.stringify(x));
const hex = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");

export class MockServer {
  constructor(webDir) {
    this.webDir = webDir;
    this.works = new Map(); // id → { base, events: [{id, op, undone, kind}], images: Map, held: [] }
    this.label = "偽のサーバー";
  }

  empty(id, body) {
    return { work: { id, title: body.title, reading_direction: body.reading_direction, text_direction: body.text_direction, medium: body.medium,
                     trim_size: null, default_page_count: null, page_spec: null, first_page_is_left: null, preferences: {}, head_seq: 0 },
             volumes: [], episodes: [], pages: [], panels: [], text_items: [], panel_layers: [], page_items: [], spreads: [], thresholds: [] };
  }

  // 取り消していない出来事を初めから当てる
  state(w) {
    const data = clone(w.base);
    const m = new Model(data);
    for (const e of w.events) if (!e.undone && e.op) apply(m, e.op);
    data.work.head_seq = w.events.length;
    return data;
  }

  submit(wid, op) {
    const w = this.works.get(wid);
    // 当てられるか先に確かめる（当てられなければ 422）
    const m = new Model(this.state(w));
    apply(m, op);
    const e = { id: hex(), op, undone: false };
    w.events.push(e);
    return { event_id: e.id, seq: w.events.length, held_changes: [] };
  }

  undo(wid, eventId) {
    const w = this.works.get(wid);
    const target = w.events.find((e) => e.id === eventId);
    if (!target) throw Object.assign(new Error("無い出来事"), { status: 404 });
    // 取り消しの出来事を取り消す＝元の出来事を戻す
    const flipTarget = target.undoOf ? w.events.find((e) => e.id === target.undoOf) : target;
    flipTarget.undone = !target.undoOf;
    if (target.undoOf) target.undone = true;
    const e = { id: hex(), op: null, undoOf: eventId, undone: false };
    w.events.push(e);
    return { event_id: e.id, seq: w.events.length };
  }

  // 試験のための判断待ち（AIの案が人の手の所を変えようとした、という形だけ）
  addHeld(wid, rows) { this.works.get(wid).held.push(...rows); }

  preflight(wid, pageIds) {
    const data = this.state(this.works.get(wid));
    const m = new Model(data);
    const issues = [];
    const spec = data.work.page_spec, pr = (data.work.preferences || {}).print;
    const pages = m.rows("pages").filter((p) => !p.removed);
    for (const page of pages) {
      if (pageIds && !pageIds.includes(page.id)) continue;
      const sides = m.sides(page.episode_id);
      const side = sides ? sides[m.pages(page.episode_id).findIndex((p) => p.id === page.id)] : null;
      if (pr && side) {
        const fx = (spec.trim_width_mm - spec.frame_width_mm) / 2, fy = (spec.trim_height_mm - spec.frame_height_mm) / 2;
        const sa = pr.safe_area, l = side === "left" ? sa.outer_mm : sa.gutter_mm, r = side === "left" ? sa.gutter_mm : sa.outer_mm;
        for (const t of m.texts(page.id)) {
          if (!t.box_mm) continue;
          const [x0, y0, x1, y1] = [t.box_mm[0] + fx, t.box_mm[1] + fy, t.box_mm[2] + fx, t.box_mm[3] + fy];
          if (x0 < l || x1 > spec.trim_width_mm - r || y0 < sa.top_mm || y1 > spec.trim_height_mm - sa.bottom_mm) {
            issues.push({ page_id: page.id, kind: "safe_area", severity: "warning", message: `文字「${(t.text || "").slice(0, 8)}」が安全線の外に出ています（偽のサーバーの検査）`, location: { table: "text_items", id: t.id } });
          }
        }
      }
      for (const t of m.texts(page.id)) if (!t.text) issues.push({ page_id: page.id, kind: "text_overflow", severity: "error", message: "文字が空です（偽のサーバーの検査）", location: { table: "text_items", id: t.id } });
      for (const p of m.panels(page.id)) {
        if (p.image_id && p.image_placement) {
          const [cx0, , cx1] = p.image_placement.crop_px, [dx0, , dx1] = p.image_placement.dest_box_mm;
          const dpi = (cx1 - cx0) / ((dx1 - dx0) / 25.4);
          if (dpi < (page.dpi || 600) - 1) issues.push({ page_id: page.id, kind: "image_resolution", severity: "error", message: `コマの絵の解像度が ${Math.round(dpi)}dpi で足りません（偽のサーバーの検査）`, location: { table: "panels", id: p.id } });
        }
      }
      for (const x of this.works.get(wid).held) if (x.page_id === page.id && x.status === "open") issues.push({ page_id: page.id, kind: "held_change", severity: "error", message: "判断待ちが残っています（偽のサーバーの検査）", location: { table: x.target_table, id: x.target_id } });
    }
    return { ok: !issues.some((x) => x.severity === "error"), errors: issues.filter((x) => x.severity === "error").length, warnings: issues.filter((x) => x.severity === "warning").length, issues };
  }

  // seed（manuscript_seed.mjs）から直に呼ぶ call
  call() {
    return async (method, path, body, form) => this.handle(method, path, body, form ? { image: form.image, fields: { origin: form.origin } } : null).then((r) => {
      if (r.status >= 400) throw new Error(`${method} ${path} → ${r.status} ${JSON.stringify(r.json)}`);
      return r.json;
    });
  }

  async handle(method, path, body, form) {
    const u = new URL(path, "http://mock");
    const parts = u.pathname.split("/").filter(Boolean);
    const ok = (json, status = 200) => ({ status, json });
    try {
      if (method === "GET" && u.pathname === "/auth/mode") return ok({ mode: "dev_header" });
      // 利用者ごとの設定（キーの割り当てを入れる。本物と同じく PUT は全部を書き換える）
      if (u.pathname === "/me/settings") {
        if (method === "PUT") this.settings = { ...body, updated_at: new Date().toISOString() };
        return ok(this.settings ?? { language: null, autosave: null, autosave_interval_seconds: null, other: {}, updated_at: null });
      }
      if (method === "GET" && u.pathname === "/works") return ok([...this.works.entries()].map(([id, w]) => ({ id, title: w.base.work.title })));
      if (method === "POST" && u.pathname === "/works") { const id = hex(); this.works.set(id, { base: this.empty(id, body), events: [], images: new Map(), held: [] }); return ok({ id }, 201); }
      const wid = parts[1];
      const w = this.works.get(wid);
      if (!w) return ok({ detail: "作品が無い" }, 404);
      if (method === "GET" && parts.length === 2) return ok(this.state(w));
      if (method === "POST" && parts[2] === "ops") {
        if (body.type === "resolve_held_change") {
          const x = w.held.find((r) => r.id === body.id);
          x.status = body.decision === "accept" ? "accepted" : "rejected";
          if (body.decision === "accept") return ok(this.submit(wid, { type: `update_${x.target_table === "text_items" ? "text_item" : "panel"}`, id: x.target_id, [x.field]: x.proposed_value }));
          return ok(this.submit(wid, { type: "resolve_held_change", id: body.id }));
        }
        return ok(this.submit(wid, body));
      }
      if (method === "POST" && parts[2] === "events" && parts[4] === "undo") return ok(this.undo(wid, parts[3]));
      if (method === "GET" && parts[2] === "held-changes") return ok(w.held.filter((x) => x.status === "open"));
      if (method === "POST" && parts[2] === "preflight") return ok(this.preflight(wid, body && body.page_ids));
      if (method === "GET" && parts[2] === "images" && parts[4] === "file") {
        const img = w.images.get(parts[3]);
        return img ? { status: 200, body: img, type: "image/png" } : ok({ detail: "絵が無い" }, 404);
      }
      if (method === "POST" && parts[2] === "panels" && parts[4] === "image") {
        const iid = hex();
        w.images.set(iid, form.image);
        const state = this.state(w);
        const prev = state.panels.find((p) => p.id === parts[3]).image_id;
        const e = this.submit(wid, { type: "update_panel", id: parts[3], image_id: iid, image_placement: null });
        return ok({ id: iid, previous_image_id: prev, register_event_id: null, select_event_id: e.event_id }, 201);
      }
      return ok({ detail: `偽のサーバーに無い口：${method} ${u.pathname}` }, 404);
    } catch (e) {
      return ok({ detail: `偽のサーバー：${e.message}` }, e.status || 422);
    }
  }

  // Playwright の page に付ける。origin の /web/ は v3/web のファイルを出し、それ以外は口として答える
  async install(page, origin) {
    await serveWeb(page, origin, async (route, u) => {
      const req = route.request();
      let body = null, form = null;
      const ct = req.headers()["content-type"] || "";
      if (ct.startsWith("multipart/form-data")) form = parseMultipart(req.postDataBuffer(), ct);
      else if (req.postData()) body = JSON.parse(req.postData());
      const r = await this.handle(req.method(), u.pathname + u.search, body, form);
      if (r.body) return route.fulfill({ status: r.status, body: r.body, contentType: r.type });
      return route.fulfill({ status: r.status, body: JSON.stringify(r.json), contentType: "application/json", headers: { "X-V3-Mock": "1" } });
    });
  }
}

function apply(m, op) {
  const d = m.data;
  switch (op.type) {
    case "set_threshold": d.thresholds = (d.thresholds || []).filter((t) => t.key !== op.key).concat(op.value ? [{ key: op.key, value: op.value, source: op.source, status: op.status }] : []); return;
    case "add_volume": d.volumes.push({ id: op.id, number: op.number, removed: false }); return;
    case "add_episode": d.episodes.push({ id: op.id, volume_id: op.volume_id, number: op.number, title: op.title || null, removed: false }); return;
    case "add_page": d.pages.push({ id: op.id, episode_id: op.episode_id, number: op.number, layout: null, page_kind: null, color_mode: null, dpi: null, nombre_display: null, human_hand_fields: [], removed: false }); return;
    case "set_removed": if (!m.find({ panel: "panels", text_item: "text_items", page_item: "page_items", panel_layer: "panel_layers", page: "pages", spread: "spreads" }[op.target_kind], op.id)) throw new Error("無い行"); break;
    case "split_panel": case "merge_panels": {
      m.applyLocal(op);
      // 読む順を振り直す（本物はページの読む向きで決める。ここは並びのまま）
      d.panels.filter((p) => !p.removed).sort((a, b) => a.order - b.order).forEach((p, i) => { p.order = i + 1; });
      return;
    }
    case "reorder_pages": {
      const live = m.pages(op.episode_id).map((p) => p.id).sort();
      if (JSON.stringify([...op.page_ids].sort()) !== JSON.stringify(live)) throw new Error("話のページの全部を渡してください");
      for (const sp of m.spreads(op.episode_id)) {
        if (Math.abs(op.page_ids.indexOf(sp.first_page_id) - op.page_ids.indexOf(sp.second_page_id)) !== 1) throw new Error("見開きの組が崩れる。先に見開きを解く");
      }
      break;
    }
    case "add_spread": {
      const a = m.find("pages", op.first_page_id), b = m.find("pages", op.second_page_id);
      if (!a || !b || Math.abs(a.number - b.number) !== 1) throw new Error("向かい合うページだけ見開きにできる");
      break;
    }
    default: break;
  }
  if (!m.applyLocal(op)) throw new Error(`偽のサーバーが当てられない操作：${op.type}`);
  if (op.type === "add_panel" || op.type === "add_text_item" || op.type === "add_page_item") void bbox;
}

// multipart/form-data を読む（絵のファイルと文字の欄だけ）
function parseMultipart(buf, ct) {
  const boundary = Buffer.from(`--${ct.split("boundary=")[1]}`);
  const out = { fields: {} };
  let i = buf.indexOf(boundary);
  while (i >= 0) {
    const next = buf.indexOf(boundary, i + boundary.length);
    if (next < 0) break;
    const part = buf.subarray(i + boundary.length + 2, next - 2);
    const sep = part.indexOf("\r\n\r\n");
    const head = part.subarray(0, sep).toString();
    const content = part.subarray(sep + 4);
    const name = /name="([^"]+)"/.exec(head)[1];
    if (/filename=/.test(head)) out.image = Buffer.from(content);
    else out.fields[name] = content.toString();
    i = next;
  }
  return out;
}
