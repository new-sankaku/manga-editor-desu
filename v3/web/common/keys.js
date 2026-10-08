// 画面がキーと表示を始める1か所（V3細部の決めごと 22章）。画面ごとに1回 startKeys(画面の id) を呼ぶ。
// どの画面でも効くキー（キーの一覧・絵だけ・全画面・Tab・Esc・画面の切り替え）はここで結ぶ。
// 画面の操作（道具・取り消すなど）は、画面が keymap.js の bind で結ぶ。
import * as km from "./keymap.js";
import * as view from "./fullscreen.js";
import { toggleHelp } from "./help_overlay.js";
import { SCREENS, screenHref, setNavTools } from "./nav.js";

export { km, view };

export async function startKeys(screen) {
  km.start(screen);
  view.startView(screen);
  km.bind("view.help", () => toggleHelp());
  km.bind("view.focus", () => view.toggleFocus());
  km.bind("view.fullscreen", () => { view.toggleFullscreen().catch((e) => console.error("全画面にできませんでした", e)); });
  km.bind("view.peek", () => view.togglePeek());
  km.bind("view.exit", () => view.exitOne());
  km.bind("input.leave", (e) => { e.target.blur(); });
  for (const s of SCREENS) {
    km.bind(`go.${s.id}`, () => {
      if (s.id === screen) return false;
      location.href = screenHref(s.id);
    });
  }
  setNavTools(navTools);
  await km.loadUserKeys();
}

// 帯の右のボタン。キーと同じ処理を呼ぶ（view.* と key_settings.js）
function navTools() {
  const box = document.createElement("span");
  box.className = "v3-nav-tools";
  const b = (id, icon, text, key, fn) => {
    const el = document.createElement("button");
    el.type = "button"; el.className = "v3-nav-b"; el.id = id; el.title = text;
    if (key) el.dataset.key = key;
    const i = document.createElement("i"); i.dataset.lucide = icon;
    el.append(i, document.createTextNode(text), document.createElement("kbd"));
    el.addEventListener("click", fn);
    return el;
  };
  box.append(
    b("v3-focus", "maximize", "絵だけ", "view.focus", () => view.toggleFocus()),
    b("v3-fullscreen", "fullscreen", "全画面", "view.fullscreen", () => { view.toggleFullscreen().catch((e) => console.error("全画面にできませんでした", e)); }),
    b("v3-keys", "keyboard", "キー", null, () => import("./key_settings.js").then((m) => m.openKeySettings())));
  queueMicrotask(() => km.applyHints(box));
  return box;
}
