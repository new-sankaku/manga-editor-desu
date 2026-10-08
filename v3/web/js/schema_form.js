// 処理の引数の JSON Schema（generation_queue/image_process_registry.py の params_model）から入力欄を作る。
// 欄の形・初めの値・まとまりはサーバーの x- の印で決める。処理を足しても、この画面のコードは変えない。
//   x-group    まとまり（「基本」と、処理の open_groups にあるものは開いて出す。ほかは畳んで出す）
//   x-initial  初めの値
//   x-widget   textarea / number / slider / select / check
//   x-labels   選ぶ欄の見出し
//   x-unit     数の単位
//   x-presets  よく使う値のボタン（見出し → 値）
const BASIC = "基本";

function plain(prop) {
  // steps のように「空ならつなぎ先の設定」を許す欄は anyOf [型, null] で来る
  if (prop.anyOf) {
    const t = prop.anyOf.find((x) => x.type !== "null");
    return { ...prop, ...t, nullable: true };
  }
  return prop;
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids) if (k) e.append(k);
  return e;
}

function stepOf(p) {
  if (p.type === "integer") return 1;
  const span = (p.maximum ?? 1) - (p.minimum ?? 0);
  return span <= 2 ? 0.01 : 0.1;
}

export function renderForm(host, schema, initial, onChange, openGroups = []) {
  host.replaceChildren();
  const props = schema.properties || {};
  const values = {};
  const setters = {};
  const groups = new Map();

  for (const [name, raw] of Object.entries(props)) {
    const p = plain(raw);
    const g = p["x-group"] || BASIC;
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push([name, p]);
    const start = initial && name in initial ? initial[name] : ("x-initial" in p ? p["x-initial"] : p.default);
    values[name] = start === undefined ? null : start;
  }

  const changed = (name, v) => { values[name] = v; onChange && onChange(name, v, values); };

  // 「基本」を先に出し、ほかは引数に出てきた順
  const ordered = [...groups].sort((a, b) => (a[0] === BASIC ? -1 : b[0] === BASIC ? 1 : 0));
  for (const [g, items] of ordered) {
    const kv = el("div", { class: "kv" });
    for (const [name, p] of items) {
      const id = `f-${name}`;
      const widget = p["x-widget"] || (p.enum ? "select" : p.type === "boolean" ? "check" : p.type === "string" ? "text" : "number");
      const label = el("label", { class: "k", for: id, text: p.title || name });
      let row;
      if (widget === "textarea") {
        const t = el("textarea", { class: "field", id, rows: 3, "data-name": name });
        t.value = values[name] ?? "";
        t.addEventListener("input", () => changed(name, t.value));
        setters[name] = (v) => { t.value = v ?? ""; };
        row = el("div", { class: "full" }, el("label", { class: "lbl", for: id, text: p.title || name }), t);
        kv.append(row);
        continue;
      }
      const v = el("div", { class: "v" });
      if (widget === "select") {
        const s = el("select", { class: "field", id, "data-name": name });
        for (const opt of p.enum) s.append(el("option", { value: opt, text: (p["x-labels"] || {})[opt] || opt }));
        s.value = values[name];
        s.addEventListener("change", () => changed(name, s.value));
        setters[name] = (x) => { s.value = x; };
        v.append(s);
      } else if (widget === "check") {
        const b = el("button", { class: "sw", id, role: "switch", type: "button", "data-name": name,
                                 "aria-checked": String(!!values[name]) });
        b.addEventListener("click", () => {
          const on = b.getAttribute("aria-checked") !== "true";
          b.setAttribute("aria-checked", String(on));
          changed(name, on);
        });
        setters[name] = (x) => b.setAttribute("aria-checked", String(!!x));
        v.append(b);
      } else if (widget === "slider") {
        const r = el("input", { type: "range", id, min: p.minimum ?? 0, max: p.maximum ?? 1, step: stepOf(p), "data-name": name });
        const out = el("span", { class: "val num" });
        const show = () => { out.textContent = Number(r.value).toFixed(stepOf(p) < 1 ? 2 : 0); };
        r.value = values[name]; show();
        r.addEventListener("input", () => { show(); changed(name, Number(r.value)); });
        setters[name] = (x) => { r.value = x; show(); };
        v.append(r, out);
      } else if (widget === "text") {
        const t = el("input", { class: "field", id, "data-name": name });
        t.value = values[name] ?? "";
        t.addEventListener("input", () => changed(name, t.value));
        setters[name] = (x) => { t.value = x ?? ""; };
        v.append(t);
      } else {
        const n = el("input", { class: "field num", id, type: "number", step: stepOf(p), "data-name": name,
                                min: p.minimum, max: p.maximum,
                                placeholder: p.nullable ? "つなぎ先の設定" : undefined });
        n.value = values[name] ?? "";
        n.addEventListener("input", () => {
          if (n.value === "") changed(name, p.nullable ? null : values[name]);
          else changed(name, p.type === "integer" ? parseInt(n.value, 10) : Number(n.value));
        });
        setters[name] = (x) => { n.value = x ?? ""; };
        v.append(n);
        if (p["x-unit"]) v.append(el("span", { class: "unit", text: p["x-unit"] }));
      }
      kv.append(label, v);
      if (p["x-presets"]) {
        const chips = el("div", { class: "chips" });
        for (const [k, x] of Object.entries(p["x-presets"])) {
          const c = el("button", { class: "chip", type: "button", text: k, "data-preset": name });
          c.addEventListener("click", () => { setters[name](x); changed(name, x); });
          chips.append(c);
        }
        kv.append(el("span"), el("div", { class: "v" }, chips));
      }
    }
    if (g === BASIC) host.append(kv);
    else {
      const d = el("details", { class: "more", open: openGroups.includes(g) },
                   el("summary", {}, chevron(), document.createTextNode(g)), kv);
      host.append(d);
    }
  }

  return {
    values: () => ({ ...values }),
    set(name, v) { if (name in setters) { setters[name](v); values[name] = v; } },
    has: (name) => name in props,
  };
}

function chevron() {
  const i = document.createElement("i");
  i.setAttribute("data-lucide", "chevron-right");
  return i;
}
