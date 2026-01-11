var tmpCanvasSnowTone=null;
var tmpCtxSnowTone=null;
var isDrawingSnowTone=false;
var nowSnowTone=null;

function snowToneStart() {
var activeObject=getLastObject();
tmpCanvasSnowTone=document.createElement("canvas");

if (isPanel(activeObject)) {
var canvasX=(activeObject.width*activeObject.scaleX);
var canvasY=(activeObject.height*activeObject.scaleY);
tmpCanvasSnowTone.width=canvasX*3;
tmpCanvasSnowTone.height=canvasY*3;
}else{
tmpCanvasSnowTone.width=canvas.width*3;
tmpCanvasSnowTone.height=canvas.height*3;
}

tmpCtxSnowTone=tmpCanvasSnowTone.getContext("2d");
tmpCtxSnowTone.scale(3,3);
}

function snowToneEnd() {
nowSnowTone=null;
if(tmpCanvasSnowTone){
if (tmpCanvasSnowTone.parentNode) {
tmpCanvasSnowTone.parentNode.removeChild(tmpCanvasSnowTone);
}
}
tmpCanvasSnowTone=null;
tmpCtxSnowTone=null;
nowSnowTone=null;
isDrawingSnowTone=false;
}

var snowToneSnowDensity=null;
var snowToneFrontSnowSize=null;
var snowToneBackSnowSize=null;
var snowToneFrontBlurLength=null;
var snowToneBackBlurLength=null;
var snowToneFrontColor=null;
var snowToneBackColor=null;
var snowToneSnowAngle=null;


function addSnowToneEventListener() {
effectLogger.debug("addSnowToneEventListener start");
snowToneSnowDensity=$(MODE_TONE_SNOW+'-density');
snowToneFrontSnowSize=$(MODE_TONE_SNOW+'-frontSize');
snowToneBackSnowSize=$(MODE_TONE_SNOW+'-backSize');
snowToneFrontBlurLength=$(MODE_TONE_SNOW+'-frontBlurSize');
snowToneBackBlurLength=$(MODE_TONE_SNOW+'-backBlurSize');
snowToneFrontColor=$(MODE_TONE_SNOW+'-frontColor');
snowToneBackColor=$(MODE_TONE_SNOW+'-backColor');
snowToneSnowAngle=$(MODE_TONE_SNOW+'-angle');

$on(snowToneSnowDensity,"input",generateSnowTone);
$on(snowToneFrontSnowSize,"input",generateSnowTone);
$on(snowToneBackSnowSize,"input",generateSnowTone);
$on(snowToneFrontBlurLength,"input",generateSnowTone);
$on(snowToneBackBlurLength,"input",generateSnowTone);
$on(snowToneFrontColor,"input",generateSnowTone);
$on(snowToneBackColor,"input",generateSnowTone);
$on(snowToneSnowAngle,"input",generateSnowTone);
}

function drawSnowflake(x,y,size,blurLength,color,angle) {
tmpCtxSnowTone.save();
tmpCtxSnowTone.translate(x,y);
tmpCtxSnowTone.rotate((angle*Math.PI)/180);

const gradient=tmpCtxSnowTone.createLinearGradient(
0,
-size/2-blurLength,
0,
size/2+blurLength
);

const offset=size/(4*blurLength);
const clamp=(value)=>Math.max(0,Math.min(1,value));

gradient.addColorStop(0,"rgba(255,255,255,0)");
gradient.addColorStop(clamp(0.5-offset),"rgba(255,255,255,0)");
gradient.addColorStop(0.5,color);
gradient.addColorStop(clamp(0.5+offset),"rgba(255,255,255,0)");
gradient.addColorStop(1,"rgba(255,255,255,0)");

tmpCtxSnowTone.beginPath();
tmpCtxSnowTone.ellipse(
0,
0,
size/4,
size/2+blurLength,
0,
0,
2*Math.PI
);
tmpCtxSnowTone.fillStyle=gradient;
tmpCtxSnowTone.fill();
tmpCtxSnowTone.restore();
}

function interpolateColor(color1,color2,factor) {
const r1=parseInt(color1.substr(1,2),16);
const g1=parseInt(color1.substr(3,2),16);
const b1=parseInt(color1.substr(5,2),16);
const r2=parseInt(color2.substr(1,2),16);
const g2=parseInt(color2.substr(3,2),16);
const b2=parseInt(color2.substr(5,2),16);
const r=Math.round(r1+factor*(r2-r1));
const g=Math.round(g1+factor*(g2-g1));
const b=Math.round(b1+factor*(b2-b1));
return `rgb(${r}, ${g}, ${b})`;
}

function generateSnowTone() {
tmpCtxSnowTone.clearRect(0,0,tmpCanvasSnowTone.width,tmpCanvasSnowTone.height);


const density=parseInt(snowToneSnowDensity.value);
const frontSize=parseInt(snowToneFrontSnowSize.value);
const backSize=parseInt(snowToneBackSnowSize.value);
const snowToneFrontBlurLengthValue=parseInt(snowToneFrontBlurLength.value);
const snowToneBackBlurLengthValue=parseInt(snowToneBackBlurLength.value);
const angle=parseInt(snowToneSnowAngle.value);

for (let i=0;i<density;i++) {
const x=Math.random()*tmpCanvasSnowTone.width;
const y=Math.random()*tmpCanvasSnowTone.height;
const depth=Math.random();
const size=backSize+(frontSize-backSize)*depth;
const blurLength=
snowToneBackBlurLengthValue+
(snowToneFrontBlurLengthValue-snowToneBackBlurLengthValue)*depth;
const color=interpolateColor(snowToneBackColor.value,snowToneFrontColor.value,depth);
drawSnowflake(x,y,size,blurLength,color,angle);
}
updateSnowTone();
}


var tmpCanvasSnowTone=null;
var tmpCtxSnowTone=null;
var isDrawingSnowTone=false;
var nowSnowTone=null;

function updateSnowTone() {
if (isDrawingSnowTone) {
return;
}

isDrawingSnowTone=true;
if (nowSnowTone) {
canvas.remove(nowSnowTone);
nowSnowTone=null;
}

const dataURL=tmpCanvasSnowTone.toDataURL({format: "png"});
fabric.Image.fromURL(dataURL,function (img) {
var activeObject=getLastObject();
if (isPanel(activeObject)) {
var canvasX=activeObject.left+(activeObject.width*activeObject.scaleX)/2;
var canvasY=activeObject.top+(activeObject.height*activeObject.scaleY)/2;
putImageInFrame(img,canvasX,canvasY,true,false,true,activeObject);
img.name='Snow Tone';
nowSnowTone=img;
}else{
img.scaleToWidth(canvas.width);
img.name='Snow Tone';
canvas.add(img);
canvas.renderAll();
nowSnowTone=img;
}
isDrawingSnowTone=false;
});
}
