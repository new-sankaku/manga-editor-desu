

var tmpCanvasTone=null;
var tmpCtxTone=null;
// var nowTone = null;
var controlElementsTone=null;
var isDrawingTone=false;

function toneStart() {
var activeObject=canvas.getActiveObject();
tmpCanvasTone=document.createElement("canvas");

if (isPanel(activeObject)) {
var canvasX=(activeObject.width*activeObject.scaleX);
var canvasY=(activeObject.height*activeObject.scaleY);
tmpCanvasTone.width=canvasX*3;
tmpCanvasTone.height=canvasY*3;
}else{
tmpCanvasTone.width=canvas.width*3;
tmpCanvasTone.height=canvas.height*3;
}

tmpCtxTone=tmpCanvasTone.getContext("2d");
tmpCtxTone.scale(3,3);
controlElementsTone={
dotSize: $(MODE_TONE+'-dot-size'),
dotSpacing: $(MODE_TONE+'-dot-spacing'),
dotShape: $(MODE_TONE+'-dot-style'),
fillColor: $(MODE_TONE+'-color'),
gradientEnabled: $(MODE_TONE+'-grad-check'),
gradientDirection: $(MODE_TONE+'-grad-style'),
gradientStart: $(MODE_TONE+'-grad-start'),
gradientEnd: $(MODE_TONE+'-grad-end'),
};

updatecanvas();
}

function toneEnd() {
nowTone=null;
if(tmpCanvasTone){
if (tmpCanvasTone.parentNode) {
tmpCanvasTone.parentNode.removeChild(tmpCanvasTone);
}
}
tmpCanvasTone=null;
tmpCtxTone=null;
controlElementsTone=null;
isDrawingTone=false;
}

function createShape(x,y,size,shape,fillColor,opacity) {
var pc=parseColor(fillColor);
const color=`rgba(${pc.r}, ${pc.g}, ${pc.b}, ${opacity*pc.a})`;

tmpCtxTone.fillStyle=color;
tmpCtxTone.beginPath();

switch (shape) {
case "circle":
tmpCtxTone.arc(x,y,size/2,0,2*Math.PI);
break;
case "square":
tmpCtxTone.rect(x-size/2,y-size/2,size,size);
break;
case "triangle":
tmpCtxTone.moveTo(x,y-size/2);
tmpCtxTone.lineTo(x+size/2,y+size/2);
tmpCtxTone.lineTo(x-size/2,y+size/2);
break;
case "star":
drawStar(x,y,size);
break;
case "cross":
drawCross(x,y,size);
break;
case "heart":
drawHeart(x,y,size);
break;
}

tmpCtxTone.fill();
}

function drawStar(x,y,size) {
const spikes=5;
const outerRadius=size/2;
const innerRadius=outerRadius/2;

tmpCtxTone.beginPath();
for (let i=0;i<spikes*2;i++) {
const radius=i%2===0 ? outerRadius : innerRadius;
const angle=(i*Math.PI)/spikes-Math.PI/2;
if (i===0) {
tmpCtxTone.moveTo(x+radius*Math.cos(angle),y+radius*Math.sin(angle));
} else {
tmpCtxTone.lineTo(x+radius*Math.cos(angle),y+radius*Math.sin(angle));
}
}
tmpCtxTone.closePath();
}

function drawCross(x,y,size) {
const thickness=size/3;
tmpCtxTone.rect(x-thickness/2,y-size/2,thickness,size);
tmpCtxTone.rect(x-size/2,y-thickness/2,size,thickness);
}

function drawHeart(x,y,size) {
const width=size;
const height=size;

tmpCtxTone.moveTo(x,y+height/4);
tmpCtxTone.quadraticCurveTo(x,y,x+width/4,y);
tmpCtxTone.quadraticCurveTo(x+width/2,y,x+width/2,y+height/4);
tmpCtxTone.quadraticCurveTo(x+width/2,y,x+width*3/4,y);
tmpCtxTone.quadraticCurveTo(x+width,y,x+width,y+height/4);
tmpCtxTone.quadraticCurveTo(x+width,y+height/2,x+width*3/4,y+height*3/4);
tmpCtxTone.lineTo(x+width/2,y+height);
tmpCtxTone.lineTo(x+width/4,y+height*3/4);
tmpCtxTone.quadraticCurveTo(x,y+height/2,x,y+height/4);
}

function generateTone() {
tmpCtxTone.clearRect(0,0,tmpCanvasTone.width,tmpCanvasTone.height);
const dotSize=parseInt(controlElementsTone.dotSize.value);
const dotSpacing=parseInt(controlElementsTone.dotSpacing.value);
const dotShape=controlElementsTone.dotShape.value;
const fillColor=controlElementsTone.fillColor.value;
const gradientEnabled=controlElementsTone.gradientEnabled.checked;
const gradientDirection=controlElementsTone.gradientDirection.value;
const gradientStart=parseInt(controlElementsTone.gradientStart.value)/100;
const gradientEnd=parseInt(controlElementsTone.gradientEnd.value)/100;
const canvasSizeX=tmpCanvasTone.width;
const canvasSizeY=tmpCanvasTone.height;

const totalSpacing=dotSize+dotSpacing;
for (let y=0;y<canvasSizeY+totalSpacing;y+=totalSpacing) {
for (let x=0;x<canvasSizeX+totalSpacing;x+=totalSpacing) {
let opacity=1;
if (gradientEnabled) {
let gradientPosition;
switch (gradientDirection) {
case "top-bottom":
gradientPosition=y/canvasSizeY;
break;
case "bottom-top":
gradientPosition=1-y/canvasSizeY;
break;
case "left-right":
gradientPosition=x/canvasSizeX;
break;
case "right-left":
gradientPosition=1-x/canvasSizeX;
break;
}
opacity=(gradientPosition-gradientStart)/(gradientEnd-gradientStart);
opacity=Math.max(0,Math.min(1,opacity));
}

createShape(x,y,dotSize,dotShape,fillColor,opacity);
}
}
updatecanvas();
}

function updatecanvas() {
if (isDrawingTone) {
return;
}

isDrawingTone=true;

if (nowTone) {
canvas.remove(nowTone);
}
fabric.Image.fromURL(tmpCanvasTone.toDataURL(),function (img) {
var activeObject=getLastObject();

if(isPanel(activeObject)){
var canvasX=(activeObject.left+(activeObject.width*activeObject.scaleX/2))  ;
var canvasY=(activeObject.top+(activeObject.height*activeObject.scaleY/2)) ;
putImageInFrame(img,canvasX,canvasY,true,false,true,activeObject);
img.name='Tone';
}else{
img.scaleToWidth(canvas.width);
img.name='Tone';
canvas.add(img);
canvas.renderAll();
}
nowTone=img;
isDrawingTone=false;
});
}

function debounce(func,wait) {
let timeout;
return function executedFunction(...args) {
const later=()=>{
clearTimeout(timeout);
func(...args);
};
clearTimeout(timeout);
timeout=setTimeout(later,wait);
};
}

const debouncedGenerateTone=debounce(generateTone,300);
function addToneEventListener() {
Object.keys(controlElementsTone).forEach((key)=>{
const element=controlElementsTone[key];
if (element) {
element.addEventListener("input",()=>{
debouncedGenerateTone();
});
}
});
}