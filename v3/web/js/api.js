// サーバーとのやり取り。利用者は X-V3-User で送る（ログインが入るまでの仮。http_dependencies.py）。
// 絵も X-V3-User が要るので、<img src> に URL を直接は入れず、取ってきて blob の URL にする。
const USER_KEY = "v3.user";

export function currentUser() {
  try { return localStorage.getItem(USER_KEY) || ""; } catch { return ""; }
}
export function setUser(name) {
  try { localStorage.setItem(USER_KEY, name); } catch { /* 保存できない環境では、この画面を開いている間だけ使う */ }
  memoUser = name;
  blobCache.clear();
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
  const r = await fetch(path, { method, headers, body });
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

export const get = (p) => call("GET", p);
export const post = (p, json) => call("POST", p, { json });
export const postForm = (p, form) => call("POST", p, { form });
export const op = (workId, body) => post(`/works/${workId}/ops`, body);
export const undo = (workId, eventId) => post(`/works/${workId}/events/${eventId}/undo`);

// 同じ URL の絵は一度だけ取る（絵の中身は id で決まり、変わらない）
const blobCache = new Map();
export function blobUrl(path) {
  if (!blobCache.has(path)) {
    const p = call("GET", path, { raw: true }).then(async (r) => ({
      url: URL.createObjectURL(await r.blob()),
      headers: r.headers,
    }));
    p.catch(() => blobCache.delete(path));
    blobCache.set(path, p);
  }
  return blobCache.get(path);
}

export function loadImage(url) {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error(`絵を読めない: ${url}`));
    im.src = url;
  });
}

// 白黒のマスク（白い所が範囲）を、色を付けた半透明の絵にする。候補の小さい絵と画面の上で使う
export async function maskOverlay(path, rgb, alpha) {
  const { url } = await blobUrl(path);
  const im = await loadImage(url);
  const c = document.createElement("canvas");
  c.width = im.naturalWidth; c.height = im.naturalHeight;
  const x = c.getContext("2d");
  x.drawImage(im, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height);
  for (let i = 0; i < d.data.length; i += 4) {
    const on = d.data[i] >= 128;
    d.data[i] = rgb[0]; d.data[i + 1] = rgb[1]; d.data[i + 2] = rgb[2];
    d.data[i + 3] = on ? Math.round(alpha * 255) : 0;
  }
  x.putImageData(d, 0, 0);
  return c;
}

export function errorText(e) {
  if (e instanceof ApiError) {
    const d = e.detail;
    if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join(" / ");
    return typeof d === "string" ? d : JSON.stringify(d);
  }
  return String(e && e.message ? e.message : e);
}
