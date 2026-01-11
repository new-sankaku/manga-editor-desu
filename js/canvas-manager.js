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

function resizeCanvasByNum(newWidth,newHeight) {
canvas.setWidth(newWidth);
canvas.setHeight(newHeight);
initialCanvasWidth=canvas.getWidth();
initialCanvasHeight=canvas.getHeight();
aspectRatio=initialCanvasWidth/initialCanvasHeight;
canvas.renderAll();
}

function resizeCanvas(newWidth,newHeight) {
canvas.setDimensions({width: newWidth,height: newHeight});
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
saveInitialState(obj);
obj.setCoords();
});
canvas.renderAll();
}

function forcedAdjustCanvasSize() {
adjustCanvasSize(true);
}

// function adjustCanvasSize() {
//   adjustCanvasSize(false);
// }

//forced = 強制
function adjustCanvasSize(forced) {
var container=$("canvas-container");
var windowWidth=container.clientWidth;
var windowHeight=container.clientHeight;

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
// console.log( "adjustCanvasSize forced true" );
} else if (newWidth==canvas.getWidth()&&newHeight==canvas.getHeight()) {
// console.log( "adjustCanvasSize forced false" );
return;
}

resizeCanvas(newWidth,newHeight);
}

window.addEventListener("resize",adjustCanvasSize);


function resizeCanvasToObject(objectWidth,objectHeight) {
var container=$("canvas-container");
var containerWidth=container.clientWidth;
var containerHeight=container.clientHeight;

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
});
$('bg-color').addEventListener('input',function (event) {
resizableContainer=$('canvas-container');
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
resizeCanvasByNum(img.width,img.height);
canvas.add(img);
canvas.renderAll();
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