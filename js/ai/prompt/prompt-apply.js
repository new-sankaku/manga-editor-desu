// 生成したプロンプトをコマ（isPanel）へ書き込む側と、全ページを順に開く送り。
// LLM呼び出しはllm/llm-story-service.js、画面はllm/llm-story-ui.jsが持つ

const STORY_SCOPE_SELECTED="selected";
const STORY_SCOPE_PAGE="page";
const STORY_SCOPE_ALL_PAGES="allPages";

function storyGetScope() {
return getSelectedValueByGroup("storyApplyScope");
}

// 対象のコマを読み順で返す。ロック（selectable=false）は除外しない。
// ひな形が作るコマは既定でロック状態のため、除外すると大半が対象外になる
function storyCollectPanels(scope,rightToLeft) {
const panels=scope===STORY_SCOPE_SELECTED
?(canvas.getActiveObjects()||[]).filter(isPanel)
:(getPanelObjectList()||[]);
if (panels.length===0) {
return[];
}
return sortPanelsInReadingOrder(panels,rightToLeft);
}

// 漫画らしさ（トーン・線）はLLMに毎回書かせると揺れるので、書き込む側で決め打つ。
// 何を足すかはユーザーが選ぶ。既定は「足さない」
const MANGA_STYLE_SUFFIX={
none: "",
screentone: "greyscale, monochrome, manga, screentone, halftone, high contrast",
lineart: "greyscale, monochrome, lineart, hatching, sketch, high contrast"
};

function getMangaStyleSuffix() {
return MANGA_STYLE_SUFFIX[$("storyArtStyle").value];
}

// 画風タグは追記のたびに重なるため、すでに入っているものは足さない。
// 既存の文面そのものには手を触れない
function appendMangaStyleSuffix(prompt) {
const suffix=getMangaStyleSuffix();
if (!suffix) {
return prompt;
}
const missing=suffix.split(",").map(function (tag) {
return tag.trim();
}).filter(function (tag) {
return tag&&!promptHasTag(prompt,tag);
});
return missing.length>0?prompt+", "+missing.join(", "):prompt;
}

// 追記は末尾のカンマを均してから繋ぐ。既存が空なら区切りを付けない。
// role: コマの役割。構図タグ（panel-composition.js）をここで足す。画風タグと同じく
// LLMには書かせず書き込み側で決め打つ。学習データの偏りを埋めるのが目的なので、
// 毎回同じ強さで入っていないと意味がないため
function promptApplyToPanel(panel,tags,append,role) {
const value=(tags||"").trim();
if (!value) {
return false;
}
// 前回この仕組みが足した構図タグを先に外す。役割が変わって作り直したときに
// 前の役割のタグが残り続けるのを防ぐ。ユーザーが手で書いたタグには触らない
const added=panel.text2img_composition||{positive: "",negative: ""};
const current=compositionStrip(panel.text2img_prompt,added.positive);
const merged=appendMangaStyleSuffix((append&&current)?current+", "+value:value);

const composition=panelCompositionForRole(role);
const addPositive=compositionMissingTags(merged,composition.positive,"");
panel.text2img_prompt=compositionJoin(merged,addPositive);

// ネガティブはLLMが作らないので置き換える相手がいない。手書きのネガティブを
// 消さないよう常に足す側に回る。ポジティブに入っているタグは打ち消し合うので外す
const currentNegative=compositionStrip(panel.text2img_negative,added.negative);
const addNegative=compositionMissingTags(currentNegative,composition.negative,panel.text2img_prompt);
panel.text2img_negative=compositionJoin(currentNegative,addNegative);

panel.text2img_composition={positive: addPositive.join(", "),negative: addNegative.join(", ")};
panelCompositionApplySize(panel);
return true;
}

// 現在のページのコマへ順に書き込む。履歴は積まず、まとめ方は呼び出し側に任せる。
// results: [{prompt,role}]
function promptApplyToOrderedPanels(ordered,results,append) {
let applied=0;
ordered.forEach(function (item,i) {
if (promptApplyToPanel(item.panel,results[i].prompt,append,results[i].role)) {
applied++;
}
});
return applied;
}

// 全ページを順に開いてonPage(index,total,guid)を呼ぶ。ページが完全に読み込まれてから
// 呼ばれ、trueを返したページだけ保存する。終わったら開始時のページへ戻す
async function storyForEachPage(loading,stepText,onPage) {
// 未登録のページを開いたまま送ると、切り替えた時点でその内容ごと失われる。
// 保留中のコミットの確定もここで済む。保存してからページ一覧を取り直す
const startGuid=getCanvasGUID();
await btmSaveCurrentPage();
const guidList=btmGetGuids();
let cancelled=false;

for (const [index,guid] of guidList.entries()) {
if (OP_isCancelled()) {
cancelled=true;
break;
}
OP_updateLoadingState(loading,{
icon: 'process',step: stepText,
substep: getText("storyPages")+" "+(index+1)+" / "+guidList.length,
progress: Math.round((index/guidList.length)*100)
});
await new Promise(requestAnimationFrame);

// 表示中のページは読み直さない。LZ4の展開と再圧縮が丸ごと1往復無駄になる
if (getCanvasGUID()!==guid) {
await chengeCanvasByGuid(guid);
}
// ページ切り替え直後は履歴復元が走っており、待たずに数えるとコマが0件になる
await btmWaitForPageReady();

const changed=await onPage(index,guidList.length,guid);
if (changed) {
// カスタム属性への直接代入はset()を通らず自動コミット網に検知されない
saveStateByManual();
flushHistory();
await btmSaveProjectFile(guid,false);
}
}

// 開始時のページへ戻す。戻さないと最後に処理したページを編集し続けることになる
if (getCanvasGUID()!==startGuid&&btmProjectsMap.has(startGuid)) {
await chengeCanvasByGuid(startGuid);
await btmWaitForPageReady();
}
return{cancelled: cancelled,total: guidList.length};
}
