// 英語の辞書。画面のまとまりごとのファイルを1つにまとめる（同じ文言は同じ訳にする。違いは test/i18n_check.mjs が止める）
import common from "./en/common.js";
import harness from "./en/harness.js";
import imagegen from "./en/imagegen.js";
import manuscript from "./en/manuscript.js";
import planning from "./en/planning.js";
import production from "./en/production.js";

export default { ...common, ...harness, ...imagegen, ...manuscript, ...planning, ...production };
