// V3 画像生成の画面。作品・ページ・コマを選び、処理を頼み、候補から選んで採用し、人の手で直し、版を戻す。
// 処理の一覧と入力欄の形はサーバー（GET /works/{id}/image-processes）から来る。処理を足しても、この画面は変えない。
import * as api from "./api.js";
import { renderForm } from "./schema_form.js";
import { Stage } from "./stage.js";
import { drawStroke } from "./pen_render.js";
import { startKeys, km } from "../common/keys.js";
import { openHelp } from "../common/help_overlay.js";
import { pollMs } from "../common/poll_interval.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ACTIVE = new Set(["queued", "running", "waiting_limit", "waiting_budget"]);
const STATUS = { queued: "順番待ち", running: "作っている", waiting_limit: "回数の上限で待ち", waiting_budget: "予算で待ち",
                 stopped: "止まった", done: "できた", cancelled: "止めた" };
const ORIGIN = { generated: "AIが作った", human_drawn: "人が描いた", imported: "取り込んだ", human_edited: "人が直した" };
const POLL_MS = pollMs(1500);
const THUMB = 256;
const PEN_INK = "#000000";   // 色の決め打ちを許す：ペンの線の色は絵の中身（墨）で、画面の色ではない（色の組を替えても変えない）

// 取り消しの記録のうち、囲みの差分が持ってよい大きさ（全部のコマを合わせて）。超えたら古い物から捨てる
const MASK_HISTORY_BYTES = 256 * 1024 * 1024;
// 候補を読めなかったとき、次に読むまでの最長の間
const POLL_MAX_MS = 30000;
// 線を描いてから、線の控え（人の手の層の絵）を上げるまで待つ間。頼む前・コマを替える前には待たずに上げる
const CACHE_IDLE_MS = 4000;

const S = {
  works: [], workId: null, work: null, pageId: null, panelId: null,
  processes: [], proc: null, form: null, control: null,
  image: null, frame: null, protectedCount: 0, layers: [],
  sets: [], selected: [], poll: null, pollFails: 0, link: null, viewing: null, tool: "select",
  // コマごとの取り消し・やり直し（Map: コマの id → { undo: [], redo: [] }）。項目は
  // { kind: "mask", edit }（囲みのタイルの差分）か { kind: "server", ids: Promise<出来事の id[]>, refresh }
  hist: new Map(), undoing: false,
  // 画面に出ている囲みがどのコマの物か。コマを替えるときに外へ出して masks に持つ
  shownPanel: null, shownViewing: false, masks: new Map(), showSeq: 0,
  // 囲みを塗ってから、まだ頼んでいない（囲みは保存しないので、閉じると消える。閉じる前に聞く）
  maskUnsent: false,
  // 描いている人の手の層（コマごと1つ）
  hand: null,
  sending: false,
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
// what：何をしようとして失敗したか（「採用」など）。理由と一緒に出す
function fail(e, what = "") {
  console.error(e);
  toast(what ? `${what}できませんでした：${api.errorText(e)}` : api.errorText(e), "bad");
}
// 線と層の id は画面で作る（保存を待たずに取り消しの記録に載せるため）。http の画面でも使えるよう getRandomValues で作る
function newId() { return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join(""); }

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
  const saved = wanted("work");
  await selectWork(S.works.some((w) => w.id === saved) ? saved : S.works[0].id);
}

async function selectWork(id) {
  S.workId = id;
  $("#pick-work").value = id;
  writePref("work", id);
  S.hist = new Map(); S.masks = new Map(); S.maskUnsent = false; S.shownPanel = null; S.hand = null; syncUndo();
  [S.work, S.processes] = await Promise.all([api.get(`/works/${id}`), api.get(`/works/${id}/image-processes`)]);
  const pages = S.work.pages.filter((p) => !p.removed).sort((a, b) => a.number - b.number);
  $("#pick-page").replaceChildren(...pages.map((p) => h("option", { value: p.id, text: `${p.number} ページ` })));
  if (!pages.length) { showEmpty("この作品にはページがありません"); return; }
  const saved = wanted("page");
  await selectPage(pages.some((p) => p.id === saved) ? saved : pages[0].id);
}

async function selectPage(id) {
  S.pageId = id;
  $("#pick-page").value = id;
  writePref("page", id);
  const panels = livePanels();
  $("#pick-panel").replaceChildren(...panels.map((p) => h("option", { value: p.id, text: `コマ ${p.order}` })));
  if (!panels.length) { showEmpty("このページにはコマがありません"); return; }
  const saved = wanted("panel");
  await selectPanel(panels.some((p) => p.id === saved) ? saved : panels[0].id);
}

function livePanels() {
  return S.work.panels.filter((p) => p.page_id === S.pageId && !p.removed).sort((a, b) => a.order - b.order);
}
const panel = () => (S.work ? S.work.panels.find((p) => p.id === S.panelId) : null);

async function selectPanel(id) {
  // 前のコマの線の控えは、待たずに上げておく（失敗は知らせる）
  if (S.hand && S.hand.dirty) uploadCache(S.hand).catch((e) => fail(e, "線の控えを上げる"));
  S.panelId = id;
  $("#pick-panel").value = id;
  writePref("panel", id);
  $("#to-manuscript").href = `manuscript/index.html?work=${encodeURIComponent(S.workId)}&page=${encodeURIComponent(S.pageId)}`;
  S.selected = []; S.viewing = null;
  $("#viewing").hidden = true;
  S.pollFails = 0; S.link = null;
  syncUndo();
  await refreshPanelRow();
  await refreshPanel();
  renderProcesses();
  await Promise.all([loadCandidates(), loadVersions()]);
}

// 今のコマの行と層だけを読み直す（作品全体は読まない）
async function refreshPanelRow() {
  const at = S.panelId;
  const r = await api.get(`/works/${S.workId}/panels/${at}/layers`);
  if (at !== S.panelId) return;
  const i = S.work.panels.findIndex((p) => p.id === at);
  if (i >= 0) S.work.panels[i] = { ...S.work.panels[i], ...r.panel };
  S.layers = r.layers;
}

// ---------------------------------------------------------------- 画面の絵
function showEmpty(text) {
  const e = $("#stage-empty");
  e.textContent = text;
  e.hidden = false;
}

// コマの絵を出す。imageId を渡すと、その版を見る（描けない）。
// 読んでいる間にコマや版を替えたら、古い読み込みの結果は捨てる（showSeq）。
// 同じコマの絵を出し直すときは、拡大・位置と囲みをそのままにする（消しゴム・採用の後も囲みは消えない）。
async function refreshPanel(imageId) {
  const token = ++S.showSeq;
  const stale = () => token !== S.showSeq;
  const p = panel();
  const shownId = imageId || p.image_id;
  const same = S.shownPanel === p.id && !S.shownViewing && !imageId;
  if (!same && S.shownPanel && !S.shownViewing) stashMask(S.shownPanel);
  $("#stage-empty").hidden = true;
  if (!shownId) {
    S.image = null; S.protectedCount = 0;
    await stage.show({ image: null });
    S.shownPanel = p.id; S.shownViewing = !!imageId;
    showEmpty("このコマにはまだ絵がありません。右の「文から作る」で作れます");
    renderInputNotes();
    return;
  }
  const { image } = await api.image(`/works/${S.workId}/images/${shownId}/file`);
  if (stale()) return;
  const { count: protectedCount, canvas: protectedCanvas } = await loadProtected(shownId);
  if (stale()) return;
  const frame = imageId ? null : pxFrame(p.image_placement);
  const size = { w: image.naturalWidth, h: image.naturalHeight };
  const layers = imageId ? [] : await panelLayers(p, frame, size);
  if (stale()) return;
  S.image = { id: shownId, width: size.w, height: size.h };
  S.protectedCount = protectedCount;
  S.frame = frame;
  const r = await stage.show({ image, protectedCanvas, layers, keepView: same, keepMask: same });
  if (same && !r.maskKept) dropMask(p.id, "絵の大きさが変わったので、塗っていた囲みを消しました");
  if (!same && !imageId && S.masks.has(p.id)) {
    const saved = S.masks.get(p.id);
    S.masks.delete(p.id);
    if (!stage.putMask(saved)) dropMask(p.id, "絵の大きさが変わったので、このコマで塗っていた囲みを消しました");
  }
  S.shownPanel = p.id; S.shownViewing = !!imageId;
  renderInputNotes();
  syncPenBar();
}

// 人の手の範囲（囲めない所）。数はサーバーの見出しから読む
async function loadProtected(imageId) {
  const protPath = `/works/${S.workId}/images/${imageId}/protected-mask`;
  const headers = await api.imageHeaders(protPath);
  const count = headers.get("X-V3-Region-Count");
  if (count === null) throw new Error("人の手の範囲の数がサーバーから来ませんでした");
  return { count: Number(count), canvas: Number(count) ? await api.maskOverlay(protPath, stage.col.protectRgb, 1) : null };
}

function stashMask(panelId) {
  const m = stage.takeMask();
  if (m) S.masks.set(panelId, m); else S.masks.delete(panelId);
}

// 囲みを捨てたときは、そのコマの囲みの取り消しの記録も捨てる（当てる先が無い）
function dropMask(panelId, why) {
  const h = S.hist.get(panelId);
  if (h) { h.undo = h.undo.filter((x) => x.kind !== "mask"); h.redo = h.redo.filter((x) => x.kind !== "mask"); }
  toast(why, "need");
  syncUndo();
}

const handLayerOf = (layers) => layers.filter((l) => l.role === "human_hand" && !l.removed)
  .sort((a, b) => b.stack_order - a.stack_order)[0];

// コマの層を、コマの絵の画素の上の位置に出す。描く先の人の手の層は canvas（S.hand）で出し、ほかは絵で出す
async function panelLayers(p, frame, size) {
  const out = [];
  if (!frame) return out;
  const target = handLayerOf(S.layers);
  const hand = await prepareHand(p, frame, size, target);
  for (const l of [...S.layers].sort((a, b) => a.stack_order - b.stack_order)) {
    if (l.removed || !l.visible) continue;
    if (target && l.id === target.id && hand.canvas) { out.push({ canvas: hand.canvas, opacity: l.opacity, x: 0, y: 0, w: size.w, h: size.h }); continue; }
    if (!l.image_id || !l.placement) continue;
    const f = pxFrame(l.placement);
    if (!f) continue;
    const { image } = await api.image(`/works/${S.workId}/images/${l.image_id}/file`);
    out.push({ image, opacity: l.opacity, x: (f.ox - frame.ox) / frame.sx, y: (f.oy - frame.oy) / frame.sy,
               w: image.naturalWidth * f.sx / frame.sx, h: image.naturalHeight * f.sy / frame.sy });
  }
  // 描く先の層がまだ無くても、描いた線を出す canvas は一番上に置く（最初の線で層を作る）
  if (!target) out.push({ canvas: hand.canvas, opacity: 1, x: 0, y: 0, w: size.w, h: size.h });
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
  km.setTool(t);   // "workbench:mask" のキー（多角形の Enter・Esc）は囲む道具の間だけ効く
  syncPenBar();
}

function syncPenBar() {
  const p = panel();
  let msg = "";
  if (!S.image) msg = "コマに絵が無いので描けません";
  else if (!S.frame) msg = "コマの絵に置き場が無いか、回転・傾き・反転があるので、ペンの線の位置を決められません";
  else if (S.hand && S.hand.blocked) msg = S.hand.blocked;
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
  const im = await api.fileImage(file);
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

// 送っている間は「頼む」を押せなくする（disabled なのでキーボードの Enter でも押せない）。2回押しても1組だけ送る
async function generate(over = {}) {
  if (S.sending) return;
  const btn = $("#generate");
  S.sending = true; btn.disabled = true; btn.setAttribute("aria-busy", "true");
  try { await send(over); } finally { S.sending = false; btn.disabled = false; btn.removeAttribute("aria-busy"); }
}

async function send(over) {
  const spec = over.proc || S.proc;
  const params = over.params || S.form.values();
  const body = { process: spec.name, params, count: over.count || countN(), seed_mode: over.seed_mode || seedMode() };
  if (body.seed_mode === "fixed") body.seed = over.seed ?? Number($("#seed").value);
  if (over.source_image_id) body.source_image_id = over.source_image_id;
  if (!over.proc && spec.mask !== "none") {
    const m = stage.maskPngBase64();
    if (m) { body.mask = { png_base64: m }; S.maskUnsent = false; }
    else if (spec.mask === "required") { toast("描き直す所を塗ってください（囲んで頼む）", "need"); setTool("mask"); return; }
  }
  if (params.control && params.control !== "none") {
    if (!S.control) { toast("形の指定に使う絵を選んでください", "need"); return; }
    body.control = { png_base64: S.control };
  }
  const svc = over.service_id || $("#service").value;
  if (svc && svc !== spec.route_service_id) body.service_id = svc;
  try {
    // 描いた線と消した所の保存が済み、線の控えが今の線と合ってから頼む（古い控えはサーバーが断る）
    await idleSaves();
    if (S.hand && S.hand.dirty) await uploadCache(S.hand);
    if (spec.source === "required" && !over.source_image_id) body.source_image_id = S.viewing || panel().image_id;
    const r = await api.post(`/works/${S.workId}/panels/${S.panelId}/generate`, body);
    toast(`${spec.label}を ${r.jobs.length} 件頼みました`);
    showTab("cands");
    await loadCandidates();
  } catch (e) { fail(e, spec.label); }
}

// ---------------------------------------------------------------- 候補
// 進み具合はポーリングで見る（EventSource は X-V3-User を付けられない）。
// 読めなかったときは知らせを重ねず、1つの状態（renderStatus）に出し、次に読むまでの間を倍にしていく（最長 POLL_MAX_MS）
async function loadCandidates() {
  clearTimeout(S.poll);
  const at = `${S.workId}/${S.panelId}`;
  try {
    const res = await api.get(`/works/${S.workId}/panels/${S.panelId}/candidates`);
    if (at !== `${S.workId}/${S.panelId}`) return;
    S.pollFails = 0; S.link = null;
    S.sets = res.sets.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    renderCandidates(res.panel_image_id);
    renderProgress();
  } catch (e) {
    if (at !== `${S.workId}/${S.panelId}`) return;
    S.pollFails += 1;
    S.link = { text: `候補と進み具合を読めません：${api.errorText(e)}` };
  }
  if (S.pollFails || S.sets.some((s) => s.jobs.some((j) => ACTIVE.has(j.status)))) {
    const wait = S.pollFails ? Math.min(POLL_MAX_MS, POLL_MS * 2 ** S.pollFails) : POLL_MS;
    if (S.link) S.link.at = Date.now() + wait;
    S.poll = setTimeout(() => loadCandidates(), wait);
  }
  renderStatus();
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
      const im = h("img", { alt: "" });
      th.prepend(im);
      api.showIn(im, `/works/${S.workId}/images/${img.id}/thumbnail?size=${THUMB}`).catch((e) => fail(e, "候補の小さい絵を読む"));
      if (img.protected_mask_url) {
        api.maskOverlay(img.protected_mask_url, stage.col.protectRgb, 0.55, THUMB * 2).then((c) => {
          const copy = h("canvas", { class: "prot" });
          copy.width = c.width; copy.height = c.height;
          copy.getContext("2d").drawImage(c, 0, 0);
          th.append(copy);
        }).catch((e) => fail(e, "人の手の範囲を出す"));
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
      const why = j.failure_detail || j.failure_kind;
      const failText = j.status === "stopped" ? (why ? `${STATUS[j.status]}：${why}` : `${STATUS[j.status]}（理由はサーバーに残っていません）`) : STATUS[j.status] || j.status;
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
  } catch (e) { fail(e, "止めること"); }
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

// ---------------------------------------------------------------- 取り消し（コマごと・囲みとサーバーの操作を1つに）
function hist(panelId = S.panelId) {
  if (!S.hist.has(panelId)) S.hist.set(panelId, { undo: [], redo: [] });
  return S.hist.get(panelId);
}

function pushUndo(entry, panelId = S.panelId) {
  const h = hist(panelId);
  h.undo.push(entry); h.redo = [];
  if (entry.kind === "server") entry.ids.catch(() => forget(entry));
  if (entry.kind === "mask") trimMaskHistory();
  syncUndo();
}

function forget(entry) {
  for (const h of S.hist.values()) { h.undo = h.undo.filter((x) => x !== entry); h.redo = h.redo.filter((x) => x !== entry); }
  syncUndo();
}

// 囲みの差分が MASK_HISTORY_BYTES を超えたら、古い物から捨てる
function trimMaskHistory() {
  const all = [];
  for (const h of S.hist.values()) for (const list of [h.undo, h.redo]) for (const x of list) if (x.kind === "mask") all.push([list, x]);
  let total = all.reduce((n, [, x]) => n + x.edit.bytes, 0);
  for (const [list, x] of all) {
    if (total <= MASK_HISTORY_BYTES) break;
    list.splice(list.indexOf(x), 1);
    total -= x.edit.bytes;
  }
}

function syncUndo() {
  const h = S.panelId ? hist() : { undo: [], redo: [] };
  $("#undo").setAttribute("aria-disabled", String(!h.undo.length));
  $("#redo").setAttribute("aria-disabled", String(!h.redo.length));
}

async function undoRedo(dir) {
  if (S.undoing) return;
  if (S.viewing) { toast("昔の版を見ている間は取り消せません。「今の絵に戻る」を押してください", "need"); return; }
  const h = hist();
  const [from, to] = dir === "undo" ? [h.undo, h.redo] : [h.redo, h.undo];
  const entry = from.pop();
  if (!entry) return;
  if (entry.kind === "mask") {
    stage.swapMaskEdit(entry.edit);
    to.push(entry);
    syncUndo();
    return;
  }
  S.undoing = true;
  try {
    await idleSaves();
    const ids = await entry.ids;
    const back = [];
    for (const id of [...ids].reverse()) back.push((await api.undo(S.workId, id)).event_id);
    to.push({ ...entry, ids: Promise.resolve(back) });
  } catch (e) {
    from.push(entry);
    fail(e, dir === "undo" ? "取り消すこと" : "やり直すこと");
    return;
  } finally { S.undoing = false; syncUndo(); }
  await refreshAfter(entry.refresh).catch((e) => fail(e, "読み直し"));
}

// 取り消した操作が変えた物だけを読み直す
async function refreshAfter(what) {
  if (what === "hand") { await reloadHand(S.hand); stage.redraw(); return; }
  if (what === "candidates") { await loadCandidates(); return; }
  await afterChange();
}

// ---------------------------------------------------------------- 後ろで保存する（描いた線・消した所）
// 画面には先に出し、保存は順に1つずつ送る。失敗したら止めて、状態の所に「もう一度送る」「この変更を捨てる」を出す
const Q = { jobs: [], running: false, failed: null, waiters: [] };

function enqueue(label, run, kind) {
  return new Promise((resolve, reject) => {
    Q.jobs.push({ label, run, kind, resolve, reject });
    pump();
  });
}

async function pump() {
  if (Q.running || Q.failed) return;
  const job = Q.jobs[0];
  if (!job) {
    for (const w of Q.waiters.splice(0)) w.resolve();
    renderStatus();
    return;
  }
  Q.running = true;
  renderStatus();
  try {
    const v = await job.run();
    Q.jobs.shift();
    job.resolve(v);
  } catch (e) {
    console.error(e);
    Q.failed = { job, error: e };
    for (const w of Q.waiters.splice(0)) w.reject(new Error(`保存できていない変更があります（${job.label}）`));
  }
  Q.running = false;
  renderStatus();
  pump();
}

// 保存が全部済むまで待つ。止まっていれば断る
function idleSaves() {
  if (Q.failed) return Promise.reject(new Error(`保存できていない変更があります（${Q.failed.job.label}）`));
  if (!Q.jobs.length) return Promise.resolve();
  return new Promise((resolve, reject) => Q.waiters.push({ resolve, reject }));
}

function retrySaves() { Q.failed = null; pump(); }

// 保存できなかった変更と、その後に描いた物を捨てて、サーバーの今の物を出し直す
async function discardSaves() {
  const jobs = Q.jobs.splice(0);
  Q.failed = null;
  for (const j of jobs) j.reject(new Error("捨てた"));
  renderStatus();
  if (S.hand) S.hand.forceReload = true;
  await refreshPanelRow();
  await refreshPanel();
}

function savingCount() { return Q.jobs.length + (S.hand && S.hand.uploading ? 1 : 0); }

// 保存と、サーバーとのつながりの状態を、画面の左下の1か所に出す
function renderStatus() {
  const host = $("#stage-msg");
  if (Q.failed) {
    const n = note(`保存できませんでした（${Q.failed.job.label}）：${api.errorText(Q.failed.error)}。描いた物は画面にだけあります`, "bad");
    n.append(h("button", { class: "btn sm", onclick: retrySaves }, "もう一度送る"),
      h("button", { class: "btn sm", onclick: () => discardSaves().catch((e) => fail(e, "読み直し")) }, "この変更を捨てる"));
    host.replaceChildren(n);
    return;
  }
  if (S.link) {
    const sec = Math.max(1, Math.round((S.link.at - Date.now()) / 1000));
    const n = note(`${S.link.text}。${sec} 秒後にもう一度読みます`, "need", "wifi-off");
    n.append(h("button", { class: "btn sm", onclick: () => loadCandidates() }, "今すぐ読む"));
    host.replaceChildren(n);
    return;
  }
  const n = savingCount();
  host.replaceChildren(n ? note(`保存しています（${n} 件）`, "", "loader") : "");
}

// ---------------------------------------------------------------- 採用・却下・版
async function submitOps(...bodies) {
  const ids = [];
  for (const b of bodies) ids.push((await api.op(S.workId, b)).event_id);
  return ids;
}

async function afterChange() {
  await refreshPanelRow();
  await refreshPanel();
  renderProcesses();
  await Promise.all([loadCandidates(), loadVersions()]);
}

async function adopt(imageId) {
  try {
    await idleSaves();
    const ids = await submitOps({ type: "adopt_image", panel_id: S.panelId, image_id: imageId });
    pushUndo({ kind: "server", ids: Promise.resolve(ids), refresh: "all" });
    toast("採用しました（取り消せます）");
    await afterChange();
  } catch (e) { fail(e, "採用"); }
}

async function discard(imageId, on) {
  try {
    const ids = await submitOps({ type: "set_image_discarded", image_id: imageId, discarded: on });
    pushUndo({ kind: "server", ids: Promise.resolve(ids), refresh: "candidates" });
    await loadCandidates();
  } catch (e) { fail(e, on ? "却下" : "却下をやめること"); }
}

async function loadVersions() {
  const at = `${S.workId}/${S.panelId}`;
  const res = await api.get(`/works/${S.workId}/panels/${S.panelId}/versions`);
  if (at !== `${S.workId}/${S.panelId}`) return;
  const host = $("#versions");
  host.replaceChildren();
  if (!res.versions.length) { host.append(h("div", { class: "meta", text: "まだ絵を置いていません" })); return; }
  const list = res.versions.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  for (const v of list) {
    const im = h("img", { alt: "" });
    const th = h("div", { class: "th" }, im);
    api.showIn(im, `/works/${S.workId}/images/${v.id}/thumbnail?size=128`).catch((e) => fail(e, "版の小さい絵を読む"));
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
  await refreshPanel(v.id).catch((e) => fail(e, "版を出すこと"));
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
  const paths = S.compareIds.map((id) => `/works/${S.workId}/images/${id}/file`);
  const imgs = await Promise.all(paths.map((p, i) => api.showIn(h("img", { alt: S.compareNames[i] }), p)));
  if (mode === "side" || imgs.length < 2) {
    body.replaceChildren(...imgs.map((im, i) => h("figure", {}, im, h("figcaption", { text: S.compareNames[i] }))));
    return;
  }
  const { image: a } = await api.image(paths[0]);
  imgs[1].className = "b";
  const wrap = h("div", { class: "slider-wrap", style: `--ar:${a.naturalWidth}/${a.naturalHeight}` }, imgs[0], imgs[1],
    h("div", { class: "bar" }));
  const r = h("input", { type: "range", min: 0, max: 100, value: 50, "aria-label": "境目の位置" });
  r.addEventListener("input", () => wrap.style.setProperty("--cut", `${r.value}%`));
  wrap.append(r);
  body.replaceChildren(h("figure", { class: "slider-fig" },
    wrap, h("figcaption", { text: `左：${S.compareNames[0]}　右：${S.compareNames[1]}` })));
}

// ---------------------------------------------------------------- 人の手で描く（ペン）
// S.hand：今のコマの、描く先の人の手の層。canvas はコマの絵と同じ画素の大きさで、層の控えの絵そのもの。
// 線は描いている間にこの canvas へ描き（stage.js）、離したら保存を後ろで送る。控えの絵（stroke-cache）は、
// 描き終えて CACHE_IDLE_MS 経ったとき・頼む前・コマを替える前に、この canvas をそのまま上げる（全部の線を描き直さない）。
// { panelId, layerId, layerNew, canvas, strokes: [サーバーの形の線], dirty, version, blocked, timer, uploading }

async function prepareHand(p, frame, size, target) {
  const old = S.hand;
  const reuse = old && !old.forceReload && old.panelId === p.id && old.canvas.width === size.w && old.canvas.height === size.h
    && (target ? old.layerId === target.id : old.layerNew || !old.layerId);
  if (reuse) return old;
  const canvas = document.createElement("canvas");
  canvas.width = size.w; canvas.height = size.h;
  const hand = { panelId: p.id, layerId: target ? target.id : null, layerNew: false, canvas, strokes: [], dirty: false,
                 version: 0, blocked: "", frame };
  S.hand = hand;
  if (!target) return hand;
  if (!target.visible) { hand.blocked = "人の手の層を隠しているので描けません"; return hand; }
  const cacheOk = target.image_id && target.stroke_revision === target.image_stroke_revision && aligned(target, frame);
  if (cacheOk) {
    // 控えが今の線と合っていれば、その絵をそのまま使う（線は読まない）
    const { image } = await api.image(`/works/${S.workId}/images/${target.image_id}/file`);
    canvas.getContext("2d").drawImage(image, 0, 0);
    // 線は id だけ読む（控えを上げるときに、画面の線とサーバーの線が同じかを比べるため）
    const { strokes } = await readStrokes(target.id, false);
    if (S.hand === hand && !hand.strokes.length) hand.strokes = strokes;
    return hand;
  }
  await reloadHand(hand);
  return hand;
}

// 控えの絵が、コマの絵の画素にぴったり重なる置き場か
function aligned(layer, frame) {
  const f = layer.placement && pxFrame(layer.placement);
  if (!f) return false;
  const near = (a, b) => Math.abs(a - b) < 0.5;
  return near((f.ox - frame.ox) / frame.sx, 0) && near((f.oy - frame.oy) / frame.sy, 0)
    && near(f.sx / frame.sx, 1) && near(f.sy / frame.sy, 1);
}

// 層の線をサーバーから区切って読み、canvas を描き直す。控えが線と合っていなければ dirty にする
async function reloadHand(hand) {
  if (!hand || !hand.layerId || hand.layerNew) return;
  hand.forceReload = false;
  const { strokes, revision, cacheRevision } = await readStrokes(hand.layerId, true);
  hand.strokes = strokes;
  hand.version += 1;
  const other = strokes.find((s) => s.brush !== "pencil");
  hand.blocked = other ? `この画面は鉛筆の線しか描けません。この層には「${other.brush}」の線があるので、描き直せません` : "";
  const x = hand.canvas.getContext("2d");
  x.clearRect(0, 0, hand.canvas.width, hand.canvas.height);
  if (!hand.blocked) for (const s of strokes) drawServerStroke(x, s, hand.frame);
  hand.dirty = revision !== cacheRevision;
  if (hand.dirty) scheduleUpload(hand);
  return revision;
}

async function readStrokes(layerId, points) {
  const out = [];
  let after = -1, revision = null, cacheRevision = null;
  do {
    const r = await api.get(`/works/${S.workId}/layers/${layerId}/pen-strokes?after=${after}&limit=2000&points=${points}`);
    out.push(...r.strokes);
    revision = r.stroke_revision; cacheRevision = r.image_stroke_revision;
    after = r.next_after;
  } while (after !== null);
  return { strokes: out, revision, cacheRevision };
}

function drawServerStroke(ctx, s, f) {
  const pts = s.points.map(([mx, my, pressure]) => ({ x: (mx - f.ox) / f.sx, y: (my - f.oy) / f.sy, pressure }));
  drawStroke(ctx, pts, s.width_mm / f.sx, s.color, s.opacity);
}

function penBegin() {
  if (S.viewing) throw new Error("昔の版を見ている間は描けません");
  if (!syncPenBar()) throw new Error($("#pen-note").textContent);
  return { canvas: S.hand.canvas, widthPx: stage.penWidthPx, color: PEN_INK };
}

function onPenStroke(points, pointerType) {
  const hand = S.hand, f = hand.frame;
  const stroke = { id: newId(), brush: "pencil", color: PEN_INK, opacity: 1,
                   width_mm: Number($("#pen-width [aria-pressed=true]").dataset.w), pointer_type: pointerType,
                   points: points.map((p) => [f.ox + p.x * f.sx, f.oy + p.y * f.sy, p.pressure, p.ms]) };
  hand.strokes.push(stroke);
  hand.version += 1; hand.dirty = true;
  clearTimeout(hand.timer);
  let makeLayer = null;
  if (!hand.layerId) {
    hand.layerId = newId(); hand.layerNew = true;
    const top = Math.max(-1, ...S.layers.map((x) => x.stack_order));
    makeLayer = { type: "add_panel_layer", id: hand.layerId, panel_id: hand.panelId, role: "human_hand", stack_order: top + 1 };
  }
  const workId = S.workId;
  // 層を作る操作が通った後で線が通らなかったときは、もう一度送るときに層を作り直さない
  let layerEvent = null;
  const ids = enqueue("ペンの線", async () => {
    const out = [];
    if (makeLayer && !layerEvent) {
      layerEvent = (await api.op(workId, makeLayer)).event_id;
      hand.layerNew = false;
      S.layers.push({ ...makeLayer, image_id: null, visible: true, opacity: 1, placement: null, removed: false,
                      stroke_revision: 0, image_stroke_revision: 0 });
    }
    if (layerEvent) out.push(layerEvent);
    out.push((await api.op(workId, { type: "add_pen_strokes", layer_id: hand.layerId, strokes: [stroke] })).event_id);
    return out;
  }, "pen");
  // 層を作った線は、層ごと1回で取り消せる
  pushUndo({ kind: "server", ids, refresh: "hand" }, hand.panelId);
  ids.then(() => scheduleUpload(hand), () => {});
}

function scheduleUpload(hand) {
  clearTimeout(hand.timer);
  hand.timer = setTimeout(() => uploadCache(hand).catch((e) => fail(e, "線の控えを上げる")), CACHE_IDLE_MS);
}

// 控えの絵を上げる。サーバーの線（id だけ読む）が画面の線と同じなら、canvas をそのまま上げる。
// 違えば（ほかの人が描いた・取り消した）線を読み直して描き直してから上げる
async function uploadCache(hand) {
  clearTimeout(hand.timer);
  if (!hand.dirty || !hand.layerId) return;
  if (hand.uploading) return hand.uploading;
  hand.uploading = (async () => {
    renderStatus();
    await idleSaves();
    let { strokes, revision: rev } = await readStrokes(hand.layerId, false);
    const here = new Set(hand.strokes.map((s) => s.id));
    if (strokes.length !== here.size || strokes.some((s) => !here.has(s.id))) {
      rev = await reloadHand(hand);
      clearTimeout(hand.timer);
    }
    // 鉛筆でない線がある層は描き直せないので、控えも上げない（サーバーの控えのままにする）
    if (hand.blocked) return;
    const version = hand.version;
    const blob = await new Promise((resolve) => hand.canvas.toBlob(resolve, "image/png"));
    if (version !== hand.version) { scheduleUpload(hand); return; }
    const f = hand.frame, c = hand.canvas;
    const form = new FormData();
    form.append("image", blob, "strokes.png");
    form.append("stroke_revision", String(rev));
    form.append("placement", JSON.stringify({ crop_px: [0, 0, c.width, c.height],
                                              dest_box_mm: [f.ox, f.oy, f.ox + c.width * f.sx, f.oy + c.height * f.sy] }));
    const r = await api.postForm(`/works/${S.workId}/layers/${hand.layerId}/stroke-cache`, form);
    if (version === hand.version) hand.dirty = false;
    const l = S.layers.find((x) => x.id === hand.layerId);
    if (l) Object.assign(l, { image_id: r.image_id, stroke_revision: rev, image_stroke_revision: rev });
  })().finally(() => { hand.uploading = null; renderStatus(); });
  return hand.uploading;
}

// ---------------------------------------------------------------- 人の手で消す（画素の消しゴム）
function eraseBegin() {
  if (S.viewing) throw new Error("昔の版を見ている間は消せません");
  if (!S.image) throw new Error("消す絵がありません");
  return true;
}

// 消した所は stage.js が絵の写しから先に消して見せている。サーバーの答え（新しい版）が来たら、その絵に替える
function onErase(points, widthPx) {
  const panelId = S.panelId, workId = S.workId;
  const ids = enqueue("消しゴム", async () => {
    const form = new FormData();
    form.append("strokes", JSON.stringify([{ points: points.map((p) => [p.x, p.y]), width_px: widthPx }]));
    const r = await api.postForm(`/works/${workId}/panels/${panelId}/erase-pixels`, form);
    const p = S.work.panels.find((x) => x.id === panelId);
    if (p) p.image_id = r.image_id;
    // まだ送っていない消しゴムがあれば、最後の答えが来てから替える（先に替えると、その消した所が見えなくなる）
    if (S.panelId === panelId && !S.viewing && !Q.jobs.slice(1).some((j) => j.kind === "erase")) {
      refreshPanel().then(() => loadVersions()).catch((e) => fail(e, "消した後の絵を読むこと"));
    }
    return [r.event_id];
  }, "erase");
  pushUndo({ kind: "server", ids, refresh: "all" }, panelId);
}

// ---------------------------------------------------------------- タブ・保存しておく選び
function showTab(t) {
  for (const b of $$(".itab")) b.setAttribute("aria-selected", String(b.dataset.tab === t));
  for (const p of $$("[data-pane]")) p.hidden = p.dataset.pane !== t;
}
function readPref(k) { try { return localStorage.getItem(`v3.gen.${k}`); } catch { return null; } }
// 原稿の画面から開いたとき（?work=&page=&panel=）は、覚えた選び方より URL を先に使う。使ったら URL から消す
const asked = new URLSearchParams(location.search);
function wanted(k) {
  const v = asked.get(k);
  if (v) { asked.delete(k); return v; }
  return readPref(k);
}
function writePref(k, v) { try { localStorage.setItem(`v3.gen.${k}`, v); } catch { /* 覚えられない環境では毎回初めから選ぶ */ } }

// ---------------------------------------------------------------- はじめ
function bindUi() {
  $("#pick-work").addEventListener("change", (e) => selectWork(e.target.value).catch(fail));
  $("#pick-page").addEventListener("change", (e) => selectPage(e.target.value).catch(fail));
  $("#pick-panel").addEventListener("change", (e) => selectPanel(e.target.value).catch(fail));
  const user = $("#user");
  user.addEventListener("change", () => { api.setUser(user.value.trim()); km.loadUserKeys(); start(); });
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
  // 囲みの「反転・全部・消す」は昔の版を見ている間は使えない（塗る筆と同じ。maskBegin）
  const maskOp = (fn) => () => { if (maskBegin()) fn(); };
  $("#mask-invert").addEventListener("click", maskOp(() => stage.invertMask()));
  $("#mask-fill").addEventListener("click", maskOp(() => stage.fillMask()));
  $("#mask-clear").addEventListener("click", maskOp(() => stage.clearMask()));
  $("#mask-show").addEventListener("click", (e) => {
    const b = e.currentTarget;
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(on));
    syncMask();
  });
  $("#zoom-in").addEventListener("click", () => stage.zoomBy(1.25));
  $("#zoom-out").addEventListener("click", () => stage.zoomBy(0.8));
  $("#zoom-fit").addEventListener("click", () => stage.fit());
  $("#undo").addEventListener("click", () => undoRedo("undo"));
  $("#redo").addEventListener("click", () => undoRedo("redo"));
  for (const b of $$(".itab")) b.addEventListener("click", () => showTab(b.dataset.tab));
  for (const b of $$("#count button")) b.addEventListener("click", () => pressed($("#count"), b));
  for (const b of $$("#seed-mode button")) b.addEventListener("click", () => { pressed($("#seed-mode"), b); $("#seed").hidden = b.dataset.m !== "fixed"; });
  $("#service").addEventListener("change", showServiceMeta);
  $("#generate").addEventListener("click", () => generate());
  $("#viewing-back").addEventListener("click", () => { S.viewing = null; $("#viewing").hidden = true; refreshPanel().catch(fail); });
  for (const b of $$("#compare-mode button")) b.addEventListener("click", () => { pressed($("#compare-mode"), b); renderCompare().catch(fail); });
  $("#compare-close").addEventListener("click", () => { $("#compare").hidden = true; });
  $("#keys-open").addEventListener("click", () => openHelp());
  window.addEventListener("online", () => { if (S.link) loadCandidates(); if (Q.failed) retrySaves(); });
  window.addEventListener("offline", () => { S.link = { text: "ネットにつながっていません", at: Date.now() + POLL_MAX_MS }; renderStatus(); });
  // 保存していない線・消した所・まだ頼んでいない囲みがあるときは、閉じる前に聞く
  window.addEventListener("beforeunload", (e) => {
    if (Q.jobs.length || (S.hand && (S.hand.dirty || S.hand.uploading)) || S.maskUnsent) e.preventDefault();
  });
}

// ---------------------------------------------------------------- キー（llm_doc/V3細部の決めごと.md 22章）
// キーは common/keymap.js の1か所で受け、ここでは操作の名前（common/key_catalog.js）に処理を結ぶだけ。
// 処理は画面のボタンを押したのと同じにする（ボタンの押せない状態もそのまま効く）。押せなかったら false で、次の候補へ回す
function press(sel) {
  const b = $(sel);
  if (!b || b.disabled || b.getAttribute("aria-disabled") === "true" || b.closest("[hidden]")) return false;
  b.click();
  return true;
}

function bindKeys() {
  const btn = (sel) => () => press(sel);
  km.bind("workbench.select", btn("[data-tool=select]"));
  km.bind("workbench.mask", btn("[data-tool=mask]"));
  km.bind("workbench.extend", btn("[data-tool=extend]"));
  km.bind("workbench.pen", btn("[data-tool=pen]"));
  km.bind("workbench.erase", btn("[data-tool=erase]"));
  km.bind("workbench.zoomIn", btn("#zoom-in"));
  km.bind("workbench.zoomOut", btn("#zoom-out"));
  km.bind("workbench.zoomFit", btn("#zoom-fit"));
  km.bind("workbench.generate", () => { press("#generate"); });
  km.bind("edit.undo", () => { press("#undo"); });
  km.bind("edit.redo", () => { press("#redo"); });
  km.bind("save.state", showSaveState);
  km.bind("workbench.compareClose", () => !$("#compare").hidden && press("#compare-close"));
  km.bind("workbench.polyClose", () => stage.polygonKey("Enter"));
  km.bind("workbench.polyCancel", () => stage.polygonKey("Escape"));
  // Space を押している間だけ「見る（動かす）」にし、離したら前の道具へ戻す
  let before = null;
  km.bind("workbench.pan", {
    down: () => { if (S.tool !== "select") { before = S.tool; setTool("select"); } },
    up: () => { if (before) { setTool(before); before = null; } },
  });
}

// Ctrl+S：保存の具合を知らせる（描いた線と消した所は、描いた後に後ろで送っている）
function showSaveState() {
  if (Q.failed) toast(`保存できていない変更があります（${Q.failed.job.label}）。左下の「もう一度送る」か「この変更を捨てる」を選んでください`, "bad");
  else if (savingCount() || (S.hand && S.hand.dirty)) toast(`保存しています（${savingCount() || 1} 件）。済むと左下の印が消えます`);
  else toast("描いた物は全部サーバーに残っています");
}

function maskBegin() {
  if (S.viewing) { toast("昔の版を見ている間は囲めません。「今の絵に戻る」を押してください", "need"); return false; }
  return true;
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
  onExtend: onExtendFromStage, penBegin, onPenStroke, eraseBegin, onErase,
  maskBegin,
  onMaskEdit: (edit) => { S.maskUnsent = true; pushUndo({ kind: "mask", edit }); },
  onRefuse: (msg) => toast(msg, "need"),
});
// 開発者ツールと画面の試験（test/image_generation_ui.mjs・persistence_e2e.mjs）から絵の画素の位置と保存の待ち行列を調べるため
window.v3Stage = stage;
window.__wb = { S, Q };
bindUi();
await showWho().catch(fail);
bindKeys();
startKeys("workbench");
icons();
setTool("select");
start();
