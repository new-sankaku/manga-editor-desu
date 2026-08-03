// プロンプトパネル（prompt-manager-area）の操作と、生成結果のプレビューウインドウ。
// 生成結果は必ず一度プレビューに出し、編集してから反映させる。黙って書き換えない

var llmStoryResult=null;

function llmStoryGetStory() {
return $("storyPromptInput").value.trim();
}

function llmStoryGetCharacters() {
return $("storyCharacterInput").value.trim();
}

function llmStoryGetLocations() {
return $("storyLocationInput").value.trim();
}

function llmStoryIsRightToLeft() {
return $("storyRightToLeft").checked;
}

function llmStorySetStatus(text) {
$("storyPromptStatus").textContent=text||'';
}

function llmStorySetBusy(busy) {
$("storyGenerateButton").disabled=busy;
$("storySheetButton").disabled=busy;
$("storyExpandButton").disabled=busy;
}

function llmStoryShowError(error) {
llmStorySetStatus('');
const message=error instanceof Error?error.message:String(error);
createToastError(getText("storyTitle"),message,1000*10);
llmLogger.error('llmStory failed: '+message);
}

function llmStoryRequireProvider() {
if (hasNotRole(AI_ROLES.Text2Prompt)) {
createToastError(getText("storyTitle"),getText("llmErrorNoProvider"),1000*8);
return false;
}
return true;
}

// キャラ表とロケーション表を1回の呼び出しでまとめて埋める
async function llmStoryExtractSheets() {
if (!llmStoryRequireProvider()) {
return;
}
const story=llmStoryGetStory();
if (!story) {
llmStorySetStatus(getText("storyNeedInput"));
return;
}
llmStorySetBusy(true);
llmStorySetStatus(getText("storyExtracting"));
try {
const sheets=await llmStorySheets(story);
$("storyCharacterInput").value=sheets.characters;
$("storyLocationInput").value=sheets.locations;
llmStorySetStatus('');
} catch (error) {
llmStoryShowError(error);
} finally {
llmStorySetBusy(false);
}
}

// ストーリーをページ数に合わせる（短ければ足し、長ければ削る）。
// ユーザーの入力を黙って書き換えず、一度プレビューへ出して
// 編集させてから「ストーリー欄へ入れる」を押させる
async function llmStoryFitStory() {
if (!llmStoryRequireProvider()) {
return;
}
const story=llmStoryGetStory();
if (!story) {
llmStorySetStatus(getText("storyNeedInput"));
return;
}
// 何ページ分に合わせるかはキャンバスのページ数で決まる
const pageCount=btmGetGuidsSize();
if (!pageCount) {
createToastError(getText("storyTitle"),getText("storyExpandNoPage"),4000);
return;
}
llmStorySetBusy(true);
llmStorySetStatus(getText("storyExpanding"));
try {
openLLMStoryFitWindow(await llmStoryFitToPages(story,pageCount),pageCount);
llmStorySetStatus('');
} catch (error) {
llmStoryShowError(error);
} finally {
llmStorySetBusy(false);
}
}

function closeLLMStoryFitWindow() {
const existing=document.querySelector('.llm-story-fit-window');
if (existing) {
existing.remove();
}
}

function openLLMStoryFitWindow(text,pageCount) {
closeLLMStoryFitWindow();
const win=document.createElement('div');
win.className='floating-windowPromptClass llm-story-fit-window';
win.style.cursor='move';
win.innerHTML=`
<h4>${getText('storyExpandTitle')}</h4>
<div class="llm-prompt-status llm-story-note">${getText('storyExpandHint')} ${pageCount}</div>
<div class="llm-prompt-field">
<textarea id="llmStoryFitText" rows="14"></textarea>
</div>
<div class="llm-prompt-actions">
<button id="llmStoryFitApply">${getText('storyExpandApply')}</button>
<button id="llmStoryFitClose">${getText('llmText2PromptClose')}</button>
</div>
`;
document.body.appendChild(win);
makeDraggable(win);
// 利用者の入力をテンプレートリテラルに埋めるとDOMが壊れる。valueへ代入する
$('llmStoryFitText').value=text;

$('llmStoryFitApply').addEventListener('click',function () {
const value=$('llmStoryFitText').value.trim();
if (!value) {
return;
}
$("storyPromptInput").value=value;
closeLLMStoryFitWindow();
createToast(getText("storyTitle"),getText("storyExpandApplied"),3000);
});
$('llmStoryFitClose').addEventListener('click',function () {
closeLLMStoryFitWindow();
});
}

// 1コマ / 1ページ: ストーリー全文をそのまま1ページ分として渡すと、どのコマにも
// 情報を詰め込もうとして緩急が消える。先に1ページ分の内容と場所へ落としてから作る
async function llmStoryGeneratePanels(story,scope) {
const rightToLeft=llmStoryIsRightToLeft();
const ordered=storyCollectPanels(scope,rightToLeft);
if (ordered.length===0) {
llmStorySetStatus('');
createToastError(getText("storyTitle"),
getText(scope===STORY_SCOPE_SELECTED?"nothingPanel":"llmStoryboardErrorNoPanel"),4000);
return;
}
llmStorySetStatus(getText("storyPlanning"));
const plan=(await llmStoryPagePlan(story,[{page: 1,panelCount: ordered.length}]))[0];
llmStorySetStatus(getText("storyGenerating"));
// 選択コマだけのときはページの先頭とは限らないので場面の始まりとして扱わない
const sceneChange=scope!==STORY_SCOPE_SELECTED;
const result=await llmStoryPanelPrompts({
pageSummary: plan.summary,
place: plan.place,
sceneChange: sceneChange,
pageIndex: 1,
pageCount: 1,
characterSheet: llmStoryGetCharacters(),
locationSheet: llmStoryGetLocations(),
layout: buildPanelLayoutSummary(ordered),
rightToLeft: rightToLeft
});
llmStoryResult={
mode: 'panels',
rightToLeft: rightToLeft,
warning: result.warning,
plan: plan,
entries: ordered.map(function (item,i) {
return{panel: item.panel,index: i+1,prompt: result.entries[i].prompt,role: result.entries[i].role};
})
};
llmStorySetStatus('');
openLLMStoryPreview();
}

// 全ページ: ページ数とコマ数を数えてから、各ページの流れをLLMに作らせる。
// コマのプロンプトはプレビューで流れを確認したあとで作る
async function llmStoryGenerateAllPages(story) {
if (isProjectBusy()) {
createToastError(getText("storyTitle"),getText("storyBusy"),4000);
return;
}
const rightToLeft=llmStoryIsRightToLeft();
const loading=OP_showLoading({
icon: 'process',step: getText("storyCollecting"),substep: '',progress: 0
},true);
await new Promise(requestAnimationFrame);
const pageInfos=[];
let cancelled=false;
let plans=null;
try {
const walk=await storyForEachPage(loading,getText("storyCollecting"),function (index,total,guid) {
const panels=getPanelObjectList()||[];
if (panels.length>0) {
// コマ配置はここで採っておく。LLM呼び出しはキャンバスを触らないので、
// 採寸を先に済ませればページごとの生成をまとめてキューへ投入できる
const ordered=sortPanelsInReadingOrder(panels,rightToLeft);
pageInfos.push({
page: index+1,
guid: guid,
panelCount: panels.length,
layout: buildPanelLayoutSummary(ordered)
});
}
return false;
});
cancelled=walk.cancelled;
if (!cancelled&&pageInfos.length>0) {
OP_updateLoadingState(loading,{
icon: 'process',step: getText("storyPlanning"),substep: '',progress: 100
});
await new Promise(requestAnimationFrame);
plans=await llmStoryPagePlan(story,pageInfos);
}
} finally {
OP_hideLoading(loading);
}
llmStorySetStatus('');
if (cancelled) {
createToastError(getText("storyCancelled"),"",4000);
return;
}
if (!plans) {
createToastError(getText("storyTitle"),getText("llmStoryboardErrorNoPanel"),4000);
return;
}
llmStoryResult={
mode: 'pages',
rightToLeft: rightToLeft,
characterSheet: llmStoryGetCharacters(),
locationSheet: llmStoryGetLocations(),
entries: pageInfos.map(function (info,i) {
return{
guid: info.guid,
page: info.page,
panelCount: info.panelCount,
layout: info.layout,
summary: plans[i].summary,
place: plans[i].place
};
})
};
openLLMStoryPreview();
}

function llmStoryGenerate() {
if (!llmStoryRequireProvider()) {
return;
}
const story=llmStoryGetStory();
if (!story) {
llmStorySetStatus(getText("storyNeedInput"));
return;
}
const scope=storyGetScope();
llmStorySetBusy(true);
const run=scope===STORY_SCOPE_ALL_PAGES
?llmStoryGenerateAllPages(story)
:llmStoryGeneratePanels(story,scope);
// 呼び出し元がawaitしないためcatchを持たせないとunhandled rejectionになり、
// 進捗表示だけ消えて無言で終わる
run.catch(function (error) {
llmStoryShowError(error);
}).finally(function () {
llmStorySetBusy(false);
});
}

function removeLLMStoryWindow() {
const existing=document.querySelector('.llm-story-window');
if (existing) {
existing.remove();
}
}

function closeLLMStoryPreview() {
removeLLMStoryWindow();
llmStoryResult=null;
}

function openLLMStoryPreview() {
// 開き直しでは窓だけ捨てる。closeLLMStoryPreview()は結果まで消すため使えない
removeLLMStoryWindow();
if (!llmStoryResult) {
return;
}
const win=document.createElement('div');
win.className='floating-windowPromptClass llm-story-window';
win.style.cursor='move';
const isPages=llmStoryResult.mode==='pages';
win.innerHTML=`
<h4>${getText(isPages?'storyPreviewPagesTitle':'storyPreviewPanelsTitle')}</h4>
<div class="llm-prompt-status llm-story-note">${getText(isPages?'storyPreviewPagesHint':'storyPreviewPanelsHint')}</div>
<div id="llmStoryPlanNote" class="llm-prompt-status llm-story-note llm-story-plan" style="display:none;"></div>
${llmStoryResult.warning?`<div class="llm-story-note llm-rhythm-warning">${getText('storyRhythmWarning')}</div>`:''}
<div id="llmStoryPreview" class="llm-storyboard-preview"></div>
<div class="llm-prompt-actions">
<button id="llmStoryAppend">${getText('storyApplyAppend')}</button>
<button id="llmStoryReplace">${getText('storyApplyReplace')}</button>
<button id="llmStoryClose">${getText('llmText2PromptClose')}</button>
</div>
`;
document.body.appendChild(win);
makeDraggable(win);
renderLLMStoryPreview();

$('llmStoryAppend').addEventListener('click',function () {
llmStoryApply(true);
});
$('llmStoryReplace').addEventListener('click',function () {
llmStoryApply(false);
});
$('llmStoryClose').addEventListener('click',function () {
closeLLMStoryPreview();
});
}

// 場所・時間の欄。ここが前のページと違えば場面転換とみなして、そのページの
// 1コマ目に引きの絵を要求する。判定を文字列一致にしてあるので手直しがそのまま効く
function buildPlaceInput(entry,index) {
const input=document.createElement('input');
input.type='text';
input.className='llm-story-place';
input.value=entry.place;
input.placeholder=getText('storyPlacePlaceholder');
input.addEventListener('input',function () {
llmStoryResult.entries[index].place=this.value;
});
return input;
}

// ストーリーを1ページ分にどう解釈したかを見せる。黙って圧縮したまま進めない
function renderLLMStoryPlanNote() {
const note=$('llmStoryPlanNote');
const plan=llmStoryResult.plan;
if (!plan) {
note.style.display='none';
return;
}
note.textContent=getText('storyDerivedPageLabel')+' '
+(plan.place ? '['+plan.place+'] ' : '')+plan.summary;
note.style.display='block';
}

// 利用者の入力をテンプレートリテラルに埋めると</textarea>を含む文字でDOMが壊れる。
// 中身は要素を作ってからvalueへ代入する
function renderLLMStoryPreview() {
renderLLMStoryPlanNote();
const container=$('llmStoryPreview');
container.textContent='';
const isPages=llmStoryResult.mode==='pages';
llmStoryResult.entries.forEach(function (entry,i) {
const row=document.createElement('div');
row.className='llm-storyboard-row';
const label=document.createElement('label');
label.className='llm-storyboard-index';
label.textContent=isPages
?getText('storyPages')+' '+entry.page+' ('+entry.panelCount+')'
:getText('llmStoryboardPanel')+' '+entry.index;
// どのコマが引き・情景なのかを見せる。ページの緩急をここで確認して作り直せる
if (!isPages) {
const role=document.createElement('span');
role.className='llm-panel-role';
role.textContent=getPanelRoleLabel(entry.role);
label.appendChild(role);
}
const area=document.createElement('textarea');
area.rows=isPages?3:2;
area.value=isPages?entry.summary:entry.prompt;
area.addEventListener('input',function () {
if (isPages) {
llmStoryResult.entries[i].summary=this.value;
} else {
llmStoryResult.entries[i].prompt=this.value;
}
});
if (!isPages) {
area.addEventListener('focus',function () {
canvas.setActiveObject(entry.panel);
canvas.renderAll();
});
}
row.appendChild(label);
if (isPages) {
const fields=document.createElement('div');
fields.className='llm-story-fields';
fields.appendChild(buildPlaceInput(entry,i));
fields.appendChild(area);
row.appendChild(fields);
} else {
row.appendChild(area);
}
container.appendChild(row);
});
}

function llmStoryApply(append) {
if (!llmStoryResult) {
return;
}
if (llmStoryResult.mode==='panels') {
llmStoryApplyPanels(append);
return;
}
const result=llmStoryResult;
closeLLMStoryPreview();
llmStoryApplyPages(result,append).catch(function (error) {
llmStoryShowError(error);
});
}

function llmStoryApplyPanels(append) {
const entries=llmStoryResult.entries;
let applied=0;
entries.forEach(function (entry) {
if (promptApplyToPanel(entry.panel,entry.prompt,append)) {
applied++;
}
});
refreshPromptPanel(canvas.getActiveObject());
updateLayerPanel();
// カスタム属性への直接代入はset()を通らず自動コミット網に検知されない
saveStateByManual();
createToast(getText("storyTitle"),getText("llmStoryboardApplied")+' '+applied,4000);
closeLLMStoryPreview();
}

// 全ページ分のコマ生成をまとめてキューへ投入する。ページは開かない。
// コマ配置は採寸済みなのでLLM呼び出しはキャンバスを必要とせず、実際に何本が
// 同時に走るかはプロバイダごとの「同時実行数」設定（TaskQueue）が決める。
// 1本の失敗で全部を捨てないよう、成否はページ単位で受ける。
// 戻り値: [{page,guid,panelResult}|{page,guid,error}]
function llmStoryGeneratePagePrompts(result,pages,loading) {
const total=pages.length;
let done=0;
return Promise.all(pages.map(function (entry,i) {
// 前ページを知らないとページ境界の場面転換が分からず、
// 転換直後に引きの絵を置くという肝心の判断ができない
const prev=pages[i-1]||null;
const next=pages[i+1]||null;
return llmStoryPanelPrompts({
pageSummary: entry.summary,
place: entry.place,
// 場所か時間が前ページと変われば場面転換。1ページ目は必ず場面の始まり。
// 欄を直せば判定も追随するよう、文字列の一致だけで見る
sceneChange:!prev||entry.place!==prev.place,
prevSummary: prev ? prev.summary : '',
prevPlace: prev ? prev.place : '',
nextSummary: next ? next.summary : '',
pageIndex: entry.page,
pageCount: total,
characterSheet: result.characterSheet,
locationSheet: result.locationSheet,
layout: entry.layout,
rightToLeft: result.rightToLeft
}).then(function (panelResult) {
return{page: entry.page,guid: entry.guid,panelResult: panelResult};
}).catch(function (error) {
return{page: entry.page,guid: entry.guid,error: error};
}).then(function (outcome) {
done++;
OP_updateLoadingState(loading,{
icon: 'process',step: getText("storyGenerating"),
substep: getText("storyPages")+" "+done+" / "+total,
progress: Math.round(done/total*100)
});
return outcome;
});
}));
}

// 全ページ: 先に全ページ分のプロンプトを作ってから、ページを順に開いて書き込む。
// 生成と書き込みを分けないとLLMの往復がページ送りに直列化され、同時実行数の
// 設定が効かない。コマ配置は生成前に採ってあるので、書き込み時にコマ数が
// 変わっていたページは書かずに報告する
async function llmStoryApplyPages(result,append) {
if (isProjectBusy()) {
createToastError(getText("storyTitle"),getText("storyBusy"),4000);
return;
}
// Undoで戻せないことは知らせるが、実行は止めない。
// トーストは--z-toast(2000)で進捗オーバーレイ(--z-modal:1000)より上に出る
createToast(getText("storyScopeAllPages"),getText("storyAllPagesNotice"),6000);

const pages=result.entries.filter(function (entry) {
return entry.summary&&entry.summary.trim()&&entry.layout.length>0;
});
if (pages.length===0) {
createToastError(getText("storyTitle"),getText("llmStoryboardErrorNoPanel"),4000);
return;
}

let panelTotal=0;
let pageDone=0;
let failure=null;
let cancelled=false;
// 役割の配分が守られなかったページ。黙って通さず最後にまとめて知らせる
const warnedPages=[];
// 生成後にコマ数が変わって書き込めなかったページ。黙って部分適用しない
const skippedPages=[];

const loading=OP_showLoading({
icon: 'process',step: getText("storyGenerating"),substep: '',progress: 0
},true);
await new Promise(requestAnimationFrame);
try {
const outcomes=await llmStoryGeneratePagePrompts(result,pages,loading);
const resultByGuid={};
outcomes.forEach(function (outcome) {
if (outcome.error) {
// 中止ボタンはclearAllQueues()で待機中のLLM呼び出しを落とすため、
// そのときの例外は失敗ではなく中止として扱う
promptLogger.error("[llmStoryApplyPages] page "+outcome.page+" failed",outcome.error);
if (!OP_isCancelled()&&!failure) {
failure=outcome.error;
}
return;
}
if (outcome.panelResult.warning) {
warnedPages.push(outcome.page);
promptLogger.warn("[llmStoryApplyPages] page "+outcome.page+": "+outcome.panelResult.warning);
}
resultByGuid[outcome.guid]=outcome.panelResult;
});
if (OP_isCancelled()) {
cancelled=true;
} else {
// 書き込みだけの送り。LLM待ちが無いのでページ切り替えの分しかかからない
const walk=await storyForEachPage(loading,getText("storyApplying"),function (index,total,guid) {
const panelResult=resultByGuid[guid];
if (!panelResult) {
return false;
}
const ordered=storyCollectPanels(STORY_SCOPE_PAGE,result.rightToLeft);
// 採寸時とコマ数が変わっていたら書かない。ずれたまま入れると
// 別のコマ用のプロンプトが別のコマに入る
if (ordered.length!==panelResult.entries.length) {
skippedPages.push(index+1);
return false;
}
const applied=promptApplyToOrderedPanels(ordered,panelResult.entries,append);
panelTotal+=applied;
pageDone++;
return applied>0;
});
cancelled=walk.cancelled;
}
} catch (error) {
// 失敗を握りつぶすと、どこまで書けたのか分からなくなる
promptLogger.error("[llmStoryApplyPages] failed",error);
if (OP_isCancelled()) {
cancelled=true;
} else {
failure=error;
}
} finally {
OP_hideLoading(loading);
}

refreshPromptPanel(canvas.getActiveObject());
updateLayerPanel();

const messages=[
getText("llmStoryboardApplied")+' '+panelTotal,
getText("storyPages")+': '+pageDone
];
if (warnedPages.length>0) {
messages.push(getText("storyRhythmWarningPages")+' '+warnedPages.join(', '));
}
if (skippedPages.length>0) {
messages.push(getText("storySkippedPages")+' '+skippedPages.join(', '));
}
if (failure) {
messages.push(failure instanceof Error?failure.name+": "+failure.message:String(failure));
createToastError(getText("storyFailed"),messages,1000*10);
return;
}
if (cancelled) {
createToastError(getText("storyCancelled"),messages,6000);
return;
}
if (panelTotal===0) {
createToastError(getText("storyTitle"),getText("llmStoryboardErrorNoPanel"),4000);
return;
}
createToast(getText("storyTitle"),messages,5000);
}

document.addEventListener("DOMContentLoaded",function () {
EventDelegator.register('llmStoryGenerate',function () {
llmStoryGenerate();
});
EventDelegator.register('llmStoryExtractSheets',function () {
// awaitしないのでcatchが要る。中でトーストまで出す
llmStoryExtractSheets().catch(function (error) {
llmStoryShowError(error);
});
});
EventDelegator.register('llmStoryExpand',function () {
llmStoryFitStory().catch(function (error) {
llmStoryShowError(error);
});
});
// セグメントは短ラベルしか出せないので、フルの説明はツールチップで補う
addTooltipByElement($("storyScopeSelectedButton"),"storyScopeSelected");
addTooltipByElement($("storyScopePageButton"),"storyScopePage");
addTooltipByElement($("storyScopeAllPagesButton"),"storyScopeAllPages");
});
