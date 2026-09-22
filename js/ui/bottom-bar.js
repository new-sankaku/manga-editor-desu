//{guid, { imageLink, blob }} blob is lz4
const btmProjectsMap=new Map();

const btmDrawer=$("btm-drawer");
const btmDrawerHandle=$("btm-drawer-handle");
const btmImageContainer=$("btm-image-container");
const btmScrollLeftBtn=$("btm-scroll-left");
const btmScrollRightBtn=$("btm-scroll-right");

let btmScrollPosition=0;
let btmIsDragging=false;
let btmIgnoreClose=false;
var btmPageOperationTail=Promise.resolve();
var btmLastPendingOperation=null;
var btmDedupeTimer=null;
var btmDedupeWindowUntil=0;
var btmNavLeft=null;
var btmNavCenter=null;
var btmNavRight=null;
var btmHandleLabel=null;
var btmHandleCount=null;

// ページ保存・切替・追加は同じcanvas/stateStackを共有するため、
// 必ず1本ずつ順に実行する。
// 押された操作は落としてはいけない（落すと「押しても反応がない」に見える）。
// 前の処理完了後に続くようチェーンへ積み、dblclickの2発目・誤った連打は
// まだ実行前の直前操作と350ms以内なら1本に集約する。実行中は取り替えない。
function btmRunPageOperation(operation) {
if(isProjectBusy()){
createToastInfo(getText("pageOperationBusy"));
return Promise.resolve(false);
}
var chain=btmPageOperationTail;
var run=new Promise(function(resolve){
chain.then(function(){
var now=Date.now();
if(btmLastPendingOperation===operation&&now<btmDedupeWindowUntil){
btmLastPendingOperation=null;
resolve(false);
return;
}
var task=(async function(){
try{
await operation();
resolve(true);
}catch(error){
uiLogger.error("btmRunPageOperation:",error);
resolve(false);
}
})();
btmLastPendingOperation=operation;
if(btmDedupeTimer)clearTimeout(btmDedupeTimer);
btmDedupeWindowUntil=Date.now()+350;
btmDedupeTimer=setTimeout(function(){
btmDedupeTimer=null;
btmLastPendingOperation=null;
},350);
return task;
});
});
btmPageOperationTail=run;
return run;
}

function btmIsPageOperationBusy(){
return isProjectBusy();
}

function btmToggleDrawer() {
btmDrawer.classList.toggle("btm-closed");
btmUpdateHandleText();
btmUpdateScrollButtons();
}

function btmCloseDrawer() {
btmDrawer.classList.add("btm-closed");
btmUpdateHandleText();
}

function btmUpdateHandleText() {
if(!btmNavCenter)return;
var isClosed=btmDrawer.classList.contains("btm-closed");
var totalPages=btmGetGuidsSize();
var currentGuid=getCanvasGUID();
var currentIndex=btmGetGuidIndex(currentGuid);
var ctrlKey=isMacOs?"⌘+B":"Ctrl+B";
// OPEN/CLOSEだけでは複数ページを並べる場所だと読めないため、ページ一覧と明示する。
// data-i18nを付け直しておくと、言語切替のupdateContent()がそのまま訳し直す
var labelKey=isClosed?"pageDrawerOpen":"pageDrawerClose";
btmHandleLabel.setAttribute("data-i18n",labelKey);
btmHandleLabel.textContent=getText(labelKey);
var pageText="";
if(totalPages>0){
// 現在ページが一覧に無い状態を「0/n」と出すと1ページ目にいるように誤読される
pageText=currentIndex>=0?" "+(currentIndex+1)+"/"+totalPages:" -/"+totalPages;
}
btmHandleCount.textContent=pageText+" ("+ctrlKey+")";
if(currentIndex>0){
btmNavLeft.textContent="\u2190 "+currentIndex+"(Alt+\u2190)";
btmNavLeft.style.visibility="visible";
}else{
btmNavLeft.textContent="";
btmNavLeft.style.visibility="hidden";
}
if(currentIndex>=0&&currentIndex<totalPages-1){
btmNavRight.textContent=(currentIndex+2)+"\u2192(Alt+\u2192)";
btmNavRight.style.visibility="visible";
}else{
btmNavRight.textContent="";
btmNavRight.style.visibility="hidden";
}
}

// 現在のキャンバスをページとしてボトムバーへ残すべきかを判定する。
// 履歴件数で判定すると、キャンバスのリサイズ等で履歴が積まれた空白ページまで
// ページとして登録されてしまうため、キャンバスの実体の有無で判定する。
// 既に登録済みのページは、内容を空にした場合でもサムネイル更新のため保存する
function btmShouldSaveCurrentPage() {
if(btmProjectsMap.has(getCanvasGUID())){
return true;
}
// 初期メッセージだけが乗っているキャンバスは空ページとみなす
return canvas.getObjects().some(obj=>!obj.isInitMessage);
}

// 保留中のコミットを確定してから保存判定する。
// 先に判定すると、直前の変更が履歴に入る前にページを離れて変更が失われる
async function btmSaveCurrentPage(openDrawer=true) {
flushHistory();
if(btmShouldSaveCurrentPage()){
await btmSaveProjectFile(null,openDrawer);
}
}

// ページを作った直後・作り直した直後に呼ぶ、ボトムバーへの登録口。
// ページはbtmSaveProjectFile()が走った時にしかbtmProjectsMapへ載らないため、
// 自動保存やページ移動といった保存の機会が来るまで一覧に出ず、
// btmGetGuidIndex()が-1のままページ番号・Alt+←→・サムネイルが成り立たなかった。
// さらに中身が無いとbtmShouldSaveCurrentPage()が偽になり、
// 空のまま別ページへ移るとページごと消えていた。
// 中身が空でもここで登録するため、作った覚えのあるページが黙って消えない。
// 登録経路はこの1か所に寄せ、呼び出し側でbtmProjectsMapを直接触らない
async function btmRegisterCurrentPage(openDrawer) {
await btmSaveProjectFile(null,openDrawer===true);
}

// chengeCanvasByGuid()は履歴復元の完了を待たずに返る。applyHistoryState()の
// canvas.loadFromJSON()がコールバック方式のため。待たずにキャンバスの中身を
// 数えると0件になり、何もせずページだけが切り替わる
// タブが非表示の間はポーリング間隔が伸びるため、隠れていた時間はタイムアウトに数えない。
// 実時間で測ると読み込みは終わっているのに誤ってタイムアウトする
async function btmWaitForPageReady(timeoutMs) {
const limit=timeoutMs||60000;
const start=performance.now();
let hiddenTotal=0;
let hiddenSince=document.visibilityState==='hidden'?performance.now():0;
function onVisibilityChange(){
if(document.visibilityState==='hidden'){
hiddenSince=performance.now();
}else if(hiddenSince){
hiddenTotal+=performance.now()-hiddenSince;
hiddenSince=0;
}
}
document.addEventListener('visibilitychange',onVisibilityChange);
try{
while (isProjectBusy()) {
const hidden=hiddenTotal+(hiddenSince?performance.now()-hiddenSince:0);
if (performance.now()-start-hidden>limit) {
throw new Error("btmWaitForPageReady: timed out waiting for the page to finish loading");
}
await waitNextFrame();
}
}finally{
document.removeEventListener('visibilitychange',onVisibilityChange);
}
}

async function btmNavigatePage(direction) {
return btmRunPageOperation(async function(){
var currentGuid=getCanvasGUID();
var currentIndex=btmGetGuidIndex(currentGuid);
var targetIndex=currentIndex+direction;
if(targetIndex<0||targetIndex>=btmGetGuidsSize())return;
var targetGuid=btmGetGuidByIndex(targetIndex);
await btmSaveCurrentPage(false);
await chengeCanvasByGuid(targetGuid);
btmUpdateHandleText();
});
}

function btmAddImage(imageLink,blob,guid,openDrawer=true) {
uiLogger.info("[btmAddImage] guid="+guid+" openDrawer="+openDrawer+" hasImageLink="+(!!imageLink)+" hasBlob="+(!!blob)+" btmProjectsMap.size="+btmProjectsMap.size);
const projectData=btmProjectsMap.get(guid);
uiLogger.info("[btmAddImage] existingProject="+(!!projectData)+" (update="+(!!projectData)+", create="+(!projectData)+")");

if (projectData) {
btmProjectsMap.set(guid,{imageLink,blob});
const image=document.querySelector(`.btm-image[data-index="${guid}"]`);
if (image&&imageLink&&imageLink.href) {
image.src=imageLink.href;
const pageNumber=image.parentElement.querySelector(".btm-page-number");
if (pageNumber) {
pageNumber.textContent=btmGetGuidIndex(guid)+1;
}
}
} else {
const imageWrapper=document.createElement("div");
imageWrapper.className="btm-image-wrapper";

const pageNumber=document.createElement("div");
pageNumber.className="btm-page-number";

let index=btmGetGuidIndex(guid);
if (index===-1) {
pageNumber.textContent=btmGetGuidsSize()+1;
} else {
pageNumber.textContent=index+1;
}

const moveLeftBtn=document.createElement("button");
moveLeftBtn.innerHTML="←";
moveLeftBtn.className="btm-move-btn btm-move-left";
moveLeftBtn.setAttribute("aria-label",getText("pageMoveLeftLabel"));
moveLeftBtn.title=getText("pageMoveLeftLabel");
moveLeftBtn.addEventListener("click",(e)=>{
e.stopPropagation();
const currentIndex=btmGetGuidIndex(guid);
if (currentIndex>0) {
const previousGuid=btmGetGuidByIndex(currentIndex-1);
swapImages(guid,previousGuid);
updateAllPageNumbers();
}
});

const image=document.createElement("img");
if(imageLink&&imageLink.href)image.src=imageLink.href;
image.className="btm-image";
image.dataset.index=guid;
image.addEventListener("click",async ()=>{
await btmRunPageOperation(async function(){
await btmSaveCurrentPage();
await chengeCanvasByGuid(guid);
btmUpdateHandleText();
});
});

const moveRightBtn=document.createElement("button");
moveRightBtn.innerHTML="→";
moveRightBtn.className="btm-move-btn btm-move-right";
moveRightBtn.setAttribute("aria-label",getText("pageMoveRightLabel"));
moveRightBtn.title=getText("pageMoveRightLabel");
moveRightBtn.addEventListener("click",(e)=>{
e.stopPropagation();
const currentIndex=btmGetGuidIndex(guid);
if (currentIndex<btmGetGuidsSize()-1) {
const nextGuid=btmGetGuidByIndex(currentIndex+1);
swapImages(guid,nextGuid);
updateAllPageNumbers();
}
});

const deleteBtn=document.createElement("button");
deleteBtn.textContent="🗑";
deleteBtn.className="btm-delete-btn";
deleteBtn.setAttribute("aria-label",getText("pageDeleteLabel"));
deleteBtn.title=getText("pageDeleteLabel");
deleteBtn.addEventListener("click",async (e)=>{
e.stopPropagation();
if(isProjectBusy())return;
// Undoはページ単位の履歴しか持たないため、削除したページは元に戻せない
var confirmed=await showConfirmDialog({
titleKey:'confirmDeletePageTitle',
message:i18next.t('confirmDeletePageBody',{page:btmGetGuidIndex(guid)+1}),
danger:true
});
if(!confirmed)return;
if(isProjectBusy())return;
// ダイアログを開いている間に他の処理がページを動かしている場合があるため取り直す
if(!btmProjectsMap.has(guid))return;
var isCurrentPage=(getCanvasGUID()===guid);
var deletedIndex=btmGetGuidIndex(guid);
btmProjectsMap.delete(guid);
imageWrapper.remove();
if(btmGetGuidsSize()>0){
// 削除したページを表示していた場合は隣のページへ移動する。
// 後ろのページを優先し、最後尾を削除したときは前のページになる
if(isCurrentPage){
var targetIndex=Math.min(deletedIndex,btmGetGuidsSize()-1);
await chengeCanvasByGuid(btmGetGuidByIndex(targetIndex));
}
}else{
// ページが無くなったら空ページを表示する。
// キャンバスに内容を残すと、一覧に無いページを編集し続けることになる
initImageHistory();
setCanvasGUID();
showEmptyPageMessage();
await btmRegisterCurrentPage(true);
}
btmUpdateScrollButtons();
updateAllPageNumbers();
btmUpdateHandleText();
});

var addBtn=document.createElement("button");
addBtn.textContent="+";
addBtn.className="btm-add-btn";
addBtn.addEventListener("click",function(e){
e.stopPropagation();
btmShowAddPageDialog(guid);
});

imageWrapper.appendChild(pageNumber);
imageWrapper.appendChild(moveLeftBtn);
imageWrapper.appendChild(image);
imageWrapper.appendChild(moveRightBtn);
imageWrapper.appendChild(deleteBtn);
imageWrapper.appendChild(addBtn);
btmImageContainer.appendChild(imageWrapper);
btmProjectsMap.set(guid,{imageLink,blob});
}

btmDrawer.style.display="block";
if (openDrawer) {
if (btmDrawer.classList.contains("btm-closed")) {
btmIgnoreClose=true;
btmToggleDrawer();
setTimeout(()=>{btmIgnoreClose=false;},200);
} else {
btmUpdateScrollButtons();
btmUpdateHandleText();
}
} else {
btmUpdateHandleText();
}
}

let btmThumbnailRefreshTimer=null;

function btmScheduleThumbnailRefresh() {
if(btmThumbnailRefreshTimer)clearTimeout(btmThumbnailRefreshTimer);
btmThumbnailRefreshTimer=setTimeout(btmRefreshThumbnail,500);
}

function btmCancelThumbnailRefresh() {
if(btmThumbnailRefreshTimer){
clearTimeout(btmThumbnailRefreshTimer);
btmThumbnailRefreshTimer=null;
}
}

function btmRefreshThumbnail() {
btmThumbnailRefreshTimer=null;
const guid=getCanvasGUID();
if(!guid)return;
const image=document.querySelector(`.btm-image[data-index="${guid}"]`);
if(!image)return;
removeGrid();
const multiplier=Math.min(1,400/canvas.height);
const dataUrl=canvas.toDataURL({format:"jpeg",multiplier:multiplier});
if(isGridVisible){
drawGrid();
isGridVisible=true;
}
image.src=dataUrl;
const projectData=btmProjectsMap.get(guid);
if(projectData){
projectData.imageLink={href:dataUrl};
}
}

function updateAllPageNumbers() {
const pageNumbers=document.querySelectorAll(".btm-page-number");
pageNumbers.forEach((numberElement,index)=>{
numberElement.textContent=index+1;
});
btmUpdateHandleText();
}

function swapImages(guid1,guid2) {
const wrapper1=document.querySelector(
`.btm-image[data-index="${guid1}"]`
).parentElement;
const wrapper2=document.querySelector(
`.btm-image[data-index="${guid2}"]`
).parentElement;

const tempElement=document.createElement("div");
btmImageContainer.insertBefore(tempElement,wrapper1);
btmImageContainer.insertBefore(wrapper1,wrapper2);
btmImageContainer.insertBefore(wrapper2,tempElement);
tempElement.remove();

const guids=btmGetGuids();
const newMap=new Map();

guids.forEach((guid)=>{
if (guid===guid1) {
newMap.set(guid2,btmProjectsMap.get(guid2));
} else if (guid===guid2) {
newMap.set(guid1,btmProjectsMap.get(guid1));
} else {
newMap.set(guid,btmProjectsMap.get(guid));
}
});

btmProjectsMap.clear();
newMap.forEach((value,key)=>{
btmProjectsMap.set(key,value);
});

updateAllPageNumbers();
}

function reorderImages(targetIndex,newGuid) {
const newWrapper=document.querySelector(
`.btm-image[data-index="${newGuid}"]`
).parentElement;
const targetWrapper=document.querySelector(
`.btm-image[data-index="${btmGetGuidByIndex(targetIndex)}"]`
).parentElement;
btmImageContainer.insertBefore(newWrapper,targetWrapper);

const newMap=new Map();
const guids=btmGetGuids();
const newGuidData=btmProjectsMap.get(newGuid);

guids.forEach((guid,index)=>{
if (index===targetIndex) {
newMap.set(newGuid,newGuidData);
}
if (guid!==newGuid) {
newMap.set(guid,btmProjectsMap.get(guid));
}
});

btmProjectsMap.clear();
newMap.forEach((value,key)=>{
btmProjectsMap.set(key,value);
});

updateAllPageNumbers();
}

function btmUpdateScrollButtons() {
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
const scrollWidth=btmImageContainer.scrollWidth;
btmScrollLeftBtn.style.display=btmScrollPosition>0 ? "block" : "none";
btmScrollRightBtn.style.display=
scrollWidth>containerWidth&&
btmScrollPosition<scrollWidth-containerWidth
? "block"
: "none";
}

function btmScroll(direction) {
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
btmScrollPosition+=direction*containerWidth;
btmScrollPosition=Math.max(
0,
Math.min(btmScrollPosition,btmImageContainer.scrollWidth-containerWidth)
);
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
btmUpdateScrollButtons();
}

document.addEventListener("DOMContentLoaded",function () {
btmDrawerHandle.textContent="";
btmNavLeft=document.createElement("span");
btmNavLeft.className="btm-nav-left";
btmNavLeft.addEventListener("click",function(e){
e.stopPropagation();
btmNavigatePage(-1);
});
btmNavCenter=document.createElement("span");
btmNavCenter.className="btm-nav-center";
// 訳す部分とページ番号を別の要素に分ける。混ぜるとdata-i18nの
// innerHTML差し替えで番号まで消える
btmHandleLabel=document.createElement("span");
btmHandleCount=document.createElement("span");
btmHandleCount.className="btm-handle-count";
btmNavCenter.appendChild(btmHandleLabel);
btmNavCenter.appendChild(btmHandleCount);
btmNavRight=document.createElement("span");
btmNavRight.className="btm-nav-right";
btmNavRight.addEventListener("click",function(e){
e.stopPropagation();
btmNavigatePage(1);
});
btmDrawerHandle.appendChild(btmNavLeft);
btmDrawerHandle.appendChild(btmNavCenter);
btmDrawerHandle.appendChild(btmNavRight);
btmUpdateHandleText();
btmDrawerHandle.addEventListener("click",btmToggleDrawer);
btmScrollLeftBtn.addEventListener("click",()=>btmScroll(-1));
btmScrollRightBtn.addEventListener("click",()=>btmScroll(1));

document.addEventListener("mousedown",function (event) {
if (
!btmDrawer.contains(event.target)&&
!btmDrawer.classList.contains("btm-closed")
) {
btmIsDragging=false;
}
});

document.addEventListener("mouseup",function (event) {
if (
!btmDrawer.contains(event.target)&&
!btmDrawer.classList.contains("btm-closed")&&
!btmIsDragging&&
!btmIgnoreClose
) {
btmCloseDrawer();
}
btmIsDragging=false;
});

function btmStartDrag(e) {
e.preventDefault();
isDragging=true;
let startX=e.clientX;
let scrollLeft=btmScrollPosition;

function btmDrag(e) {
const diff=startX-e.clientX;
btmScrollPosition=scrollLeft+diff;
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
}

function btmStopDrag() {
document.removeEventListener("mousemove",btmDrag);
document.removeEventListener("mouseup",btmStopDrag);
const containerWidth=btmDrawer.querySelector(
".btm-drawer-content"
).offsetWidth;
btmScrollPosition=Math.max(
0,
Math.min(
btmScrollPosition,
btmImageContainer.scrollWidth-containerWidth
)
);
btmImageContainer.style.transform=`translateX(-${btmScrollPosition}px)`;
btmUpdateScrollButtons();
}

document.addEventListener("mousemove",btmDrag);
document.addEventListener("mouseup",btmStopDrag);
}

btmImageContainer.addEventListener("mousedown",btmStartDrag);
window.addEventListener("resize",btmUpdateScrollButtons);
});

async function chengeCanvasByGuid(guid) {
btmCancelThumbnailRefresh();
const projectData=btmProjectsMap.get(guid);
if(!projectData||!projectData.blob){
uiLogger.error("[chengeCanvasByGuid] project data not found. guid="+guid);
createToastError(getText("pageLoadErrorTitle"),getText("pageLoadErrorMessage"));
return;
}
try {
await loadLz4BlobProjectFile(projectData.blob,guid);
} catch (error) {
uiLogger.error("Error loading ZIP:",error);
createToastError(getText("pageLoadErrorTitle"),getText("pageLoadErrorMessage"));
throw error;
}
}

//return [string, string]
function btmGetGuids() {
return Array.from(btmProjectsMap.keys());
}

//return number
function btmGetGuidIndex(targetGuid) {
const guids=Array.from(btmProjectsMap.keys());
return guids.indexOf(targetGuid);
}

//return number
function btmGetGuidsSize() {
return btmProjectsMap.size;
}

//return guid
function btmGetGuidByIndex(index) {
const guids=Array.from(btmProjectsMap.keys());
return guids[index];
}

function btmGetFirstGuidByIndex() {
return Array.from(btmProjectsMap.keys())[0];
}

function btmShowAddPageDialog(guid) {
// 二重に開くとIDが重複して2枚目のボタンが効かなくなる
if(document.querySelector(".btm-dialog-overlay"))return;
var dialog=document.createElement("div");
dialog.className="btm-dialog-overlay";
dialog.innerHTML='<div class="btm-dialog"><div class="btm-dialog-content">'+
'<h3>'+getText("pageAddDialogTitle")+'</h3>'+
'<div class="btm-radio-group">'+
'<label><input type="radio" name="page-size" value="portrait" checked>'+getText("pagePortrait")+'</label>'+
'<label><input type="radio" name="page-size" value="landscape">'+getText("pageLandscape")+'</label>'+
'</div>'+
'<div class="btm-dialog-buttons">'+
'<button class="btm-dialog-button" id="btm-dialog-cancel">'+getText("cancel")+'</button>'+
'<button class="btm-dialog-button btm-dialog-submit" id="btm-dialog-submit">'+getText("pageAddDialogSubmit")+'</button>'+
'</div></div></div>';
document.body.appendChild(dialog);
var cancelButton=document.getElementById("btm-dialog-cancel");
var submitButton=document.getElementById("btm-dialog-submit");
cancelButton.addEventListener("click",function(){
document.body.removeChild(dialog);
});
submitButton.addEventListener("click",async function(){
await btmRunPageOperation(async function(){
var selectedSize=document.querySelector('input[name="page-size"]:checked').value;
document.body.removeChild(dialog);
var currentIndex=btmGetGuidIndex(guid);
if(currentIndex<0)return;
var newGuid=generateGUID();
var w,h;
if(selectedSize==="portrait"){w=210;h=297;}
else{w=297;h=210;}
// 離れる前に今のページを確定する。原稿サイズ(mm)はこの後の
// resizeCanvasToObject()が決めるので、ここで書き換えると
// 今のページに次のページのサイズが記録されてしまう
await btmSaveCurrentPage(false);
withoutHistory(function(){
resizeCanvasToObject(w,h);
});
initImageHistory();
setCanvasGUID(newGuid);
// 中身は空で揃える。案内文はページの中身とは数えない
showEmptyPageMessage();
await btmRegisterCurrentPage(true);
reorderImages(currentIndex+1,newGuid);
updateAllPageNumbers();
btmUpdateHandleText();
});
});
}
