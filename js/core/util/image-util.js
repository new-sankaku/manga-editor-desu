

// 透明でない部分の境界を見つける関数
function findNonTransparentBounds(imageData) {
const {width,height,data}=imageData;
let minX=width,minY=height,maxX=0,maxY=0;

for (let y=0;y<height;y++) {
for (let x=0;x<width;x++) {
const alpha=data[(y*width+x)*4+3];
if (alpha>0) {
minX=Math.min(minX,x);
minY=Math.min(minY,y);
maxX=Math.max(maxX,x);
maxY=Math.max(maxY,y);
}
}
}

return {minX,minY,maxX,maxY};
}

// クリッピングされた部分のみを含む新しいキャンバスを作成する関数
function createClippedCanvas(sourceCanvas,bounds) {
const {minX,minY,maxX,maxY}=bounds;
const clipWidth=maxX-minX+1;
const clipHeight=maxY-minY+1;

const clippedCanvas=document.createElement('canvas');
clippedCanvas.width=clipWidth;
clippedCanvas.height=clipHeight;
const clippedCtx=clippedCanvas.getContext('2d');
clippedCtx.drawImage(sourceCanvas,minX,minY,clipWidth,clipHeight,0,0,clipWidth,clipHeight);

return clippedCanvas;
}

// メイン関数
function sendHtmlCanvas2FabricCanvas(blendedCanvas,quality=0.98) {
const ctx=blendedCanvas.getContext('2d');
const imageData=ctx.getImageData(0,0,blendedCanvas.width,blendedCanvas.height);
const bounds=findNonTransparentBounds(imageData);
if (bounds.minX>bounds.maxX||bounds.minY>bounds.maxY) {
imageLogger.warn('The image is completely transparent');
return;
}
const clippedCanvas=createClippedCanvas(blendedCanvas,bounds);
const webpDataUrl=clippedCanvas.toDataURL('image/webp',quality);
fabric.Image.fromURL(webpDataUrl,(img)=>{
img.scaleToWidth(canvas.width);
canvas.add(img);
canvas.setActiveObject(img);
canvas.renderAll();
},{crossOrigin: 'anonymous'});
}


// await img = imgFile2webpFile(img);
async function imgFile2webpFile(file) {
if (file.type==='image/webp') {
return file;
}
var options={
fileType: 'image/webp',
initialQuality: webpQuality
};
try {
var compressedFile=await imageCompression(file,options);
return compressedFile;
} catch (error) {
imageLogger.error(error);
throw error;
}
}




async function img2webp(i) {
const blob=await fetch(i._element.src).then(response=>response.blob());
const fileType=blob.type;
const fileName='image.'+fileType.split('/')[1];
const file=new File([blob],fileName,{type: fileType});
const webpFile=await imgFile2webpFile(file);

const webpBlob=webpFile.slice(0,webpFile.size,'image/webp');

// BlobをデータURIに変換
const reader=new FileReader();
return new Promise((resolve,reject)=>{
reader.onloadend=()=>{
const webpDataUrl=reader.result;
const webpImgElement=new Image();
webpImgElement.src=webpDataUrl;
webpImgElement.onload=()=>{
const webpImg={
...i,
_element: webpImgElement,
_originalElement: webpImgElement,
cacheKey: 'webp_texture'
};
// Copy prototype methods from the original image object
Object.setPrototypeOf(webpImg,Object.getPrototypeOf(i));
resolve(webpImg);
};
};
reader.onerror=reject;
reader.readAsDataURL(webpBlob);
});
}

function flipHorizontally() {
var activeObject=canvas.getActiveObject();
if (isImage(activeObject)) {
activeObject.set("flipX",!activeObject.flipX);
canvas.renderAll();
}
}

function flipVertically() {
var activeObject=canvas.getActiveObject();
if (isImage(activeObject)) {
activeObject.set("flipY",!activeObject.flipY);
canvas.renderAll();
}
}


document.addEventListener("DOMContentLoaded",function () {
$("crop").style.display="none";
$("cropMode").style.display="inline";

$("crop").addEventListener("click",function (event) {
$("crop").style.display="none";
$("cropMode").style.display="inline";

var left=cropFrame.left-cropActiveObject.left;
var top=cropFrame.top-cropActiveObject.top;

left*=1;
top*=1;

var width=cropFrame.width*1;
var height=cropFrame.height*1;

cropImage(
cropActiveObject,
cropFrame.left,
cropFrame.top,
parseInt(cropFrame.scaleY*height),
parseInt(width*cropFrame.scaleX)
);
if (cropModeClear()) {
return true;
}
});

$("cropMode").addEventListener("click",function () {
$("crop").style.display="inline";
$("cropMode").style.display="none";
$("crop").classList.add("toggled");

if (canvas.getActiveObject()) {
if (cropModeClear()) {
return true;
}

if(isImage(canvas.getActiveObject())){
imageLogger.debug("canvas.getActiveObject().type",canvas.getActiveObject().type);
}else{
createToast("Select Image!",canvas.getActiveObject().type);
$("crop").style.display="none";
$("cropMode").style.display="inline";
return;
}

cropActiveObject=canvas.getActiveObject();
cropFrame=new fabric.Rect({
fill: "rgba(0,0,0,0)",
originX: "left",
originY: "top",
stroke: "rgba(0,0,0,0)",
strokeWidth: 0,
width: 1,
height: 1,
borderColor: "#36fd00",
cornerColor: "green",
hasRotatingPoint: false,
selectable: true,
});

cropFrame.left=canvas.getActiveObject().left;
cropFrame.top=canvas.getActiveObject().top;
cropFrame.width=canvas.getActiveObject().width*canvas.getActiveObject().scaleX;
cropFrame.height=canvas.getActiveObject().height*canvas.getActiveObject().scaleY;

canvas.add(cropFrame);
canvas.setActiveObject(cropFrame);
canvas.renderAll();
} else {
createToast("Select Image!","");
$("crop").style.display="none";
$("cropMode").style.display="inline";
}
});
});



function cropImage(png,left,top,height,width) {
if (top<png.top) {
height=height-(png.top-top);
top=png.top;
}
if (left<png.left) {
width=width-(png.left-left);
left=png.left;
}
if (top+height>png.top+png.height*png.scaleY)
height=png.top+png.height*png.scaleY-top;
if (left+width>png.left+png.width*png.scaleX)
width=png.left+png.width*png.scaleX-left;

var tempCanvas=new fabric.Canvas(document.createElement("canvas"));
tempCanvas.setWidth(png.width*png.scaleX);
tempCanvas.setHeight(png.height*png.scaleY);

var clonedObject=fabric.util.object.clone(png);
clonedObject.set({left: 0,top: 0});

if (clonedObject.clipPath) {
clonedObject.clipPath=clonedObject.clipPath.clone();
}

tempCanvas.add(clonedObject);
tempCanvas.renderAll();

fabric.Image.fromURL(
tempCanvas.toDataURL({format: "webp",multiplier: 2}),
function (img) {
var scaledLeft=(left-png.left)*2;
var scaledTop=(top-png.top)*2;
var scaledWidth=width*2;
var scaledHeight=height*2;

img.set("left",-scaledLeft);
img.set("top",-scaledTop);
var canvasCrop=new fabric.Canvas("canvasCrop");
canvasCrop.setHeight(scaledHeight);
canvasCrop.setWidth(scaledWidth);
canvasCrop.add(img);
canvasCrop.renderAll();

fabric.Image.fromURL(
canvasCrop.toDataURL({format: "webp",multiplier: 1}),
function (croppedImg) {
croppedImg.set({
left: left,
top: top,
scaleX: 0.5,
scaleY: 0.5,
});

if (png.clipPath) {
var clonedClipPath=fabric.util.object.clone(png.clipPath);
if (clonedClipPath) {
croppedImg.clipPath=clonedClipPath;
}
}

replaceGuids(png.guid,croppedImg);
canvas.add(croppedImg).renderAll();
canvas.remove(cropActiveObject);
canvas.setActiveObject(croppedImg);
canvas.renderAll();
updateLayerPanel();
}
);
}
);
}

function getObjLeft(objWidth) {
return canvas.getWidth()/2-objWidth/2;
}

function getObjTop(objHeight) {
return canvas.getHeight()/2-objHeight/2;
}



function canvas2DataURL(multiplier,format) {
return canvas.toDataURL({
format: format,
multiplier: multiplier
});
}


function getCropAndDownloadLinkByMultiplier(multiplier,format) {
var cropped=canvas.toDataURL({
format: format,
multiplier: multiplier
});

function getFormattedDateTime() {
var date=new Date();
var yyyy=date.getFullYear();
var MM=('0'+(date.getMonth()+1)).slice(-2);
var dd=('0'+date.getDate()).slice(-2);
var hh=('0'+date.getHours()).slice(-2);
var mm=('0'+date.getMinutes()).slice(-2);
var ss=('0'+date.getSeconds()).slice(-2);
var SSS=('00'+date.getMilliseconds()).slice(-3);
return `${yyyy}${MM}${dd}_${hh}${mm}${ss}_${SSS}`;
}

var link=document.createElement('a');
link.download='DESU-'+getFormattedDateTime()+'.'+format;
link.href=cropped;
return link;
}
function getCropAndDownloadLink() {
var a5WidthInches=148/25.4;
var a5HeightInches=210/25.4;

var dpi=parseFloat($('outputDpi').value);
var canvasWidthPixels=canvas.width;
var canvasHeightPixels=canvas.height;

var targetWidthPixels=a5WidthInches*dpi;
var targetHeightPixels=a5HeightInches*dpi;

if (canvasWidthPixels>canvasHeightPixels) {
targetWidthPixels=a5HeightInches*dpi;
targetHeightPixels=a5WidthInches*dpi;
}

var multiplierWidth=targetWidthPixels/canvasWidthPixels;
var multiplierHeight=targetHeightPixels/canvasHeightPixels;
var multiplier=Math.max(multiplierWidth,multiplierHeight);

return getCropAndDownloadLinkByMultiplier(multiplier,'png');
}


function clipCopy() {
removeGrid();
var link=getCropAndDownloadLink();
fetch(link.href)
.then(res=>res.blob())
.then(blob=>{
const item=new ClipboardItem({"image/png": blob});
navigator.clipboard.write([item]).then(function () {
createToast("Success","Image copied to clipboard successfully!");
},function (error) {
createToastError("Error","Unable to write to clipboard. Error");
});
});
if (isGridVisible) {
drawGrid();
isGridVisible=true;
}
}

function cropAndDownload() {
removeGrid();
var link=getCropAndDownloadLink();
link.click();
if (isGridVisible) {
drawGrid();
isGridVisible=true;
}
}


function getLink(dataURL) {
const link=document.createElement('a');
link.href=dataURL;
link.download='selected-image.png';
return link;
}



function getWidth(fabricImage) {
const img=fabricImage.getElement();
if (img.naturalWidth) {
return img.naturalWidth;
} else {
return fabricImage.width;
}
}

function getHeight(fabricImage) {
const img=fabricImage.getElement();
if (img.naturalHeight) {
return img.naturalHeight;
} else {
return fabricImage.height;
}
}

function imageObject2Base64ImageEffectKeep(layer,scaleFactor=1) {
if (layer.type==='image'&&layer._element) {
const imgElement=layer._element;
const originalWidth=imgElement.naturalWidth||imgElement.width;
const originalHeight=imgElement.naturalHeight||imgElement.height;

const offscreenCanvas=createOffscreenCanvas(originalWidth,originalHeight);
const ctx=offscreenCanvas.getContext('2d');

ctx.drawImage(imgElement,0,0,originalWidth,originalHeight);
return offscreenCanvas.toDataURL('image/png');
} else {
const {width,height,scaleX,scaleY,clipPath,left,top}=layer;
const pixelRatio=window.devicePixelRatio||1;
const enhancedScaleFactor=scaleFactor*2*pixelRatio;
const offscreenCanvas=createOffscreenCanvas(
Math.ceil(width*scaleX*enhancedScaleFactor),
Math.ceil(height*scaleY*enhancedScaleFactor)
);
renderLayerToCanvas(offscreenCanvas,layer,enhancedScaleFactor,left,top);
return offscreenCanvas.toDataURL('image/png');
}
}

function createOffscreenCanvas(width,height) {
const canvas=document.createElement('canvas');
canvas.width=width;
canvas.height=height;
return canvas;
}

function renderLayerToCanvas(canvas,layer,scaleFactor,left,top) {
const ctx=canvas.getContext('2d');
const originalClipPath=layer.clipPath;
layer.clipPath=null;

ctx.fillStyle='white';
ctx.fillRect(0,0,canvas.width,canvas.height);
ctx.scale(scaleFactor,scaleFactor);
ctx.translate(-left,-top);
layer.render(ctx);

layer.clipPath=originalClipPath;
}

function imageObject2Base64Image(object) {
imageObject2Base64Image(object,1.0);
}

function imageObject2Base64Image(object,scale=1.0) {
try {
const src=object.getSrc();
if (!src) {
throw new Error("Image source is not defined.");
}

const imageFormat=src.split('.').pop().toLowerCase();
const supportedFormats=['png','jpeg','jpg','webp'];
const format=supportedFormats.includes(imageFormat) ? imageFormat : 'png';

const base64Image=object.toDataURL({
format: format,
quality: scale
});

return base64Image;
} catch (error) {
imageLogger.error("Error converting image object to Base64:",error);
return null;
}
}

function imageObject2DataURL(activeObject) {
if (activeObject&&activeObject.type==='image') {
const originalWidth=activeObject.width;
const originalHeight=activeObject.height;
const tempCanvas=document.createElement('canvas');
const tempContext=tempCanvas.getContext('2d');
tempCanvas.width=originalWidth;
tempCanvas.height=originalHeight;
tempContext.drawImage(activeObject.getElement(),0,0,originalWidth,originalHeight);
return tempCanvas.toDataURL('image/png');
}
return null;
}




function imageObject2DataURLByCrop(activeObject) {
imageLogger.debug("Function start: imageObject2DataURLByCrop");
imageLogger.debug("activeObject:",activeObject);

if (activeObject&&activeObject.isPanel) {
var dataURL=canvas2DataURL(3,"png");

return new Promise((resolve,reject)=>{
var image=new Image();
image.crossOrigin="Anonymous";
image.src=dataURL;

image.onload=function() {
var tempCanvas=document.createElement('canvas');
var context=tempCanvas.getContext('2d');
tempCanvas.width=image.width;
tempCanvas.height=image.height;
context.drawImage(image,0,0);
var objectWidth=activeObject.width*activeObject.scaleX;
var objectHeight=activeObject.height*activeObject.scaleY;
var objectLeft=activeObject.left;
var objectTop=activeObject.top;

imageLogger.debug("objectWidth  activeObject.strokeWidth",objectWidth,activeObject.strokeWidth);
imageLogger.debug("objectHeight activeObject.strokeWidth",objectHeight,activeObject.strokeWidth);

var scaleX=tempCanvas.width/activeObject.canvas.width;
var scaleY=tempCanvas.height/activeObject.canvas.height;
var cropX=(objectLeft)*scaleX;
var cropY=(objectTop)*scaleY;
var cropWidth=(objectWidth*scaleX)+(activeObject.strokeWidth*scaleX);
var cropHeight=(objectHeight*scaleY)+(activeObject.strokeWidth*scaleX);
var cropCanvas=document.createElement('canvas');
var cropContext=cropCanvas.getContext('2d');
cropCanvas.width=cropWidth;
cropCanvas.height=cropHeight;
cropContext.drawImage(tempCanvas,cropX,cropY,cropWidth,cropHeight,0,0,cropWidth,cropHeight);
var croppedDataURL=cropCanvas.toDataURL("image/png");
resolve(croppedDataURL);
};

image.onerror=function(err) {
imageLogger.error("Image loading error:",err);
reject(err);
};
});
}
imageLogger.debug("Function end: imageObject2DataURLByCrop (no valid activeObject)");
return Promise.resolve(null);
}


function createCanvasFromFabricImage(fabricImage) {
const tempCanvas=document.createElement("canvas");
tempCanvas.width=canvas.width;
tempCanvas.height=canvas.height;
const tempCtx=tempCanvas.getContext("2d");

tempCtx.save();

tempCtx.translate(fabricImage.left,fabricImage.top);
tempCtx.rotate(fabricImage.angle*Math.PI/180);
tempCtx.scale(fabricImage.scaleX,fabricImage.scaleY);

if (fabricImage.type==='image') {
tempCtx.drawImage(
fabricImage._element,
0,
0,
fabricImage.width,
fabricImage.height
);
} else if (fabricImage.type==='rect') {
if (typeof fabricImage.fill==='string') {
tempCtx.fillStyle=fabricImage.fill;
tempCtx.fillRect(
0,
0,
fabricImage.width,
fabricImage.height
);
} else if (fabricImage.fill instanceof fabric.Gradient) {
const grad=tempCtx.createLinearGradient(
0,
0,
fabricImage.width,
0
);
fabricImage.fill.colorStops.forEach(stop=>{
grad.addColorStop(stop.offset,stop.color);
});
tempCtx.fillStyle=grad;
tempCtx.fillRect(
0,
0,
fabricImage.width,
fabricImage.height
);
}
}
tempCtx.restore();

return tempCanvas;
}











function enhanceDarkRegionsCPU(imageData,intensity) {
const data=imageData.data;
for (let i=0;i<data.length;i+=4) {
const r=data[i];
const g=data[i+1];
const b=data[i+2];
const brightness=(r+g+b)/3;
if (brightness<200) {
const darkFactor=Math.max(0,1-Math.pow(intensity*0.2,1.5));
data[i]*=darkFactor;
data[i+1]*=darkFactor;
data[i+2]*=darkFactor;
}
}
return imageData;
}





async function fabricImage2ImageData(fabricImage) {
const img=fabricImage.getElement();
// console.log('Original image size:', {
//   naturalWidth: img.naturalWidth,
//   naturalHeight: img.naturalHeight,
//   width: fabricImage.width,
//   height: fabricImage.height,
//   scaleX: fabricImage.scaleX,
//   scaleY: fabricImage.scaleY
// });
// console.log('Canvas size:', {
//   width: canvas.width,
//   height: canvas.height
// });

const tempCanvas=document.createElement('canvas');
tempCanvas.width=img.naturalWidth;
tempCanvas.height=img.naturalHeight;
const tempCtx=tempCanvas.getContext('2d',{
alpha: true,
willReadFrequently: true
});

tempCtx.drawImage(img,0,0,img.naturalWidth,img.naturalHeight);
return tempCtx.getImageData(0,0,img.naturalWidth,img.naturalHeight);
}



async function enhanceDarkImage() {
const loading=OP_showLoading({
icon: 'process',
step: 'Step1',
substep: 'Start up',
progress: 0
});
await new Promise(resolve=>setTimeout(resolve,10));


try {
const activeObject=canvas.getActiveObject();
const img=activeObject.getElement();
const originalScaleX=activeObject.scaleX||1;
const originalScaleY=activeObject.scaleY||1;
const intensity=parseFloat($('effectEnhanceDarkIntensity').value);
const originalImageData=await fabricImage2ImageData(activeObject);

OP_updateLoadingState(loading,{
icon: 'process',
step: 'Step2',
substep: 'Dark enhance',
progress: 25
});
await new Promise(resolve=>setTimeout(resolve,10));


const processedImageData=enhanceDarkRegionsCPU(originalImageData,intensity);

OP_updateLoadingState(loading,{
icon: 'process',
step: 'Step3',
substep: 'Image marge',
progress: 90
});
await new Promise(resolve=>setTimeout(resolve,10));

const tempCanvas=document.createElement('canvas');
tempCanvas.width=img.naturalWidth;
tempCanvas.height=img.naturalHeight;

const tempCtx=tempCanvas.getContext('2d',{
alpha: true,
willReadFrequently: true
});
tempCtx.imageSmoothingEnabled=true;
tempCtx.imageSmoothingQuality='high';
tempCtx.putImageData(processedImageData,0,0);

const webpDataUrl=tempCanvas.toDataURL('image/webp',1.0);


await new Promise((resolve)=>{
fabric.Image.fromURL(webpDataUrl,img=>{
img.set({
left: activeObject.left,
top: activeObject.top,
scaleX: originalScaleX,
scaleY: originalScaleY
});
copy(activeObject,img);
canvas.remove(activeObject);
canvas.add(img);
canvas.setActiveObject(img);
canvas.renderAll();
updateLayerPanel();
resolve();
});
});

} catch(err) {
imageLogger.error('Process error:',err);
} finally {
OP_hideLoading(loading);
}
}

function hexToRgba(hex,opacity=1) {
if (hex.startsWith('rgba')) {
const [r,g,b]=hex.match(/\d+/g);
return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

if (hex.startsWith('rgb')) {
const [r,g,b]=hex.match(/\d+/g);
return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

hex=hex.replace('#','');
const r=parseInt(hex.substring(0,2),16);
const g=parseInt(hex.substring(2,4),16);
const b=parseInt(hex.substring(4,6),16);
return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

function rgbToHex(color) {
if (!color) {
return '#000000';
}

if (color.startsWith('#')) {
return color;
}

let match=color.match(/^rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)$/);
if (!match) {
return color;
}

function convert(color) {
let hex=parseInt(color).toString(16);
return hex.length===1 ? '0'+hex : hex;
}

return '#'+convert(match[1])+convert(match[2])+convert(match[3]);
}

function rgbaToHex(color) {
if (!color) return '#000000';
if (color.startsWith('#')) return color;

const match=color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d*\.?\d+))?\)/);
if (!match) return '#000000';

const r=parseInt(match[1]);
const g=parseInt(match[2]);
const b=parseInt(match[3]);

const toHex=(n)=>{
const hex=n.toString(16);
return hex.length===1 ? '0'+hex : hex;
};

return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}