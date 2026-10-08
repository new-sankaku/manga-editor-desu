// V3 の全部の画面のキーの一覧（V3細部の決めごと 22章）。キーの初めの割り当ては、ここ1か所に書く。
// 画面は keymap.js の bind(id, 処理) で、ここの id に処理を結ぶ。結んでいない物は、その画面では効かない（一覧にも出ない）。
// キーを変える画面（key_settings.js）は、ここの全部を出す。重なりの確かめも、ここの全部で行う。
//
// 1つの項目：
//   id：操作の名前（画面の名前.操作）。利用者が変えたキーはこの id で残す
//   scope：効く所。"global"（どの画面でも）・画面の id（nav.js の SCREENS）・"画面の id:道具"（その道具を選んでいる間）
//   label：すること（キーの一覧と設定に出す）
//   keys：初めのキー。tinykeys の書き方（"$mod+z" の $mod は Windows・Linux で Ctrl、Mac で Cmd。"g 1" は G のあと 1）
//   where："input" は文字を打つ欄の中だけで効く。"any" は欄の中でも外でも効く。書かないときは欄の外だけ
//   chain：true は、同じキーの物を「道具 → 画面 → どの画面でも」の順に試し、処理が false を返したら次へ回す
//          （Esc・Tab など）。chain どうしは重なりとして出さない
//   hold：true は、押している間だけ効く（離すと戻る）。Space で手のひら、Alt でスポイトなど
//   current：今のアプリ（js/shortcut.js）での割り当て。「今のアプリのキーを読み込む」で使う。違わない物は書かない

export const SCOPES = {
  global: "どの画面でも",
  works: "作品と話", plan: "企画", structure: "構成", materials: "設定資料", harness: "工程", manuscript: "原稿",
  workbench: "画像生成", "workbench:mask": "画像生成・囲んで頼む",
  translation: "翻訳", review: "確認", export: "書き出し", import: "取り込み", services: "生成サービス",
};

export const KEYS = [
  // ---------------------------------------------------------------- どの画面でも
  { id: "view.help", scope: "global", label: "キーの一覧", keys: ["Shift+?"], current: ["F1"] },
  { id: "view.focus", scope: "global", label: "絵だけにする（パネルを隠す）・戻す", keys: ["Shift+F"] },
  { id: "view.fullscreen", scope: "global", label: "全画面にする・戻す", keys: ["$mod+Shift+F"] },
  { id: "view.peek", scope: "global", label: "絵だけのとき、パネルを出す・隠す", keys: ["Tab"], chain: true },
  { id: "view.exit", scope: "global", label: "絵だけ・全画面から抜ける（順に1つずつ）", keys: ["Escape"], chain: true },
  { id: "input.leave", scope: "global", label: "入力の欄から出る", keys: ["Escape"], where: "input", chain: true },
  { id: "edit.undo", scope: "global", label: "取り消す", keys: ["$mod+z"] },
  { id: "edit.redo", scope: "global", label: "やり直す", keys: ["$mod+Shift+z", "$mod+y"] },
  { id: "save.state", scope: "global", label: "保存の具合を見る", keys: ["$mod+s"] },
  { id: "search.focus", scope: "global", label: "探す欄に入る", keys: ["/"] },
  { id: "go.plan", scope: "global", label: "企画へ", keys: ["g 1"] },
  { id: "go.structure", scope: "global", label: "構成へ", keys: ["g 2"] },
  { id: "go.materials", scope: "global", label: "設定資料へ", keys: ["g 3"] },
  { id: "go.manuscript", scope: "global", label: "原稿へ", keys: ["g 4"] },
  { id: "go.export", scope: "global", label: "書き出しへ", keys: ["g 5"] },
  { id: "go.services", scope: "global", label: "生成サービスへ", keys: ["g 6"] },
  { id: "go.harness", scope: "global", label: "工程へ", keys: ["g 7"] },
  { id: "go.workbench", scope: "global", label: "画像生成へ", keys: ["g 8"] },
  { id: "go.translation", scope: "global", label: "翻訳へ", keys: ["g 9"] },
  { id: "go.review", scope: "global", label: "確認へ", keys: ["g 0"] },
  { id: "go.works", scope: "global", label: "作品と話へ", keys: ["g w"] },
  { id: "go.import", scope: "global", label: "取り込みへ", keys: [] },

  // ---------------------------------------------------------------- 画像生成
  { id: "workbench.select", scope: "workbench", label: "見る（動かす）", keys: ["v", "h"] },
  { id: "workbench.mask", scope: "workbench", label: "囲んで頼む", keys: ["l"] },
  { id: "workbench.extend", scope: "workbench", label: "描き足す", keys: [] },
  { id: "workbench.pen", scope: "workbench", label: "ペン", keys: ["b"] },
  { id: "workbench.erase", scope: "workbench", label: "消しゴム", keys: ["e"] },
  { id: "workbench.zoomIn", scope: "workbench", label: "広げる", keys: ["+", "Shift++", "="], current: ["$mod+8"] },
  { id: "workbench.zoomOut", scope: "workbench", label: "縮める", keys: ["-"], current: ["$mod+9"] },
  { id: "workbench.zoomFit", scope: "workbench", label: "合わせる", keys: [], current: ["$mod+0"] },
  { id: "workbench.generate", scope: "workbench", label: "頼む", keys: ["$mod+Enter"], where: "any" },
  { id: "workbench.pan", scope: "workbench", label: "押している間、手のひら（ドラッグで動かす）", keys: ["Space"], hold: true },
  { id: "workbench.compareClose", scope: "workbench", label: "比べるを閉じる", keys: ["Escape"], chain: true },
  { id: "workbench.polyClose", scope: "workbench:mask", label: "多角形を閉じる", keys: ["Enter"], chain: true },
  { id: "workbench.polyCancel", scope: "workbench:mask", label: "多角形をやめる", keys: ["Escape"], chain: true },

  // ---------------------------------------------------------------- 確認
  { id: "review.left", scope: "review", label: "読み通すとき、左のページへ（右から左の作品では次）", keys: ["ArrowLeft"], chain: true },
  { id: "review.right", scope: "review", label: "読み通すとき、右のページへ（右から左の作品では前）", keys: ["ArrowRight"], chain: true },
  { id: "review.next", scope: "review", label: "読み通すとき、次のページ", keys: ["PageDown"], chain: true },
  { id: "review.prev", scope: "review", label: "読み通すとき、前のページ", keys: ["PageUp"], chain: true },
  { id: "review.read", scope: "review", label: "読み通す（ページを大きく1枚ずつ）", keys: ["r"] },

  // ---------------------------------------------------------------- 原稿（22.2。処理は原稿の画面が結ぶ）
  { id: "manuscript.nextDecision", scope: "manuscript", label: "次の判断", keys: ["j"] },
  { id: "manuscript.prevDecision", scope: "manuscript", label: "前の判断", keys: ["k"] },
  { id: "manuscript.adopt", scope: "manuscript", label: "採用", keys: ["a"] },
  { id: "manuscript.reject", scope: "manuscript", label: "却下・このまま", keys: ["x"] },
  { id: "manuscript.pick", scope: "manuscript", label: "候補を選ぶ・赤入れの選択肢を選ぶ（1〜6）", keys: ["1", "2", "3", "4", "5", "6"] },
  { id: "manuscript.instruct", scope: "manuscript", label: "指示の欄に入る", keys: ["i"] },
  { id: "manuscript.ask", scope: "manuscript", label: "頼む（指示の欄の中で）", keys: ["$mod+Enter"], where: "any" },
  { id: "manuscript.select", scope: "manuscript", label: "選ぶ", keys: ["v"] },
  { id: "manuscript.mask", scope: "manuscript", label: "囲んで頼む", keys: ["l"] },
  { id: "manuscript.redline", scope: "manuscript", label: "赤入れ", keys: ["r"] },
  { id: "manuscript.pen", scope: "manuscript", label: "ペン", keys: ["b"] },
  { id: "manuscript.erase", scope: "manuscript", label: "消しゴム", keys: ["e"] },
  { id: "manuscript.text", scope: "manuscript", label: "文字", keys: ["t"] },
  { id: "manuscript.frame", scope: "manuscript", label: "コマ枠", keys: ["f"] },
  { id: "manuscript.balloon", scope: "manuscript", label: "フキダシ", keys: ["s"] },
  { id: "manuscript.knife", scope: "manuscript", label: "ナイフ", keys: ["c"] },
  { id: "manuscript.tone", scope: "manuscript", label: "トーン", keys: ["n"] },
  { id: "manuscript.shape", scope: "manuscript", label: "図形", keys: ["u"] },
  { id: "manuscript.hand", scope: "manuscript", label: "手のひら", keys: ["h"] },
  { id: "manuscript.order", scope: "manuscript", label: "読む順", keys: ["o"] },
  { id: "manuscript.side", scope: "manuscript", label: "右の欄を切り替える（判断・道具・層）", keys: ["d"] },
  { id: "manuscript.show", scope: "manuscript", label: "表示するもの", keys: ["w"] },
  { id: "manuscript.zoomIn", scope: "manuscript", label: "広げる", keys: ["+", "Shift++", "="], current: ["$mod+8"] },
  { id: "manuscript.zoomOut", scope: "manuscript", label: "縮める", keys: ["-"], current: ["$mod+9"] },
  { id: "manuscript.zoomFit", scope: "manuscript", label: "合わせる", keys: [], current: ["$mod+0"] },
  { id: "manuscript.prevSpread", scope: "manuscript", label: "前の見開き", keys: ["PageUp"], current: ["Alt+ArrowLeft"] },
  { id: "manuscript.nextSpread", scope: "manuscript", label: "次の見開き", keys: ["PageDown"], current: ["Alt+ArrowRight"] },
  { id: "manuscript.queue", scope: "manuscript", label: "待ち行列", keys: ["q"] },
  { id: "manuscript.pan", scope: "manuscript", label: "押している間、手のひら", keys: ["Space"], hold: true },
  { id: "manuscript.eyedropper", scope: "manuscript", label: "押している間、スポイト（ペン・消しゴムの間）", keys: ["Alt"], hold: true },
];

// 今のアプリ（js/shortcut.js）にあって、V3 では別の操作に分けた・無くした物（読み込みの画面で知らせる）
export const CURRENT_APP_NOT_MAPPED = [
  "Ctrl+G（グリッド）・Ctrl+L（層の欄）・Ctrl+K（操作の欄）・Ctrl+B（下の帯）：V3 には同じ欄が無い",
  "Ctrl+C・Ctrl+V・Delete・矢印（物を動かす）：原稿の画面が自分で受ける（ブラウザの写し・貼り付けと同じ）",
  "Ctrl+O（読み込み）・Ctrl+D（絵を保存）・Ctrl+Shift+S（設定を保存）・Ctrl+P（プロンプト）・Alt+N（ページを足す）：V3 では取り込み・書き出し・生成サービスの画面のボタン",
];
