// 項目の並び（spec）から入力欄を作り、入れた値を形のある値（入れ子の object）に戻す。
// spec の1つ：{ key: "safe_area.top_mm", label, type: "text"|"number"|"textarea"|"select"|"bool"|"color"|"lines", options?, step?, hint? }
// - 空の欄は null にする（既定の値で埋めない。サーバーが「決まっていない」と言えるように）
// - lines は1行1つの文字の並び
import { html, nothing } from "../vendor/lit-html-3.2.1/lit-html.js";

export function getPath(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
function setPath(obj, path, value) {
  const ks = path.split(".");
  let o = obj;
  for (const k of ks.slice(0, -1)) o = o[k] ??= {};
  o[ks.at(-1)] = value;
}

export function fieldsHtml(spec, values, prefix = "") {
  return spec.map((f) => {
    const name = prefix + f.key;
    const v = getPath(values || {}, f.key);
    const id = `f-${name.replace(/\./g, "-")}`;
    let input;
    if (f.type === "textarea" || f.type === "lines") {
      input = html`<textarea class="field" id=${id} name=${name} rows=${f.rows || 3}
        .value=${f.type === "lines" ? (v || []).join("\n") : (v ?? "")}></textarea>`;
    } else if (f.type === "select") {
      input = html`<select class="field" id=${id} name=${name}>
        <option value="" ?selected=${v == null}>（決めていない）</option>
        ${Object.entries(f.options).map(([k, l]) => html`<option value=${k} ?selected=${String(v) === k}>${l}</option>`)}</select>`;
    } else if (f.type === "bool") {
      input = html`<select class="field" id=${id} name=${name}>
        <option value="" ?selected=${v == null}>（決めていない）</option>
        <option value="true" ?selected=${v === true}>${f.yes || "はい"}</option>
        <option value="false" ?selected=${v === false}>${f.no || "いいえ"}</option></select>`;
    } else {
      input = html`<input class="field" id=${id} name=${name} type=${f.type === "number" ? "number" : "text"}
        step=${f.step || "any"} .value=${v == null ? "" : String(v)} placeholder=${f.placeholder || ""}>`;
    }
    return html`<label class="k" for=${id}>${f.label}</label><div class="v">${input}${f.hint ? html`<span class="meta">${f.hint}</span>` : nothing}</div>`;
  });
}

// 利用規約の要点（v3server/usage_terms_schema.py の UsageTerms。V3細部の決めごと 20章）。人が確かめて入れる
const YNU = { yes: "はい", no: "いいえ", unknown: "未確認" };
export const USAGE_TERMS = [
  { key: "commercial_use", label: "商用に使える", type: "select", options: YNU },
  { key: "rights_holder", label: "出力の権利", placeholder: "誰にあるか" },
  { key: "training_use", label: "学習に使われる", type: "select", options: YNU },
  { key: "credit_required", label: "クレジットが要る", type: "select", options: YNU },
  { key: "credit_text", label: "クレジットの文" },
  { key: "terms_url", label: "規約の URL" },
  { key: "terms_note", label: "規約のメモ", hint: "URL か、このメモのどちらかが要る" },
  { key: "checked_on", label: "確かめた日", placeholder: "2026-10-08" },
];

// form から spec の値を読む。どれも空なら null（その組を丸ごと決めていない）
export function readFields(form, spec, prefix = "") {
  const out = {};
  let any = false;
  for (const f of spec) {
    const raw = form.elements[prefix + f.key].value;
    let v;
    if (f.type === "lines") v = raw.split("\n").map((s) => s.trim()).filter(Boolean);
    else if (raw.trim() === "") v = null;
    else if (f.type === "number") v = Number(raw);
    else if (f.type === "bool") v = raw === "true";
    else if (f.type === "select" && f.numeric) v = Number(raw);
    else v = f.type === "textarea" ? raw : raw.trim();
    if (v !== null && !(Array.isArray(v) && !v.length)) any = true;
    setPath(out, f.key, v);
  }
  return any ? out : null;
}
