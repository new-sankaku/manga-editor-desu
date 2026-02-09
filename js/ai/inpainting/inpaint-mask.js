// Inpaintマスク描画管理
var inpaintMaskLogger=new SimpleLogger('inpaintMask',LogLevel.DEBUG);

var InpaintMask=(function(){
var maskCanvas=null;
var maskCtx=null;
var isDrawing=false;
var brushSize=30;
var maskMode='brush';
var maskColor='rgba(255,0,0,0.5)';
var lastX=0;
var lastY=0;

function init(canvasElement){
maskCanvas=canvasElement;
maskCtx=maskCanvas.getContext('2d');
maskCtx.lineCap='round';
maskCtx.lineJoin='round';
setupEvents();
inpaintMaskLogger.debug("InpaintMask initialized");
}

function setupEvents(){
maskCanvas.addEventListener('mousedown',onMouseDown);
maskCanvas.addEventListener('mousemove',onMouseMove);
maskCanvas.addEventListener('mouseup',onMouseUp);
maskCanvas.addEventListener('mouseleave',onMouseUp);
}

function removeEvents(){
maskCanvas.removeEventListener('mousedown',onMouseDown);
maskCanvas.removeEventListener('mousemove',onMouseMove);
maskCanvas.removeEventListener('mouseup',onMouseUp);
maskCanvas.removeEventListener('mouseleave',onMouseUp);
}

function onMouseDown(e){
isDrawing=true;
var rect=maskCanvas.getBoundingClientRect();
var scaleX=maskCanvas.width/rect.width;
var scaleY=maskCanvas.height/rect.height;
lastX=(e.clientX-rect.left)*scaleX;
lastY=(e.clientY-rect.top)*scaleY;
draw(lastX,lastY);
}

function onMouseMove(e){
if(!isDrawing) return;
var rect=maskCanvas.getBoundingClientRect();
var scaleX=maskCanvas.width/rect.width;
var scaleY=maskCanvas.height/rect.height;
var x=(e.clientX-rect.left)*scaleX;
var y=(e.clientY-rect.top)*scaleY;
drawLine(lastX,lastY,x,y);
lastX=x;
lastY=y;
}

function onMouseUp(){
isDrawing=false;
}

function draw(x,y){
maskCtx.beginPath();
if(maskMode==='eraser'){
maskCtx.globalCompositeOperation='destination-out';
}else{
maskCtx.globalCompositeOperation='source-over';
}
maskCtx.fillStyle=maskColor;
maskCtx.arc(x,y,brushSize/2,0,Math.PI*2);
maskCtx.fill();
}

function drawLine(x1,y1,x2,y2){
if(maskMode==='eraser'){
maskCtx.globalCompositeOperation='destination-out';
}else{
maskCtx.globalCompositeOperation='source-over';
}
maskCtx.strokeStyle=maskColor;
maskCtx.lineWidth=brushSize;
maskCtx.beginPath();
maskCtx.moveTo(x1,y1);
maskCtx.lineTo(x2,y2);
maskCtx.stroke();
}

function setMode(mode){
maskMode=mode;
inpaintMaskLogger.debug("Mask mode:",mode);
}

function setBrushSize(size){
brushSize=size;
}

function clearMask(){
if(!maskCtx) return;
maskCtx.clearRect(0,0,maskCanvas.width,maskCanvas.height);
}

function invertMask(){
if(!maskCtx) return;
var imageData=maskCtx.getImageData(0,0,maskCanvas.width,maskCanvas.height);
var data=imageData.data;
for(var i=0;i<data.length;i+=4){
if(data[i+3]>0){
data[i+3]=0;
}else{
data[i]=255;
data[i+1]=0;
data[i+2]=0;
data[i+3]=128;
}
}
maskCtx.putImageData(imageData,0,0);
}

function getMaskAsBlackWhite(){
if(!maskCanvas) return null;
var outCanvas=document.createElement('canvas');
outCanvas.width=maskCanvas.width;
outCanvas.height=maskCanvas.height;
var outCtx=outCanvas.getContext('2d');
outCtx.fillStyle='black';
outCtx.fillRect(0,0,outCanvas.width,outCanvas.height);
var maskData=maskCtx.getImageData(0,0,maskCanvas.width,maskCanvas.height);
var outData=outCtx.getImageData(0,0,outCanvas.width,outCanvas.height);
for(var i=0;i<maskData.data.length;i+=4){
if(maskData.data[i+3]>0){
outData.data[i]=255;
outData.data[i+1]=255;
outData.data[i+2]=255;
outData.data[i+3]=255;
}
}
outCtx.putImageData(outData,0,0);
return outCanvas.toDataURL('image/png');
}

function hasMask(){
if(!maskCtx) return false;
var imageData=maskCtx.getImageData(0,0,maskCanvas.width,maskCanvas.height);
var data=imageData.data;
for(var i=3;i<data.length;i+=4){
if(data[i]>0) return true;
}
return false;
}

function destroy(){
if(maskCanvas){
removeEvents();
}
maskCanvas=null;
maskCtx=null;
}

return{
init:init,
setMode:setMode,
setBrushSize:setBrushSize,
clearMask:clearMask,
invertMask:invertMask,
getMaskAsBlackWhite:getMaskAsBlackWhite,
hasMask:hasMask,
destroy:destroy
};
})();
