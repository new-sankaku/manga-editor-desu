// 原稿のデータとしての色。新しく作るフキダシ・コマの枠・トーンに入れる色で、書き出し（PNG・PDF・PSD）にそのまま入る。
// 画面の色の組（common/theme.css）ではない。色の組を替えても刷る色は変わらないよう、ここに分けて置く。
// 画面に塗る色は theme_colors.js から読む。
export const PRINT_INK = "#000000"; // 刷る黒（線・文字・トーン）
export const PRINT_PAPER = "#FFFFFF"; // 紙の白（フキダシの塗り・コマの地）
