// 画面どうしを行き来する帯（V3の全部の画面で共通）。
// 使い方：<nav class="v3-nav" data-v3-nav="<この画面の id>"></nav> と
//         <link rel="stylesheet" href="…/common/nav.css"> と <script type="module" src="…/common/nav.js"></script> を置く。
// 読み込まれると [data-v3-nav] の全部にリンクを入れる。リンクの先は v3/web からの相対で決める（このファイルの場所から求める）。
// 選んでいる作品は ?work=<id> で次の画面へ渡し、localStorage の v3.work にも残す（読めない環境では URL だけ）。
import { t, LANGS, lang, setLang } from "./i18n.js";

const ROOT = new URL("../", import.meta.url);
const WORK_KEY = "v3.work";

// 並びは工程の順（企画→構成→設定資料→工程の進み→原稿→画像生成→翻訳→確認→書き出し）。そのあとに作品をまたぐもの
export const SCREENS = [
  { id: "works", label: t("作品と話"), href: "works/", icon: "library" },
  { id: "plan", label: t("企画"), href: "plan/", icon: "file-text" },
  { id: "structure", label: t("構成"), href: "structure/", icon: "layout-grid" },
  { id: "materials", label: t("設定資料"), href: "materials/", icon: "contact" },
  { id: "harness", label: t("工程"), href: "harness/", icon: "workflow" },
  { id: "manuscript", label: t("原稿"), href: "manuscript/", icon: "book-open" },
  { id: "workbench", label: t("画像生成"), href: "index.html", icon: "sparkles" },
  { id: "translation", label: t("翻訳"), href: "translation/", icon: "languages" },
  { id: "review", label: t("確認"), href: "review/", icon: "badge-check" },
  { id: "export", label: t("書き出し"), href: "export/", icon: "download" },
  { id: "import", label: t("取り込み"), href: "import/", icon: "upload" },
  { id: "services", label: t("生成サービス"), href: "services/", icon: "server" },
];

export function storedWork() {
  const fromUrl = new URLSearchParams(location.search).get("work");
  if (fromUrl) return fromUrl;
  try { return localStorage.getItem(WORK_KEY) || ""; } catch { return ""; }
}
export function rememberWork(id) {
  try { if (id) localStorage.setItem(WORK_KEY, id); else localStorage.removeItem(WORK_KEY); } catch { /* 残せない環境では URL だけで渡す */ }
  const u = new URL(location.href);
  if (id) u.searchParams.set("work", id); else u.searchParams.delete("work");
  history.replaceState(null, "", u);
  for (const nav of document.querySelectorAll("[data-v3-nav]")) fill(nav);
}

export function screenHref(id, workId = storedWork()) {
  const s = SCREENS.find((x) => x.id === id);
  const u = new URL(s.href, ROOT);
  if (workId) u.searchParams.set("work", workId);
  return u.href;
}

function fill(nav) {
  const here = nav.dataset.v3Nav;
  nav.setAttribute("aria-label", t("画面"));
  nav.replaceChildren(...SCREENS.map((s) => {
    const a = document.createElement("a");
    a.className = "v3-nav-a";
    a.href = screenHref(s.id);
    a.dataset.screen = s.id;
    if (s.id === here) a.setAttribute("aria-current", "page");
    const i = document.createElement("i");
    i.dataset.lucide = s.icon;
    a.append(i, document.createTextNode(s.label));
    return a;
  }));
  nav.append(langSelect());
  if (tools) nav.append(tools(nav));
  // 印は lucide の絵に替える（lucide が読み込まれていない画面では文字だけ）
  if (window.lucide) {
    for (const i of nav.querySelectorAll("i[data-lucide]")) {
      const name = i.dataset.lucide.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase());
      const svg = window.lucide.createElement(window.lucide.icons[name]);
      svg.classList.add("lucide");
      i.replaceWith(svg);
    }
  }
}

// 画面の言語を選ぶ欄。辞書のある言語だけを出す（common/i18n.js の LANGS）。選ぶと読み込み直す
function langSelect() {
  const sel = document.createElement("select");
  sel.className = "v3-nav-lang";
  sel.setAttribute("aria-label", t("画面の言語"));
  for (const [code, name] of LANGS) sel.append(new Option(name, code, false, code === lang));
  sel.addEventListener("change", () => setLang(sel.value));
  return sel;
}

// 帯の右に置くボタン（絵だけ・全画面・キー）。common/keys.js の startKeys が入れる（キーを始めていない画面には出さない）
let tools = null;
export function setNavTools(make) {
  tools = make;
  for (const nav of document.querySelectorAll("[data-v3-nav]")) fill(nav);
}

for (const nav of document.querySelectorAll("[data-v3-nav]")) fill(nav);
