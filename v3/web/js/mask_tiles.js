// 囲みの1回の変更を、変わった所のタイル（TILE 画素四方）の前の画素だけで覚える（全画素を写さない）。
// 塗る前に、その線が当たるタイルを1度だけ写す。何も塗っていないタイルは画素を持たずに「空」と覚える。
// 戻すとやり直すは同じ処理：今のタイルを写してから、覚えたタイルを置き、覚えた物と入れ替える。
// どのコマの囲みかは app.js のコマごとの取り消しの記録が持つ。ここは渡された canvas に当てるだけ。
export const TILE = 256;
const EMPTY = 0;

export class MaskEdit {
  constructor(boxBefore) {
    this.tiles = new Map();
    this.box = boxBefore;      // 入れ替える相手の「塗った所の外接の箱」
    this.bytes = 0;
  }

  // rect（[x0, y0, x1, y1]）が当たるタイルのうち、まだ写していない物を写す。paintedBox は今の塗った所の外接の箱
  touch(canvas, rect, paintedBox) {
    const w = canvas.width, h = canvas.height;
    const tx0 = Math.max(0, Math.floor(rect[0] / TILE)), ty0 = Math.max(0, Math.floor(rect[1] / TILE));
    const tx1 = Math.min(Math.ceil(w / TILE) - 1, Math.floor((rect[2] - 1) / TILE));
    const ty1 = Math.min(Math.ceil(h / TILE) - 1, Math.floor((rect[3] - 1) / TILE));
    for (let ty = ty0; ty <= ty1; ty++) {
      for (let tx = tx0; tx <= tx1; tx++) {
        const k = ty * 100000 + tx;
        if (this.tiles.has(k)) continue;
        const t = capture(canvas, tx, ty, paintedBox);
        this.tiles.set(k, t);
        if (t !== EMPTY) this.bytes += t.data.length;
      }
    }
  }

  // 戻す・やり直す。paintedBox は今の外接の箱。入れ替えた後の外接の箱を返す
  swap(canvas, paintedBox) {
    const ctx = canvas.getContext("2d");
    let bytes = 0;
    for (const [k, saved] of this.tiles) {
      const tx = k % 100000, ty = Math.floor(k / 100000);
      const now = capture(canvas, tx, ty, paintedBox);
      const x = tx * TILE, y = ty * TILE;
      if (saved === EMPTY) ctx.clearRect(x, y, Math.min(TILE, canvas.width - x), Math.min(TILE, canvas.height - y));
      else ctx.putImageData(saved, x, y);
      this.tiles.set(k, now);
      if (now !== EMPTY) bytes += now.data.length;
    }
    this.bytes = bytes;
    const box = this.box;
    this.box = paintedBox;
    return box;
  }
}

function capture(canvas, tx, ty, paintedBox) {
  const x = tx * TILE, y = ty * TILE;
  const tw = Math.min(TILE, canvas.width - x), th = Math.min(TILE, canvas.height - y);
  if (!paintedBox || x >= paintedBox[2] || y >= paintedBox[3] || x + tw <= paintedBox[0] || y + th <= paintedBox[1]) return EMPTY;
  const d = canvas.getContext("2d").getImageData(x, y, tw, th);
  for (let i = 3; i < d.data.length; i += 4) if (d.data[i]) return d;
  return EMPTY;
}
