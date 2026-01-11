var tmpCanvasToneNoise=null;
var tmpCtxToneNoise=null;
var nowToneNoise=null;
var isDrawingToneNoise=false;

function toneNoiseStart() {
var activeObject=getLastObject();
tmpCanvasToneNoise=document.createElement("canvas");

if (isPanel(activeObject)) {
var canvasX=activeObject.width*activeObject.scaleX;
var canvasY=activeObject.height*activeObject.scaleY;
tmpCanvasToneNoise.width=canvasX*3;
tmpCanvasToneNoise.height=canvasY*3;
} else {
tmpCanvasToneNoise.width=canvas.width*3;
tmpCanvasToneNoise.height=canvas.height*3;
}

tmpCtxToneNoise=tmpCanvasToneNoise.getContext("2d");
tmpCtxToneNoise.scale(3,3);
}

function toneNoiseEnd() {
nowTone=null;
if (tmpCanvasToneNoise) {
if (tmpCanvasToneNoise.parentNode) {
tmpCanvasToneNoise.parentNode.removeChild(tmpCanvasToneNoise);
}
}
tmpCanvasToneNoise=null;
tmpCtxToneNoise=null;
nowToneNoise=null;
isDrawingTone=false;
}

var toneNoiseColorPicker=null;
var toneNoiseNoiseMinSlider=null;
var toneNoiseNoiseMaxSlider=null;
var toneNoiseGradientStartX=null;
var toneNoiseGradientStartY=null;
var toneNoiseGradientEndX=null;
var toneNoiseGradientEndY=null;

function hexToRgb(hex) {
const result=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
return result
? {
r: parseInt(result[1],16),
g: parseInt(result[2],16),
b: parseInt(result[3],16),
}
: null;
}

function generateNoiseWithGradient(color,noiseMin,noiseMax) {
const imageData=tmpCtxToneNoise.createImageData(
tmpCanvasToneNoise.width,
tmpCanvasToneNoise.height
);
const data=imageData.data;
const rgb=hexToRgb(color);

const startX=parseInt(toneNoiseGradientStartX.value);
const startY=parseInt(toneNoiseGradientStartY.value);
const endX=parseInt(toneNoiseGradientEndX.value);
const endY=parseInt(toneNoiseGradientEndY.value);

for (let y=0;y<tmpCanvasToneNoise.height;y++) {
for (let x=0;x<tmpCanvasToneNoise.width;x++) {
const index=(y*tmpCanvasToneNoise.width+x)*4;

const dx=endX-startX;
const dy=endY-startY;
const progress=
((x-startX)*dx+(y-startY)*dy)/(dx*dx+dy*dy);

const noiseThreshold=noiseMin+progress*(noiseMax-noiseMin);
const noise=Math.random()*100;

if (noise<noiseThreshold) {
data[index]=rgb.r;
data[index+1]=rgb.g;
data[index+2]=rgb.b;
data[index+3]=255;
} else {
data[index]=255;
data[index+1]=255;
data[index+2]=255;
data[index+3]=0;
}
}
}

return imageData;
}


function addToneNoiseEventListener() {
toneNoiseColorPicker=$(MODE_TONE_NOISE+'-color');
toneNoiseNoiseMinSlider=$(MODE_TONE_NOISE+'-min-noise');
toneNoiseNoiseMaxSlider=$(MODE_TONE_NOISE+'-max-noise');
toneNoiseGradientStartX=$(MODE_TONE_NOISE+'-grad-start-x');
toneNoiseGradientStartY=$(MODE_TONE_NOISE+'-grad-start-y');
toneNoiseGradientEndX=$(MODE_TONE_NOISE+'-grad-end-x');
toneNoiseGradientEndY=$(MODE_TONE_NOISE+'-grad-end-y');

$on(toneNoiseColorPicker,"input",updateToneNoise);
$on(toneNoiseNoiseMinSlider,"input",updateToneNoise);
$on(toneNoiseNoiseMaxSlider,"input",updateToneNoise);
$on(toneNoiseGradientStartX,"input",updateToneNoise);
$on(toneNoiseGradientStartY,"input",updateToneNoise);
$on(toneNoiseGradientEndX,"input",updateToneNoise);
$on(toneNoiseGradientEndY,"input",updateToneNoise);
}


function updateToneNoise() {
if (isDrawingToneNoise) {
return;
}

isDrawingToneNoise=true;
if (nowToneNoise) {
canvas.remove(nowToneNoise);
nowToneNoise=null;
}

const color=toneNoiseColorPicker.value;
const noiseMin=parseInt(toneNoiseNoiseMinSlider.value);
const noiseMax=parseInt(toneNoiseNoiseMaxSlider.value);

const noiseData=generateNoiseWithGradient(color,noiseMin,noiseMax);
tmpCtxToneNoise.putImageData(noiseData,0,0);


fabric.Image.fromURL(tmpCanvasToneNoise.toDataURL(),function (img) {
var activeObject=getLastObject();
if (isPanel(activeObject)) {
var canvasX=activeObject.left+(activeObject.width*activeObject.scaleX)/2;
var canvasY=activeObject.top+(activeObject.height*activeObject.scaleY)/2;
putImageInFrame(img,canvasX,canvasY,true,false,true,activeObject);
img.name='Tone Noise';
nowToneNoise=img;
}else{
img.name='Tone Noise';
canvas.add(img);
canvas.renderAll();
nowToneNoise=img;
}
isDrawingToneNoise=false;
});
}
