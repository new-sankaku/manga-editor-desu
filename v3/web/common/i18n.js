// 画面の文言を言語ごとに出す1か所（llm_doc/V3細部の決めごと.md 24章）。部品は i18next（vendor/i18next-26.4.2。MIT）。
// - 文言は日本語のまま書いて t("保存") のように包む。日本語は辞書を持たず、書いた文言がそのまま出る
// - ほかの言語の辞書は i18n/<言語>.js（中身は i18n/<言語>/<画面のまとまり>.js）。選べる言語は LANGS だけで、辞書の無い言語は出さない
// - 値を入れるときは t("{{n}}ページ", { n })。数で形が変わる文言は count で渡す（辞書に _one・_other などを書く）
// - t() の1つ目は、文字列をそのまま書く（変数や式を渡さない）。表から引く文言は、表を作る所で1つずつ t() に包む
// - 辞書に無い文言は、黙って日本語で出さない。頭に ⚠ を付けて出し、console.error に出す。抜けは test/i18n_check.mjs で止める
// - HTML に直接書いた文言は、要素に data-i18n（中の文字）か data-i18n-attr="title aria-label"（属性）を付ける
// - 言語は選んだときに読み込み直して替える（?ui=en でも開ける。?lang= と v3.lang は翻訳の画面の「訳す言語」なので使わない）。選んでいなければ日本語
import i18next from "../vendor/i18next-26.4.2/i18next.js";

export const LANGS = [["ja", "日本語"], ["en", "English"]];  // i18n:data（言語の名前は、その言語のまま出す）
const LANG_KEY = "v3.ui_lang";

function chosenLang() {
  if (typeof location === "undefined") return "ja";  // 画面の無い所（Node の試験が計算のモジュールを読むとき）は、書いた文言のまま
  let v = new URLSearchParams(location.search).get("ui") || "";
  if (!v) { try { v = localStorage.getItem(LANG_KEY) || ""; } catch { /* 残せない環境では URL の ui だけ */ } }
  return LANGS.some(([k]) => k === v) ? v : "ja";
}
export const lang = chosenLang();
export function setLang(code) {
  try { localStorage.setItem(LANG_KEY, code); } catch { /* 残せない環境では URL で渡す */ }
  const u = new URL(location.href);
  u.searchParams.set("ui", code);
  location.replace(u);
}

const dict = lang === "ja" ? {} : (await import(`../i18n/${lang}.js`)).default;
i18next.init({
  lng: lang, resources: { [lang]: { translation: dict } }, initAsync: false, showSupportNotice: false,
  keySeparator: false, nsSeparator: false, interpolation: { escapeValue: false },
});

const missing = new Set();
export function t(key, opts) {
  if (lang === "ja" || i18next.exists(key, opts)) return i18next.t(key, opts);
  if (!missing.has(key)) { missing.add(key); console.error(`i18n: ${lang} の辞書に無い文言：${key}`); }
  return `⚠ ${i18next.t(key, opts)}`;
}

// HTML に直接書いた文言を替える（日本語のときは何もしない）
const squash = (s) => s.replace(/\s+/g, " ").trim();
export function localizeStatic(root = document) {
  if (lang === "ja") return;
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(squash(el.textContent));
  for (const el of root.querySelectorAll("[data-i18n-attr]")) {
    for (const a of el.dataset.i18nAttr.split(/\s+/).filter(Boolean)) el.setAttribute(a, t(squash(el.getAttribute(a))));
  }
}
if (typeof document !== "undefined") { document.documentElement.lang = lang; localizeStatic(); }
