// 絵を見て、囲む・描き足す枠を動かす・ペンで描く・画素を消す所（fabric.js。vendor/fabric-7.4.0）。
// 座標は絵の画素（1単位 = 元の絵の 1 画素）。拡大と移動は fabric の viewportTransform で行う。
// 囲んだ範囲は fabric の図形ではなく、絵と同じ大きさの画素のマスク（offscreen の canvas）に塗る。
// 送るのは画素のマスクなので、見えている物と送る物が同じになる。人の手の範囲は、塗るたびにマスクから引く（塗れない）。
const { Canvas, FabricImage, Rect, Polyline, Circle, Point } = window.fabric;

const MASK_RGB = "rgb(61,90,214)";       // --ai
const PROT_RGB = [196, 106, 0];          // --need
const MASK_HISTORY = 30;

export class Stage {
  constructor(host, hooks) {
    this.host = host;
    this.hooks = hooks; // { onExtend(l,t,r,b), onPenStroke(points), onErase(points, widthPx), onMaskChange(hasMask) }
    const el = document.createElement("canvas");
    host.append(el);
    this.c = new Canvas(el, { selection: false, preserveObjectStacking: true, fireRightClick: false,
                              stopContextMenu: true, enableRetinaScaling: true });
    this.tool = "select";
    this.maskTool = "brush";
    this.brushPx = 24;
    this.penWidthPx = 3;
    this.erasePx = 16;
    this.base = null; this.size = null;
    this.layerObjs = [];
    this.maskCanvas = null; this.maskObj = null;
    this.protCanvas = null; this.protObj = null;
    this.extendRect = null; this.extend = null;
    this.drag = null; this.poly = null;
    this.maskHistory = [];
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
  // key：出す絵の id。前と違う絵なら囲んだ範囲を消す（前の絵の上で塗った物を、別の絵に重ねない）
  async show({ image, protectedCanvas, layers, key }) {
    for (const o of this.c.getObjects()) if (o !== this.cursor) this.c.remove(o);
    this.layerObjs = [];
    this.extendRect = null;
    this.size = image ? { w: image.naturalWidth, h: image.naturalHeight } : null;
    if (!image) { this.base = null; this.maskCanvas = null; this.c.requestRenderAll(); return; }
    const opts = { left: 0, top: 0, originX: "left", originY: "top", selectable: false, evented: false };
    this.base = new FabricImage(image, opts);
    this.c.add(this.base);
    for (const l of layers || []) {
      const o = new FabricImage(l.image, { ...opts, left: l.x, top: l.y,
        scaleX: l.w / l.image.naturalWidth, scaleY: l.h / l.image.naturalHeight, opacity: l.opacity ?? 1 });
      this.layerObjs.push(o);
      this.c.add(o);
    }
    if (!this.maskCanvas || this.maskKey !== key || this.maskCanvas.width !== this.size.w || this.maskCanvas.height !== this.size.h) {
      this.maskCanvas = document.createElement("canvas");
      this.maskCanvas.width = this.size.w; this.maskCanvas.height = this.size.h;
      this.maskHistory = [];
      this.maskKey = key;
    }
    this.maskObj = new FabricImage(this.maskCanvas, { ...opts, opacity: 0.45, objectCaching: false,
                                                     visible: this.maskVisible !== false });
    this.c.add(this.maskObj);
    this.protCanvas = protectedCanvas || null;
    if (this.protCanvas) {
      this.protObj = new FabricImage(this.protCanvas, { ...opts, opacity: 0.5, objectCaching: false });
      this.c.add(this.protObj);
      this.subtractProtected();
    } else this.protObj = null;
    this.c.bringObjectToFront(this.cursor);
    if (this.extend) this.setExtend(this.extend);
    this.fit();
    this.maskChanged();
  }

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
    this.fit();
    this.c.requestRenderAll();
  }

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

  pushHistory() {
    if (!this.maskCanvas) return;
    this.maskHistory.push(this.maskCtx().getImageData(0, 0, this.size.w, this.size.h));
    if (this.maskHistory.length > MASK_HISTORY) this.maskHistory.shift();
  }

  undoMask() {
    const d = this.maskHistory.pop();
    if (!d) return false;
    this.maskCtx().putImageData(d, 0, 0);
    this.maskChanged();
    return true;
  }

  subtractProtected() {
    if (!this.protCanvas || !this.maskCanvas) return;
    const x = this.maskCtx();
    x.save();
    x.globalCompositeOperation = "destination-out";
    x.drawImage(this.protCanvas, 0, 0);
    x.restore();
  }

  maskChanged() {
    this.subtractProtected();
    if (this.maskObj) this.maskObj.dirty = true;
    this.c.requestRenderAll();
    this.hooks.onMaskChange && this.hooks.onMaskChange(this.hasMask());
  }

  clearMask() { if (!this.maskCanvas) return; this.pushHistory(); this.maskCtx().clearRect(0, 0, this.size.w, this.size.h); this.maskChanged(); }
  fillMask() {
    if (!this.maskCanvas) return;
    this.pushHistory();
    const x = this.maskCtx();
    x.fillStyle = MASK_RGB; x.fillRect(0, 0, this.size.w, this.size.h);
    this.maskChanged();
  }
  invertMask() {
    if (!this.maskCanvas) return;
    this.pushHistory();
    const x = this.maskCtx();
    const d = x.getImageData(0, 0, this.size.w, this.size.h);
    for (let i = 0; i < d.data.length; i += 4) {
      const a = 255 - d.data[i + 3];
      d.data[i] = 61; d.data[i + 1] = 90; d.data[i + 2] = 214; d.data[i + 3] = a;
    }
    x.putImageData(d, 0, 0);
    this.maskChanged();
  }

  hasMask() {
    if (!this.maskCanvas) return false;
    const d = this.maskCtx().getImageData(0, 0, this.size.w, this.size.h).data;
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

  paintLine(a, b, erase) {
    const x = this.maskCtx();
    x.save();
    x.globalCompositeOperation = erase ? "destination-out" : "source-over";
    x.strokeStyle = MASK_RGB; x.fillStyle = MASK_RGB;
    x.lineWidth = this.brushPx; x.lineCap = "round"; x.lineJoin = "round";
    x.beginPath(); x.moveTo(a.x, a.y); x.lineTo(b.x, b.y); x.stroke();
    x.restore();
  }

  fillPolygon(points) {
    if (points.length < 3) return;
    const x = this.maskCtx();
    x.save();
    x.fillStyle = MASK_RGB;
    x.beginPath(); x.moveTo(points[0].x, points[0].y);
    for (const p of points.slice(1)) x.lineTo(p.x, p.y);
    x.closePath(); x.fill();
    x.restore();
    this.maskChanged();
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

  // ---------------------------------------------------------------- 線の見本（描いている間だけ）
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
    window.addEventListener("keydown", (e) => {
      if (e.target.closest && e.target.closest("input,textarea,select")) return;
      if (e.key === "Escape" && this.poly) { this.poly = null; this.clearPreview(); }
      if (e.key === "Enter" && this.poly) this.closePolygon();
    });
  }

  onDown(p, e) {
    if (!this.size) return;
    const t = this.tool;
    if (t === "select" || e.button === 1) {
      this.drag = { kind: "pan", x: e.clientX, y: e.clientY };
      return;
    }
    if (t === "mask") {
      const m = this.maskTool;
      if (m === "brush" || m === "eraser") {
        this.pushHistory();
        this.drag = { kind: m, last: p };
        this.paintLine(p, p, m === "eraser");
        this.maskChanged();
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
      this.drag = { kind: "pen", points: [this.penPoint(p, e)], t0: performance.now() };
      return;
    }
    if (t === "erase") {
      this.drag = { kind: "erase", points: [p] };
    }
  }

  penPoint(p, e) {
    // PointerEvent の筆圧（マウスは押している間 0.5 が来る。https://www.w3.org/TR/pointerevents3/#dom-pointerevent-pressure）
    return { x: p.x, y: p.y, pressure: typeof e.pressure === "number" ? e.pressure : 0.5,
             ms: this.drag && this.drag.t0 !== undefined ? performance.now() - this.drag.t0 : 0 };
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
      this.paintLine(d.last, p, d.kind === "eraser");
      d.last = p;
      this.maskChanged();
    } else if (d.kind === "lasso") {
      d.points.push(p);
      this.setPreview(this.polyline(d.points, "#3D5AD6", 1.5, "rgba(61,90,214,0.15)"));
    } else if (d.kind === "rect") {
      const x0 = Math.min(d.from.x, p.x), y0 = Math.min(d.from.y, p.y);
      this.setPreview(new Rect({ left: x0, top: y0, width: Math.abs(p.x - d.from.x), height: Math.abs(p.y - d.from.y),
        originX: "left", originY: "top", fill: "rgba(61,90,214,0.15)", stroke: "#3D5AD6", strokeWidth: 1.5,
        strokeUniform: true }));
    } else if (d.kind === "pen") {
      d.points.push(this.penPoint(p, e));
      this.setPreview(this.polyline(d.points, "#14171C", this.penWidthPx));
    } else if (d.kind === "erase") {
      d.points.push(p);
      this.setPreview(this.polyline(d.points, "rgba(204,53,39,0.45)", this.erasePx));
    }
  }

  onUp(p) {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (d.kind === "lasso") {
      this.clearPreview();
      this.pushHistory();
      this.fillPolygon(d.points);
    } else if (d.kind === "rect") {
      this.clearPreview();
      const x0 = Math.min(d.from.x, p.x), y0 = Math.min(d.from.y, p.y), x1 = Math.max(d.from.x, p.x), y1 = Math.max(d.from.y, p.y);
      if (x1 - x0 < 1 || y1 - y0 < 1) return;
      this.pushHistory();
      this.fillPolygon([{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }]);
    } else if (d.kind === "pen") {
      this.hooks.onPenStroke && this.hooks.onPenStroke(d.points, () => this.clearPreview());
    } else if (d.kind === "erase") {
      this.hooks.onErase && this.hooks.onErase(d.points, this.erasePx, () => this.clearPreview());
    }
  }

  closePolygon() {
    const pts = this.poly;
    this.poly = null;
    this.clearPreview();
    if (pts && pts.length >= 3) { this.pushHistory(); this.fillPolygon(pts); }
  }
}
