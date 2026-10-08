// 原稿のページ（1ページか見開き）を出し、コマ枠・フキダシ・文字の箱・トーン・コマの絵を動かす所（fabric.js 7.4.0）。
// 座標は mm（1 単位 = 1mm）。ページごとに、基本枠の左上を原点にした正本の座標へ、ページの置き場（ox, oy）を足して置く。
// 拡大・移動の途中は、描いた絵を CSS で動かすだけにし、止まってから描き直す（600dpi の絵でも動かす間は描き直さない）。
import { apply, bbox, chordThrough, lineNormal, pointInPolygon, tailPolygon } from "./geometry.js";
import { drawTone } from "./tone_draw.js";
import { TextLayer } from "./text_layer.js";
import * as api from "../../js/api.js";
import { C, alpha, readTheme } from "./theme_colors.js";

const { Canvas, FabricObject, FabricImage, Point, Control, util } = window.fabric;

const MIN_Z = 0.3, MAX_Z = 120;
const COMMIT_MS = 140;

// 選ぶ所を枠の外接の四角でなく、形（多角形）で決める
class PageCanvas extends Canvas {
  _pointIsInObjectSelectionArea(obj, p) {
    if (!super._pointIsInObjectSelectionArea(obj, p)) return false;
    return obj.hitTest ? obj.hitTest(p) : true;
  }
}

// 形を描く物。local の多角形（中心が原点）で当たりを決め、paint で描く
class Item extends FabricObject {
  _render(ctx) { if (this.paint) this.paint(ctx, this.canvas ? this.canvas.getZoom() : 1, this); }
  hitTest(p) {
    if (!this.hit) return true;
    const q = util.transformPoint(p, util.invertTransform(this.calcTransformMatrix()));
    return this.hit.some((poly) => pointInPolygon([q.x, q.y], poly));
  }
  // 局所の点 → 原稿の mm（ページの置き場を足した座標）
  toWorld([x, y]) { const q = util.transformPoint(new Point(x, y), this.calcTransformMatrix()); return [q.x, q.y]; }
}

function trace(ctx, P) {
  ctx.beginPath();
  P.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.closePath();
}

// 世界の多角形の並びから、中心・大きさ・中心を原点にした多角形を作る
function localize(polys, margin) {
  const [x0, y0, x1, y1] = bbox(polys.flat());
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return { cx, cy, w: x1 - x0 + margin * 2, h: y1 - y0 + margin * 2, loc: polys.map((P) => P.map(([x, y]) => [x - cx, y - cy])) };
}

const shift = (P, ox, oy) => P.map(([x, y]) => [x + ox, y + oy]);

export class PageView {
  constructor(host, hooks) {
    this.host = host;
    this.hooks = hooks;
    this.pv = document.createElement("div");
    this.pv.className = "pv";
    host.append(this.pv);
    readTheme(this.pv);
    const el = document.createElement("canvas");
    this.pv.append(el);
    this.c = new PageCanvas(el, { selection: false, preserveObjectStacking: true, fireRightClick: false, stopContextMenu: true,
                                  enableRetinaScaling: true, enablePointerEvents: true, uniformScaling: false });
    this.text = new TextLayer(this.pv, {
      onEditDone: (id, text) => hooks.onEditDone(id, text),
      onEditing: (id, text) => hooks.onEditing && hooks.onEditing(id, text),
    });
    this.tool = "select";
    this.frameMode = "move";
    this.knife = { direction: "horizontal", angle: 12, gap: 2 };
    this.slots = [];
    this.images = new Map();
    this.vpt = [1, 0, 0, 1, 0, 0];
    this.panning = null;
    this.space = false;
    this.selectedId = null;
    this.perf = { renders: [], moves: [] };
    this.c.on("before:render", () => { this._t0 = performance.now(); });
    this.c.on("after:render", () => { if (this._t0) this.perf.renders.push(performance.now() - this._t0); if (this.perf.renders.length > 2000) this.perf.renders.splice(0, 1000); });
    new ResizeObserver(() => this.resize()).observe(host);
    this.bind();
    this.resize();
  }

  // ---------------------------------------------------------------- 大きさ・拡大・移動
  resize() {
    const r = this.host.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    this.c.setDimensions({ width: r.width, height: r.height });
    // 合わせたまま手で動かしていなければ、大きさが変わったら合わせ直す
    if ((!this.fitted || this.autoFit) && this.slots.length) this.fit();
    else this.commit();
  }

  zoom() { return this.vpt[0]; }

  extent() {
    if (!this.slots.length) return null;
    const xs = this.slots.map((s) => s.x), w = this.slots[0].trimW, h = this.slots[0].trimH, b = this.slots[0].bleed;
    return [Math.min(...xs) - b, -b, Math.max(...xs) + w + b, h + b];
  }

  fit() {
    const e = this.extent();
    if (!e) return;
    // 上の道具の帯（約 56px）の下に収める
    const W = this.c.width, H = this.c.height, pad = 24, top = 60;
    const z = Math.max(MIN_Z, Math.min((W - pad * 2) / (e[2] - e[0]), (H - pad - top) / (e[3] - e[1])));
    this.vpt = [z, 0, 0, z, (W - (e[2] - e[0]) * z) / 2 - e[0] * z, top + (H - pad - top - (e[3] - e[1]) * z) / 2 - e[1] * z];
    this.fitted = true;
    this.autoFit = true;
    this.commit();
  }

  zoomTo(z, cx = this.c.width / 2, cy = this.c.height / 2, now = false) {
    z = Math.max(MIN_Z, Math.min(MAX_Z, z));
    this.autoFit = false;
    const k = z / this.vpt[0];
    this.vpt = [z, 0, 0, z, cx - (cx - this.vpt[4]) * k, cy - (cy - this.vpt[5]) * k];
    if (now) this.commit(); else this.preview();
  }
  zoomBy(f) { this.zoomTo(this.vpt[0] * f, undefined, undefined, true); }
  panBy(dx, dy) { this.autoFit = false; this.vpt[4] += dx; this.vpt[5] += dy; this.preview(); }

  // 描いた物を CSS で動かして見せ、止まってから描き直す
  preview() {
    const v0 = this.c.viewportTransform, v = this.vpt;
    const k = v[0] / v0[0];
    this.pv.style.transform = `matrix(${k},0,0,${k},${v[4] - k * v0[4]},${v[5] - k * v0[5]})`;
    clearTimeout(this.commitT);
    this.commitT = setTimeout(() => this.commit(), COMMIT_MS);
    this.hooks.onView && this.hooks.onView();
  }

  commit() {
    clearTimeout(this.commitT);
    this.pv.style.transform = "";
    this.c.setViewportTransform(this.vpt.slice());
    this.text.setViewport(this.vpt);
    this.hooks.onView && this.hooks.onView();
  }

  // 画面の点 → 原稿の mm
  sceneAt(clientX, clientY) {
    const r = this.c.upperCanvasEl.getBoundingClientRect();
    return [(clientX - r.left - this.vpt[4]) / this.vpt[0], (clientY - r.top - this.vpt[5]) / this.vpt[3]];
  }

  // ある箱（ページの mm）が見えるように動かす。小さい物は 3 倍ほどの範囲を出す
  focusBox(pageId, box) {
    const s = this.slots.find((x) => x.page.id === pageId);
    if (!s) return;
    const [x0, y0, x1, y1] = [box[0] + s.ox, box[1] + s.oy, box[2] + s.ox, box[3] + s.oy];
    const W = this.c.width, H = this.c.height;
    const z = Math.max(MIN_Z, Math.min(MAX_Z, Math.min(W / ((x1 - x0) * 3 + 20), H / ((y1 - y0) * 3 + 20))));
    this.vpt = [z, 0, 0, z, W / 2 - ((x0 + x1) / 2) * z, H / 2 - ((y0 + y1) / 2) * z];
    this.autoFit = false;
    this.commit();
  }

  bind() {
    const host = this.host;
    // 拡大は Ctrl を押したホイール（トラックパッドのつまむ動きも Ctrl 付きで来る）。Ctrl なしは動かす
    host.addEventListener("wheel", (e) => {
      e.preventDefault();
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? host.clientHeight : 1;
      const r = this.c.upperCanvasEl.getBoundingClientRect();
      if (e.ctrlKey || e.metaKey) this.zoomTo(this.vpt[0] * Math.exp(-e.deltaY * unit * 0.0025), e.clientX - r.left, e.clientY - r.top);
      else if (e.shiftKey) this.panBy(-e.deltaY * unit, 0);
      else this.panBy(-e.deltaX * unit, -e.deltaY * unit);
    }, { passive: false });
    // 手のひら：道具の手のひら・スペースを押している間・真ん中のボタン。fabric より先に受ける
    host.addEventListener("pointerdown", (e) => {
      if (this.commitT) this.commit();
      if (this.tool === "hand" || this.space || e.button === 1) {
        this.panning = { x: e.clientX, y: e.clientY, id: e.pointerId };
        host.setPointerCapture(e.pointerId);
        host.classList.add("panning");
        e.stopPropagation(); e.preventDefault();
      }
    }, true);
    host.addEventListener("pointermove", (e) => {
      if (!this.panning) return;
      this.panBy(e.clientX - this.panning.x, e.clientY - this.panning.y);
      this.panning.x = e.clientX; this.panning.y = e.clientY;
      e.stopPropagation();
    }, true);
    const end = (e) => {
      if (!this.panning) return;
      this.panning = null;
      host.classList.remove("panning");
      this.commit();
      e.stopPropagation();
    };
    host.addEventListener("pointerup", end, true);
    host.addEventListener("pointercancel", end, true);

    const c = this.c;
    c.on("mouse:move", (o) => this.onMove(o));
    c.on("mouse:out", () => this.clearKnife());
    c.on("mouse:down", (o) => this.onDown(o));
    c.on("mouse:dblclick", (o) => this.onDbl(o));
    c.on("selection:created", (o) => this.onSel(o));
    c.on("selection:updated", (o) => this.onSel(o));
    c.on("selection:cleared", () => { this.selectedId = null; this.touch(); if (!this.quiet) this.hooks.onSelect(null); });
    c.on("object:moving", (o) => this.onMoving(o));
    c.on("object:scaling", (o) => this.onMoving(o));
    // fabric が手の動きを終えてから送る（送ると描き直すので、終える前に描き直すと同じ通知がまた来る）
    c.on("object:modified", (o) => setTimeout(() => this.onModified(o), 0));
  }

  // ---------------------------------------------------------------- 物を作る
  // slots：[{ page, ox, oy, x, trimW, trimH, bleed }]。data：{ model, opts }
  // 色の組を差し替えたあと：色を読み直して作り直す
  retheme() {
    readTheme(this.pv);
    this.rebuild();
  }

  setScene(slots, model, opts) {
    const keepView = this.slots.length && slots.length === this.slots.length && slots.every((s, i) => s.page.id === this.slots[i].page.id);
    this.slots = slots;
    this.model = model;
    this.opts = opts;
    this.rebuild();
    if (!keepView || !this.fitted) this.fit(); else this.commit();
  }

  rebuild() {
    const active = this.c.getActiveObject();
    const keep = active && active.v3 ? { kind: active.v3.kind, id: active.v3.id } : null;
    this.quiet = true;
    this.c.discardActiveObject();
    this.quiet = false;
    this.c.remove(...this.c.getObjects());
    this.text.clear();
    this.knifeObj = null;
    const layers = { paper: [], art: [], tone: [], frame: [], balloon: [], cover: [] };
    for (const s of this.slots) this.buildPage(s, layers);
    this.c.add(...layers.paper, ...layers.art, ...layers.tone, ...layers.frame, ...layers.balloon, ...layers.cover);
    this.applyTool();
    if (keep) this.select(keep.kind, keep.id, false);
    this.c.requestRenderAll();
  }

  buildPage(s, L) {
    const m = this.model, o = this.opts, page = s.page;
    const spec = m.spec();
    const { ox, oy } = s;
    // 紙・塗り足し・基本枠・安全線（画面だけの線）
    const fx = (spec.trim_width_mm - spec.frame_width_mm) / 2, fy = (spec.trim_height_mm - spec.frame_height_mm) / 2;
    const tx = ox - fx, ty = oy - fy, b = spec.bleed_mm;
    const safe = o.safeArea;
    const paper = new Item({ left: tx + spec.trim_width_mm / 2, top: ty + spec.trim_height_mm / 2,
                             width: spec.trim_width_mm + b * 2, height: spec.trim_height_mm + b * 2,
                             originX: "center", originY: "center", selectable: false, evented: false, objectCaching: false });
    const W = spec.trim_width_mm, H = spec.trim_height_mm;
    paper.paint = (ctx, z) => {
      ctx.save();
      ctx.translate(-W / 2, -H / 2);
      ctx.fillStyle = C.pasteboard;
      ctx.fillRect(-b, -b, W + b * 2, H + b * 2);
      ctx.fillStyle = C.paper;
      ctx.fillRect(0, 0, W, H);
      ctx.lineWidth = 1 / z;
      ctx.strokeStyle = C.edge;
      ctx.strokeRect(0, 0, W, H);
      if (o.show.guide) {
        ctx.setLineDash([4 / z, 3 / z]);
        ctx.strokeStyle = C.aiLine;
        ctx.strokeRect(fx, fy, spec.frame_width_mm, spec.frame_height_mm);
      }
      if (o.show.safe && safe) {
        const leftPage = s.side === "left";
        const l = leftPage ? safe.outer_mm : safe.gutter_mm, r = leftPage ? safe.gutter_mm : safe.outer_mm;
        ctx.setLineDash([2 / z, 2 / z]);
        ctx.strokeStyle = C.badLine;
        ctx.strokeRect(l, safe.top_mm, W - l - r, H - safe.top_mm - safe.bottom_mm);
      }
      if (o.show.grid) {
        ctx.setLineDash([]);
        ctx.strokeStyle = alpha(C.ai, 0.14);
        ctx.beginPath();
        for (let x = 10; x < W; x += 10) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
        for (let y = 10; y < H; y += 10) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
        ctx.stroke();
      }
      ctx.restore();
    };
    paper.v3 = { kind: "paper", pageId: page.id };
    L.paper.push(paper);

    const prefStyle = (m.work.preferences || {}).frame_style || null;
    const panels = m.panels(page.id);
    // コマの地の色（絵の下）とコマの絵・層
    for (const p of panels) {
      const poly = shift(p.frame.polygon_mm, ox, oy);
      const style = p.frame_style || prefStyle;
      if (style && style.fill_color) L.paper.push(this.fillItem(poly, style.fill_color));
      if (o.show.cat.art !== false) this.panelArt(p, poly, ox, oy, L.art);
    }
    // 見開きにまたがる絵
    const sp = m.caps.print ? m.spreadOf(page.id) : null;
    if (sp && sp.image_id && sp.image_placement && s.spreadLeft) this.spreadArt(sp, s, L.art);
    // トーン・図形
    if (o.show.cat.tone !== false) {
      for (const it of m.items(page.id)) {
        if (!it.visible) continue;
        L.tone.push(this.toneItem(it, panels, ox, oy));
      }
    }
    // コマ枠
    if (o.show.cat.frame !== false) {
      for (const p of panels) L.frame.push(this.panelItem(p, p.frame_style || prefStyle, ox, oy));
    }
    // フキダシ・文字の箱
    const texts = m.texts(page.id);
    const tsDefault = (m.work.preferences || {}).typesetting || null;
    const fonts = (m.work.preferences || {}).fonts_by_kind || {};
    const groups = new Map();
    for (const t of texts) {
      if (!t.box_mm) continue;
      const cat = t.item_kind === "drawn_sfx" ? "sfx" : "balloon";
      const show = o.show.cat[cat] !== false;
      const item = this.textItem(t, ox, oy);
      if (show) L.balloon.push(item);
      this.text.put(t, ox, oy, t.typesetting || tsDefault, t.font_family || fonts[t.item_kind] || null,
                    { visible: o.show.cat[t.item_kind === "drawn_sfx" ? "sfx" : "type"] !== false });
      if (item.v3.outline) {
        const key = t.panel_id;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push({ t, item });
      }
    }
    // つないだフキダシ：線を全部描いた上に、つないだ組の塗りを重ねて、重なった所の線を隠す
    for (const list of groups.values()) {
      list.sort((a, b) => a.t.order - b.t.order);
      let run = [];
      const flush = () => { if (run.length > 1) L.cover.push(this.coverItem(run)); run = []; };
      for (const x of list) { if (!x.t.joined_to_previous) flush(); run.push(x); }
      flush();
    }
    // 人の手・判断待ちの印
    this.marks(page, panels, texts, ox, oy);
  }

  fillItem(poly, color) {
    const g = localize([poly], 0);
    const it = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center",
                          selectable: false, evented: false });
    it.paint = (ctx) => { trace(ctx, g.loc[0]); ctx.fillStyle = color; ctx.fill(); };
    return it;
  }

  panelArt(p, poly, ox, oy, out) {
    const clip = () => {
      const g = localize([poly], 0);
      const cl = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center", absolutePositioned: true });
      cl.paint = (ctx) => { trace(ctx, g.loc[0]); ctx.fill(); };
      cl._render = function (ctx) { trace(ctx, g.loc[0]); ctx.fill(); };
      return cl;
    };
    const parts = [];
    if (p.image_id && p.image_placement) parts.push({ image_id: p.image_id, placement: p.image_placement, opacity: 1, base: true });
    for (const l of this.model.layers(p.id)) {
      if (!l.visible || !l.image_id || !l.placement) continue;
      parts.push({ image_id: l.image_id, placement: l.placement, opacity: l.opacity, layer: l });
    }
    for (const part of parts) {
      const im = this.images.get(part.image_id);
      if (!im) { this.loadImage(part.image_id); continue; }
      const pl = part.placement;
      const [cx0, cy0, cx1, cy1] = pl.crop_px;
      const [dx0, dy0, dx1, dy1] = pl.dest_box_mm;
      const fi = new FabricImage(im, {
        cropX: cx0, cropY: cy0, width: cx1 - cx0, height: cy1 - cy0,
        scaleX: (dx1 - dx0) / (cx1 - cx0), scaleY: (dy1 - dy0) / (cy1 - cy0),
        left: ox + (dx0 + dx1) / 2, top: oy + (dy0 + dy1) / 2, originX: "center", originY: "center",
        angle: pl.rotation_deg || 0, skewX: pl.skew_x_deg || 0, skewY: pl.skew_y_deg || 0, flipX: !!pl.flip_h, flipY: !!pl.flip_v,
        opacity: part.opacity, selectable: false, evented: false, lockRotation: true, lockSkewingX: true, lockSkewingY: true,
      });
      fi.clipPath = clip();
      fi.v3 = { kind: "image", id: p.id, pageId: p.page_id, base: !!part.base, layerId: part.layer ? part.layer.id : null, ox, oy };
      fi.setControlsVisibility({ mtr: false });
      out.push(fi);
    }
  }

  spreadArt(sp, s, out) {
    const im = this.images.get(sp.image_id);
    if (!im) { this.loadImage(sp.image_id); return; }
    const pl = sp.image_placement;
    const [cx0, cy0, cx1, cy1] = pl.crop_px;
    const [dx0, dy0, dx1, dy1] = pl.dest_box_mm;
    out.push(new FabricImage(im, { cropX: cx0, cropY: cy0, width: cx1 - cx0, height: cy1 - cy0,
      scaleX: (dx1 - dx0) / (cx1 - cx0), scaleY: (dy1 - dy0) / (cy1 - cy0), left: s.ox + (dx0 + dx1) / 2, top: s.oy + (dy0 + dy1) / 2,
      originX: "center", originY: "center", selectable: false, evented: false }));
  }

  loadImage(id) {
    if (this.images.has(id) || (this.loading && this.loading.has(id))) return;
    if (!this.loading) this.loading = new Set();
    this.loading.add(id);
    api.image(`/works/${this.model.work.id}/images/${id}/file`).then(({ image }) => {
      this.images.set(id, image);
      this.loading.delete(id);
      clearTimeout(this.reloadT);
      this.reloadT = setTimeout(() => this.rebuild(), 30);
    }).catch((e) => { this.loading.delete(id); this.hooks.onError(e, "コマの絵を読むこと"); });
  }

  panelItem(p, style, ox, oy) {
    const poly = shift(p.frame.polygon_mm, ox, oy);
    const lw = style ? style.line_width_mm : 0;
    const g = localize([poly], lw / 2 + 0.3);
    const it = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center",
                          lockRotation: true, hasBorders: true, borderColor: C.ai, cornerColor: C.ai, cornerSize: 9, transparentCorners: false });
    it.hit = g.loc;
    it.v3 = { kind: "panel", id: p.id, pageId: p.page_id, ox, oy, loc: g.loc[0], held: false };
    it.setControlsVisibility({ mtr: false });
    const view = this;
    it.paint = (ctx, z) => {
      trace(ctx, it.v3.loc);
      if (style && lw > 0) {
        ctx.lineJoin = "miter"; ctx.lineWidth = lw; ctx.strokeStyle = style.line_color; ctx.stroke();
      } else {
        // 枠の線が決まっていない：書き出しで止まる。画面では細い破線の目安で見せる
        ctx.setLineDash([3 / z, 2 / z]); ctx.lineWidth = 1 / z; ctx.strokeStyle = C.ai; ctx.stroke(); ctx.setLineDash([]);
      }
      if (view.selectedId === p.id || view.pickA === p.id) {
        trace(ctx, it.v3.loc);
        ctx.fillStyle = alpha(C.ai, 0.10); ctx.fill();
        ctx.lineWidth = 2 / z; ctx.strokeStyle = C.ai; ctx.stroke();
      }
    };
    return it;
  }

  textItem(t, ox, oy) {
    const bs = t.balloon_shape && t.balloon_shape.kind !== "none" ? t.balloon_shape : null;
    const box = [[t.box_mm[0] + ox, t.box_mm[1] + oy], [t.box_mm[2] + ox, t.box_mm[3] + oy]];
    const outline = bs ? shift(bs.outline_mm, ox, oy) : null;
    const target = t.tail_target_mm ? [t.tail_target_mm[0] + ox, t.tail_target_mm[1] + oy] : null;
    const tail = outline && target && bs.tail_base_width_mm ? tailPolygon(outline, target, bs.tail_base_width_mm, bs.tail_bend_ratio || 0) : null;
    const boxPoly = [box[0], [box[1][0], box[0][1]], box[1], [box[0][0], box[1][1]]];
    const polys = [outline || boxPoly, ...(tail ? [tail] : []), boxPoly];
    const lw = bs && bs.line_width_mm != null ? bs.line_width_mm : 0;
    const g = localize(polys, lw / 2 + 0.3);
    const it = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center",
                          lockRotation: true, borderColor: C.ai, cornerColor: C.ai, cornerSize: 9, transparentCorners: false });
    const [locOutline, locTail, locBox] = outline ? [g.loc[0], tail ? g.loc[1] : null, g.loc[g.loc.length - 1]] : [null, null, g.loc[0]];
    it.hit = [locOutline || locBox, ...(locTail ? [locTail] : [])];
    it.v3 = { kind: "text", id: t.id, pageId: t.page_id, ox, oy, outline: !!outline, locOutline, locTail, locBox, target, bs, row: t };
    it.setControlsVisibility({ mtr: false });
    const view = this;
    it.paint = (ctx, z) => {
      const v = it.v3;
      if (v.locOutline) {
        const decided = bs.line_width_mm != null && bs.line_color;
        ctx.lineJoin = "round";
        ctx.lineWidth = decided ? bs.line_width_mm : 1 / z;
        ctx.strokeStyle = decided ? bs.line_color : C.ai;
        if (!decided) ctx.setLineDash([3 / z, 2 / z]);
        if (v.locTail) { trace(ctx, v.locTail); ctx.stroke(); }
        trace(ctx, v.locOutline); ctx.stroke();
        ctx.setLineDash([]);
        if (bs.fill_color) {
          ctx.fillStyle = bs.fill_color;
          if (v.locTail) { trace(ctx, v.locTail); ctx.fill(); }
          trace(ctx, v.locOutline); ctx.fill();
        }
      } else if (view.opts.show.boxes) {
        ctx.setLineDash([2 / z, 2 / z]); ctx.lineWidth = 1 / z; ctx.strokeStyle = alpha(C.ai, 0.55);
        trace(ctx, v.locBox); ctx.stroke(); ctx.setLineDash([]);
      }
      if (view.selectedId === t.id && v.locOutline) {
        ctx.setLineDash([2 / z, 2 / z]); ctx.lineWidth = 1 / z; ctx.strokeStyle = C.ai; trace(ctx, v.locBox); ctx.stroke(); ctx.setLineDash([]);
      }
    };
    if (outline) {
      // しっぽの先を掴んで動かす
      it.controls = { ...it.controls, tail: new Control({
        cursorStyle: "crosshair", sizeX: 12, sizeY: 12,
        positionHandler: () => {
          const tg = it.v3.target || it.toWorld([0, g.h / 2 - 0.3]);
          return util.transformPoint(new Point(tg[0], tg[1]), view.c.viewportTransform);
        },
        actionHandler: (e, tr, x, y) => {
          it.v3.target = [x, y];
          const outW = locOutline.map((q) => it.toWorld(q));
          const tl = bs.tail_base_width_mm ? tailPolygon(outW, it.v3.target, bs.tail_base_width_mm, bs.tail_bend_ratio || 0) : null;
          const inv = util.invertTransform(it.calcTransformMatrix());
          it.v3.locTail = tl ? tl.map(([a, b]) => { const q = util.transformPoint(new Point(a, b), inv); return [q.x, q.y]; }) : null;
          it.objectCaching = false;
          it.v3.tailMoved = true;
          return true;
        },
        render: (ctx, left, top) => {
          ctx.save(); ctx.fillStyle = C.on; ctx.strokeStyle = C.ai; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(left, top, 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore();
        },
        actionName: "tail",
      }) };
    }
    return it;
  }

  coverItem(run) {
    const polys = [];
    for (const { item } of run) {
      polys.push(item.v3.locOutline.map((q) => item.toWorld(q)));
      if (item.v3.locTail) polys.push(item.v3.locTail.map((q) => item.toWorld(q)));
    }
    const g = localize(polys, 0);
    const fill = run[0].t.balloon_shape.fill_color;
    const it = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center", selectable: false, evented: false });
    it.paint = (ctx) => { if (!fill) return; ctx.fillStyle = fill; for (const P of g.loc) { trace(ctx, P); ctx.fill(); } };
    it.v3 = { kind: "cover" };
    return it;
  }

  toneItem(t, panels, ox, oy) {
    const box = t.box_mm;
    const target = t.item_kind === "tone" ? t.spec.target : null;
    let clipPoly = null;
    if (target && target.kind === "panel") { const p = panels.find((x) => x.id === target.panel_id); if (p) clipPoly = p.frame.polygon_mm; }
    if (target && target.kind === "polygon") clipPoly = target.polygon_mm;
    const boxPoly = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]];
    const g = localize([shift(boxPoly, ox, oy), shift(clipPoly || boxPoly, ox, oy)], 0);
    const it = new Item({ left: g.cx, top: g.cy, width: g.w, height: g.h, originX: "center", originY: "center", opacity: t.opacity,
                          lockRotation: true, borderColor: C.ai, cornerColor: C.ai, cornerSize: 9, transparentCorners: false });
    it.hit = [g.loc[1]];
    it.v3 = { kind: "tone", id: t.id, pageId: t.page_id, ox, oy, row: t };
    it.setControlsVisibility({ mtr: false });
    const lbox = [g.loc[0][0][0], g.loc[0][0][1], g.loc[0][2][0], g.loc[0][2][1]];
    const view = this;
    it.paint = (ctx, z) => {
      ctx.save();
      trace(ctx, g.loc[1]); ctx.clip();
      if (t.item_kind === "tone") {
        const spec = t.spec.center_mm ? { ...t.spec, center_mm: [t.spec.center_mm[0] + ox - g.cx, t.spec.center_mm[1] + oy - g.cy] } : t.spec;
        drawTone(ctx, spec, lbox, z);
      } else {
        // 図形（絵記号）の中身を描くのは、まだ作っていない。置いた範囲だけ見せる
        ctx.setLineDash([3 / z, 2 / z]); ctx.lineWidth = 1 / z; ctx.strokeStyle = C.need; trace(ctx, g.loc[0]); ctx.stroke();
      }
      ctx.restore();
      if (view.selectedId === t.id) { ctx.lineWidth = 2 / z; ctx.strokeStyle = C.ai; trace(ctx, g.loc[1]); ctx.stroke(); }
    };
    return it;
  }

  marks(page, panels, texts, ox, oy) {
    const show = this.opts.show;
    const held = this.opts.heldBy || new Map();
    const add = (row, x, y, kind) => {
      const h = held.get(row.id) || [];
      if (show.hand && (row.human_hand_fields || []).length) this.text.mark(`${row.id}:hand`, x, y, "hand", `人の手：${row.human_hand_fields.join("・")}`);
      if (show.held && h.length) this.text.mark(`${row.id}:held`, x, y, "held", `判断待ち ${h.length} 件`, h.length);
    };
    for (const p of panels) { const [, y0, x1] = bbox(p.frame.polygon_mm); add(p, x1 + ox, y0 + oy, "panel"); }
    for (const t of texts) if (t.box_mm) add(t, t.box_mm[2] + ox, t.box_mm[1] + oy, "text");
    for (const it of this.model.items(page.id)) add(it, it.box_mm[2] + ox, it.box_mm[1] + oy, "tone");
  }

  // ---------------------------------------------------------------- 道具
  setTool(tool, sub = {}) {
    this.tool = tool;
    Object.assign(this, sub);
    this.pickA = null;
    this.clearKnife();
    this.c.discardActiveObject();
    this.applyTool();
    this.host.dataset.tool = tool;
    const add = tool === "balloon" || tool === "text" || tool === "tone" || (tool === "frame" && this.frameMode === "add");
    this.c.defaultCursor = tool === "knife" ? "crosshair" : tool === "hand" ? "grab" : add ? "copy" : "default";
    this.c.requestRenderAll();
  }

  applyTool() {
    const t = this.tool, lock = this.opts ? this.opts.lock : {};
    for (const o of this.c.getObjects()) {
      const v = o.v3;
      if (!v || !["panel", "text", "tone", "image"].includes(v.kind)) continue;
      let on = false;
      if (v.kind === "panel") on = (t === "select" || t === "frame") && !lock.frame;
      if (v.kind === "text") on = (t === "select" || t === "balloon" || t === "text") && !lock[v.row.item_kind === "drawn_sfx" ? "sfx" : "balloon"];
      if (v.kind === "tone") on = t === "tone" && !lock.tone;
      if (v.kind === "image") on = this.imageEdit === v.id && v.base;
      const fixed = v.row ? v.row.fixed : v.kind === "panel" ? this.model.find("panels", v.id).fixed : false;
      o.selectable = on;
      o.evented = on || (v.kind === "panel" && (t === "knife" || t === "balloon" || t === "text" || t === "tone"));
      o.hasControls = on && !fixed && !(t === "frame" && this.frameMode === "join");
      o.lockMovementX = o.lockMovementY = !!fixed;
      o.hoverCursor = on ? (fixed ? "not-allowed" : "move") : "default";
      if (v.kind === "panel" && t === "frame" && this.frameMode === "edit") this.vertexControls(o);
    }
  }

  // コマ枠の角を直す：頂点ごとの掴み
  vertexControls(o) {
    const view = this;
    const ctl = {};
    o.v3.loc.forEach((_, i) => {
      ctl[`p${i}`] = new Control({
        cursorStyle: "pointer", actionName: "vertex",
        positionHandler: () => { const w = o.toWorld(o.v3.loc[i]); return util.transformPoint(new Point(w[0], w[1]), view.c.viewportTransform); },
        actionHandler: (e, tr, x, y) => {
          const q = util.transformPoint(new Point(x, y), util.invertTransform(o.calcTransformMatrix()));
          o.v3.loc = o.v3.loc.map((p, k) => (k === i ? [q.x, q.y] : p));
          o.hit = [o.v3.loc];
          o.objectCaching = false;
          o.v3.vertexMoved = true;
          return true;
        },
        render: (ctx, left, top) => { ctx.save(); ctx.fillStyle = C.on; ctx.strokeStyle = C.ai; ctx.lineWidth = 2; ctx.fillRect(left - 4, top - 4, 8, 8); ctx.strokeRect(left - 4, top - 4, 8, 8); ctx.restore(); },
      });
    });
    o.controls = ctl;
    o.hasBorders = false;
  }

  // ---------------------------------------------------------------- 手の動き
  slotAt(p) { return this.slots.find((s) => p[0] >= s.x - s.bleed && p[0] <= s.x + s.trimW + s.bleed) || null; }

  panelAt(p) {
    const s = this.slotAt(p);
    if (!s) return null;
    const q = [p[0] - s.ox, p[1] - s.oy];
    const panels = this.model.panels(s.page.id);
    for (let i = panels.length - 1; i >= 0; i--) if (pointInPolygon(q, panels[i].frame.polygon_mm)) return { panel: panels[i], slot: s, q };
    return { panel: null, slot: s, q };
  }

  onMove(o) {
    const t0 = performance.now();
    if (this.tool !== "knife") return;
    const p = this.c.getScenePoint(o.e);
    const hit = this.panelAt([p.x, p.y]);
    if (!hit || !hit.panel) { this.clearKnife(); return; }
    const n = lineNormal(this.knife.direction, this.knife.angle);
    const ch = chordThrough(hit.panel.frame.polygon_mm, hit.q, n);
    if (!ch) { this.clearKnife(); return; }
    const pts = ch.map(([x, y]) => [x + hit.slot.ox, y + hit.slot.oy]);
    const gap = this.knife.gap;
    if (!this.knifeObj) {
      this.knifeObj = new Item({ originX: "center", originY: "center", selectable: false, evented: false, objectCaching: false });
      this.knifeObj.v3 = { kind: "ui" };
      this.c.add(this.knifeObj);
    }
    const [a, b] = pts;
    const cx = (a[0] + b[0]) / 2, cy = (a[1] + b[1]) / 2;
    this.knifeObj.set({ left: cx, top: cy, width: Math.abs(a[0] - b[0]) + gap + 2, height: Math.abs(a[1] - b[1]) + gap + 2 });
    this.knifeObj.paint = (ctx, z) => {
      ctx.save();
      for (const s of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(a[0] - cx + n[0] * s * gap / 2, a[1] - cy + n[1] * s * gap / 2);
        ctx.lineTo(b[0] - cx + n[0] * s * gap / 2, b[1] - cy + n[1] * s * gap / 2);
        ctx.lineWidth = 1.5 / z; ctx.strokeStyle = C.ai; ctx.setLineDash([5 / z, 3 / z]); ctx.stroke();
      }
      ctx.restore();
    };
    this.knifeAt = { panel: hit.panel, through: hit.q, pageId: hit.slot.page.id };
    this.c.requestRenderAll();
    this.perf.moves.push(performance.now() - t0);
  }

  clearKnife() {
    if (this.knifeObj) { this.c.remove(this.knifeObj); this.knifeObj = null; this.c.requestRenderAll(); }
    this.knifeAt = null;
  }

  onDown(o) {
    const p = this.c.getScenePoint(o.e);
    const hit = this.panelAt([p.x, p.y]);
    if (hit) this.hooks.onPageFocus(hit.slot.page.id);
    const t = this.tool;
    if (t === "knife") {
      if (this.knifeAt) this.hooks.onKnife(this.knifeAt.panel, this.knifeAt.through, this.knifeAt.pageId);
      return;
    }
    if (t === "frame" && this.frameMode === "join" && o.target && o.target.v3 && o.target.v3.kind === "panel") {
      const id = o.target.v3.id;
      if (!this.pickA) { this.pickA = id; this.touch(); this.hooks.onJoinPick(id, null); }
      else if (this.pickA !== id) { const a = this.pickA; this.pickA = null; this.hooks.onJoinPick(a, id); }
      return;
    }
    if (t === "frame" && this.frameMode === "add" && hit && !o.target?.selectable) { this.hooks.onAdd("frame", hit, [p.x, p.y]); return; }
    if ((t === "balloon" || t === "text" || t === "tone") && hit && hit.panel) {
      const target = o.target && o.target.selectable ? o.target : null;
      if (!target) this.hooks.onAdd(t, hit, [p.x, p.y]);
      else if (t === "text" && target.v3.kind === "text") this.editText(target.v3.id);
    }
  }

  onDbl(o) {
    const tg = o.target;
    if (!tg || !tg.v3) return;
    if (tg.v3.kind === "text") this.editText(tg.v3.id);
    else if (tg.v3.kind === "panel" && this.tool === "select") this.hooks.onImageEdit(tg.v3.id);
  }

  editText(id) {
    const t = this.model.find("text_items", id);
    if (!t) return;
    if (t.fixed) { this.hooks.onRefuse("動かさない印の付いた文字は直せません"); return; }
    this.c.discardActiveObject();
    // 文字の道具で押したとき（mouse:down の中）に欄へフォーカスを移しても、そのあとのブラウザの既定の動き
    // （押した所へフォーカスを移す）で欄から外れ、打つ前に終わっていた。押す出来事が終わってから打てる状態にする
    setTimeout(() => { const cur = this.model.find("text_items", id); if (cur) this.text.edit(cur); }, 0);
  }

  onSel(o) {
    const a = this.c.getActiveObject();
    this.selectedId = a && a.v3 ? a.v3.id : null;
    this.touch();
    this.hooks.onSelect(a && a.v3 ? { kind: a.v3.kind, id: a.v3.id, pageId: a.v3.pageId } : null);
  }

  // 動かしている間：文字の要素も一緒に動かす
  onMoving(o) {
    const t0 = performance.now();
    const it = o.target;
    if (it && it.v3 && it.v3.kind === "text") this.text.movePreview(it.v3.id, this.boxOf(it));
    this.perf.moves.push(performance.now() - t0);
  }

  boxOf(it) {
    const b = it.v3.locBox;
    const a = it.toWorld(b[0]), c = it.toWorld(b[2]);
    return [Math.min(a[0], c[0]) - it.v3.ox, Math.min(a[1], c[1]) - it.v3.oy, Math.max(a[0], c[0]) - it.v3.ox, Math.max(a[1], c[1]) - it.v3.oy];
  }

  onModified(o) {
    const it = o.target;
    if (!it || !it.v3) return;
    const v = it.v3;
    const back = (P) => P.map((q) => { const w = it.toWorld(q); return [w[0] - v.ox, w[1] - v.oy]; });
    if (v.kind === "panel") {
      const before = this.model.find("panels", v.id);
      const poly = back(v.loc);
      // 動かしただけ（大きさを変えていない）ならコマの絵も同じだけ動かす
      const moved = Math.abs(it.scaleX - 1) < 1e-6 && Math.abs(it.scaleY - 1) < 1e-6 && !v.vertexMoved;
      const d = [poly[0][0] - before.frame.polygon_mm[0][0], poly[0][1] - before.frame.polygon_mm[0][1]];
      this.hooks.onPanelChange(v.id, poly, moved ? d : null);
    } else if (v.kind === "text") {
      const box = this.boxOf(it);
      this.hooks.onTextChange(v.id, {
        box, outline: v.locOutline ? back(v.locOutline) : null,
        target: v.target ? this.targetAfter(it) : null,
      });
    } else if (v.kind === "tone") {
      const [x0, y0, x1, y1] = this.boxAfter(it, v.row.box_mm);
      this.hooks.onToneChange(v.id, [x0, y0, x1, y1], it);
    } else if (v.kind === "image") {
      const w = it.width * it.scaleX, h = it.height * it.scaleY;
      this.hooks.onImageChange(v.id, [it.left - v.ox - w / 2, it.top - v.oy - h / 2, it.left - v.ox + w / 2, it.top - v.oy + h / 2]);
    }
  }

  // しっぽの先：掴んで動かしたならその点、物ごと動かしたなら同じだけ動かした点
  targetAfter(it) {
    const v = it.v3;
    if (v.tailMoved) return [v.target[0] - v.ox, v.target[1] - v.oy];
    const t = v.row.tail_target_mm;
    // 作ったときの変換（平行移動だけ）から、今の変換への写し
    const c0 = this.createdCenter(it);
    const local = apply([1, 0, 0, 1, -c0[0], -c0[1]], [t[0] + v.ox, t[1] + v.oy]);
    const w = it.toWorld(local);
    return [w[0] - v.ox, w[1] - v.oy];
  }

  createdCenter(it) { return it.v3.created || (it.v3.created = [it.left, it.top]); }

  boxAfter(it, box) {
    const v = it.v3;
    const c0 = this.createdCenter(it);
    const a = it.toWorld([box[0] + v.ox - c0[0], box[1] + v.oy - c0[1]]);
    const b = it.toWorld([box[2] + v.ox - c0[0], box[3] + v.oy - c0[1]]);
    return [Math.min(a[0], b[0]) - v.ox, Math.min(a[1], b[1]) - v.oy, Math.max(a[0], b[0]) - v.ox, Math.max(a[1], b[1]) - v.oy];
  }

  // 確かめ・判断待ちから飛んだ所を、少しの間だけ囲んで見せる
  flash(pageId, box) {
    const s = this.slots.find((x) => x.page.id === pageId);
    if (!s) return;
    const [x0, y0, x1, y1] = [box[0] + s.ox - 1.5, box[1] + s.oy - 1.5, box[2] + s.ox + 1.5, box[3] + s.oy + 1.5];
    const it = new Item({ left: (x0 + x1) / 2, top: (y0 + y1) / 2, width: x1 - x0 + 2, height: y1 - y0 + 2, originX: "center", originY: "center",
                          selectable: false, evented: false, objectCaching: false });
    it.v3 = { kind: "ui" };
    it.paint = (ctx, z) => { ctx.lineWidth = 3 / z; ctx.strokeStyle = C.need; ctx.strokeRect(x0 - it.left, y0 - it.top, x1 - x0, y1 - y0); };
    this.c.add(it);
    this.c.requestRenderAll();
    setTimeout(() => { this.c.remove(it); this.c.requestRenderAll(); }, 1600);
  }

  // 選んだ物の見た目が変わったので、描いた物の控え（fabric の cache）を捨てて描き直す
  touch() { for (const o of this.c.getObjects()) o.dirty = true; this.c.requestRenderAll(); }

  // ---------------------------------------------------------------- 外から選ぶ
  select(kind, id, pan = true) {
    const o = this.c.getObjects().find((x) => x.v3 && x.v3.kind === kind && x.v3.id === id && x.selectable);
    if (!o) return false;
    this.c.setActiveObject(o);
    this.selectedId = id;
    void pan;
    this.c.requestRenderAll();
    return true;
  }

  objectOf(kind, id) { return this.c.getObjects().find((x) => x.v3 && x.v3.kind === kind && x.v3.id === id) || null; }
}

// 作った物の中心を、作ったときに覚えておく（動かした後の写しに使う）
const origAdd = PageCanvas.prototype.add;
PageCanvas.prototype.add = function (...objs) {
  for (const o of objs) if (o.v3 && !o.v3.created) o.v3.created = [o.left, o.top];
  return origAdd.apply(this, objs);
};
