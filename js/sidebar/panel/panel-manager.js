// function handleSelection(e) {
//   var selectedObject = e.target;
//   updateControls(selectedObject);
// }

document.addEventListener('DOMContentLoaded',function() {
$("canvas-container").addEventListener(
"dragover",
function (e) {
e.preventDefault();
},
false
);

$("canvas-container").addEventListener("drop",async function (e) {
e.preventDefault();
var file=e.dataTransfer.files[0];
var canvasElement=canvas.getElement();
var rect=canvasElement.getBoundingClientRect();
var x=e.clientX-rect.left;
var y=e.clientY-rect.top;


if (file.type==='image/svg+xml') {
var reader=new FileReader();
reader.onload=function(event) {
var svgText=event.target.result;
if (stateStack.length>=2&&getObjectCount()>0) {
var canvasX=x/canvasContinerScale;
var canvasY=y/canvasContinerScale;
putImageInFrame(svgText,canvasX,canvasY);
} else {

// SVGをFabric.jsのCanvasに読み込む
fabric.loadSVGFromString(svgText,function(objects,options) {
var loadedObject=fabric.util.groupSVGElements(objects,options);
resizeCanvasByNum(loadedObject.width,loadedObject.height);
initialPutImage(loadedObject,0,0);
canvas.add(loadedObject);
canvas.renderAll();
});
}
};
reader.readAsText(file);
return;
}

// WebPに変換
var webpFile;
try {
webpFile=await imgFile2webpFile(file);
} catch (error) {
console.error("Failed to convert to WebP",error);
return;
}

var reader=new FileReader();
reader.onload=function (f) {
var data=f.target.result;

fabric.Image.fromURL(data,function (img) {
console.log("drop stateStack.length",stateStack.length);
if (stateStack.length>=2&&getObjectCount()>0) {
var canvasX=x/canvasContinerScale;
var canvasY=y/canvasContinerScale;
putImageInFrame(img,canvasX,canvasY);
} else {
// console.log("drop img.width, img.height", img.width, img.height);
resizeCanvasByNum(img.width,img.height);
initialPutImage(img,0,0);
}

setImage2ImageInitPrompt(img);
});
};

reader.readAsDataURL(webpFile);
},
false
);

});

function initialPutImage(img) {
img.set({
left: 0,
top: 0,
});
setNotSave(img);
canvas.add(img);

canvas.setActiveObject(img);
saveInitialState(img);
canvas.renderAll();

updateLayerPanel();
saveStateByManual();
return img;
}

function replaceImageObject(oldImageObject,newImageObject,Type){
oldImageObject.visible;

if (Type=='Upscaler') {
const oldDisplayWidth=oldImageObject.width*oldImageObject.scaleX;
const oldDisplayHeight=oldImageObject.height*oldImageObject.scaleY;

newImageObject.set({
left: oldImageObject.left,
top: oldImageObject.top,
scaleX: oldDisplayWidth/newImageObject.width,
scaleY: oldDisplayHeight/newImageObject.height,
});

console.log("newImageObject,",newImageObject);
}else{
newImageObject.set({
left: oldImageObject.left,
top: oldImageObject.top,
scaleX: oldImageObject.scaleX,
scaleY: oldImageObject.scaleY,
});
}

saveInitialState(newImageObject);
canvas.add(newImageObject);
avtive(newImageObject);
updateLayerPanel();
}


function putImageInFrame(imgOrSvg,x,y,isNotActive=false,notReplace=false,isFit=true,targetLayer=null) {
let obj;

if (typeof imgOrSvg==='string'&&imgOrSvg.startsWith('<svg')) {
fabric.loadSVGFromString(imgOrSvg,function(objects,options) {
obj=fabric.util.groupSVGElements(objects,options);
placeObject(obj,x,y,isNotActive,true,isFit,targetLayer);
});
} else {
obj=imgOrSvg;
placeObject(obj,x,y,isNotActive,notReplace,isFit,targetLayer);
}

function placeObject(obj,x,y,isNotActive,notReplace,isFit,targetLayer) {
if(isFit){
obj.set({left: x,top: y});
}
setNotSave(obj);

if(notReplace){
//skip
}else{
canvas.add(obj);
}

var targetFrameIndex=targetLayer?canvas.getObjects().indexOf(targetLayer):findTargetFrame(x,y);
console.log("targetFrameIndex",targetFrameIndex);
if (targetFrameIndex!==-1) {
var targetFrame=canvas.item(targetFrameIndex);
var frameCenterX=targetFrame.left+(targetFrame.width*targetFrame.scaleX)/2;
var frameCenterY=targetFrame.top+(targetFrame.height*targetFrame.scaleY)/2;
var scaleToFitX=(targetFrame.width*targetFrame.scaleX)/obj.width;
var scaleToFitY=(targetFrame.height*targetFrame.scaleY)/obj.height;
var scaleToFit=Math.max(scaleToFitX,scaleToFitY);
moveSettings(obj,targetFrame);
if(isFit){
obj.set({
left: frameCenterX-(obj.width*scaleToFit)/2,
top: frameCenterY-(obj.height*scaleToFit)/2,
scaleX: scaleToFit*1.05,
scaleY: scaleToFit*1.05,
});
}
if (obj.name) {
obj.name=targetFrame.name+"-"+obj.name;
} else {
obj.name=targetFrame.name+" In Image";
}
setGUID(targetFrame,obj);
} else {
if(isFit){
var scaleToCanvasWidth=300/obj.width;
var scaleToCanvasHeight=300/obj.height;
var scaleToCanvas=Math.min(scaleToCanvasWidth,scaleToCanvasHeight);

obj.set({
left: 50,
top: 50,
scaleX: scaleToCanvas,
scaleY: scaleToCanvas,
});
}
}

if (!isNotActive) {
canvas.setActiveObject(obj);
}
saveInitialState(obj);

canvas.renderAll();
updateLayerPanel();
saveStateByManual();
return obj;
}

return obj;
}


function findTargetFrame(x,y) {
//console.log( "findTargetFrame:x y, ", x, " ", y );

let objects=canvas.getObjects().reverse();
for (let i=0;i<objects.length;i++) {
if (isShapes(objects[i])) {
let frameBounds=objects[i].getBoundingRect(true);
if (
x>=frameBounds.left&&
x<=frameBounds.left+frameBounds.width&&
y>=frameBounds.top&&
y<=frameBounds.top+frameBounds.height
) {
return canvas.getObjects().length-1-i;
}
}
}
return-1;
}

function isWithin(image,frame) {
let frameBounds=frame.getBoundingRect(true);
let imageBounds=image.getBoundingRect(true);

let within=
imageBounds.left>=frameBounds.left&&
imageBounds.top>=frameBounds.top&&
imageBounds.left+imageBounds.width*image.scaleX<=
frameBounds.left+frameBounds.width&&
imageBounds.top+imageBounds.height*image.scaleY<=
frameBounds.top+frameBounds.height;
return within;
}

function adjustImageToFitFrame(image,frame) {
let frameBounds=frame.getBoundingRect();
let scale=Math.min(
frameBounds.width/image.getScaledWidth(),
frameBounds.height/image.getScaledHeight()
);
image.set({
left: frameBounds.left+(frameBounds.width-image.width*scale)/2,
top: frameBounds.top+(frameBounds.height-image.height*scale)/2,
scaleX: scale,
scaleY: scale,
});
}



/** Load SVG(Verfical, Landscope) */
function loadSVGPlusReset(svgString,isLand=false) {
initImageHistory();
saveState();
changeDoNotSaveHistory();
// console.log("svgPagging", svgPagging);

fabric.loadSVGFromString(svgString,function (objects,options) {
resizeCanvasToObject(options.width,options.height);

var strokeWidthScale=canvas.width/700;
var strokeWidth=2*strokeWidthScale;
var canvasUsableHeight=canvas.height-svgPagging;
var canvasUsableWidth=canvas.width-svgPagging;
var overallScaleX=canvasUsableWidth/options.width;
var overallScaleY=canvasUsableHeight/options.height;
var scaleToFit=Math.min(overallScaleX,overallScaleY);
var offsetVerticalY=(svgPagging/1.5)+((canvasUsableHeight-options.height*overallScaleY)/2)+strokeWidth;
var offsetHorizontalY=(svgPagging/2)+((canvasUsableHeight-options.height*overallScaleY)/2)+strokeWidth;
var offsetVerticalX=(svgPagging/2)+((canvasUsableWidth-options.width*overallScaleX)/2);
var offsetHorizontalX=(svgPagging/1.5)+((canvasUsableWidth-options.width*overallScaleX)/2);
var bgColorInput=$("bg-color");
canvas.backgroundColor=bgColorInput.value;

objects.reverse().forEach(function (obj,index) {
if (obj.type==="path") {
var points=obj.path.map(function (item) {
return {
x: item[item.length-2],
y: item[item.length-1],
command: item[0],
};
});

var threshold=Math.max(obj.width,obj.height)*0.004;
var startX=0;
var startY=0;

var vertices=points.filter(function (point,index,self) {
if (point.command==="M") {
startX=point.x;
startY=point.y;
return true;
} else if (point.command==="C") {
if (index===0) {
return true;
}
var prevPoint=self[index-1];
var xDiff=Math.abs(point.x-prevPoint.x);
var yDiff=Math.abs(point.y-prevPoint.y);

if (xDiff<threshold&&yDiff<threshold) {
return false;
}

var xDiff=Math.abs(point.x-startX);
var yDiff=Math.abs(point.y-startY);
if (xDiff<threshold&&yDiff<threshold) {
return false;
}
return true;
}
return false;
});

var polygon=new fabric.Polygon(vertices,{
isPanel: true,
scaleX: scaleToFit,
scaleY: scaleToFit,
top: obj.top*scaleToFit+offsetY,
left: obj.left*scaleToFit+offsetX,
stroke: obj.stroke,
strokeWidth: strokeWidth,
selectable: false,
hasControls: true,
lockMovementX: false,
lockMovementY: false,
lockRotation: false,
lockScalingX: false,
lockScalingY: false,
edit: false,
hasBorders: true,
cornerStyle: "rect",
objectCaching: false,

controls: fabric.Object.prototype.controls,
});
setText2ImageInitPrompt(polygon);
canvas.add(polygon);
} else {

obj.isPanel=true;
obj.scaleX=scaleToFit;
obj.scaleY=scaleToFit;
if(isLand){
obj.top=obj.top*scaleToFit+offsetHorizontalY-(strokeWidth);
obj.left=obj.left*scaleToFit+offsetHorizontalX;
}else{
obj.top=obj.top*scaleToFit+offsetVerticalY-(strokeWidth);
obj.left=obj.left*scaleToFit+offsetVerticalX;
}

obj.setCoords();
obj.strokeWidth=strokeWidth;
obj.hasControls=true;
obj.lockMovementX=false;
obj.lockMovementY=false;
obj.lockRotation=false;
obj.lockScalingX=false;
obj.lockScalingY=false;
obj.objectCaching=false;
canvas.add(obj);
obj.selectable=false;
}
});

panelStrokeChange()
canvas.renderAll();
});

resizeCanvas(canvas.width,canvas.height);
changeDoSaveHistory();
saveState();

updateLayerPanel();
}






/** Disallow drag-on-drop. */
document.addEventListener("DOMContentLoaded",function () {
var svgPreviewArea=$("svg-container-vertical");
svgPreviewArea.addEventListener(
"mousedown",
function (event) {
event.preventDefault();
event.stopPropagation();
},
false
);
});

/** Disallow drag-on-drop. */
document.addEventListener("DOMContentLoaded",function () {
var svgPreviewArea=$("svg-container-landscape");
svgPreviewArea.addEventListener(
"mousedown",
function (event) {
event.preventDefault();
event.stopPropagation();
},
false
);
});

document.addEventListener("DOMContentLoaded",function () {
var svgPreviewArea=$("speech-bubble-preview");
svgPreviewArea.addEventListener(
"mousedown",
function (event) {
if (
!event.target.closest("input[type='range']")&&
!event.target.closest("input[type='number']")
) {
event.preventDefault();
event.stopPropagation();
}
},
false
);
});


function canvasInScale(originalWidth,originalHeight){
const canvasWidth=canvas.width;
const canvasHeight=canvas.height;
const scaleX=(canvasWidth*0.4)/originalWidth;
const scaleY=(canvasHeight*0.4)/originalHeight;
const scale=Math.min(scaleX,scaleY);
return scale;
}


function Edit() {
var poly=canvas.getActiveObject();
if (!poly) return;

poly.edit=!poly.edit;
if (poly.edit) {
var lastControl=poly.points.length-1;
poly.cornerStyle="circle";
poly.cornerColor="rgba(0,0,255,0.5)";
poly.controls=poly.points.reduce(function (acc,point,index) {
acc["p"+index]=new fabric.Control({
positionHandler: polygonPositionHandler,
actionHandler: anchorWrapper(
index>0 ? index-1 : lastControl,
actionHandler
),
actionName: "modifyPolygon",
pointIndex: index,
});
return acc;
},{});
} else {
poly.cornerStyle="rect";
poly.controls=fabric.Object.prototype.controls;
}
poly.hasBorders=!poly.edit;
canvas.requestRenderAll();
updateLayerPanel();
}

function changePanelStrokeWidth(value) {
var activeObject=canvas.getActiveObject();
if (isPanel(activeObject)) {
activeObject.set({
strokeWidth: parseFloat(value),
strokeUniform: true,
});
canvas.requestRenderAll();
}
}
function changePanelStrokeColor(value) {
var activeObject=canvas.getActiveObject();
if (isPanel(activeObject)) {
activeObject.set("stroke",value);
canvas.requestRenderAll();
}
}
function changePanelOpacity(value) {
var activeObject=canvas.getActiveObject();
if (isPanel(activeObject)) {
const opacity=value/100;
activeObject.set("opacity",opacity);
canvas.requestRenderAll();
}
}
function changePanelFillColor(value) {
var activeObject=canvas.getActiveObject();
if (isPanel(activeObject)) {
activeObject.set("fill",value);
canvas.requestRenderAll();
}
}


function panelStrokeChange() {
var strokeWidthValue=$("panelStrokeWidth").value;
var strokeColorValue=$("panelStrokeColor").value;

canvas.getObjects().forEach(function (obj) {
if (isPanel(obj)) {
obj.set({
strokeWidth: parseFloat(strokeWidthValue),
strokeUniform: true,
});
obj.set("stroke",strokeColorValue);
}
});
canvas.requestRenderAll();
}


function panelAllChange() {
var strokeWidthValue=$("panelStrokeWidth").value;
var strokeColorValue=$("panelStrokeColor").value;
var opacityValue=$("panelOpacity").value;
const opacity=opacityValue/100;
var fillValue=$("panelFillColor").value;

canvas.getObjects().forEach(function (obj) {
if (isPanel(obj)) {
obj.set({
strokeWidth: parseFloat(strokeWidthValue),
strokeUniform: true,
});
obj.set("stroke",strokeColorValue);
obj.set("fill",fillValue);
obj.set("opacity",opacity);
}
});
canvas.requestRenderAll();
}

function setPanelValue(obj) {
// console.log("setPanelValue");
var strokeWidthValue=$("panelStrokeWidth").value;
var strokeColorValue=$("panelStrokeColor").value;
var opacityValue=$("panelOpacity").value;
const opacity=opacityValue/100;
var fillValue=$("panelFillColor").value;

if (isPanel(obj)) {
// console.log("setPanelValue isPanel");

obj.set({
strokeWidth: parseFloat(strokeWidthValue),
strokeUniform: true,
});
obj.set("stroke",strokeColorValue);
obj.set("fill",fillValue);
obj.set("opacity",opacity);

canvas.requestRenderAll();
}
}

function polygonPositionHandler(dim,finalMatrix,fabricObject) {
var x=fabricObject.points[this.pointIndex].x-fabricObject.pathOffset.x,
y=fabricObject.points[this.pointIndex].y-fabricObject.pathOffset.y;
return fabric.util.transformPoint(
{x: x,y: y},
fabric.util.multiplyTransformMatrices(
fabricObject.canvas.viewportTransform,
fabricObject.calcTransformMatrix()
)
);
}

function getObjectSizeWithStroke(object) {
var stroke=new fabric.Point(
object.strokeUniform ? 1/object.scaleX : 1,
object.strokeUniform ? 1/object.scaleY : 1
).multiply(object.strokeWidth);
return new fabric.Point(object.width+stroke.x,object.height+stroke.y);
}

function actionHandler(eventData,transform,x,y) {
var polygon=transform.target,
currentControl=polygon.controls[polygon.__corner],
mouseLocalPosition=polygon.toLocalPoint(
new fabric.Point(x,y),
"center",
"center"
),
polygonBaseSize=getObjectSizeWithStroke(polygon),
size=polygon._getTransformedDimensions(0,0),
finalPointPosition={
x:
(mouseLocalPosition.x*polygonBaseSize.x)/size.x+
polygon.pathOffset.x,
y:
(mouseLocalPosition.y*polygonBaseSize.y)/size.y+
polygon.pathOffset.y,
};
polygon.points[currentControl.pointIndex]=finalPointPosition;
polygon.dirty=true;
return true;
}

function anchorWrapper(anchorIndex,fn) {
return function (eventData,transform,x,y) {
var fabricObject=transform.target,
absolutePoint=fabric.util.transformPoint(
{
x: fabricObject.points[anchorIndex].x-fabricObject.pathOffset.x,
y: fabricObject.points[anchorIndex].y-fabricObject.pathOffset.y,
},
fabricObject.calcTransformMatrix()
),
actionPerformed=fn(eventData,transform,x,y),
newDim=fabricObject._setPositionDimensions({}),
polygonBaseSize=getObjectSizeWithStroke(fabricObject),
newX=
(fabricObject.points[anchorIndex].x-fabricObject.pathOffset.x)/
polygonBaseSize.x,
newY=
(fabricObject.points[anchorIndex].y-fabricObject.pathOffset.y)/
polygonBaseSize.y;
fabricObject.setPositionByOrigin(absolutePoint,newX+0.5,newY+0.5);
return actionPerformed;
};
}

document.addEventListener('DOMContentLoaded',function() {
$("view_layers_checkbox").addEventListener("change",function () {
changeView("layer-panel",this.checked);
});
$("view_controles_checkbox").addEventListener("change",function () {
changeView("controls",this.checked);
});
});







let areNamesVisible=false;
const promptTexts=[];

function View() {
if (areNamesVisible) {
// Clear the contextTop
canvas.clearContext(canvas.contextTop);
promptTexts.length=0;
} else {
canvas.getObjects().forEach((obj)=>{
if (isPanel(obj)) {
let viewText=obj.name+"\n\nPrompt\n"+(obj.text2img_prompt||'nothing');
const wrappedText=wrapText(viewText,obj.width*obj.scaleX-20,16);
const text=new fabric.Text(wrappedText,{
left: obj.left+10,
top: obj.top+(obj.height*obj.scaleY/4),
fontSize: 16,
fontFamily: 'Arial, sans-serif',
fontWeight: 'normal',
fill: "rgba(0, 0, 0, 0.8)",
backgroundColor: "rgba(255, 255, 255, 0.7)",
selectable: false,
evented: false,
lineHeight: 1.3,
textAlign: 'left',
padding: 5,
});
promptTexts.push(text);
}
});
}
areNamesVisible=!areNamesVisible;
canvas.renderAll();
}


// カスタムレンダリングメソッドを追加
fabric.util.object.extend(fabric.Canvas.prototype,{
renderTop: function () {
if (areNamesVisible) {
const ctx=this.contextTop;
ctx.save();
ctx.transform.apply(ctx,this.viewportTransform);
promptTexts.forEach((text)=>{
ctx.save();
text.transform(ctx);
text._render(ctx);
ctx.restore();
});
ctx.restore();
}
}
});

// renderAllメソッドをオーバーライド
const originalRenderAll=fabric.Canvas.prototype.renderAll;
fabric.Canvas.prototype.renderAll=function() {
originalRenderAll.call(this);
this.renderTop();
};

function wrapText(text,width,fontSize) {
const words=text.split(' ');
let lines=[];
let currentLine=words[0];

for (let i=1;i<words.length;i++) {
const word=words[i];
const testLine=currentLine+' '+word;
const testWidth=getTextWidth(testLine,fontSize);
if (testWidth>width) {
lines.push(currentLine);
currentLine=word;
} else {
currentLine=testLine;
}
}
lines.push(currentLine);
return lines.join('\n');
}

function getTextWidth(text,fontSize) {
const canvas=document.createElement('canvas');
const context=canvas.getContext('2d');
context.font=fontSize+'px Arial';
const metrics=context.measureText(text);
return metrics.width;
}