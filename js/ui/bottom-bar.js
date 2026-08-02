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
var btmNavLeft=null;
var btmNavCenter=null;
var btmNavRight=null;

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
var stateText=isClosed?"OPEN":"CLOSE";
var totalPages=btmGetGuidsSize();
var currentGuid=getCanvasGUID();
var currentIndex=btmGetGuidIndex(currentGuid);
var pageText=totalPages>0?" "+(currentIndex+1)+"/"+totalPages:"";
var ctrlKey=isMacOs?"⌘+B":"Ctrl+B";
btmNavCenter.textContent=stateText+pageText+" ("+ctrlKey+")";
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
async function btmSaveCurrentPage() {
flushHistory();
if(btmShouldSaveCurrentPage()){
await btmSaveProjectFile();
}
}

// chengeCanvasByGuid()は履歴復元の完了を待たずに返る。applyHistoryState()の
// canvas.loadFromJSON()がコールバック方式のため。待たずにキャンバスの中身を
// 数えると0件になり、何もせずページだけが切り替わる
async function btmWaitForPageReady(timeoutMs) {
const limit=timeoutMs||60000;
const start=performance.now();
while (isProjectBusy()) {
if (performance.now()-start>limit) {
throw new Error("btmWaitForPageReady: timed out waiting for the page to finish loading");
}
await new Promise(requestAnimationFrame);
}
}

async function btmNavigatePage(direction) {
if(isProjectBusy())return;
var currentGuid=getCanvasGUID();
var currentIndex=btmGetGuidIndex(currentGuid);
var targetIndex=currentIndex+direction;
if(targetIndex<0||targetIndex>=btmGetGuidsSize())return;
var targetGuid=btmGetGuidByIndex(targetIndex);
await btmSaveCurrentPage();
await chengeCanvasByGuid(targetGuid);
btmUpdateHandleText();
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
if(isProjectBusy())return;
await btmSaveCurrentPage();
await chengeCanvasByGuid(guid);
btmUpdateHandleText();
});

const moveRightBtn=document.createElement("button");
moveRightBtn.innerHTML="→";
moveRightBtn.className="btm-move-btn btm-move-right";
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
deleteBtn.addEventListener("click",async (e)=>{
e.stopPropagation();
if(isProjectBusy())return;
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
await btmSaveProjectFile();
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
if(isProjectBusy())return;
var selectedSize=document.querySelector('input[name="page-size"]:checked').value;
document.body.removeChild(dialog);
var currentIndex=btmGetGuidIndex(guid);
var newGuid=generateGUID();
var w,h;
if(selectedSize==="portrait"){w=210;h=297;}
else{w=297;h=210;}
setPageSizeMm(w,h);
var pc=document.createElement('canvas');
pc.width=100;
pc.height=Math.round(100*h/w);
var pctx=pc.getContext('2d');
pctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--color-tertiary').trim()||'#505050';
pctx.fillRect(0,0,pc.width,pc.height);
var placeholderUrl=pc.toDataURL('image/jpeg',0.5);
if(btmShouldSaveCurrentPage()){
await btmSaveProjectFile(null,false);
}
btmAddImage({href:placeholderUrl},null,newGuid,true);
reorderImages(currentIndex+1,newGuid);
withoutHistory(function(){
resizeCanvasToObject(w,h);
});
initImageHistory();
setCanvasGUID(newGuid);
await btmSaveProjectFile(newGuid,false);
updateAllPageNumbers();
btmUpdateHandleText();
});
}
