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

import { t } from "./i18n.js";

export const SCOPES = {
  global: t("どの画面でも"),
  works: t("作品と話"), plan: t("企画"), structure: t("構成"), materials: t("設定資料"), harness: t("工程"), manuscript: t("原稿"),
  workbench: t("画像生成"), "workbench:mask": t("画像生成・囲んで頼む"),
  translation: t("翻訳"), review: t("確認"), export: t("書き出し"), import: t("取り込み"), services: t("生成サービス"),
};

export const KEYS = [
  // ---------------------------------------------------------------- どの画面でも
  { id: "view.help", scope: "global", label: t("キーの一覧"), keys: ["Shift+?"], current: ["F1"] },
  { id: "view.focus", scope: "global", label: t("絵だけにする（パネルを隠す）・戻す"), keys: ["Shift+F"] },
  { id: "view.fullscreen", scope: "global", label: t("全画面にする・戻す"), keys: ["$mod+Shift+F"] },
  { id: "view.peek", scope: "global", label: t("絵だけのとき、パネルを出す・隠す"), keys: ["Tab"], chain: true },
  { id: "view.exit", scope: "global", label: t("絵だけ・全画面から抜ける（順に1つずつ）"), keys: ["Escape"], chain: true },
  { id: "input.leave", scope: "global", label: t("入力の欄から出る"), keys: ["Escape"], where: "input", chain: true },
  { id: "edit.undo", scope: "global", label: t("取り消す"), keys: ["$mod+z"] },
  { id: "edit.redo", scope: "global", label: t("やり直す"), keys: ["$mod+Shift+z", "$mod+y"] },
  { id: "save.state", scope: "global", label: t("保存の具合を見る"), keys: ["$mod+s"] },
  { id: "search.focus", scope: "global", label: t("探す欄に入る"), keys: ["/"] },
  { id: "go.plan", scope: "global", label: t("企画へ"), keys: ["g 1"] },
  { id: "go.structure", scope: "global", label: t("構成へ"), keys: ["g 2"] },
  { id: "go.materials", scope: "global", label: t("設定資料へ"), keys: ["g 3"] },
  { id: "go.manuscript", scope: "global", label: t("原稿へ"), keys: ["g 4"] },
  { id: "go.export", scope: "global", label: t("書き出しへ"), keys: ["g 5"] },
  { id: "go.services", scope: "global", label: t("生成サービスへ"), keys: ["g 6"] },
  { id: "go.harness", scope: "global", label: t("工程へ"), keys: ["g 7"] },
  { id: "go.workbench", scope: "global", label: t("画像生成へ"), keys: ["g 8"] },
  { id: "go.translation", scope: "global", label: t("翻訳へ"), keys: ["g 9"] },
  { id: "go.review", scope: "global", label: t("確認へ"), keys: ["g 0"] },
  { id: "go.works", scope: "global", label: t("作品と話へ"), keys: ["g w"] },
  { id: "go.import", scope: "global", label: t("取り込みへ"), keys: [] },

  // ---------------------------------------------------------------- 画像生成
  { id: "workbench.select", scope: "workbench", label: t("見る（動かす）"), keys: ["v", "h"] },
  { id: "workbench.mask", scope: "workbench", label: t("囲んで頼む"), keys: ["l"] },
  { id: "workbench.extend", scope: "workbench", label: t("描き足す"), keys: [] },
  { id: "workbench.pen", scope: "workbench", label: t("ペン"), keys: ["b"] },
  { id: "workbench.erase", scope: "workbench", label: t("消しゴム"), keys: ["e"] },
  { id: "workbench.zoomIn", scope: "workbench", label: t("広げる"), keys: ["+", "Shift++", "="], current: ["$mod+8"] },
  { id: "workbench.zoomOut", scope: "workbench", label: t("縮める"), keys: ["-"], current: ["$mod+9"] },
  { id: "workbench.zoomFit", scope: "workbench", label: t("合わせる"), keys: [], current: ["$mod+0"] },
  { id: "workbench.generate", scope: "workbench", label: t("頼む"), keys: ["$mod+Enter"], where: "any" },
  { id: "workbench.pan", scope: "workbench", label: t("押している間、手のひら（ドラッグで動かす）"), keys: ["Space"], hold: true },
  { id: "workbench.compareClose", scope: "workbench", label: t("比べるを閉じる"), keys: ["Escape"], chain: true },
  { id: "workbench.polyClose", scope: "workbench:mask", label: t("多角形を閉じる"), keys: ["Enter"], chain: true },
  { id: "workbench.polyCancel", scope: "workbench:mask", label: t("多角形をやめる"), keys: ["Escape"], chain: true },

  // ---------------------------------------------------------------- 確認
  { id: "review.left", scope: "review", label: t("読み通すとき、左のページへ（右から左の作品では次）"), keys: ["ArrowLeft"], chain: true },
  { id: "review.right", scope: "review", label: t("読み通すとき、右のページへ（右から左の作品では前）"), keys: ["ArrowRight"], chain: true },
  { id: "review.next", scope: "review", label: t("読み通すとき、次のページ"), keys: ["PageDown"], chain: true },
  { id: "review.prev", scope: "review", label: t("読み通すとき、前のページ"), keys: ["PageUp"], chain: true },
  // 工程（harness）
  { id: "harness.fit", scope: "harness", label: t("図の全体を見る"), keys: ["0"] },
  { id: "harness.stageView", scope: "harness", label: t("工程の図へ戻る"), keys: [] },

  // ---------------------------------------------------------------- 原稿（22.2。処理は原稿の画面が結ぶ）
  { id: "manuscript.nextDecision", scope: "manuscript", label: t("次の判断"), keys: ["j"] },
  { id: "manuscript.prevDecision", scope: "manuscript", label: t("前の判断"), keys: ["k"] },
  { id: "manuscript.adopt", scope: "manuscript", label: t("採用"), keys: ["a"] },
  { id: "manuscript.reject", scope: "manuscript", label: t("却下・このまま"), keys: ["x"] },
  { id: "manuscript.pick", scope: "manuscript", label: t("候補を選ぶ・赤入れの選択肢を選ぶ（1〜6）"), keys: ["1", "2", "3", "4", "5", "6"] },
  { id: "manuscript.instruct", scope: "manuscript", label: t("指示の欄に入る"), keys: ["i"] },
  { id: "manuscript.ask", scope: "manuscript", label: t("頼む（指示の欄の中で）"), keys: ["$mod+Enter"], where: "any" },
  { id: "manuscript.select", scope: "manuscript", label: t("選ぶ"), keys: ["v"] },
  { id: "manuscript.mask", scope: "manuscript", label: t("選んだコマの絵を画像生成の画面で頼む（囲んで頼む）"), keys: ["l"] },
  { id: "manuscript.redline", scope: "manuscript", label: t("赤入れ"), keys: ["r"] },
  { id: "manuscript.pen", scope: "manuscript", label: t("ペン"), keys: ["b"] },
  { id: "manuscript.erase", scope: "manuscript", label: t("消しゴム"), keys: ["e"] },
  { id: "manuscript.text", scope: "manuscript", label: t("文字"), keys: ["t"] },
  { id: "manuscript.frame", scope: "manuscript", label: t("コマ枠"), keys: ["f"] },
  { id: "manuscript.balloon", scope: "manuscript", label: t("フキダシ"), keys: ["s"] },
  { id: "manuscript.knife", scope: "manuscript", label: t("ナイフ"), keys: ["c"] },
  { id: "manuscript.tone", scope: "manuscript", label: t("トーン"), keys: ["n"] },
  { id: "manuscript.shape", scope: "manuscript", label: t("図形"), keys: ["u"] },
  { id: "manuscript.hand", scope: "manuscript", label: t("手のひら"), keys: ["h"] },
  { id: "manuscript.order", scope: "manuscript", label: t("読む順"), keys: ["o"] },
  { id: "manuscript.side", scope: "manuscript", label: t("右のパネルを切り替える（判断・ツール・レイヤー）"), keys: ["d"] },
  { id: "manuscript.show", scope: "manuscript", label: t("表示するもの（レイヤーの欄）"), keys: ["w"] },
  { id: "manuscript.zoomIn", scope: "manuscript", label: t("広げる"), keys: ["+", "Shift++", "="], current: ["$mod+8"] },
  { id: "manuscript.zoomOut", scope: "manuscript", label: t("縮める"), keys: ["-"], current: ["$mod+9"] },
  { id: "manuscript.zoomFit", scope: "manuscript", label: t("合わせる"), keys: ["0"], current: ["$mod+0"] },
  { id: "manuscript.prevSpread", scope: "manuscript", label: t("前の見開き"), keys: ["PageUp"], current: ["Alt+ArrowLeft"] },
  { id: "manuscript.nextSpread", scope: "manuscript", label: t("次の見開き"), keys: ["PageDown"], current: ["Alt+ArrowRight"] },
  { id: "manuscript.queue", scope: "manuscript", label: t("キュー"), keys: ["q"] },
  { id: "manuscript.remove", scope: "manuscript", label: t("選んだ物を消す（取り消せます）"), keys: ["Delete", "Backspace"], current: ["Delete", "Backspace"] },
  { id: "manuscript.cancel", scope: "manuscript", label: t("打つ・選ぶ・コマの絵を動かすのをやめる"), keys: ["Escape"], chain: true },
  { id: "manuscript.pan", scope: "manuscript", label: t("押している間、手のひら"), keys: ["Space"], hold: true },
  { id: "manuscript.eyedropper", scope: "manuscript", label: t("押している間、スポイト（ペン・消しゴムの間）"), keys: ["Alt"], hold: true },
];

// 今のアプリ（js/shortcut.js）にあって、V3 では別の操作に分けた・無くした物（読み込みの画面で知らせる）
export const CURRENT_APP_NOT_MAPPED = [
  t("Ctrl+G（グリッド）・Ctrl+L（レイヤーの欄）・Ctrl+K（操作の欄）・Ctrl+B（下の帯）：V3 には同じ欄が無い"),
  t("Ctrl+C・Ctrl+V・Delete・矢印（物を動かす）：原稿の画面が自分で受ける（ブラウザの写し・貼り付けと同じ）"),
  t("Ctrl+O（読み込み）・Ctrl+D（絵を保存）・Ctrl+Shift+S（設定を保存）・Ctrl+P（プロンプト）・Alt+N（ページを足す）：V3 では取り込み・書き出し・生成サービスの画面のボタン"),
];
