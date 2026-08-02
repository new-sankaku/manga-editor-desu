// エフェクトの一括適用。1画像への適用処理そのものは各エフェクト側
// （c2bwApplyToImage / c2cApplyToImage / enhanceDarkToImage）を使い、
// ここは対象の選別・進捗・履歴のまとめ・ページ送りだけを持つ

const EFFECT_SCOPE_SELECTED="selected";
const EFFECT_SCOPE_PAGE="page";
const EFFECT_SCOPE_ALL_PAGES="allPages";

// 一括適用に対応するエフェクト。Glow/GLFX/Blendは1枚ずつ調整する種類なので対象外
const EFFECT_BATCH_TYPES=[
MODE_EFFECT_C2BW_LIGHT,
MODE_EFFECT_C2BW_DARK,
MODE_EFFECT_C2BW_ROUGHT,
MODE_EFFECT_C2BW_SIMPLE,
MODE_EFFECT_C2BC_LIGHT,
MODE_EFFECT_ENHANCE_DARK
];

function effectIsBatchType(type) {
return EFFECT_BATCH_TYPES.indexOf(type)>=0;
}

function effectGetScope() {
return getSelectedValueByGroup("effectApplyScope");
}

// レイヤーパネルの鍵ボタン（moveLockChange）が切り替えるのはselectable。
// lockMovement*ではないので、そちらを見ても永久に引っかからない
function effectIsLockedObject(object) {
return object.selectable===false;
}

function effectHasRunningAiTask(object) {
if (!object.guid) {
return false;
}
return getAiTasksForLayer(object.guid,getCanvasGUID()).length>0;
}

// 非表示・ロック・AI生成中・一時オブジェクトは一括の対象にしない
function effectIsBatchTarget(object) {
if (!isImage(object)) {
return false;
}
if (object.visible===false) {
return false;
}
if (object.saveHistory===false) {
return false;
}
if (object.excludeFromLayerPanel) {
return false;
}
if (object.isPanel||object.isIcon) {
return false;
}
if (effectIsLockedObject(object)) {
return false;
}
if (effectHasRunningAiTask(object)) {
return false;
}
return true;
}

function effectGetEnhanceDarkIntensity() {
const input=$("effectEnhanceDarkIntensity");
if (!input) {
throw new Error("effectGetEnhanceDarkIntensity: effectEnhanceDarkIntensity is not rendered");
}
return parseFloat(input.value);
}

async function effectApplyToImage(type,object) {
if (type===MODE_EFFECT_ENHANCE_DARK) {
await enhanceDarkToImage(object,effectGetEnhanceDarkIntensity());
return;
}
if (type===MODE_EFFECT_C2BC_LIGHT) {
await c2cApplyToImage(object);
return;
}
const preset=c2bwGetPreset(type);
if (!preset) {
throw new Error("effectApplyToImage: unknown effect type "+type);
}
await c2bwApplyToImage(object,preset);
}

// 現在のキャンバスの対象画像すべてに適用する。履歴は積まず、まとめ方は呼び出し側に任せる
async function effectApplyToPageImages(type,onProgress) {
const allImages=getImageObjectList()||[];
const targets=allImages.filter(effectIsBatchTarget);
const result={applied: 0,skipped: allImages.length-targets.length,total: targets.length,cancelled: false,error: null};

// 枚数分コミットすると画像1枚分のスナップショットが枚数だけ積まれ、
// メモリ圧迫とUndo連打の原因になる。非同期をまたぐのでwithoutHistoryは使えない
changeDoNotSaveHistory();
try {
for (let i=0;i<targets.length;i++) {
if (OP_isCancelled()) {
result.cancelled=true;
break;
}
if (onProgress) {
onProgress(i,targets.length);
}
// 1枚ごとに描画を通さないと処理中ずっと画面が固まる
await new Promise(requestAnimationFrame);
try {
await effectApplyToImage(type,targets[i]);
} catch (error) {
// 失敗を握りつぶして次の画像へ進むと、どこまで掛かったのか分からなくなる。
// 打ち切ってどこで止まったかを呼び出し側に返す
effectLogger.error("[effectApplyToPageImages] failed",error);
result.error=error;
break;
}
result.applied++;
}
} finally {
changeDoSaveHistory();
}
canvas.requestRenderAll();
return result;
}

function effectBuildResultMessages(result,pageCount) {
const messages=[];
messages.push(getText("effectBatchApplied")+": "+result.applied);
if (result.skipped>0) {
messages.push(getText("effectBatchSkipped")+": "+result.skipped);
}
if (pageCount>1) {
messages.push(getText("effectBatchPages")+": "+pageCount);
}
return messages;
}

function effectShowBatchResult(result,pageCount) {
if (result.error) {
// 途中で止まった状態を隠さない。どこまで適用されたかを必ず出す
const messages=effectBuildResultMessages(result,pageCount);
const error=result.error;
messages.push(error instanceof Error?error.name+": "+error.message:String(error));
createToastError(getText("effectBatchFailed"),messages,8000);
return;
}
if (result.cancelled) {
createToastError(getText("effectBatchCancelled"),effectBuildResultMessages(result,pageCount),6000);
return;
}
if (result.applied===0) {
createToastError(getText("effectBatchNoTarget"),"",4000);
return;
}
createToast(getText("effectBatchDone"),effectBuildResultMessages(result,pageCount),4000);
}

async function effectApplyToCurrentPage(type) {
const loading=OP_showLoading({
icon: 'process',step: getText("effectScopePage"),substep: '',progress: 0
},true);
await new Promise(requestAnimationFrame);
let result=null;
try {
// ページ切り替え直後は履歴復元が走っており、待たずに数えるとオブジェクトが0件になる
await btmWaitForPageReady();
result=await effectApplyToPageImages(type,function (index,total) {
OP_updateLoadingState(loading,{
icon: 'process',step: getText("effectScopePage"),
substep: (index+1)+" / "+total,
progress: Math.round((index/total)*100)
});
});
if (result.applied>0) {
updateLayerPanel();
// setElementはfabricのset()を通らず自動コミット網に検知されないため明示的に積む
saveStateByManual();
}
} catch (error) {
effectLogger.error("[effectApplyToCurrentPage] failed",error);
result={applied: 0,skipped: 0,total: 0,cancelled: false,error: error};
} finally {
OP_hideLoading(loading);
}
effectShowBatchResult(result,1);
}

async function effectApplyToAllPages(type) {
if (isProjectBusy()) {
createToastError(getText("effectBatchBusy"),"",4000);
return;
}
const guidList=btmGetGuids();
if (guidList.length===0) {
createToastError(getText("effectBatchNoTarget"),"",4000);
return;
}
// Undoで戻せないことは知らせるが、実行は止めない。
// トーストは--z-toast(2000)で進捗オーバーレイ(--z-modal:1000)より上に出る
createToast(getText("effectScopeAllPages"),getText("effectBatchAllPagesNotice"),6000);

const startGuid=getCanvasGUID();
const total={applied: 0,skipped: 0,total: 0,cancelled: false,error: null};
let pageCount=0;

const loading=OP_showLoading({
icon: 'process',step: getText("effectScopeAllPages"),substep: '',progress: 0
},true);
await new Promise(requestAnimationFrame);
try {
// ページを離れる前に保留中のコミットを確定しないと直前の変更が失われる
flushHistory();
await effectSaveBatchBackup();

for (const [index,guid] of guidList.entries()) {
if (OP_isCancelled()) {
total.cancelled=true;
break;
}
OP_updateLoadingState(loading,{
icon: 'process',step: getText("effectScopeAllPages"),
substep: getText("effectBatchPages")+" "+(index+1)+" / "+guidList.length,
progress: Math.round((index/guidList.length)*100)
});
await new Promise(requestAnimationFrame);

// 表示中のページは読み直さない。LZ4の展開と再圧縮が丸ごと1往復無駄になる。
// 離れる前の保存はループ前のバックアップと各ページ処理後の保存で済んでいるので
// ここで再度btmSaveCurrentPage()すると同じページを二重に圧縮することになる
if (getCanvasGUID()!==guid) {
await chengeCanvasByGuid(guid);
}
await btmWaitForPageReady();

const result=await effectApplyToPageImages(type,function (i,count) {
OP_updateLoadingState(loading,{
icon: 'process',step: getText("effectScopeAllPages"),
substep: getText("effectBatchPages")+" "+(index+1)+" / "+guidList.length+" - "+(i+1)+" / "+count,
progress: Math.round(((index+(i/Math.max(count,1)))/guidList.length)*100)
});
});
total.applied+=result.applied;
total.skipped+=result.skipped;
total.total+=result.total;
pageCount++;

if (result.applied>0) {
updateLayerPanel();
saveStateByManual();
flushHistory();
await btmSaveProjectFile(guid,false);
}
if (result.error) {
total.error=result.error;
break;
}
if (result.cancelled) {
total.cancelled=true;
break;
}
}

// 開始時のページへ戻す。戻さないと最後に処理したページを編集し続けることになる
if (getCanvasGUID()!==startGuid&&btmProjectsMap.has(startGuid)) {
await chengeCanvasByGuid(startGuid);
await btmWaitForPageReady();
}
} catch (error) {
effectLogger.error("[effectApplyToAllPages] failed",error);
total.error=error;
} finally {
OP_hideLoading(loading);
}
effectShowBatchResult(total,pageCount);
effectRefreshRestoreButton();
}

// 一括適用前の退避。IndexedDB等には保存せず、開いている間だけメモリに持つ。
//
// 永続化しない理由:
//  - 目的は「今やった一括適用を取り消す」ことだけで、次のセッションまで
//    持ち越す必要がない
//  - 中身は全ページのblobで容量が大きい。永続化すると使われないまま
//    ブラウザに残り続け、削除する導線も別途必要になる
//  - プロジェクトごとのスロット管理・世代の上限・古いものの掃除といった
//    仕組みが要らなくなる
//
// この変数はリロード・タブを閉じた時点で失われる。
// つまり「リロードしたら一括適用は取り消せない」。
// auto-save（js/core/auto-save.js）とは別物で、あちらは永続化する
var effectBatchBackup=null;

// ページGUID（canvasGuid）はcommonPropertiesに含まれstate_*.jsonとして
// プロジェクトファイルに保存され、読み込み後も同じ値が復元される。
// リロードせずにプロジェクトを切り替えると退避だけが残るため、
// 現在開いているページのGUIDと突き合わせて別プロジェクトのものを弾く
function effectBackupMatchesCurrentProject(backup) {
if (!backup||!Array.isArray(backup.pageOrder)) {
return false;
}
const current=btmGetGuids();
return current.some(function (guid) {
return backup.pageOrder.indexOf(guid)>=0;
});
}

// 一括適用前の全ページを退避する
async function effectSaveBatchBackup() {
await btmSaveCurrentPage();
const pages=[];
btmProjectsMap.forEach(function (data,guid) {
pages.push({guid: guid,blob: data.blob});
});
effectBatchBackup={
pages: pages,
currentPageGuid: getCanvasGUID(),
pageOrder: btmGetGuids()
};
effectLogger.info("[effectSaveBatchBackup] pages="+pages.length);
}

function effectHasBatchBackup() {
return effectBackupMatchesCurrentProject(effectBatchBackup);
}

// 一括適用前の状態に戻す
async function effectRestoreBatchBackup() {
if (isProjectBusy()) {
createToastError(getText("effectBatchBusy"),"",4000);
return;
}
// ボタンの表示制御だけに任せず、実行直前にも確認する。
// 取り違えると現在のプロジェクトが丸ごと置き換わる
if (!effectHasBatchBackup()) {
createToastError(getText("effectRestoreNoBackup"),"",4000);
effectRefreshRestoreButton();
return;
}
const metadata=effectBatchBackup;
const pages=effectBatchBackup.pages;
if (!pages||pages.length===0) {
createToastError(getText("effectRestoreNoBackup"),"",4000);
return;
}
const loading=OP_showLoading({
icon: 'file',step: getText("effectRestoreBatch"),substep: '',progress: 0
});
await new Promise(requestAnimationFrame);
try {
btmProjectsMap.clear();
const container=$("btm-image-container");
if (container) {
container.innerHTML='';
}
const pageBlobs={};
for (let i=0;i<pages.length;i++) {
pageBlobs[pages[i].guid]=pages[i].blob;
}
const bufferList=[];
for (let j=0;j<metadata.pageOrder.length;j++) {
const guid=metadata.pageOrder[j];
if (pageBlobs[guid]) {
const arrayBuffer=await pageBlobs[guid].arrayBuffer();
bufferList.push({name: guid,data: new Uint8Array(arrayBuffer)});
}
}
OP_updateLoadingState(loading,{
icon: 'file',step: getText("effectRestoreBatch"),substep: '',progress: 50
});
await multiLoadLz4(bufferList);

let targetGuid=metadata.currentPageGuid;
if (!btmProjectsMap.has(targetGuid)) {
targetGuid=btmProjectsMap.keys().next().value;
}
await loadLz4BlobProjectFile(btmProjectsMap.get(targetGuid).blob,targetGuid);
OP_updateLoadingState(loading,{
icon: 'file',step: getText("effectRestoreBatch"),substep: '',progress: 100
});
createToast(getText("effectRestoreDone"),"",3000);
} catch (error) {
effectLogger.error("[effectRestoreBatchBackup] failed",error);
createToastError(getText("effectRestoreFailed"),
error instanceof Error?error.name+": "+error.message:String(error),6000);
} finally {
OP_hideLoading(loading);
}
}

document.addEventListener("DOMContentLoaded",function () {
EventDelegator.register('effectRestoreBatchBackup',function () {
effectRestoreBatchBackup();
});
// セグメントは短ラベルしか出せないので、フルの説明はツールチップで補う
addTooltipByElement($("effectScopeSelectedButton"),"effectScopeSelected");
addTooltipByElement($("effectScopePageButton"),"effectScopePage");
addTooltipByElement($("effectScopeAllPagesButton"),"effectScopeAllPages");
addTooltipByElement($("effectRestoreBatchButton"),"effectRestoreBatchHint");
effectRefreshRestoreButton();
});

// バックアップが無い間は押せないようにする
function effectRefreshRestoreButton() {
const button=$("effectRestoreBatchButton");
if (!button) {
return;
}
// メモリ上の退避を見るだけなので同期で済む。
// バックアップが無い間はCSS側（:disabled）でボタンごと消える
button.disabled=!effectHasBatchBackup();
}
