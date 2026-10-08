// V3 画像生成の画面。作品・ページ・コマを選び、処理を頼み、候補から選んで採用し、人の手で直し、版を戻す。
// 処理の一覧と入力欄の形はサーバー（GET /works/{id}/image-processes）から来る。処理を足しても、この画面は変えない。
import * as api from "./api.js";
import { renderForm } from "./schema_form.js";
import { Stage } from "./stage.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ACTIVE = new Set(["queued", "running", "waiting_limit", "waiting_budget"]);
const STATUS = { queued: "順番待ち", running: "作っている", waiting_limit: "回数の上限で待ち", waiting_budget: "予算で待ち",
                 stopped: "止まった", done: "できた", cancelled: "止めた" };
const ORIGIN = { generated: "AIが作った", human_drawn: "人が描いた", imported: "取り込んだ", human_edited: "人が直した" };
const POLL_MS = 1500;
const THUMB = 256;
const PROT_RGB = [196, 106, 0];

const S = {
  works: [], workId: null, work: null, pageId: null, panelId: null,
  processes: [], proc: null, form: null, control: null,
  image: null, frame: null, protectedCount: 0,
  sets: [], selected: [], undo: [], redo: [], poll: null, viewing: null, tool: "select",
};

let stage;

// ---------------------------------------------------------------- 知らせ
function toast(msg, kind = "") {
  const t = $("#toast");
  t.replaceChildren(note(msg, kind));
  clearTimeout(toast.h);
  toast.h = setTimeout(() => t.replaceChildren(), kind === "bad" ? 9000 : 4000);
}
function note(text, kind = "", icon = kind === "bad" ? "circle-alert" : kind === "need" ? "triangle-alert" : "info") {
  const n = h("div", { class: `note ${kind}` }, icon ? h("i", { "data-lucide": icon }) : null, h("span", { text }));
  queueMicrotask(icons);
  return n;
}
function icons() { window.lucide.createIcons({ attrs: { class: "lucide" } }); }
function fail(e) { console.error(e); toast(api.errorText(e), "bad"); }

function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids) if (k !== null && k !== undefined && k !== false) e.append(k);
  return e;
}
function pressed(group, btn) { for (const b of group.children) if (b.tagName === "BUTTON") b.setAttribute("aria-pressed", String(b === btn)); }

// ---------------------------------------------------------------- コマの絵の画素と mm
// コマの絵の置き場（切り抜きの画素 → 基本枠の mm）から、絵の画素と mm の比と原点を出す。回転・傾き・反転があれば null
function pxFrame(placement) {
  if (!placement) return null;
  if ((placement.rotation_deg || 0) !== 0 || (placement.skew_x_deg || 0) !== 0 || (placement.skew_y_deg || 0) !== 0
      || placement.flip_h || placement.flip_v) return null;
  const [cx0, cy0, cx1, cy1] = placement.crop_px;
  const [dx0, dy0, dx1, dy1] = placement.dest_box_mm;
  const sx = (dx1 - dx0) / (cx1 - cx0), sy = (dy1 - dy0) / (cy1 - cy0);
  return { sx, sy, ox: dx0 - cx0 * sx, oy: dy0 - cy0 * sy };
}

// ---------------------------------------------------------------- 選ぶ
async function loadWorks() {
  S.works = await api.get("/works");
  const sel = $("#pick-work");
  sel.replaceChildren(...S.works.map((w) => h("option", { value: w.id, text: w.title })));
  if (!S.works.length) { showEmpty("見てよい作品がありません"); return; }
  const saved = readPref("work");
  await selectWork(S.works.some((w) => w.id === saved) ? saved : S.works[0].id);
}

async function selectWork(id) {
  S.workId = id;
  $("#pick-work").value = id;
  writePref("work", id);
  S.undo = []; S.redo = []; syncUndo();
  [S.work, S.processes] = await Promise.all([api.get(`/works/${id}`), api.get(`/works/${id}/image-processes`)]);
  const pages = S.work.pages.filter((p) => !p.removed).sort((a, b) => a.number - b.number);
  $("#pick-page").replaceChildren(...pages.map((p) => h("option", { value: p.id, text: `${p.number} ページ` })));
  if (!pages.length) { showEmpty("この作品にはページがありません"); return; }
  const saved = readPref("page");
  await selectPage(pages.some((p) => p.id === saved) ? saved : pages[0].id);
}

async function selectPage(id) {
  S.pageId = id;
  $("#pick-page").value = id;
  writePref("page", id);
  const panels = livePanels();
  $("#pick-panel").replaceChildren(...panels.map((p) => h("option", { value: p.id, text: `コマ ${p.order}` })));
  if (!panels.length) { showEmpty("このページにはコマがありません"); return; }
  const saved = readPref("panel");
  await selectPanel(panels.some((p) => p.id === saved) ? saved : panels[0].id);
}

function livePanels() {
  return S.work.panels.filter((p) => p.page_id === S.pageId && !p.removed).sort((a, b) => a.order - b.order);
}
const panel = () => (S.work ? S.work.panels.find((p) => p.id === S.panelId) : null);

async function selectPanel(id) {
  S.panelId = id;
  $("#pick-panel").value = id;
  writePref("panel", id);
  S.selected = []; S.viewing = null;
  $("#viewing").hidden = true;
  await refreshPanel();
  renderProcesses();
  await Promise.all([loadCandidates(), loadVersions()]);
}

async function refreshWork() {
  S.work = await api.get(`/works/${S.workId}`);
}

// ---------------------------------------------------------------- 画面の絵
function showEmpty(text) {
  const e = $("#stage-empty");
  e.textContent = text;
  e.hidden = false;
}

async function refreshPanel(imageId) {
  const p = panel();
  const shownId = imageId || p.image_id;
  S.image = null; S.protectedCount = 0;
  $("#stage-empty").hidden = true;
  if (!shownId) {
    await stage.show({ image: null });
    showEmpty("このコマにはまだ絵がありません。右の「文から作る」で作れます");
    renderInputNotes();
    return;
  }
  const { url } = await api.blobUrl(`/works/${S.workId}/images/${shownId}/file`);
  const image = await api.loadImage(url);
  const protPath = `/works/${S.workId}/images/${shownId}/protected-mask`;
  const prot = await api.blobUrl(protPath);
  S.protectedCount = Number(prot.headers.get("X-V3-Region-Count") || 0);
  const protectedCanvas = S.protectedCount ? await api.maskOverlay(protPath, PROT_RGB, 1) : null;
  S.image = { id: shownId, width: image.naturalWidth, height: image.naturalHeight };
  S.frame = imageId ? null : pxFrame(p.image_placement);
  const layers = imageId ? [] : await handLayers(p);
  await stage.show({ image, protectedCanvas, layers, key: shownId });
  renderInputNotes();
  syncPenBar();
}

function handLayer(p = panel()) {
  return S.work.panel_layers.filter((l) => l.panel_id === p.id && l.role === "human_hand" && !l.removed)
    .sort((a, b) => b.stack_order - a.stack_order)[0];
}

// 人の手の層の控えの絵を、コマの絵の画素の上の位置に出す
async function handLayers(p) {
  const out = [];
  if (!S.frame) return out;
  for (const l of S.work.panel_layers) {
    if (l.panel_id !== p.id || l.removed || !l.visible || !l.image_id || !l.placement) continue;
    const f = pxFrame(l.placement);
    if (!f) continue;
    const { url } = await api.blobUrl(`/works/${S.workId}/images/${l.image_id}/file`);
    const image = await api.loadImage(url);
    out.push({ image, opacity: l.opacity, x: (f.ox - S.frame.ox) / S.frame.sx, y: (f.oy - S.frame.oy) / S.frame.sy,
               w: image.naturalWidth * f.sx / S.frame.sx, h: image.naturalHeight * f.sy / S.frame.sy });
  }
  return out;
}

// ---------------------------------------------------------------- 道具
function setTool(t) {
  S.tool = t;
  for (const b of $$(".ftb .tool[data-tool]")) b.setAttribute("aria-pressed", String(b.dataset.tool === t));
  $("#mask-bar").hidden = t !== "mask";
  $("#pen-bar").hidden = t !== "pen";
  $("#erase-bar").hidden = t !== "erase";
  stage.setTool(t);
  syncPenBar();
}

function syncPenBar() {
  const p = panel();
  let msg = "";
  if (!S.image) msg = "コマに絵が無いので描けません";
  else if (!S.frame) msg = "コマの絵に置き場が無いか、回転・傾き・反転があるので、ペンの線の位置を決められません";
  $("#pen-note").textContent = msg || "人の手の層に描きます。線は人の手の範囲として残ります";
  if (!msg) { stage.penWidthPx = Number($("#pen-width [aria-pressed=true]").dataset.w) / S.frame.sx; stage.syncCursor(); }
  return p && !msg;
}

// ---------------------------------------------------------------- 処理を選ぶ・入力欄
function renderProcesses() {
  const host = $("#process-list");
  host.replaceChildren();
  const usable = (sp) => sp.source !== "required" || !!panel().image_id;
  for (const sp of S.processes) {
    const blocked = !usable(sp);
    host.append(h("button", { class: "chip", type: "button", "data-process": sp.name,
      "aria-pressed": String(S.proc && S.proc.name === sp.name), "aria-disabled": blocked ? "true" : null,
      title: blocked ? "コマに絵があるときに使えます" : sp.hint, text: sp.label,
      onclick: () => { if (!blocked) selectProcess(sp.name); } }));
  }
  // 選んでいた処理がまだ使えるなら、入力欄と道具はそのままにする（採用・描いた後に入れた値や道具を変えない）
  const keep = S.proc && S.processes.find((x) => x.name === S.proc.name);
  if (keep && usable(keep)) { S.proc = keep; renderInputNotes(); syncMask(); return; }
  const first = S.processes.find(usable);
  if (first) selectProcess(first.name);
}

function selectProcess(name, initial = null) {
  S.proc = S.processes.find((x) => x.name === name);
  for (const b of $$("#process-list .chip")) b.setAttribute("aria-pressed", String(b.dataset.process === name));
  $("#process-hint").textContent = S.proc.hint;
  S.form = renderForm($("#form"), S.proc.params_schema, initial, onFormChange, S.proc.open_groups);
  S.control = null;
  icons();
  renderServices();
  renderInputNotes();
  if (S.proc.canvas_tool === "mask") setTool("mask");
  else if (S.proc.canvas_tool === "extend") { setTool("extend"); syncExtendFromForm(); }
  else if (S.tool === "mask" || S.tool === "extend") setTool("select");
  syncMask();
}

// 囲んだ範囲は、囲む処理を選んでいるときだけ見せる（「見せる」を切っていれば見せない）
function syncMask() {
  const on = !!S.proc && S.proc.mask !== "none" && $("#mask-show").getAttribute("aria-pressed") === "true";
  stage.setMaskVisible(on);
}

function onFormChange(name) {
  if (S.proc.canvas_tool === "extend" && ["unit", "left", "top", "right", "bottom"].includes(name)) syncExtendFromForm();
  if (name === "control") renderInputNotes();
}

// 描き足す量（入力欄）を、画面の枠（絵の画素）にする
function syncExtendFromForm() {
  const v = S.form.values();
  const notes = $("#extend-note");
  if (v.unit === "frame") {
    stage.setExtend({ left: 0, top: 0, right: 0, bottom: 0 });
    if (notes) notes.textContent = "コマの枠までの量は、頼むときにサーバーがコマの置き場から決めます。枠を動かすと「画素で」に変わります";
    return;
  }
  let k = 1;
  if (v.unit === "mm") {
    if (!S.frame) { if (notes) notes.textContent = "コマの絵に置き場が無いので mm を画素に直せません"; return; }
    k = 1 / S.frame.sx;
  }
  stage.setExtend({ left: Math.ceil(v.left * k), top: Math.ceil(v.top * k), right: Math.ceil(v.right * k),
                    bottom: Math.ceil(v.bottom * k) });
  if (notes) notes.textContent = "画面の枠の角や辺を動かしても決められます（動かすと「画素で」に変わります）";
}

function onExtendFromStage(e) {
  if (!S.proc || S.proc.canvas_tool !== "extend") return;
  S.form.set("unit", "px");
  for (const k of ["left", "top", "right", "bottom"]) S.form.set(k, e[k]);
  const n = $("#extend-note");
  if (n) n.textContent = `画素で 左 ${e.left}・上 ${e.top}・右 ${e.right}・下 ${e.bottom}`;
}

function renderInputNotes() {
  const host = $("#input-notes");
  host.replaceChildren();
  if (!S.proc) return;
  if (S.proc.source === "required" && !S.image) host.append(note("コマに絵があるときに使えます", "need"));
  if (S.proc.mask === "required") host.append(note("描き直す所を、画面の「囲んで頼む」で塗ってください。塗った所だけを描き直します", "", "lasso-select"));
  if (S.proc.mask === "optional") host.append(note("画面で塗ると、その所だけを直します。塗らなければ絵の全体に指示を効かせます", "", "lasso-select"));
  if (S.proc.source === "required" && S.protectedCount) {
    host.append(note(`橙の所は人の手の範囲（${S.protectedCount} か所）です。塗れず、描き直しません。できた絵にも元の画素を戻します`, "need", "shield"));
  }
  if (S.proc.canvas_tool === "extend") host.append(h("div", { class: "meta", id: "extend-note" }));
  const v = S.form ? S.form.values() : {};
  if (v.control && v.control !== "none") {
    const input = h("input", { type: "file", accept: "image/*", class: "field", id: "control-file" });
    input.addEventListener("change", async () => {
      S.control = input.files[0] ? await toPngBase64(input.files[0]) : null;
    });
    host.append(h("div", { class: "full" }, h("label", { class: "lbl", for: "control-file", text: "形の指定に使う絵" }), input,
      h("div", { class: "meta", text: "線画・落書き・骨格・奥行きの絵。コマの絵と同じ縦横の比で用意してください" })));
  }
  if (S.proc.canvas_tool === "extend") syncExtendFromForm();
}

async function toPngBase64(file) {
  const im = await api.loadImage(URL.createObjectURL(file));
  const c = h("canvas");
  c.width = im.naturalWidth; c.height = im.naturalHeight;
  c.getContext("2d").drawImage(im, 0, 0);
  return c.toDataURL("image/png").split(",")[1];
}

function renderServices() {
  const sel = $("#service");
  sel.replaceChildren();
  for (const s of S.proc.services) {
    const why = !s.allowed ? "（この作品からは送れない）" : s.paused ? "（休ませている）" : "";
    sel.append(h("option", { value: s.service_id, text: `${s.name}・${s.location === "local" ? "手元" : "API"}${why}`,
                             disabled: !s.allowed || null }));
  }
  if (S.proc.route_service_id) sel.value = S.proc.route_service_id;
  const none = !S.proc.services.length;
  $("#generate").setAttribute("aria-disabled", String(none));
  showServiceMeta();
  if (none) $("#service-meta").textContent = "この処理をできるつなぎ先がまだありません（つなぎ先の管理で、処理の設定を足してください）";
}

function showServiceMeta() {
  const s = S.proc.services.find((x) => x.service_id === $("#service").value);
  const st = s && s.settings;
  $("#service-meta").textContent = st ? [st.model, st.native_long_side && `長い辺 ${st.native_long_side}px`,
    st.resolution && `読ませる大きさ ${st.resolution}px`, st.controlnet ? "形の指定を使える" : "形の指定は使えない",
    ...(st.loras || [])].filter(Boolean).join("・") : "";
}

// ---------------------------------------------------------------- 頼む
function countN() { return Number($("#count [aria-pressed=true]").dataset.n); }
function seedMode() { return $("#seed-mode [aria-pressed=true]").dataset.m; }

async function generate(over = {}) {
  const spec = over.proc || S.proc;
  const params = over.params || S.form.values();
  const body = { process: spec.name, params, count: over.count || countN(), seed_mode: over.seed_mode || seedMode() };
  if (body.seed_mode === "fixed") body.seed = over.seed ?? Number($("#seed").value);
  if (spec.source === "required") body.source_image_id = over.source_image_id || S.image?.id;
  if (!over.proc && spec.mask !== "none") {
    const m = stage.maskPngBase64();
    if (m) body.mask = { png_base64: m };
    else if (spec.mask === "required") { toast("描き直す所を塗ってください（囲んで頼む）", "need"); setTool("mask"); return; }
  }
  if (params.control && params.control !== "none") {
    if (!S.control) { toast("形の指定に使う絵を選んでください", "need"); return; }
    body.control = { png_base64: S.control };
  }
  const svc = over.service_id || $("#service").value;
  if (svc && svc !== spec.route_service_id) body.service_id = svc;
  try {
    const r = await api.post(`/works/${S.workId}/panels/${S.panelId}/generate`, body);
    toast(`${spec.label}を ${r.jobs.length} 件頼みました`);
    showTab("cands");
    await loadCandidates();
  } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- 候補
// 進み具合はポーリングで見る（EventSource は X-V3-User を付けられない）。取れなかった回も、作っている物があれば続ける
async function loadCandidates() {
  clearTimeout(S.poll);
  const at = `${S.workId}/${S.panelId}`;
  try {
    const res = await api.get(`/works/${S.workId}/panels/${S.panelId}/candidates`);
    if (at !== `${S.workId}/${S.panelId}`) return;
    S.sets = res.sets.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    renderCandidates(res.panel_image_id);
    renderProgress();
  } catch (e) {
    fail(e);
  }
  if (S.sets.some((s) => s.jobs.some((j) => ACTIVE.has(j.status)))) {
    S.poll = setTimeout(() => loadCandidates(), POLL_MS);
  }
}

function paramText(params) {
  const v = params || {};
  const parts = [];
  if (v.strength !== undefined) parts.push(`強さ ${v.strength}`);
  if (v.denoise !== undefined) parts.push(`描き直し ${v.denoise}`);
  return parts.join("・");
}

function renderCandidates(currentId) {
  const host = $("#sets");
  host.replaceChildren();
  const waiting = S.sets.reduce((n, s) => n + s.images.filter((i) => !i.discarded).length, 0);
  $("#cand-count").textContent = waiting ? String(waiting) : "";
  if (!S.sets.length) { host.append(h("div", { class: "meta", text: "まだ頼んでいません" })); return; }
  const variation = S.processes.find((p) => p.name === "variation");
  const presets = Object.entries(variation ? variation.params_schema.properties.strength["x-presets"] || {} : {})
    .sort((a, b) => a[1] - b[1]);
  for (const set of S.sets) {
    const active = set.jobs.filter((j) => ACTIVE.has(j.status));
    const head = h("div", { class: "set-h" },
      h("span", { class: "lbl grow", text: set.label }),
      h("span", { class: "meta num", text: new Date(set.created_at).toLocaleString("ja-JP", { dateStyle: "short", timeStyle: "short" }) }),
      active.length ? h("button", { class: "btn sm", text: "止める", onclick: () => cancelSet(set) }) : null,
      h("button", { class: "btn sm ghost", onclick: () => reuse(set) }, h("i", { "data-lucide": "rotate-ccw" }), "この設定でもう一度"));
    const prompt = set.requested_params && set.requested_params.prompt;
    const grid = h("div", { class: "cands" });
    let k = 0;
    for (const img of set.images) {
      k += 1;
      const sel = S.selected.includes(img.id);
      const cur = img.id === currentId;
      const th = h("button", { class: "th", type: "button", title: "選ぶ", onclick: () => toggleSelect(img.id) });
      api.blobUrl(`/works/${S.workId}/images/${img.id}/thumbnail?size=${THUMB}`).then(({ url }) => th.prepend(h("img", { src: url, alt: "" })));
      if (img.protected_mask_url) {
        api.maskOverlay(img.protected_mask_url, PROT_RGB, 0.55).then((c) => { c.className = "prot"; th.append(c); }).catch(fail);
      }
      const flags = h("div", { class: "flags" },
        cur ? h("span", { class: "flag on", text: "採用中" }) : null,
        img.discarded ? h("span", { class: "flag bad", text: "却下" }) : null,
        img.protected_mask_url ? h("span", { class: "flag warn", title: "人の手の範囲は元の画素のまま", text: "人の手そのまま" }) : null);
      const model = img.settings && img.settings.model && img.settings.model.replace(/\.(safetensors|ckpt|gguf)$/, "");
      const meta = h("div", { class: "meta num",
        text: [img.service_name, model, `seed ${img.seed}`, paramText(set.params)].filter(Boolean).join("・") });
      const acts = h("div", { class: "acts" },
        h("button", { class: "btn sm primary", "aria-disabled": String(cur || img.discarded), onclick: () => adopt(img.id) }, "採用"),
        img.discarded
          ? h("button", { class: "btn sm", onclick: () => discard(img.id, false) }, "却下をやめる")
          : h("button", { class: "btn sm", "aria-disabled": String(cur), onclick: () => discard(img.id, true) }, "却下"),
        ...presets.map(([label, strength]) => h("button", { class: "btn sm ai-o", title: "この絵を元に似た別案を作る",
          onclick: () => similar(img, set, strength) }, `似た別案 ${label}`)));
      grid.append(h("div", { class: `cand${img.discarded ? " discarded" : ""}`, "aria-pressed": String(sel), "data-image": img.id },
        th, h("span", { class: "id num", text: String(k) }), flags, h("div", { class: "cand-f" }, meta, acts)));
    }
    for (const j of set.jobs) {
      if (set.images.some((i) => i.job_id === j.id)) continue;
      const failText = j.status === "stopped" ? `${STATUS[j.status]}：${j.failure_detail || j.failure_kind || ""}` : STATUS[j.status] || j.status;
      grid.append(h("div", { class: "cand wait" },
        h("div", { class: "th" }, ACTIVE.has(j.status) ? h("i", { "data-lucide": "loader", class: "spin" }) : null),
        h("div", { class: "cand-f" }, h("div", { class: `meta${j.status === "stopped" ? " bad" : ""}`, text: failText }),
          h("div", { class: "meta num", text: `seed ${j.seed}` }))));
    }
    const compare = h("button", { class: "btn sm", "aria-disabled": String(!S.selected.length), onclick: openCompare },
      h("i", { "data-lucide": "columns-2" }), "比べる");
    host.append(h("div", { class: "set" }, head,
      prompt ? h("div", { class: "meta", text: `指示：${prompt}` }) : null, grid, h("div", { class: "row" }, compare)));
  }
  icons();
}

function renderProgress() {
  const host = $("#progress");
  host.replaceChildren();
  for (const set of S.sets) {
    const active = set.jobs.filter((j) => ACTIVE.has(j.status));
    if (!active.length) continue;
    const done = set.jobs.filter((j) => j.status === "done").length;
    host.append(h("div", { class: "job" }, h("i", { "data-lucide": "loader", class: "spin" }),
      h("span", { class: "s", text: `${set.label}：${done} / ${set.jobs.length} 枚（${STATUS[active[0].status]}）` }),
      h("button", { class: "btn sm", onclick: () => cancelSet(set) }, "止める")));
  }
  icons();
}

async function cancelSet(set) {
  try {
    for (const j of set.jobs.filter((x) => ACTIVE.has(x.status))) await api.post(`/works/${S.workId}/jobs/${j.id}/cancel`);
    await loadCandidates();
  } catch (e) { fail(e); }
}

function toggleSelect(id) {
  const i = S.selected.indexOf(id);
  if (i >= 0) S.selected.splice(i, 1);
  else { S.selected.push(id); if (S.selected.length > 2) S.selected.shift(); }
  for (const c of $$(".cand[data-image]")) c.setAttribute("aria-pressed", String(S.selected.includes(c.dataset.image)));
  for (const b of $$("#sets .set .row .btn")) b.setAttribute("aria-disabled", String(!S.selected.length));
}

function reuse(set) {
  showTab("ask");
  selectProcess(set.process, set.requested_params || {});
  const spec = S.processes.find((p) => p.name === set.process);
  if (spec && spec.mask !== "none") toast("囲んだ範囲は前のものを使いません。塗り直してください", "need");
}

function similar(img, set, strength) {
  const spec = S.processes.find((p) => p.name === "variation");
  const props = spec.params_schema.properties;
  const params = {};
  for (const [k, p] of Object.entries(props)) if ("x-initial" in p) params[k] = p["x-initial"];
  const prev = set.requested_params || {};
  if ("prompt" in props && prev.prompt !== undefined) params.prompt = prev.prompt;
  if ("negative_prompt" in props && prev.negative_prompt !== undefined) params.negative_prompt = prev.negative_prompt;
  params.strength = strength;
  const job = set.jobs.find((j) => j.id === img.job_id);
  generate({ proc: spec, params, source_image_id: img.id, service_id: job ? job.service_id : null });
}

// ---------------------------------------------------------------- 採用・却下・版
async function submitOps(...bodies) {
  const ids = [];
  for (const b of bodies) ids.push((await api.op(S.workId, b)).event_id);
  return ids;
}

function pushUndo(ids) { S.undo.push(ids); S.redo = []; syncUndo(); }
function syncUndo() {
  $("#undo").setAttribute("aria-disabled", String(!S.undo.length));
  $("#redo").setAttribute("aria-disabled", String(!S.redo.length));
}

async function afterChange() {
  await refreshWork();
  await refreshPanel();
  renderProcesses();
  await Promise.all([loadCandidates(), loadVersions()]);
}

async function adopt(imageId) {
  try {
    pushUndo(await submitOps({ type: "adopt_image", panel_id: S.panelId, image_id: imageId }));
    toast("採用しました（取り消せます）");
    await afterChange();
  } catch (e) { fail(e); }
}

async function discard(imageId, on) {
  try {
    pushUndo(await submitOps({ type: "set_image_discarded", image_id: imageId, discarded: on }));
    await loadCandidates();
  } catch (e) { fail(e); }
}

async function undoRedo(from, to) {
  const group = from.pop();
  if (!group) return;
  try {
    const back = [];
    for (const id of [...group].reverse()) back.push((await api.undo(S.workId, id)).event_id);
    to.push(back);
  } catch (e) { from.push(group); fail(e); }
  syncUndo();
  await afterChange().catch(fail);
}

async function loadVersions() {
  const res = await api.get(`/works/${S.workId}/panels/${S.panelId}/versions`);
  const host = $("#versions");
  host.replaceChildren();
  if (!res.versions.length) { host.append(h("div", { class: "meta", text: "まだ絵を置いていません" })); return; }
  const list = res.versions.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  for (const v of list) {
    const th = h("div", { class: "th" });
    api.blobUrl(`/works/${S.workId}/images/${v.id}/thumbnail?size=128`).then(({ url }) => th.append(h("img", { src: url, alt: "" })));
    const proc = v.details && v.details.process;
    const label = proc ? (S.processes.find((p) => p.name === proc) || {}).label || proc : ORIGIN[v.origin] || v.origin;
    host.append(h("div", { class: `vrow${v.current ? " cur" : ""}`, "data-version": v.id }, th,
      h("div", {}, h("div", { class: "row wrap" }, h("span", { class: "lbl", text: label }),
          v.current ? h("span", { class: "flag on", text: "今の絵" }) : null,
          h("span", { class: `flag ${v.origin === "generated" ? "ai" : "mut"}`, text: ORIGIN[v.origin] || v.origin })),
        h("div", { class: "meta num", text: `${v.width}×${v.height}・${new Date(v.created_at).toLocaleString("ja-JP", { dateStyle: "short", timeStyle: "short" })}` })),
      h("div", { class: "acts" },
        h("button", { class: "btn sm", onclick: () => view(v, label) }, "見る"),
        h("button", { class: "btn sm primary", "aria-disabled": String(v.current), onclick: () => adopt(v.id) }, "戻す"))));
  }
}

async function view(v, label) {
  S.viewing = v.id;
  $("#viewing-text").textContent = `${label}（${v.width}×${v.height}）を見ています。描いたり囲んだりはできません`;
  $("#viewing").hidden = false;
  setTool("select");
  await refreshPanel(v.id).catch(fail);
}

// ---------------------------------------------------------------- 比べる
async function openCompare() {
  if (!S.selected.length) return;
  const ids = S.selected.length === 1 && panel().image_id ? [panel().image_id, S.selected[0]] : S.selected.slice(0, 2);
  const names = ids.map((id) => (id === panel().image_id ? "今の絵" : `候補 ${candNo(id)}`));
  S.compareIds = ids; S.compareNames = names;
  $("#compare").hidden = false;
  $("#compare-title").textContent = `比べる：${names.join(" と ")}`;
  await renderCompare();
}

function candNo(id) {
  for (const s of S.sets) { const i = s.images.findIndex((x) => x.id === id); if (i >= 0) return `${s.label} ${i + 1}`; }
  return id.slice(0, 6);
}

async function renderCompare() {
  const mode = $("#compare-mode [aria-pressed=true]").dataset.mode;
  const body = $("#compare-body");
  body.className = `compare-b ${mode}`;
  const urls = await Promise.all(S.compareIds.map((id) => api.blobUrl(`/works/${S.workId}/images/${id}/file`).then((x) => x.url)));
  if (mode === "side" || urls.length < 2) {
    body.replaceChildren(...urls.map((u, i) => h("figure", {}, h("img", { src: u, alt: S.compareNames[i] }),
      h("figcaption", { text: S.compareNames[i] }))));
    return;
  }
  const a = await api.loadImage(urls[0]);
  const wrap = h("div", { class: "slider-wrap", style: `--ar:${a.naturalWidth}/${a.naturalHeight}` },
    h("img", { src: urls[0], alt: S.compareNames[0] }), h("img", { class: "b", src: urls[1], alt: S.compareNames[1] }),
    h("div", { class: "bar" }));
  const r = h("input", { type: "range", min: 0, max: 100, value: 50, "aria-label": "境目の位置" });
  r.addEventListener("input", () => wrap.style.setProperty("--cut", `${r.value}%`));
  wrap.append(r);
  body.replaceChildren(h("figure", { class: "slider-fig" },
    wrap, h("figcaption", { text: `左：${S.compareNames[0]}　右：${S.compareNames[1]}` })));
}

// ---------------------------------------------------------------- 人の手で描く・消す
async function ensureHandLayer() {
  const l = handLayer();
  if (l) return { layer: l, ids: [] };
  const p = panel();
  const top = Math.max(-1, ...S.work.panel_layers.filter((x) => x.panel_id === p.id).map((x) => x.stack_order));
  const ids = await submitOps({ type: "add_panel_layer", panel_id: p.id, role: "human_hand", stack_order: top + 1 });
  await refreshWork();
  return { layer: handLayer(), ids };
}

// 層の線から控えの絵を作る。この画面が描けるのは鉛筆（pencil）だけ。ほかの筆の線があれば作らずに断る
function renderStrokeCache(layer) {
  const strokes = S.work.pen_strokes.filter((s) => s.layer_id === layer.id && !s.removed).sort((a, b) => a.stack_order - b.stack_order);
  const other = strokes.find((s) => s.brush !== "pencil");
  if (other) throw new Error(`この画面は鉛筆の線しか描けません。この層には「${other.brush}」の線があるので、控えの絵を作り直せません`);
  const f = S.frame;
  const c = h("canvas");
  c.width = S.image.width; c.height = S.image.height;
  const x = c.getContext("2d");
  x.lineCap = "round"; x.lineJoin = "round";
  for (const s of strokes) {
    x.globalAlpha = s.opacity;
    x.strokeStyle = s.color; x.fillStyle = s.color;
    x.lineWidth = s.width_mm / f.sx;
    const pts = s.points.map(([mx, my]) => [(mx - f.ox) / f.sx, (my - f.oy) / f.sy]);
    x.beginPath(); x.moveTo(pts[0][0], pts[0][1]);
    for (const [px, py] of pts.slice(1)) x.lineTo(px, py);
    if (pts.length === 1) x.lineTo(pts[0][0] + 0.01, pts[0][1]);
    x.stroke();
  }
  const placement = { crop_px: [0, 0, c.width, c.height],
                      dest_box_mm: [f.ox, f.oy, f.ox + c.width * f.sx, f.oy + c.height * f.sy] };
  return new Promise((resolve) => c.toBlob((b) => resolve({ blob: b, placement }), "image/png"));
}

async function onPenStroke(points, done) {
  try {
    if (S.viewing) throw new Error("昔の版を見ている間は描けません");
    if (!syncPenBar()) throw new Error($("#pen-note").textContent);
    const f = S.frame;
    const widthMm = Number($("#pen-width [aria-pressed=true]").dataset.w);
    const { layer: l0, ids } = await ensureHandLayer();
    ids.push(...await submitOps({ type: "add_pen_strokes", layer_id: l0.id, strokes: [{
      brush: "pencil", color: "#000000", opacity: 1, width_mm: widthMm,
      points: points.map((p) => [f.ox + p.x * f.sx, f.oy + p.y * f.sy, p.pressure, p.ms]) }] }));
    await refreshWork();
    const layer = S.work.panel_layers.find((x) => x.id === l0.id);
    const { blob, placement } = await renderStrokeCache(layer);
    const form = new FormData();
    form.append("image", blob, "strokes.png");
    form.append("stroke_revision", String(layer.stroke_revision));
    form.append("placement", JSON.stringify(placement));
    ids.push((await api.postForm(`/works/${S.workId}/layers/${layer.id}/stroke-cache`, form)).event_id);
    pushUndo(ids);
    await refreshWork();
    await refreshPanel();
    await loadVersions();
  } catch (e) { fail(e); } finally { done(); }
}

async function onErase(points, widthPx, done) {
  try {
    if (S.viewing) throw new Error("昔の版を見ている間は消せません");
    if (!S.image) throw new Error("消す絵がありません");
    const form = new FormData();
    form.append("strokes", JSON.stringify([{ points: points.map((p) => [p.x, p.y]), width_px: widthPx }]));
    const r = await api.postForm(`/works/${S.workId}/panels/${S.panelId}/erase-pixels`, form);
    pushUndo([r.event_id]);
    await afterChange();
  } catch (e) { fail(e); } finally { done(); }
}

// ---------------------------------------------------------------- タブ・保存しておく選び
function showTab(t) {
  for (const b of $$(".itab")) b.setAttribute("aria-selected", String(b.dataset.tab === t));
  for (const p of $$("[data-pane]")) p.hidden = p.dataset.pane !== t;
}
function readPref(k) { try { return localStorage.getItem(`v3.gen.${k}`); } catch { return null; } }
function writePref(k, v) { try { localStorage.setItem(`v3.gen.${k}`, v); } catch { /* 覚えられない環境では毎回初めから選ぶ */ } }

// ---------------------------------------------------------------- はじめ
function bindUi() {
  $("#pick-work").addEventListener("change", (e) => selectWork(e.target.value).catch(fail));
  $("#pick-page").addEventListener("change", (e) => selectPage(e.target.value).catch(fail));
  $("#pick-panel").addEventListener("change", (e) => selectPanel(e.target.value).catch(fail));
  const user = $("#user");
  user.addEventListener("change", () => { api.setUser(user.value.trim()); start(); });
  for (const b of $$(".ftb .tool[data-tool]")) b.addEventListener("click", () => setTool(b.dataset.tool));
  for (const b of $$("#mask-tools button")) b.addEventListener("click", () => { pressed($("#mask-tools"), b); stage.setMaskTool(b.dataset.mask); });
  for (const b of $$("#pen-width button")) b.addEventListener("click", () => {
    pressed($("#pen-width"), b);
    if (S.frame) { stage.penWidthPx = Number(b.dataset.w) / S.frame.sx; stage.syncCursor(); }
  });
  const bs = $("#brush-size");
  bs.addEventListener("input", () => { $("#brush-size-v").textContent = bs.value; stage.setBrushPx(Number(bs.value)); });
  const es = $("#erase-size");
  es.addEventListener("input", () => { $("#erase-size-v").textContent = es.value; stage.erasePx = Number(es.value); stage.syncCursor(); });
  $("#mask-undo").addEventListener("click", () => stage.undoMask());
  $("#mask-invert").addEventListener("click", () => stage.invertMask());
  $("#mask-fill").addEventListener("click", () => stage.fillMask());
  $("#mask-clear").addEventListener("click", () => stage.clearMask());
  $("#mask-show").addEventListener("click", (e) => {
    const b = e.currentTarget;
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(on));
    syncMask();
  });
  $("#zoom-in").addEventListener("click", () => stage.zoomBy(1.25));
  $("#zoom-out").addEventListener("click", () => stage.zoomBy(0.8));
  $("#zoom-fit").addEventListener("click", () => stage.fit());
  $("#undo").addEventListener("click", () => undoRedo(S.undo, S.redo));
  $("#redo").addEventListener("click", () => undoRedo(S.redo, S.undo));
  for (const b of $$(".itab")) b.addEventListener("click", () => showTab(b.dataset.tab));
  for (const b of $$("#count button")) b.addEventListener("click", () => pressed($("#count"), b));
  for (const b of $$("#seed-mode button")) b.addEventListener("click", () => { pressed($("#seed-mode"), b); $("#seed").hidden = b.dataset.m !== "fixed"; });
  $("#service").addEventListener("change", showServiceMeta);
  $("#generate").addEventListener("click", () => generate());
  $("#viewing-back").addEventListener("click", () => { S.viewing = null; $("#viewing").hidden = true; refreshPanel().catch(fail); });
  for (const b of $$("#compare-mode button")) b.addEventListener("click", () => { pressed($("#compare-mode"), b); renderCompare().catch(fail); });
  $("#compare-close").addEventListener("click", () => { $("#compare").hidden = true; });
  window.addEventListener("keydown", (e) => {
    if (e.target.closest("input,textarea,select")) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      if (e.shiftKey) undoRedo(S.redo, S.undo); else undoRedo(S.undo, S.redo);
      return;
    }
    const key = { v: "select", m: "mask", o: "extend", p: "pen", e: "erase" }[e.key.toLowerCase()];
    if (key && !e.ctrlKey && !e.metaKey && !e.altKey) setTool(key);
  });
}

// ログインの方式で右上を変える。oidc はログインした名前とログアウト、dev_header は名前の欄（開発用と出す）
async function showWho() {
  const mode = await api.loadAuth();
  if (mode === "oidc") {
    $("#who-dev").hidden = true;
    $("#who-name").textContent = api.myName();
    $("#who-login").hidden = false;
  } else {
    $("#user").value = api.currentUser();
    api.setUser($("#user").value);
  }
}

async function start() {
  if (!api.currentUser()) { showEmpty("右上の「利用者」に名前を入れてください"); return; }
  try { await loadWorks(); } catch (e) { fail(e); }
}

stage = new Stage($("#stage"), {
  onExtend: onExtendFromStage, onPenStroke, onErase,
  onMaskChange: () => {},
});
// 開発者ツールと画面の試験（test/image_generation_ui.mjs）から絵の画素の位置を調べるため
window.v3Stage = stage;
bindUi();
await showWho().catch(fail);
icons();
setTool("select");
start();
