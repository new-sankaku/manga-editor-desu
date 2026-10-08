// 絵を見て、囲む・描き足す枠を動かす・ペンで描く・画素を消す所（fabric.js。vendor/fabric-7.4.0）。
// 座標は絵の画素（1単位 = 元の絵の 1 画素）。拡大と移動は fabric の viewportTransform で行う。
// 手の出来事は PointerEvent で受ける（enablePointerEvents）。ペンタブレットの筆圧・pointerType が届き、
// 間の点（getCoalescedEvents）も拾う。
// 囲んだ範囲は fabric の図形ではなく、絵と同じ大きさの画素のマスク（offscreen の canvas）に塗る。
// 送るのは画素のマスクなので、見えている物と送る物が同じになる。人の手の範囲は、塗るたびにマスクから引く（塗れない）。
// 塗るときに触るのは、線が当たった所の画素だけ（全画素を読まない）。1回の変更はタイルの差分で覚える（mask_tiles.js）。
import { MaskEdit } from "./mask_tiles.js";
import { drawSegment } from "./pen_render.js";

const { Canvas, FabricImage, Rect, Polyline, Circle, Point } = window.fabric;

const MASK_RGB = "rgb(61,90,214)";       // --ai

export class Stage {
  constructor(host, hooks) {
    this.host = host;
    // { onExtend(e), penBegin() → {canvas, widthPx, color}, onPenStroke(points, pointerType), eraseBegin(),
    //   onErase(points, widthPx), onMaskEdit(edit), maskBegin() → 塗ってよいか, onRefuse(message) }
    this.hooks = hooks;
    const el = document.createElement("canvas");
    host.append(el);
    this.c = new Canvas(el, { selection: false, preserveObjectStacking: true, fireRightClick: false,
                              stopContextMenu: true, enableRetinaScaling: true, enablePointerEvents: true });
    this.tool = "select";
    this.maskTool = "brush";
    this.brushPx = 24;
    this.penWidthPx = 3;
    this.erasePx = 16;
    this.base = null; this.size = null;
    this.layerObjs = [];
    this.maskCanvas = null; this.maskObj = null; this.maskBox = null; this.edit = null;
    this.protCanvas = null; this.protObj = null;
    this.extendRect = null; this.extend = null;
    this.drag = null; this.poly = null;
    this.cursor = new Circle({ radius: 10, fill: "rgba(0,0,0,0)", stroke: "#14171C", strokeWidth: 1,
                               originX: "center", originY: "center", selectable: false, evented: false,
                               visible: false, strokeUniform: true, excludeFromExport: true });
    this.c.add(this.cursor);
    new ResizeObserver(() => this.resize()).observe(host);
    this.resize();
    this.bind();
  }

  resize() {
    const r = this.host.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    this.c.setDimensions({ width: r.width, height: r.height });
    if (this.size) this.fit();
  }

  // ---------------------------------------------------------------- 絵を出す
  // layers：[{ image か canvas, x, y, w, h, opacity }]。canvas の層（描いている人の手の層）は、描くたびに描き直す。
  // keepView：拡大と位置をそのままにする（同じコマの絵を替えたとき）。
  // keepMask：囲んだ範囲を残す。絵の大きさが違えば残せないので消して、戻り値の maskKept を false にする
  async show({ image, protectedCanvas, layers, keepView = false, keepMask = false }) {
    for (const o of this.c.getObjects()) if (o !== this.cursor) this.c.remove(o);
    this.layerObjs = [];
    this.extendRect = null;
    this.drag = null;
    const size = image ? { w: image.naturalWidth || image.width, h: image.naturalHeight || image.height } : null;
    const sameSize = !!(size && this.size && size.w === this.size.w && size.h === this.size.h);
    this.size = size;
    const hadMask = !!this.maskBox;
    if (!image) { this.base = null; this.maskCanvas = null; this.maskBox = null; this.c.requestRenderAll(); return { maskKept: !hadMask }; }
    const opts = { left: 0, top: 0, originX: "left", originY: "top", selectable: false, evented: false };
    this.base = new FabricImage(image, { ...opts, objectCaching: false });
    this.c.add(this.base);
    for (const l of layers || []) {
      const src = l.canvas || l.image;
      const sw = l.canvas ? l.canvas.width : l.image.naturalWidth, sh = l.canvas ? l.canvas.height : l.image.naturalHeight;
      const o = new FabricImage(src, { ...opts, left: l.x, top: l.y, scaleX: l.w / sw, scaleY: l.h / sh,
                                       opacity: l.opacity ?? 1, objectCaching: false });
      this.layerObjs.push(o);
      this.c.add(o);
    }
    const kept = keepMask && sameSize && this.maskCanvas;
    if (!kept) {
      this.maskCanvas = document.createElement("canvas");
      this.maskCanvas.width = size.w; this.maskCanvas.height = size.h;
      this.maskCanvas.getContext("2d", { willReadFrequently: true });
      this.maskBox = null;
    }
    this.maskObj = new FabricImage(this.maskCanvas, { ...opts, opacity: 0.45, objectCaching: false,
                                                     visible: this.maskVisible !== false });
    this.c.add(this.maskObj);
    this.protCanvas = protectedCanvas || null;
    if (this.protCanvas) {
      this.protObj = new FabricImage(this.protCanvas, { ...opts, opacity: 0.5, objectCaching: false });
      this.c.add(this.protObj);
      if (this.maskBox) this.subtractProtected(this.maskBox);
    } else this.protObj = null;
    this.c.bringObjectToFront(this.cursor);
    if (this.extend) this.setExtend(this.extend);
    if (!(keepView && sameSize)) this.fit();
    this.prepareErase();
    this.c.requestRenderAll();
    return { maskKept: !hadMask || !!kept };
  }

  redraw() { this.c.requestRenderAll(); }

  fit() {
    if (!this.size) return;
    const e = this.tool === "extend" && this.extend ? this.extend : { left: 0, top: 0, right: 0, bottom: 0 };
    const w = this.size.w + e.left + e.right, h = this.size.h + e.top + e.bottom;
    const pad = 72;
    const z = Math.min((this.c.width - pad * 2) / w, (this.c.height - pad * 2) / h);
    const zz = Math.max(0.02, z);
    this.c.setViewportTransform([zz, 0, 0, zz, (this.c.width - w * zz) / 2 + e.left * zz,
                                 (this.c.height - h * zz) / 2 + e.top * zz + 16]);
    this.syncCursor();
  }

  zoomBy(f) {
    const ctr = new Point(this.c.width / 2, this.c.height / 2);
    this.c.zoomToPoint(ctr, Math.min(32, Math.max(0.02, this.c.getZoom() * f)));
    this.syncCursor();
  }

  // ---------------------------------------------------------------- 道具
  setTool(tool) {
    const extendChanged = (tool === "extend") !== (this.tool === "extend");
    this.tool = tool;
    this.poly = null; this.drag = null;
    this.clearPreview();
    if (this.extendRect) {
      const on = tool === "extend";
      this.extendRect.set({ visible: on, selectable: on, evented: on });
      if (on) this.c.setActiveObject(this.extendRect); else this.c.discardActiveObject();
    }
    this.c.defaultCursor = tool === "select" ? "grab" : "crosshair";
    this.syncCursor();
    // 描き足す枠を出す・しまうときだけ合わせ直す（ほかの道具に替えても拡大はそのまま）
    if (extendChanged) this.fit();
    this.prepareErase();
    this.c.requestRenderAll();
  }

  // 消しゴムを選んだとき・消しゴムのまま絵を替えたときに、絵を canvas に写しておく
  // （大きい絵では写すのに数百 ms かかるので、消し始めたときに写すと最初の線が遅れる）
  prepareErase() { if (this.tool === "erase" && this.base) this.baseCanvas(); }

  setMaskTool(t) { this.maskTool = t; this.poly = null; this.clearPreview(); this.syncCursor(); }
  setBrushPx(px) { this.brushPx = px; this.syncCursor(); }
  setMaskVisible(on) { this.maskVisible = on; if (this.maskObj) { this.maskObj.visible = on; this.c.requestRenderAll(); } }

  syncCursor() {
    const r = this.tool === "mask" && (this.maskTool === "brush" || this.maskTool === "eraser") ? this.brushPx / 2
      : this.tool === "erase" ? this.erasePx / 2 : this.tool === "pen" ? this.penWidthPx / 2 : 0;
    this.cursor.set({ radius: Math.max(r, 0.5), visible: r > 0 && this.cursor.visible });
    this.cursorRadius = r;
    this.c.requestRenderAll();
  }

  // ---------------------------------------------------------------- マスク
  maskCtx() { return this.maskCanvas.getContext("2d"); }

  clip(rect) {
    const x0 = Math.max(0, Math.floor(rect[0])), y0 = Math.max(0, Math.floor(rect[1]));
    const x1 = Math.min(this.size.w, Math.ceil(rect[2])), y1 = Math.min(this.size.h, Math.ceil(rect[3]));
    return x1 > x0 && y1 > y0 ? [x0, y0, x1, y1] : null;
  }

  beginEdit() { this.edit = new MaskEdit(this.maskBox); }

  // rect に塗る前に、その所の前の画素を覚える
  touch(rect) { this.edit.touch(this.maskCanvas, rect, this.maskBox); }

  // 塗った後：人の手の範囲を引き、塗った所の外接の箱を広げ、画面を描き直す
  painted(rect, grow = true) {
    this.subtractProtected(rect);
    if (grow) this.maskBox = this.maskBox ? [Math.min(this.maskBox[0], rect[0]), Math.min(this.maskBox[1], rect[1]),
      Math.max(this.maskBox[2], rect[2]), Math.max(this.maskBox[3], rect[3])] : rect.slice();
    this.c.requestRenderAll();
  }

  endEdit() {
    const e = this.edit;
    this.edit = null;
    if (e && e.tiles.size) this.hooks.onMaskEdit && this.hooks.onMaskEdit(e);
  }

  // 取り消す・やり直す（どちらも入れ替え）。どのコマの変更かは呼ぶ側（app.js のコマごとの記録）が決める
  swapMaskEdit(edit) {
    if (!this.maskCanvas) return false;
    this.maskBox = edit.swap(this.maskCanvas, this.maskBox);
    this.c.requestRenderAll();
    return true;
  }

  subtractProtected(rect) {
    if (!this.protCanvas || !this.maskCanvas) return;
    const r = this.clip(rect);
    if (!r) return;
    const [x0, y0, x1, y1] = r;
    const x = this.maskCtx();
    x.save();
    x.globalCompositeOperation = "destination-out";
    x.drawImage(this.protCanvas, x0, y0, x1 - x0, y1 - y0, x0, y0, x1 - x0, y1 - y0);
    x.restore();
  }

  whole() { return [0, 0, this.size.w, this.size.h]; }

  clearMask() {
    if (!this.maskCanvas || !this.maskBox) return;
    this.beginEdit();
    const b = this.maskBox;
    this.touch(b);
    this.maskCtx().clearRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
    this.maskBox = null;
    this.c.requestRenderAll();
    this.endEdit();
  }
  fillMask() {
    if (!this.maskCanvas) return;
    this.beginEdit();
    this.touch(this.whole());
    const x = this.maskCtx();
    x.fillStyle = MASK_RGB; x.fillRect(0, 0, this.size.w, this.size.h);
    this.painted(this.whole());
    this.endEdit();
  }
  // 反転：塗った色で全体を埋めた上から、今の囲みを抜く（画素ごとの計算をしない）
  invertMask() {
    if (!this.maskCanvas) return;
    this.beginEdit();
    this.touch(this.whole());
    const t = document.createElement("canvas");
    t.width = this.size.w; t.height = this.size.h;
    const tx = t.getContext("2d");
    tx.fillStyle = MASK_RGB; tx.fillRect(0, 0, t.width, t.height);
    tx.globalCompositeOperation = "destination-out";
    tx.drawImage(this.maskCanvas, 0, 0);
    const x = this.maskCtx();
    x.clearRect(0, 0, this.size.w, this.size.h);
    x.drawImage(t, 0, 0);
    this.maskBox = null;
    this.painted(this.whole());
    this.endEdit();
  }

  // 囲んだ所があるか。塗った所の外接の箱の中だけを読む（頼むときに1回）
  hasMask() {
    if (!this.maskCanvas || !this.maskBox) return false;
    const r = this.clip(this.maskBox);
    if (!r) return false;
    const d = this.maskCtx().getImageData(r[0], r[1], r[2] - r[0], r[3] - r[1]).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] >= 128) return true;
    return false;
  }

  // 送るマスク：塗った所が白（不透明）、ほかは透明の PNG。サーバーは 赤×不透明度 を読む（image_process_inputs.to_array）
  maskPngBase64() {
    if (!this.hasMask()) return null;
    const c = document.createElement("canvas");
    c.width = this.size.w; c.height = this.size.h;
    const x = c.getContext("2d");
    x.drawImage(this.maskCanvas, 0, 0);
    x.globalCompositeOperation = "source-in";
    x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height);
    return c.toDataURL("image/png").split(",")[1];
  }

  // コマを替える前に、囲みを外へ出す。持つのは塗った所の箱の画素だけ（絵の全体の canvas は捨てる）。囲みが無ければ null
  takeMask() {
    if (!this.maskCanvas || !this.maskBox) return null;
    const r = this.clip(this.maskBox);
    if (!r) return null;
    const c = document.createElement("canvas");
    c.width = r[2] - r[0]; c.height = r[3] - r[1];
    c.getContext("2d").drawImage(this.maskCanvas, r[0], r[1], c.width, c.height, 0, 0, c.width, c.height);
    return { w: this.size.w, h: this.size.h, box: this.maskBox, rect: r, canvas: c };
  }

  // 前に出した囲みを戻す。大きさが違えば戻さずに false
  putMask(saved) {
    if (!saved || !this.size || saved.w !== this.size.w || saved.h !== this.size.h) return false;
    const x = this.maskCtx();
    x.clearRect(0, 0, this.size.w, this.size.h);
    x.drawImage(saved.canvas, saved.rect[0], saved.rect[1]);
    this.maskBox = saved.box;
    if (this.protCanvas) this.subtractProtected(this.maskBox);
    this.c.requestRenderAll();
    return true;
  }

  segRect(a, b, w) {
    const r = w / 2 + 2;
    return this.clip([Math.min(a.x, b.x) - r, Math.min(a.y, b.y) - r, Math.max(a.x, b.x) + r, Math.max(a.y, b.y) + r]);
  }

  paintLine(a, b, erase) {
    const rect = this.segRect(a, b, this.brushPx);
    if (!rect) return;
    this.touch(rect);
    const x = this.maskCtx();
    x.save();
    x.globalCompositeOperation = erase ? "destination-out" : "source-over";
    x.strokeStyle = MASK_RGB;
    x.lineWidth = this.brushPx; x.lineCap = "round"; x.lineJoin = "round";
    x.beginPath(); x.moveTo(a.x, a.y); x.lineTo(a === b ? b.x + 0.01 : b.x, b.y); x.stroke();
    x.restore();
    this.painted(rect, !erase);
  }

  fillPolygon(points) {
    if (points.length < 3) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of points) { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); }
    const rect = this.clip([x0 - 1, y0 - 1, x1 + 1, y1 + 1]);
    if (!rect) return;
    this.beginEdit();
    this.touch(rect);
    const x = this.maskCtx();
    x.save();
    x.fillStyle = MASK_RGB;
    x.beginPath(); x.moveTo(points[0].x, points[0].y);
    for (const p of points.slice(1)) x.lineTo(p.x, p.y);
    x.closePath(); x.fill();
    x.restore();
    this.painted(rect);
    this.endEdit();
  }

  // ---------------------------------------------------------------- 描き足す枠
  setExtend(e) {
    this.extend = { ...e };
    if (!this.size) return;
    const geo = { left: -e.left, top: -e.top, width: this.size.w + e.left + e.right, height: this.size.h + e.top + e.bottom,
                  scaleX: 1, scaleY: 1 };
    if (!this.extendRect) {
      this.extendRect = new Rect({ ...geo, originX: "left", originY: "top", fill: "rgba(61,90,214,0.06)",
        stroke: "#3D5AD6", strokeWidth: 1.5, strokeDashArray: [6, 4], strokeUniform: true,
        lockMovementX: true, lockMovementY: true, lockRotation: true, lockScalingFlip: true,
        cornerColor: "#3D5AD6", cornerStrokeColor: "#fff", transparentCorners: false, cornerSize: 11,
        borderColor: "#3D5AD6", visible: this.tool === "extend", selectable: this.tool === "extend",
        evented: this.tool === "extend", hoverCursor: "default" });
      this.extendRect.setControlsVisibility({ mtr: false });
      this.extendRect.on("modified", () => this.extendFromRect());
      this.extendRect.on("scaling", () => this.extendFromRect(true));
      this.c.add(this.extendRect);
      if (this.tool === "extend") this.c.setActiveObject(this.extendRect);
    } else {
      this.extendRect.set(geo);
      this.extendRect.setCoords();
    }
    if (this.tool === "extend") this.fit();
    this.c.requestRenderAll();
  }

  extendFromRect(live) {
    const r = this.extendRect;
    const x0 = r.left, y0 = r.top, x1 = r.left + r.width * r.scaleX, y1 = r.top + r.height * r.scaleY;
    const e = { left: Math.max(0, Math.round(-x0)), top: Math.max(0, Math.round(-y0)),
                right: Math.max(0, Math.round(x1 - this.size.w)), bottom: Math.max(0, Math.round(y1 - this.size.h)) };
    if (!live) this.setExtend(e);
    this.hooks.onExtend && this.hooks.onExtend(e);
  }

  // ---------------------------------------------------------------- 線の見本（多角形・投げ縄・四角だけ）
  clearPreview() {
    if (this.preview) { this.c.remove(this.preview); this.preview = null; }
    this.c.requestRenderAll();
  }

  setPreview(obj) {
    this.clearPreview();
    this.preview = obj;
    obj.set({ selectable: false, evented: false, objectCaching: false });
    this.c.add(obj);
    this.c.bringObjectToFront(this.cursor);
  }

  polyline(points, stroke, width, fill) {
    return new Polyline(points.map((p) => ({ x: p.x, y: p.y })), {
      stroke, strokeWidth: width, fill: fill || "", strokeLineCap: "round", strokeLineJoin: "round",
      strokeUniform: width < 3, originX: "left", originY: "top" });
  }

  // 多角形の途中で Enter（閉じる）・Esc（やめる）。キーは app.js の1か所で受ける。扱ったら true
  polygonKey(key) {
    if (!this.poly) return false;
    if (key === "Escape") { this.poly = null; this.clearPreview(); return true; }
    if (key === "Enter") { this.closePolygon(); return true; }
    return false;
  }

  // ---------------------------------------------------------------- 手の動き
  bind() {
    const c = this.c;
    c.on("mouse:wheel", (o) => {
      const e = o.e;
      c.zoomToPoint(new Point(e.offsetX, e.offsetY), Math.min(32, Math.max(0.02, c.getZoom() * (0.999 ** e.deltaY))));
      e.preventDefault(); e.stopPropagation();
    });
    c.on("mouse:move", (o) => {
      const p = c.getScenePoint(o.e);
      if (this.cursorRadius > 0) { this.cursor.set({ left: p.x, top: p.y, visible: true }); }
      this.onMove(p, o.e);
      c.requestRenderAll();
    });
    c.on("mouse:out", () => { this.cursor.set({ visible: false }); c.requestRenderAll(); });
    c.on("mouse:down", (o) => this.onDown(c.getScenePoint(o.e), o.e));
    c.on("mouse:up", (o) => this.onUp(c.getScenePoint(o.e), o.e));
    c.on("mouse:dblclick", () => { if (this.poly) this.closePolygon(); });
  }

  // 1回の出来事と、その間にまとめられた出来事（ペンタブレットの細かい点）
  events(e) {
    const list = typeof e.getCoalescedEvents === "function" ? e.getCoalescedEvents() : [];
    return list.length ? list : [e];
  }

  onDown(p, e) {
    if (!this.size) return;
    const t = this.tool;
    if (t === "select" || e.button === 1) {
      this.drag = { kind: "pan", x: e.clientX, y: e.clientY };
      return;
    }
    if (t === "mask") {
      if (this.hooks.maskBegin && !this.hooks.maskBegin()) return;
      const m = this.maskTool;
      if (m === "brush" || m === "eraser") {
        this.beginEdit();
        this.drag = { kind: m, last: p };
        this.paintLine(p, p, m === "eraser");
      } else if (m === "lasso") {
        this.drag = { kind: "lasso", points: [p] };
      } else if (m === "rect") {
        this.drag = { kind: "rect", from: p };
      } else if (m === "polygon") {
        if (!this.poly) this.poly = [p];
        else {
          const f = this.poly[0];
          const near = Math.hypot(f.x - p.x, f.y - p.y) * this.c.getZoom() < 10;
          if (near && this.poly.length >= 3) { this.closePolygon(); return; }
          this.poly.push(p);
        }
        this.setPreview(this.polyline([...this.poly, p], "#3D5AD6", 1.5));
      }
      return;
    }
    if (t === "pen") {
      const target = this.refusable(() => this.hooks.penBegin());
      if (!target) return;
      this.drag = { kind: "pen", points: [], t0: e.timeStamp, pointerType: e.pointerType || "mouse", target };
      const pt = this.penPoint(p, e);
      this.drag.points.push(pt);
      drawSegment(target.canvas.getContext("2d"), pt, pt, target.widthPx, target.color);
      return;
    }
    if (t === "erase") {
      if (!this.refusable(() => this.hooks.eraseBegin())) return;
      const canvas = this.baseCanvas();
      this.drag = { kind: "erase", points: [p], canvas };
      this.eraseSeg(canvas, p, p);
    }
  }

  // 描き始めてよいか（app.js が理由を返して断る）
  refusable(fn) {
    try { return fn(); } catch (err) { this.hooks.onRefuse && this.hooks.onRefuse(err.message); return null; }
  }

  // 画素の消しゴム：保存を待たずに、絵の写し（canvas）から消して見せる。サーバーの答えが来たら、その絵に替わる
  baseCanvas() {
    const el = this.base.getElement();
    if (el instanceof HTMLCanvasElement) return el;
    const c = document.createElement("canvas");
    c.width = this.size.w; c.height = this.size.h;
    c.getContext("2d").drawImage(el, 0, 0);
    this.base.setElement(c);
    return c;
  }

  eraseSeg(canvas, a, b) {
    const x = canvas.getContext("2d");
    x.save();
    x.globalCompositeOperation = "destination-out";
    x.lineWidth = this.erasePx; x.lineCap = "round"; x.lineJoin = "round";
    x.beginPath(); x.moveTo(a.x, a.y); x.lineTo(a === b ? b.x + 0.01 : b.x, b.y); x.stroke();
    x.restore();
  }

  // 筆圧は、機器が筆圧を返すペン（pointerType=pen）のときだけ持つ。マウス・指は筆圧を返さない機器でも 0.5 が来る
  // （https://www.w3.org/TR/pointerevents3/#dom-pointerevent-pressure）ので、その値は使わずに null にする
  penPoint(p, e) {
    const pressure = e.pointerType === "pen" && typeof e.pressure === "number" ? e.pressure : null;
    const pts = this.drag.points;
    // 描き始めからの ms（出来事の時刻）。まとめられた出来事の時刻が前後しても、並びは描いた順のまま
    const ms = Math.max(0, e.timeStamp - this.drag.t0, pts.length ? pts[pts.length - 1].ms : 0);
    return { x: p.x, y: p.y, pressure, ms };
  }

  onMove(p, e) {
    const d = this.drag;
    if (this.poly && !d) { this.setPreview(this.polyline([...this.poly, p], "#3D5AD6", 1.5)); return; }
    if (!d) return;
    if (d.kind === "pan") {
      const v = this.c.viewportTransform.slice();
      v[4] += e.clientX - d.x; v[5] += e.clientY - d.y;
      d.x = e.clientX; d.y = e.clientY;
      this.c.setViewportTransform(v);
    } else if (d.kind === "brush" || d.kind === "eraser") {
      for (const ev of this.events(e)) {
        const q = this.c.getScenePoint(ev);
        this.paintLine(d.last, q, d.kind === "eraser");
        d.last = q;
      }
    } else if (d.kind === "lasso") {
      d.points.push(p);
      this.setPreview(this.polyline(d.points, "#3D5AD6", 1.5, "rgba(61,90,214,0.15)"));
    } else if (d.kind === "rect") {
      const x0 = Math.min(d.from.x, p.x), y0 = Math.min(d.from.y, p.y);
      this.setPreview(new Rect({ left: x0, top: y0, width: Math.abs(p.x - d.from.x), height: Math.abs(p.y - d.from.y),
        originX: "left", originY: "top", fill: "rgba(61,90,214,0.15)", stroke: "#3D5AD6", strokeWidth: 1.5,
        strokeUniform: true }));
    } else if (d.kind === "pen") {
      const x = d.target.canvas.getContext("2d");
      for (const ev of this.events(e)) {
        const pt = this.penPoint(this.c.getScenePoint(ev), ev);
        const last = d.points[d.points.length - 1];
        d.points.push(pt);
        drawSegment(x, last, pt, d.target.widthPx, d.target.color);
      }
    } else if (d.kind === "erase") {
      for (const ev of this.events(e)) {
        const q = this.c.getScenePoint(ev);
        this.eraseSeg(d.canvas, d.points[d.points.length - 1], q);
        d.points.push(q);
      }
    }
  }

  onUp(p) {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (d.kind === "brush" || d.kind === "eraser") {
      this.endEdit();
    } else if (d.kind === "lasso") {
      this.clearPreview();
      this.fillPolygon(d.points);
    } else if (d.kind === "rect") {
      this.clearPreview();
      const x0 = Math.min(d.from.x, p.x), y0 = Math.min(d.from.y, p.y), x1 = Math.max(d.from.x, p.x), y1 = Math.max(d.from.y, p.y);
      if (x1 - x0 < 1 || y1 - y0 < 1) return;
      this.fillPolygon([{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }]);
    } else if (d.kind === "pen") {
      this.hooks.onPenStroke && this.hooks.onPenStroke(d.points, d.pointerType);
    } else if (d.kind === "erase") {
      this.hooks.onErase && this.hooks.onErase(d.points, this.erasePx);
    }
  }

  closePolygon() {
    const pts = this.poly;
    this.poly = null;
    this.clearPreview();
    if (pts && pts.length >= 3) this.fillPolygon(pts);
  }
}
