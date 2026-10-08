// ペンの線を canvas に描く（描いている間の線・層の控えの絵・取り消した後の描き直しで同じ処理を使う）。
// 点は {x, y, pressure}（絵の画素）。筆圧は機器が返したときだけ数、返さないときは null（作った値を入れない）。
// 筆圧のある線：区間ごとに、両端の筆圧の平均 × 太さで描く（筆圧 0 の所は描かない）。
// 筆圧の無い線：筆の太さのまま一定の太さで描く（筆圧の代わりの値は使わない）。
export function drawStroke(ctx, pts, widthPx, color, opacity = 1) {
  if (!pts.length) return null;
  const pressured = pts[0].pressure !== null && pts[0].pressure !== undefined;
  const box = strokeBox(pts, widthPx);
  if (!pressured) {
    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = color; ctx.lineWidth = widthPx; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
    for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y);
    if (pts.length === 1) ctx.lineTo(pts[0].x + 0.01, pts[0].y);
    ctx.stroke();
    ctx.restore();
    return box;
  }
  if (opacity >= 1) { drawPressured(ctx, pts, widthPx, color); return box; }
  // 半透明で区間ごとに描くと重なりが濃くなるので、線の箱だけの canvas に描いてから重ねる
  const x0 = Math.floor(box[0]), y0 = Math.floor(box[1]);
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.ceil(box[2]) - x0); c.height = Math.max(1, Math.ceil(box[3]) - y0);
  const x = c.getContext("2d");
  x.translate(-x0, -y0);
  drawPressured(x, pts, widthPx, color);
  ctx.save(); ctx.globalAlpha = opacity; ctx.drawImage(c, x0, y0); ctx.restore();
  return box;
}

// 描いている間に、最後の区間だけを足す（drawStroke の筆圧のある線・無い線と同じ見た目になる）
export function drawSegment(ctx, a, b, widthPx, color) {
  const w = a.pressure === null || a.pressure === undefined ? widthPx : widthPx * (a.pressure + b.pressure) / 2;
  if (w <= 0) return null;
  ctx.save();
  ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(a === b ? b.x + 0.01 : b.x, b.y); ctx.stroke();
  ctx.restore();
  return [Math.min(a.x, b.x) - w / 2, Math.min(a.y, b.y) - w / 2, Math.max(a.x, b.x) + w / 2, Math.max(a.y, b.y) + w / 2];
}

function drawPressured(ctx, pts, widthPx, color) {
  if (pts.length === 1) { drawSegment(ctx, pts[0], pts[0], widthPx, color); return; }
  for (let i = 1; i < pts.length; i++) drawSegment(ctx, pts[i - 1], pts[i], widthPx, color);
}

export function strokeBox(pts, widthPx) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of pts) { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); }
  const r = widthPx / 2 + 1;
  return [x0 - r, y0 - r, x1 + r, y1 + r];
}
