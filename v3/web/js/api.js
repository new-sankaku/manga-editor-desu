// サーバーとのやり取り。利用者は X-V3-User で送る（ログインが入るまでの仮。http_dependencies.py）。
// 絵も X-V3-User が要るので、<img src> に URL を直接は入れず、取ってきて blob の URL にする。
// blob の URL は絵を読み終えたらすぐ解放する（revokeObjectURL）。取ってきた中身（Blob）は大きさの上限つきで持つ。
const USER_KEY = "v3.user";

export function currentUser() {
  try { return localStorage.getItem(USER_KEY) || ""; } catch { return ""; }
}
export function setUser(name) {
  try { localStorage.setItem(USER_KEY, name); } catch { /* 保存できない環境では、この画面を開いている間だけ使う */ }
  memoUser = name;
  blobCache.clear(); blobBytes = 0; overlayCache.clear();
}
let memoUser = currentUser();

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function call(method, path, { json, form, raw } = {}) {
  if (!memoUser) throw new ApiError(401, "利用者の名前を入れてください");
  const headers = { "X-V3-User": memoUser };
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form !== undefined) body = form;
  let r;
  try {
    r = await fetch(path, { method, headers, body });
  } catch (e) {
    // fetch が答えを受け取れない（回線が切れた・サーバーが止まった）。英語の「Failed to fetch」をそのまま見せない
    throw new NetworkError(navigator.onLine === false
      ? "オフラインです。回線がつながったら、もう一度してください"
      : "サーバーにつながりません。サーバーが止まっているか、回線が切れています");
  }
  if (raw) {
    if (!r.ok) throw new ApiError(r.status, await r.text());
    return r;
  }
  const text = await r.text();
  const isJson = (r.headers.get("content-type") || "").includes("application/json");
  if (!r.ok) {
    const data = isJson && text ? JSON.parse(text) : null;
    throw new ApiError(r.status, data && data.detail !== undefined ? data.detail : `${r.status} ${text}`);
  }
  return isJson && text ? JSON.parse(text) : null;
}

// 届かなかった（送れたかどうかも分からない）
export class NetworkError extends Error {}

export const get = (p) => call("GET", p);
export const post = (p, json) => call("POST", p, { json });
export const postForm = (p, form) => call("POST", p, { form });
export const op = (workId, body) => post(`/works/${workId}/ops`, body);
export const undo = (workId, eventId) => post(`/works/${workId}/events/${eventId}/undo`);

// 同じ URL の絵は一度だけ取る（絵の中身は id で決まり、変わらない）。持つのは Blob（縮めた中身）で、合わせて
// BLOB_LIMIT を超えたら古い物から捨てる。
const BLOB_LIMIT = 192 * 1024 * 1024;
const blobCache = new Map();
let blobBytes = 0;
function fetchBlob(path) {
  const hit = blobCache.get(path);
  if (hit) { blobCache.delete(path); blobCache.set(path, hit); return hit.p; }
  const entry = { p: null, bytes: 0 };
  entry.p = call("GET", path, { raw: true }).then(async (r) => {
    const blob = await r.blob();
    entry.bytes = blob.size; blobBytes += blob.size;
    for (const [k, e] of blobCache) {
      if (blobBytes <= BLOB_LIMIT || k === path) break;
      blobCache.delete(k); blobBytes -= e.bytes;
    }
    return { blob, headers: r.headers };
  });
  entry.p.catch(() => { if (blobCache.get(path) === entry) blobCache.delete(path); });
  blobCache.set(path, entry);
  return entry.p;
}

// 絵を読んで HTMLImageElement で返す（blob の URL は読み終えたら解放する）
export async function image(path) {
  const { blob, headers } = await fetchBlob(path);
  const url = URL.createObjectURL(blob);
  try { return { image: await loadImage(url), headers }; } finally { URL.revokeObjectURL(url); }
}

// 絵の見出しだけ（中身は読み込まない）
export async function imageHeaders(path) { return (await fetchBlob(path)).headers; }

// <img> に絵を出す。読み終えたら blob の URL を解放する
export async function showIn(img, path) {
  const { blob } = await fetchBlob(path);
  const url = URL.createObjectURL(blob);
  const free = () => URL.revokeObjectURL(url);
  img.addEventListener("load", free, { once: true });
  img.addEventListener("error", free, { once: true });
  img.src = url;
  return img;
}

// 手元のファイルを絵として読む（URL は読み終えたら解放する）
export async function fileImage(file) {
  const url = URL.createObjectURL(file);
  try { return await loadImage(url); } finally { URL.revokeObjectURL(url); }
}

// decode() で読む：絵を開く処理を画面の処理の外で済ませる（onload で受けると、初めて描くときに画面の処理の中で開くので、
// 大きい絵ではその間画面が止まる）
export async function loadImage(url) {
  const im = new Image();
  im.src = url;
  try { await im.decode(); } catch { throw new Error("絵を読めませんでした"); }
  return im;
}

// 白黒のマスク（白い所が範囲）を、色を付けた半透明の絵にする。候補の小さい絵と画面の上で使う。
// 画素ごとの計算はせず、SVG の feColorMatrix（明るさを不透明度にする。index.html の #v3-lum-to-alpha）で
// 描いてから色を重ねる。同じマスク・同じ大きさの物は作り直さない（マスクの中身は URL で決まる）。
// maxSide を渡すと、長い辺をその大きさまで縮めて作る（小さい絵用）
const overlayCache = new Map();
const OVERLAY_KEEP = 8;
export function maskOverlay(path, rgb, alpha, maxSide = 0) {
  const key = `${path}|${rgb}|${alpha}|${maxSide}`;
  if (!overlayCache.has(key)) {
    const p = (async () => {
      if (!("filter" in CanvasRenderingContext2D.prototype)) {
        throw new Error("このブラウザは canvas の filter に対応していないので、人の手の範囲を色で出せません");
      }
      const { image: im } = await image(path);
      const k = maxSide ? Math.min(1, maxSide / Math.max(im.naturalWidth, im.naturalHeight)) : 1;
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(im.naturalWidth * k)); c.height = Math.max(1, Math.round(im.naturalHeight * k));
      const x = c.getContext("2d");
      x.filter = "url(#v3-lum-to-alpha)";
      x.drawImage(im, 0, 0, c.width, c.height);
      x.filter = "none";
      x.globalCompositeOperation = "source-in";
      x.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`;
      x.fillRect(0, 0, c.width, c.height);
      return c;
    })();
    p.catch(() => overlayCache.delete(key));
    overlayCache.set(key, p);
    while (overlayCache.size > OVERLAY_KEEP) overlayCache.delete(overlayCache.keys().next().value);
  }
  return overlayCache.get(key);
}

export function errorText(e) {
  if (e instanceof NetworkError) return e.message;
  if (e instanceof ApiError) {
    const d = e.detail;
    if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join(" / ");
    if (typeof d === "string" && d) return d;
    if (d && typeof d === "object" && !Array.isArray(d)) return JSON.stringify(d);
    return `サーバーが ${e.status} を返しました`;
  }
  return String(e && e.message ? e.message : e);
}
