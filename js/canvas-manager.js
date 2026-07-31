var initialCanvasWidth=0;
var initialCanvasHeight=0;
var aspectRatio=0;

let resizeTimer;
function initResizeCanvas(event) {
canvasLogger.debug("initResizeCanvas");
if(event){
event.stopPropagation();
event.preventDefault();
}
var container=$("canvas-container");
var containerWidth=container.clientWidth;
var containerHeight=container.clientHeight;

if (
containerWidth<minCanvasSizeWidth||
containerHeight<minCanvasSizeHeight
) {
return;
}

if (resizeTimer) {
clearTimeout(resizeTimer);
}
resizeTimer=setTimeout(function () {
loadBookSize(210,297,false);
initMessage();
},15);
}

// 原稿の物理サイズ(mm)。キャンバスのピクセルサイズはウィンドウ依存のため、
// 出力解像度はこの値とDPIから決める
const DEFAULT_PAGE_WIDTH_MM=148;
const DEFAULT_PAGE_HEIGHT_MM=210;
var hasProjectPageSize=true;

function getPageSizeMm(){
var widthInput=$("pageWidthMm");
var heightInput=$("pageHeightMm");
var width=widthInput ? parseFloat(widthInput.value) : NaN;
var height=heightInput ? parseFloat(heightInput.value) : NaN;
if(!(width>0)||!(height>0)){
return {width:DEFAULT_PAGE_WIDTH_MM,height:DEFAULT_PAGE_HEIGHT_MM};
}
return {width:width,height:height};
}

function setPageSizeMm(width,height){
if(!(width>0)||!(height>0)){
return;
}
var widthInput=$("pageWidthMm");
var heightInput=$("pageHeightMm");
if(widthInput){widthInput.value=width;}
if(heightInput){heightInput.value=height;}
}

// プロジェクト読み込み時に原稿サイズを復元する。未記録の旧プロジェクトは
// 従来どおりA5換算で出力するが、その旨を出力時に明示する
function applyPageSizeMm(canvasInfo){
if(canvasInfo&&canvasInfo.pageWidthMm>0&&canvasInfo.pageHeightMm>0){
setPageSizeMm(canvasInfo.pageWidthMm,canvasInfo.pageHeightMm);
hasProjectPageSize=true;
return;
}
setPageSizeMm(DEFAULT_PAGE_WIDTH_MM,DEFAULT_PAGE_HEIGHT_MM);
hasProjectPageSize=false;
}

function resizeCanvasByNum(newWidth,newHeight) {
canvas.setWidth(newWidth);
canvas.setHeight(newHeight);
initialCanvasWidth=canvas.getWidth();
initialCanvasHeight=canvas.getHeight();
aspectRatio=initialCanvasWidth/initialCanvasHeight;
canvas.renderAll();
}

function resizeCanvas(newWidth,newHeight) {
if(!newWidth||!newHeight||isNaN(newWidth)||isNaN(newHeight)){
return;
}
canvas.setDimensions({width: newWidth,height: newHeight});
// キャンバスの再フィットは表示上の追従であり編集操作ではないため履歴に残さない
withoutHistory(function(){
canvas.getObjects().forEach((obj)=>{

var scaleX=newWidth/obj.initial.canvasWidth;
var scaleY=newHeight/obj.initial.canvasHeight;

obj.set({
scaleX: obj.initial.scaleX*scaleX,
scaleY: obj.initial.scaleY*scaleY,
left: obj.initial.left*scaleX,
top: obj.initial.top*scaleY,
strokeWidth: obj.initial.strokeWidth*scaleX,
});

if (obj.clipPath) {
scaleX=newWidth/obj.clipPath.initial.canvasWidth;
scaleY=newHeight/obj.clipPath.initial.canvasHeight;
const clipPath=obj.clipPath;
clipPath.set({
scaleX: obj.clipPath.initial.scaleX*scaleX,
scaleY: obj.clipPath.initial.scaleY*scaleY,
left: obj.clipPath.initial.left*scaleX,
top: obj.clipPath.initial.top*scaleY,
});
clipPath.setCoords();
}
// initialは再フィットの基準点。ここで更新すると基準が毎回ずれて誤差が蓄積するため更新しない
obj.setCoords();
});
});
canvas.renderAll();
}

function forcedAdjustCanvasSize() {
adjustCanvasSize(true);
}


//forced = 強制
function adjustCanvasSize(forced) {
var container=$("canvas-container");
var windowWidth=container.clientWidth;
var windowHeight=container.clientHeight;
if(!windowWidth||!windowHeight||!aspectRatio||isNaN(aspectRatio)){
return;
}
const windowAspectRatio=windowWidth/windowHeight;
let newWidth,newHeight;
if (windowAspectRatio>aspectRatio) {
newHeight=windowHeight;
newWidth=windowHeight*aspectRatio;
} else {
newWidth=windowWidth;
newHeight=windowWidth/aspectRatio;
}

if (forced) {
//next
} else if (newWidth==canvas.getWidth()&&newHeight==canvas.getHeight()) {
return;
}

resizeCanvas(newWidth,newHeight);
}

window.addEventListener("resize",adjustCanvasSize);

function adjustCanvasSizeWithContainer(windowWidth,windowHeight) {
const windowAspectRatio=windowWidth/windowHeight;
let newWidth,newHeight;
if (windowAspectRatio>aspectRatio) {
newHeight=windowHeight;
newWidth=windowHeight*aspectRatio;
} else {
newWidth=windowWidth;
newHeight=windowWidth/aspectRatio;
}
resizeCanvas(newWidth,newHeight);
}

function addInitialImageToCanvas(img) {
var container=$("canvas-container");
var containerWidth=container.clientWidth;
var containerHeight=container.clientHeight;
resizeCanvasByNum(img.width,img.height);
initialPutImage(img);
adjustCanvasSizeWithContainer(containerWidth,containerHeight);
}


function resizeCanvasToObject(objectWidth,objectHeight) {
var container=$("canvas-container");
var containerWidth=container.clientWidth;
var containerHeight=container.clientHeight;
if(!containerWidth||!containerHeight||!objectWidth||!objectHeight){
return;
}
var objectAspectRatio=objectWidth/objectHeight;
var containerAspectRatio=containerWidth/containerHeight;

if (objectAspectRatio>containerAspectRatio) {
var newHeight=containerWidth/objectAspectRatio;
canvas.setDimensions({width: containerWidth,height: newHeight});
initialCanvasWidth=containerWidth;
initialCanvasHeight=newHeight;
aspectRatio=initialCanvasWidth/initialCanvasHeight;
} else {
var newWidth=containerHeight*objectAspectRatio;
canvas.setDimensions({width: newWidth,height: containerHeight});
initialCanvasWidth=newWidth;
initialCanvasHeight=containerHeight;
aspectRatio=initialCanvasWidth/initialCanvasHeight;
}

canvas.renderAll();

}

var resizableContainer=0;

document.addEventListener('DOMContentLoaded',function() {
$('bg-color').addEventListener('input',function (event) {
var color=event.target.value;
canvas.setBackgroundColor(color,canvas.renderAll.bind(canvas));
commitHistoryDebounced();
});
$('bg-color').addEventListener('input',function (event) {
resizableContainer=$('canvas-container');
});
['pageWidthMm','pageHeightMm'].forEach(function(id){
var input=$(id);
if(input){
input.addEventListener('input',function(){hasProjectPageSize=true;});
}
});
});


let canvasContinerScale=1;

function zoomIn() {
const containerRect=resizableContainer.getBoundingClientRect();

canvasContinerScale+=0.1;
$('canvas-container').style.transform=`scale(${canvasContinerScale})`;

const newContentRect=$('canvas-container').getBoundingClientRect();
const centerX=containerRect.left+containerRect.width/2;
const centerY=containerRect.top+containerRect.height/2;
const newScrollLeft=(centerX-newContentRect.width/2-containerRect.left)+resizableContainer.scrollLeft;
const newScrollTop=(centerY-newContentRect.height/2-containerRect.top)+resizableContainer.scrollTop;

resizableContainer.scrollLeft=newScrollLeft;
resizableContainer.scrollTop=newScrollTop;
forcedAdjustCanvasSize();
}

function zoomFit() {
const containerRect=resizableContainer.getBoundingClientRect();

canvasContinerScale=1.0;
$('canvas-container').style.transform=`scale(${canvasContinerScale})`;

const newContentRect=$('canvas-container').getBoundingClientRect();
const centerX=containerRect.left+containerRect.width/2;
const centerY=containerRect.top+containerRect.height/2;
const newScrollLeft=(centerX-newContentRect.width/2-containerRect.left)+resizableContainer.scrollLeft;
const newScrollTop=(centerY-newContentRect.height/2-containerRect.top)+resizableContainer.scrollTop;

resizableContainer.scrollLeft=newScrollLeft;
resizableContainer.scrollTop=newScrollTop;
forcedAdjustCanvasSize();

}

function zoomOut() {
if (canvasContinerScale>0.1) {
const containerRect=resizableContainer.getBoundingClientRect();

canvasContinerScale-=0.1;
$('canvas-container').style.transform=`scale(${canvasContinerScale})`;

const newContentRect=$('canvas-container').getBoundingClientRect();
const centerX=containerRect.left+containerRect.width/2;
const centerY=containerRect.top+containerRect.height/2;
const newScrollLeft=(centerX-newContentRect.width/2-containerRect.left)+resizableContainer.scrollLeft;
const newScrollTop=(centerY-newContentRect.height/2-containerRect.top)+resizableContainer.scrollTop;

resizableContainer.scrollLeft=newScrollLeft;
resizableContainer.scrollTop=newScrollTop;
forcedAdjustCanvasSize();
}
}


function inputImageFile() {
$('imageInput').click();
}

document.addEventListener('DOMContentLoaded',function() {
$('imageInput').addEventListener('change',function(e) {
var files=e.target.files;
for (var i=0;i<files.length;i++) {
(function(file) {
var reader=new FileReader();
reader.onload=function(f) {
var data=f.target.result;
fabric.Image.fromURL(data,function(img) {

if (stateStack.length>2) {
canvasLogger.debug("imageInput stateStack.length > 2");
var scaleFactor=Math.min(canvas.width/img.width,canvas.height/img.height);
img.scale(scaleFactor);
canvas.add(img);
canvas.renderAll();
}else{
canvasLogger.debug("imageInput resizeCanvasByNum ");
addInitialImageToCanvas(img);
}
});
};
reader.readAsDataURL(file);
})(files[i]);
}
});
});



function changeView(elementId,isVisible) {
var element=$(elementId);
if (isVisible) {
element.style.display="block";
} else {
element.style.display="none";
}
adjustCanvasSize();
}