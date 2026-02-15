//{guid, { imageLink, blob }} blob is lz4
const btmProjectsMap=new Map();

const btmDrawer=$("btm-drawer");
const btmDrawerHandle=$("btm-drawer-handle");
const btmImageContainer=$("btm-image-container");
const btmScrollLeftBtn=$("btm-scroll-left");
const btmScrollRightBtn=$("btm-scroll-right");

var btmSaveStateThreshold=2;
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

async function btmNavigatePage(direction) {
var currentGuid=getCanvasGUID();
var currentIndex=btmGetGuidIndex(currentGuid);
var targetIndex=currentIndex+direction;
if(targetIndex<0||targetIndex>=btmGetGuidsSize())return;
var targetGuid=btmGetGuidByIndex(targetIndex);
if(stateStack.length>=btmSaveStateThreshold){
await btmSaveProjectFile();
}
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
if(stateStack.length>=btmSaveStateThreshold){
await btmSaveProjectFile();
}
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
if(btmGetGuidsSize()>1){
var isCurrentPage=(getCanvasGUID()===guid);
var deletedIndex=btmGetGuidIndex(guid);
btmProjectsMap.delete(guid);
imageWrapper.remove();
if(isCurrentPage){
var targetIndex=Math.min(deletedIndex,btmGetGuidsSize()-1);
var targetGuid=btmGetGuidByIndex(targetIndex);
await chengeCanvasByGuid(targetGuid);
}
}else{
var isCurrentPage=(getCanvasGUID()===guid);
btmProjectsMap.delete(guid);
imageWrapper.remove();
if(isCurrentPage&&getObjectCount()===0){
initImageHistory();
setCanvasGUID();
await btmSaveProjectFile();
}
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
const projectData=btmProjectsMap.get(guid);
try {
await loadLz4BlobProjectFile(projectData.blob,guid);
} catch (error) {
uiLogger.error("Error loading ZIP:",error);
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
var dialog=document.createElement("div");
dialog.className="btm-dialog-overlay";
dialog.innerHTML='<div class="btm-dialog"><div class="btm-dialog-content">'+
'<h3>ページサイズを選択</h3>'+
'<div class="btm-radio-group">'+
'<label><input type="radio" name="page-size" value="portrait" checked>縦</label>'+
'<label><input type="radio" name="page-size" value="landscape">横</label>'+
'</div>'+
'<div class="btm-dialog-buttons">'+
'<button class="btm-dialog-button" id="btm-dialog-cancel">キャンセル</button>'+
'<button class="btm-dialog-button btm-dialog-submit" id="btm-dialog-submit">作成</button>'+
'</div></div></div>';
document.body.appendChild(dialog);
var cancelButton=document.getElementById("btm-dialog-cancel");
var submitButton=document.getElementById("btm-dialog-submit");
cancelButton.addEventListener("click",function(){
document.body.removeChild(dialog);
});
submitButton.addEventListener("click",async function(){
var selectedSize=document.querySelector('input[name="page-size"]:checked').value;
document.body.removeChild(dialog);
var currentIndex=btmGetGuidIndex(guid);
var newGuid=generateGUID();
var w,h;
if(selectedSize==="portrait"){w=210;h=297;}
else{w=297;h=210;}
var pc=document.createElement('canvas');
pc.width=100;
pc.height=Math.round(100*h/w);
var pctx=pc.getContext('2d');
pctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--color-tertiary').trim()||'#505050';
pctx.fillRect(0,0,pc.width,pc.height);
var placeholderUrl=pc.toDataURL('image/jpeg',0.5);
await btmSaveProjectFile(null,false);
btmAddImage({href:placeholderUrl},null,newGuid,true);
reorderImages(currentIndex+1,newGuid);
changeDoNotSaveHistory();
resizeCanvasToObject(w,h);
changeDoSaveHistory();
initImageHistory();
setCanvasGUID(newGuid);
await btmSaveProjectFile(newGuid,false);
updateAllPageNumbers();
btmUpdateHandleText();
});
}
