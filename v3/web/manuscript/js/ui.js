// 画面の部品を作る小さな道具（画像生成の画面 js/app.js と同じ形・同じ言い方）
import * as api from "../../js/api.js";
import { PRINT_INK } from "./print_colors.js";

export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];

export function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "value") e.value = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k);
  return e;
}

let iconT = 0;
export function icons() {
  cancelAnimationFrame(iconT);
  iconT = requestAnimationFrame(() => window.lucide.createIcons({ attrs: { class: "lucide" } }));
}

export function note(text, kind = "", icon = kind === "bad" ? "circle-alert" : kind === "need" ? "triangle-alert" : "info") {
  const n = h("div", { class: `note ${kind}` }, icon ? h("i", { "data-lucide": icon }) : null, h("span", { text }));
  icons();
  return n;
}

export function toast(msg, kind = "") {
  const t = $("#toast");
  t.replaceChildren(note(msg, kind));
  clearTimeout(toast.h);
  toast.h = setTimeout(() => t.replaceChildren(), kind === "bad" ? 9000 : 4000);
}

// what：何をしようとして失敗したか。理由と一緒に出す
export function fail(e, what = "") {
  console.error(e);
  toast(what ? `${what}できませんでした：${api.errorText(e)}` : api.errorText(e), "bad");
}

// 押した方だけ aria-pressed を true にする並び
export function seg(items, current, onPick, label) {
  return h("div", { class: "seg", role: "group", "aria-label": label },
    items.map(([v, text, icon, disabled]) => h("button", {
      "aria-pressed": String(v === current), "data-v": v, disabled: !!disabled, title: disabled || null,
      onclick: () => onPick(v),
    }, icon ? h("i", { "data-lucide": icon }) : null, text)));
}

// 数の欄。確定（change）したときだけ onSet を呼ぶ（打っている途中では送らない）
export function num(value, onSet, { min, max, step = "any", unit, label, disabled } = {}) {
  const i = h("input", { class: "field num", type: "number", min, max, step, value: value ?? "", "aria-label": label, disabled });
  i.addEventListener("change", () => {
    if (i.value === "") return;
    const v = Number(i.value);
    if (!Number.isFinite(v)) return;
    onSet(v);
  });
  return unit ? h("span", { class: "row" }, i, h("span", { class: "unit", text: unit })) : i;
}

export function color(value, onSet, label) {
  const i = h("input", { class: "swatch", type: "color", value: value || PRINT_INK, "aria-label": label });
  i.addEventListener("change", () => onSet(i.value.toUpperCase()));
  return i;
}

export function range(value, onInput, onSet, { min = 0, max = 1, step = 0.01, label } = {}) {
  const v = h("span", { class: "val num", text: `${Math.round(value * 100)}%` });
  const i = h("input", { type: "range", min, max, step, value, "aria-label": label, class: "grow" });
  i.addEventListener("input", () => { v.textContent = `${Math.round(Number(i.value) * 100)}%`; onInput && onInput(Number(i.value)); });
  i.addEventListener("change", () => onSet(Number(i.value)));
  return h("span", { class: "row grow" }, i, v);
}

export function kv(...pairs) {
  const out = h("div", { class: "kv" });
  for (const [k, v] of pairs) {
    if (k === null) { out.append(h("div", { class: "full" }, v)); continue; }
    out.append(h("span", { class: "k", text: k }), h("div", { class: "v" }, v));
  }
  return out;
}

export function sec(label, ...kids) {
  return h("div", { class: "sec" }, h("div", { class: "sec-h" }, h("span", { class: "lbl", text: label })), ...kids);
}

export function flag(text, kind = "mut", title) { return h("span", { class: `flag ${kind}`, text, title }); }
