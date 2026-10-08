// 画面がキーと表示を始める1か所（V3細部の決めごと 22章）。画面ごとに1回 startKeys(画面の id) を呼ぶ。
// どの画面でも効くキー（キーの一覧・絵だけ・全画面・Tab・Esc・画面の切り替え）はここで結ぶ。
// 画面の操作（道具・取り消すなど）は、画面が keymap.js の bind で結ぶ。
import * as km from "./keymap.js";
import * as view from "./fullscreen.js";
import { toggleHelp } from "./help_overlay.js";
import { SCREENS, screenHref } from "./nav.js";

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
  await km.loadUserKeys();
}
