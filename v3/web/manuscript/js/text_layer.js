// 文字を原稿の上に出す所（HTML の要素。fabric の文字は縦書きを持たないため）。
// 画面の組み方はブラウザの縦書き（CSS の writing-mode）に、正本の組版（Typesetting）を次のように写して見せる：
//   行間 line_spacing_ratio → line-height、改行 none／character／phrase → white-space・line-break: strict・
//   word-break: auto-phrase、縦中横 → text-combine-upright、揃え → text-align。
// 書き出しの組み方はサーバー（v3/psd_writer/text_layout.js：HarfBuzz・UAX #14・BudouX）で、画面とは別の実装。
// 2つが同じ所で改行するかは未検証。入りきるかの最後の判断は、入稿前の確かめ（サーバーの組版で測る）に任せる。
import { PT_MM } from "./geometry.js";

// 要素の中の 1mm の大きさ（CSS の px）。文字が小さすぎてブラウザに丸められないように、mm を K 倍して置く
export const K = 10;

const cps = (s) => Array.from(s);

// 文字の飾り・一部の書式・ルビ・縦中横を当てた要素を作る
function richNodes(t, ts) {
  const chars = cps(t.text || "");
  const cuts = new Set([0, chars.length]);
  for (const r of [...(t.ruby || []), ...(t.spans || [])]) { cuts.add(r.start); cuts.add(r.end); }
  const order = [...cuts].filter((c) => c >= 0 && c <= chars.length).sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i + 1 < order.length; i++) {
    const s = order[i], e = order[i + 1];
    const seg = chars.slice(s, e).join("");
    const span = document.createElement("span");
    for (const sp of t.spans || []) {
      if (s >= sp.start && e <= sp.end) {
        if (sp.size_ratio) span.style.fontSize = `${sp.size_ratio}em`;
        if (sp.color) span.style.color = sp.color;
        if (sp.embolden_ratio) span.style.webkitTextStroke = `${sp.embolden_ratio}em currentColor`;
        if (sp.font_family) span.style.fontFamily = `"${sp.font_family}"`;
      }
    }
    span.append(...tcyNodes(seg, ts, t.writing_direction === "vertical"));
    const ruby = (t.ruby || []).find((r) => r.start === s && r.end === e);
    if (ruby) {
      const rb = document.createElement("ruby");
      const rt = document.createElement("rt");
      rt.textContent = ruby.text;
      rb.append(span, rt);
      out.push(rb);
    } else out.push(span);
  }
  return out;
}

// 縦中横：半角の数字が tate_chu_yoko_max_digits 字以下で続く所と、「!?」など2字の感嘆符・疑問符
function tcyNodes(seg, ts, vertical) {
  if (!vertical || !ts) return [seg];
  const parts = [];
  const max = ts.tate_chu_yoko_max_digits || 0;
  const re = new RegExp(`${max > 0 ? `(?<![0-9])[0-9]{1,${max}}(?![0-9])` : "(?!)"}${ts.tate_chu_yoko_marks ? "|[!?！？]{2}" : ""}`, "g");
  let last = 0;
  for (const m of seg.matchAll(re)) {
    if (m.index > last) parts.push(seg.slice(last, m.index));
    const s = document.createElement("span");
    s.className = "tcy";
    s.textContent = m[0];
    parts.push(s);
    last = m.index + m[0].length;
  }
  if (last < seg.length) parts.push(seg.slice(last));
  return parts;
}

export class TextLayer {
  constructor(host, hooks) {
    this.el = document.createElement("div");
    this.el.className = "tx-layer paper"; // 紙の上の文字：色は紙の組（common/theme.css の .paper）
    host.append(this.el);
    this.hooks = hooks;
    this.nodes = new Map();
    this.editing = null;
  }

  // 置き場の変換（fabric の viewportTransform と同じ並び）
  setViewport(v) {
    this.el.style.transform = `matrix(${v[0] / K},0,0,${v[3] / K},${v[4]},${v[5]})`;
    this.el.style.setProperty("--inv", String(K / v[0]));
  }

  clear() { if (this.editing) this.finishEdit(); this.el.replaceChildren(); this.nodes.clear(); }

  // t：文字の行。ox, oy：ページの基本枠の左上（mm）。ts：組版（無ければ null）。font：書体の名前（無ければ null）
  put(t, ox, oy, ts, font, opts) {
    if (!t.box_mm) return;
    let n = this.nodes.get(t.id);
    if (!n) {
      n = document.createElement("div");
      n.className = "tx";
      n.dataset.id = t.id;
      n.inner = document.createElement("div");
      n.inner.className = "tx-in";
      n.append(n.inner);
      this.el.append(n);
      this.nodes.set(t.id, n);
    }
    n.dataset.ox = ox; n.dataset.oy = oy;
    this.place(n, t.box_mm, ox, oy);
    const vertical = t.writing_direction === "vertical";
    n.classList.toggle("v", vertical);
    n.classList.toggle("sfx", t.item_kind === "drawn_sfx");
    n.hidden = !opts.visible;
    const st = n.inner.style;
    st.fontSize = t.font_size_pt ? `${t.font_size_pt * PT_MM * K}px` : "";
    st.fontFamily = font ? `"${font}", serif` : "serif";
    st.lineHeight = ts ? String(1 + ts.line_spacing_ratio) : "";
    st.textAlign = ts ? (ts.align === "center" ? "center" : "start") : "";
    st.whiteSpace = ts && ts.line_break === "none" ? "pre" : "pre-wrap";
    st.wordBreak = ts && ts.line_break === "phrase" ? "auto-phrase" : "normal";
    st.opacity = String(t.opacity ?? 1);
    const deco = t.decoration || {};
    st.color = deco.fill || "";
    st.letterSpacing = deco.spacing_ratio ? `${deco.spacing_ratio}em` : "";
    if (deco.edge) {
      st.webkitTextStroke = `${deco.edge.ratio * 2}em ${deco.edge.color}`;
      st.paintOrder = "stroke fill";
    } else { st.webkitTextStroke = ""; st.paintOrder = ""; }
    n.classList.toggle("nofont", !font);
    n.classList.toggle("nots", !ts && t.item_kind !== "drawn_sfx");
    if (this.editing !== t.id) n.inner.replaceChildren(...richNodes(t, ts));
    n.title = [!font ? "書体が決まっていません（画面はこのブラウザの書体で見せています）" : "",
               !ts ? "組版が決まっていません" : ""].filter(Boolean).join("。");
    this.checkOverflow(n);
  }

  place(n, box, ox, oy) {
    n.style.left = `${(ox + box[0]) * K}px`;
    n.style.top = `${(oy + box[1]) * K}px`;
    n.style.width = `${(box[2] - box[0]) * K}px`;
    n.style.height = `${(box[3] - box[1]) * K}px`;
  }

  // 箱を動かしている間：要素だけを動かす（保存は離したとき）
  movePreview(id, box) {
    const n = this.nodes.get(id);
    if (n) this.place(n, box, Number(n.dataset.ox), Number(n.dataset.oy));
  }

  // 画面の組み方で箱に入りきらないか（目安。サーバーの組版とは違うことがある）
  checkOverflow(n) {
    const i = n.inner;
    const over = i.scrollHeight > n.clientHeight + 1 || i.scrollWidth > n.clientWidth + 1;
    n.classList.toggle("over", over);
  }

  // 人の手・判断待ちの印。x, y：原稿の mm。印の大きさは拡大しても変わらない（--inv で戻す）
  mark(key, x, y, kind, title, count) {
    const n = document.createElement("div");
    n.className = `mk mk-${kind}`;
    n.dataset.key = key;
    n.style.left = `${x * K}px`;
    n.style.top = `${y * K}px`;
    n.title = title;
    n.textContent = kind === "hand" ? "手" : `判断 ${count ?? ""}`.trim();
    this.el.append(n);
  }

  removeMissing(ids) { for (const [id, n] of this.nodes) if (!ids.has(id)) { n.remove(); this.nodes.delete(id); } }

  // その場で打つ。打っている間の見え方は、縦書きのまま（同じ要素を書き換えられるようにする）
  edit(t) {
    if (this.editing) this.finishEdit();
    const n = this.nodes.get(t.id);
    if (!n) return;
    this.editing = t.id;
    n.classList.add("editing");
    n.inner.replaceChildren(t.text || "");
    n.inner.setAttribute("contenteditable", "plaintext-only");
    n.inner.setAttribute("aria-label", "文字");
    n.inner.focus();
    const sel = getSelection();
    sel.selectAllChildren(n.inner);
    sel.collapseToEnd();
    n.inner.oninput = () => { this.checkOverflow(n); if (this.hooks.onEditing) this.hooks.onEditing(t.id, n.inner.innerText); };
    n.inner.onblur = () => this.finishEdit();
    n.inner.onkeydown = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); n.inner.blur(); } };
  }

  finishEdit() {
    const id = this.editing;
    if (!id) return;
    this.editing = null;
    const n = this.nodes.get(id);
    if (!n) return;
    n.classList.remove("editing");
    n.inner.removeAttribute("contenteditable");
    n.inner.onblur = null; n.inner.oninput = null; n.inner.onkeydown = null;
    const text = n.inner.innerText.replace(/\n$/, "");
    this.hooks.onEditDone(id, text);
  }
}
