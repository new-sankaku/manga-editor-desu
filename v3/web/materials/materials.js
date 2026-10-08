// 設定資料：人物・場所・小物・その他。名前・特徴・服・絵と、生成の設定（見た目の指示・入れない指示・追加学習・参照の絵・seed）。
// AIが企画から抜き出した案（proposal_state=proposed）は、人が採る・採らないを決める。
// 口：GET /works/{id}（material_entries）、POST /works/{id}/images（絵を置く）、GET /works/{id}/images/{id}/thumbnail、
//     操作 add_material_entry・update_material_entry・decide_material_proposal・set_removed
import { html, render, nothing, api, icon, toast, fail, op, startShell, emptyNote, loadThumbs } from "../common/shell.js";
import { fieldsHtml, readFields, USAGE_TERMS } from "../common/form_fields.js";

const main = document.getElementById("main");
main.className = "screen two";
const KIND = { character: "人物", background: "場所", prop: "小物", other: "その他" };
const STATE = { proposed: "AIの案", adopted: "使う", rejected: "採らなかった" };
const S = { workId: null, work: null, sel: null, draft: null, q: "", why: null, busy: false, showRejected: false };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null;
  if (id) {
    try { S.work = await api.get(`/works/${id}`); } catch (e) { fail(e, "作品を読む"); S.why = api.errorText(e); }
  }
  const e = S.work && S.work.material_entries.find((m) => m.id === S.sel);
  S.draft = e ? structuredClone(e) : null;
  if (!e) S.sel = null;
  draw();
}
async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; await loadWork(S.workId); }
}
function select(id) {
  S.sel = id;
  S.draft = structuredClone(S.work.material_entries.find((m) => m.id === id));
  draw();
}

// ---------------------------------------------------------------- 一覧
function addEntry(kind) {
  const name = prompt(`${KIND[kind]}の名前`);
  if (!name || !name.trim()) return;
  run("設定資料を足す", async () => {
    const id = crypto.randomUUID().replace(/-/g, "");
    await op(S.workId, { type: "add_material_entry", id, kind, name: name.trim() });
    S.sel = id;
    toast(`${KIND[kind]}「${name.trim()}」を足しました`);
  });
}
function sideList() {
  const all = S.work.material_entries.filter((m) => !m.removed && (S.showRejected || m.proposal_state !== "rejected"));
  const q = S.q.trim();
  const hit = (m) => !q || m.name.includes(q) || (m.traits || "").includes(q);
  return html`<nav class="card" aria-label="設定資料の一覧">
    <input class="field" type="search" placeholder="探す" aria-label="設定資料を探す" .value=${S.q} @input=${(e) => { S.q = e.target.value; draw(); }}>
    ${Object.entries(KIND).map(([k, l]) => html`<div class="sec-h grp"><span class="lbl">${l}</span>
      <button class="ibtn" title="${l}を足す" aria-label="${l}を足す" @click=${() => addEntry(k)}>${icon("plus")}</button></div>
      <div class="list">${all.filter((m) => m.kind === k && hit(m)).map((m) => html`
        <button class="item" data-entry=${m.id} aria-current=${String(S.sel === m.id)} @click=${() => select(m.id)}>
          <span class="nm">${m.name}</span>
          ${m.proposal_state !== "adopted" ? html`<span class="flag ${m.proposal_state === "proposed" ? "warn" : "mut"}">${STATE[m.proposal_state]}</span>` : nothing}
          ${m.image_ids.length ? html`<span class="meta num">絵 ${m.image_ids.length}</span>` : nothing}</button>`)}</div>`)}
    <label class="row meta"><input type="checkbox" .checked=${S.showRejected} @change=${(e) => { S.showRejected = e.target.checked; draw(); }}>採らなかった案も出す</label>
  </nav>`;
}

// ---------------------------------------------------------------- 絵
const thumb = (id) => `/works/${S.workId}/images/${id}/thumbnail?size=256`;
function imageGrid(ids, onRemove) {
  return html`<div class="thumbs">${ids.map((id) => html`<div class="thumb paper"><img data-thumb=${thumb(id)} alt="設定資料の絵">
    <button class="ibtn x" title="外す" aria-label="この絵を外す" @click=${() => onRemove(id)}>${icon("x")}</button></div>`)}</div>`;
}
// 絵を置く（人が描いた絵か、持ち込んだ絵）。持ち込んだ絵は利用規約の要点が要る（V3細部の決めごと 20章）
async function upload(form, role) {
  const file = form.elements.file.files[0];
  if (!file) { toast("絵のファイルを選んでください", "need"); return null; }
  const fd = new FormData();
  fd.append("image", file);
  fd.append("role", role);
  const origin = form.elements.origin.value;
  fd.append("origin", origin);
  if (origin === "imported") {
    const terms = readFields(form, USAGE_TERMS, "terms.");
    if (!terms) { toast("持ち込んだ絵は、利用規約の要点を入れてください", "need"); return null; }
    fd.append("usage_terms", JSON.stringify(Object.fromEntries(Object.entries(terms).filter(([, v]) => v !== null))));
  }
  const r = await api.postForm(`/works/${S.workId}/images`, fd);
  form.reset();
  return r.id;
}
function uploadForm(label, role, onDone) {
  let origin = "human_drawn";
  const submit = (e) => {
    e.preventDefault();
    const f = e.target;
    S.busy = true; draw();
    upload(f, role).then((id) => { if (id) onDone(id); }).catch((err) => fail(err, "絵を置く")).finally(() => { S.busy = false; draw(); });
  };
  return html`<details class="more"><summary>${icon("chevron-right")}${label}</summary>
    <form class="form" @submit=${submit}>
      <label class="k">ファイル</label><input class="field" type="file" name="file" accept="image/*">
      <label class="k">出どころ</label><select class="field" name="origin" @change=${(e) => { origin = e.target.value; e.target.form.querySelector(".terms").hidden = origin !== "imported"; }}>
        <option value="human_drawn">人が描いた</option><option value="imported">持ち込んだ</option></select>
      <div class="full terms" hidden><div class="form">${fieldsHtml(USAGE_TERMS, {}, "terms.")}</div></div>
      <div class="full acts"><button class="btn sm" ?disabled=${S.busy}>${icon("image-plus")}置く</button></div>
    </form></details>`;
}

// ---------------------------------------------------------------- 1件
const BASIC = [
  { key: "name", label: "名前" },
  { key: "kind", label: "種類", type: "select", options: KIND },
  { key: "traits", label: "特徴", type: "textarea", rows: 4, hint: "検査に使う決まり（髪・目・背丈など）" },
  { key: "notes", label: "メモ", type: "textarea", rows: 2 },
];
const GEN = [
  { key: "prompt", label: "見た目の指示", type: "textarea", rows: 3 },
  { key: "negative_prompt", label: "入れない指示", type: "textarea", rows: 2 },
  { key: "seed", label: "seed", type: "number", step: 1 },
];
function save(e) {
  e.preventDefault();
  const f = e.target;
  const d = S.draft;
  const basic = readFields(f, BASIC) || {};
  const gen = readFields(f, GEN, "gen.") || { prompt: null, negative_prompt: null, seed: null };
  const loras = f.elements.loras.value.split("\n").map((s) => s.trim()).filter(Boolean).map((line) => {
    const m = line.match(/^(.+?)\s*[:：]\s*(-?[\d.]+)$/);
    if (!m) throw new Error(`追加学習の行「${line}」は「名前:重み」の形で書いてください`);
    return { name: m[1], weight: Number(m[2]) };
  });
  const clothes = d.clothes.map((c, i) => ({ name: f.elements[`cl-name-${i}`].value.trim(), description: f.elements[`cl-desc-${i}`].value.trim() || null, image_ids: c.image_ids }));
  const next = { ...basic, clothes, image_ids: d.image_ids,
                 generation: { ...gen, loras, reference_image_ids: d.generation.reference_image_ids || [] } };
  const entry = S.work.material_entries.find((m) => m.id === S.sel);
  const body = { type: "update_material_entry", id: entry.id };
  for (const [k, v] of Object.entries(next)) if (JSON.stringify(v) !== JSON.stringify(entry[k] ?? null)) body[k] = v;
  if (Object.keys(body).length === 2) { toast("変わった所がありません"); return; }
  run("設定資料を残す", async () => { await op(S.workId, body); toast("残しました"); });
}
function saveSafe(e) { try { save(e); } catch (err) { fail(err, "設定資料を残す"); } }
function decide(state) {
  run(state === "adopted" ? "案を採る" : "案を採らない", async () => { await op(S.workId, { type: "decide_material_proposal", id: S.sel, state }); });
}

function detail() {
  const d = S.draft;
  if (!d) return html`<section class="card">${emptyNote("左の一覧から選ぶか、＋で足してください")}</section>`;
  d.generation.reference_image_ids ??= [];
  return html`<form class="card" aria-label=${d.name} @submit=${saveSafe}>
    <div class="card-h"><span class="h1">${d.name}</span><span class="flag ${d.proposal_state === "adopted" ? "on" : d.proposal_state === "proposed" ? "warn" : "mut"}">${STATE[d.proposal_state]}</span>
      ${d.human_hand_fields.length ? html`<span class="meta">人が書いた項目はAIが変えません</span>` : nothing}</div>
    ${d.proposal_state !== "adopted" ? html`<div class="note need">${icon("triangle-alert")}<span>AIの案です。採るまで描く工程には使いません</span>
      <span class="grow"></span><button type="button" class="btn sm primary" @click=${() => decide("adopted")}>採る</button>
      ${d.proposal_state === "proposed" ? html`<button type="button" class="btn sm" @click=${() => decide("rejected")}>採らない</button>` : nothing}</div>` : nothing}
    <section class="sec"><div class="form">${fieldsHtml(BASIC, d)}</div></section>
    <section class="sec"><div class="sec-h"><span class="lbl">絵</span><span class="meta">三面図・表情など</span></div>
      ${d.image_ids.length ? imageGrid(d.image_ids, (id) => { d.image_ids = d.image_ids.filter((x) => x !== id); draw(); }) : html`<span class="meta">まだありません</span>`}
      ${uploadForm("絵を置く", "character_sheet", (id) => { d.image_ids = [...d.image_ids, id]; toast("絵を置きました。「残す」で設定資料に入ります"); draw(); })}</section>
    <section class="sec"><div class="sec-h"><span class="lbl">服</span>
      <button type="button" class="btn ghost sm" @click=${() => { d.clothes = [...d.clothes, { name: "", description: null, image_ids: [] }]; draw(); }}>${icon("plus")}足す</button></div>
      ${d.clothes.map((c, i) => html`<div class="form cloth">
        <label class="k" for="cl-name-${i}">名前</label><div class="row"><input class="field" id="cl-name-${i}" name="cl-name-${i}" .value=${c.name}
          @input=${(e) => { c.name = e.target.value; }}>
          <button type="button" class="ibtn" aria-label="この服を外す" @click=${() => { d.clothes = d.clothes.filter((x) => x !== c); draw(); }}>${icon("x")}</button></div>
        <label class="k" for="cl-desc-${i}">説明</label><input class="field" id="cl-desc-${i}" name="cl-desc-${i}" .value=${c.description || ""} @input=${(e) => { c.description = e.target.value; }}>
      </div>`)}</section>
    <section class="sec"><div class="sec-h"><span class="lbl">生成の設定</span><span class="meta">この${KIND[d.kind]}の絵を作る依頼に使います</span></div>
      <div class="form">${fieldsHtml(GEN, d.generation, "gen.")}
        <label class="k" for="loras">追加学習</label><div class="v"><textarea class="field" id="loras" name="loras" rows="2"
          .value=${(d.generation.loras || []).map((l) => `${l.name}:${l.weight}`).join("\n")}></textarea><span class="meta">1行に「名前:重み」</span></div></div>
      <div class="lbl">参照の絵</div>
      ${d.generation.reference_image_ids.length ? imageGrid(d.generation.reference_image_ids, (id) => { d.generation.reference_image_ids = d.generation.reference_image_ids.filter((x) => x !== id); draw(); }) : html`<span class="meta">まだありません</span>`}
      <div class="acts">${d.image_ids.filter((id) => !d.generation.reference_image_ids.includes(id)).length ? html`<span class="meta">上の絵から：</span>
        ${d.image_ids.filter((id) => !d.generation.reference_image_ids.includes(id)).map((id) => html`<button type="button" class="btn ghost sm"
          @click=${() => { d.generation.reference_image_ids = [...d.generation.reference_image_ids, id]; draw(); }}>${icon("plus")}<img class="mini" data-thumb=${`/works/${S.workId}/images/${id}/thumbnail?size=64`} alt="">参照にする</button>`)}` : nothing}</div>
      ${uploadForm("参照の絵を置く", "reference", (id) => { d.generation.reference_image_ids = [...d.generation.reference_image_ids, id]; draw(); })}
      <span class="meta">設定資料の生成の設定が、絵を作る依頼で読まれるかは、サーバーの処理の手順しだいです（V3点検の結果 3章：まだ作画に渡っていない）</span></section>
    <div class="acts"><button class="btn primary" ?disabled=${S.busy}>${icon("save")}残す</button>
      <button type="button" class="btn ghost" @click=${() => select(S.sel)}>直したのをやめる</button>
      <span class="grow"></span>
      <button type="button" class="btn ghost sm" @click=${() => run("抜く", async () => { await op(S.workId, { type: "set_removed", target_kind: "material_entry", id: S.sel, removed: true }); S.sel = null; })}>${icon("trash-2")}抜く</button></div>
  </form>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || "作品を選んでください", S.why ? "need" : ""), main); return; }
  render(html`${sideList()}<div class="col">${detail()}</div>`, main);
  loadThumbs(main);
}

await startShell({ screen: "materials", onWork: loadWork });
