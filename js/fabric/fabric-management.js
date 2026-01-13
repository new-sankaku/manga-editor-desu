var lastActiveObjectState=null;

canvas.on('selection:created',function(event) {
eventLogger.trace('1: selection:created');
lastActiveObjectState=canvas.getActiveObject();
});
canvas.on('selection:updated',function(event) {
eventLogger.trace('2: selection:updated');
glfxReset();
lastActiveObjectState=canvas.getActiveObject();
});



canvas.on('selection:cleared',function() {
eventLogger.trace('3: selection:cleared');
glfxReset();
});
canvas.on("object:added",(e)=>{
eventLogger.trace('4: object:added');
const obj=e.target;
if (!obj.initial) {
saveInitialState(obj);
}
forcedAdjustCanvasSize();

if(currentMode==='freehand'){
changeObjectCursor('freehand',obj)
}else if(currentMode==='point'){
changeObjectCursor('point',obj)
}else if (isKnifeMode) {
changeObjectCursor('knife',obj)
obj.set({
selectable: false
});
}
});

var shiftTempDisabledMode=null;
var shiftTempDisabledKnife=false;

document.addEventListener("keydown",function(e){
if(e.key!=="Shift"||shiftTempDisabledMode!==null||shiftTempDisabledKnife)return;
if(currentMode==="freehand"||currentMode==="point"){
shiftTempDisabledMode=currentMode;
currentMode="select";
canvas.selection=true;
canvas.forEachObject(function(obj){
if(obj.excludeFromLayerPanel)return;
obj.set({selectable:true,evented:true});
});
changeDefaultCursor();
canvas.renderAll();
}else if(isKnifeMode){
shiftTempDisabledKnife=true;
canvas.selection=true;
canvas.forEachObject(function(obj){
if(obj.excludeFromLayerPanel)return;
obj.set({selectable:true,evented:true});
});
changeDefaultCursor();
canvas.renderAll();
}
});

document.addEventListener("keyup",function(e){
if(e.key!=="Shift")return;
if(shiftTempDisabledMode!==null){
currentMode=shiftTempDisabledMode;
shiftTempDisabledMode=null;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
changeCursor(currentMode);
canvas.renderAll();
}else if(shiftTempDisabledKnife){
shiftTempDisabledKnife=false;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
changeCursor("knife");
canvas.renderAll();
}
});

canvas.on("object:modified",(e)=>{
eventLogger.trace('5: object:modified');
const obj=e.target;
saveInitialState(obj);
});


canvas.on('object:added',function(e) {eventLogger.trace('6: object:added');saveStateByListener(e,'object:added');});
canvas.on('object:modified',function(e) {eventLogger.trace('7: object:modified');saveStateByListener(e,'object:modified');});
canvas.on('object:removed',function(e) {eventLogger.trace('8: object:removed');saveStateByListener(e,'object:removed');});
canvas.on('path:created',function(e) {eventLogger.trace('9: path:created');saveStateByListener(e,'path:created');});
canvas.on('canvas:cleared',function(e) {eventLogger.trace('10: canvas:cleared');saveStateByListener(e,'canvas:cleared');});



//Crop Mode from start
canvas.on('selection:cleared',function() {
eventLogger.trace('11: selection:cleared');
if (cropFrame) {
canvas.remove(cropFrame);
cropFrame=null;
$('crop').style.display='none';
}
});
canvas.on('selection:updated',function() {
eventLogger.trace('12: selection:updated');
if (cropFrame&&canvas.getActiveObject()!==cropFrame) {
canvas.remove(cropFrame);
cropFrame=null;
$('crop').style.display='none';
}
});
//Crop Mode from finish



//highligh from start
canvas.on('selection:created',function(event)  {eventLogger.trace('50: selection:created');highlightActiveLayerByCanvas(event);});
canvas.on('selection:updated',function(event)  {eventLogger.trace('51: selection:updated');highlightActiveLayerByCanvas(event);});
canvas.on('object:added',function(event)  {eventLogger.trace('52: object:added');highlightActiveLayerByCanvas(event);});
canvas.on('object:modified',function(event)  {eventLogger.trace('53: object:modified');highlightActiveLayerByCanvas(event);});
canvas.on('selection:cleared',function() {eventLogger.trace('13: selection:cleared');highlightClear();});
//highligh from finish



canvas.on("object:moving",function (e) {
if (isGridVisible) {
eventLogger.trace('14: object:moving');

debounceSnapToGrid(e.target);
}
});

canvas.on('selection:created',function(event) {
eventLogger.trace('15: selection:created');
if (event.selected&&event.selected[0]) {
updateTextControls(event.selected[0]);
}
});
canvas.on('selection:updated',function(event) {
eventLogger.trace('16: selection:updated');
if (event.selected&&event.selected[0]) {
updateTextControls(event.selected[0]);
}
});

function moveSettings(img,poly) {
eventLogger.trace('moveSettings');
eventLogger.traceWithStack('moveSettings');

updateClipPath(img,poly);

function updateOnModification() {
updateClipPath(img,poly);
canvas.renderAll();
}

img.relatedPoly=poly;
img._clipPathHandler=updateOnModification;

['moving','scaling','rotating','skewing','modified'].forEach(eventName=>{
poly.on(eventName,updateOnModification);
img.on(eventName,updateOnModification);
});

img.removeClipPathListeners=function() {
const events=['moving','scaling','rotating','skewing','modified'];
const handler=this._clipPathHandler;
if(handler){
events.forEach(eventName=>{
this.off(eventName,handler);
if(this.relatedPoly){
this.relatedPoly.off(eventName,handler);
}
});
}
delete this._clipPathHandler;
delete this.removeClipPathListeners;
};

img.removeSettings=function() {
removeGUID(this.relatedPoly,this);
if(this.removeClipPathListeners){
this.removeClipPathListeners();
}else{
const events=['moving','scaling','rotating','skewing','modified'];
const handler=this._clipPathHandler;
if(handler){
events.forEach(eventName=>{
this.off(eventName,handler);
if(this.relatedPoly){
this.relatedPoly.off(eventName,handler);
}
});
}
delete this._clipPathHandler;
}
delete this.relatedPoly;
delete this.removeSettings;
};
}

function updateClipPath(imageObj,fabricObj) {
if (fabricObj.type==='path') {
updatePathClipPath(imageObj,fabricObj);
return;
}

const matrix=fabricObj.calcTransformMatrix();
if(!fabricObj.points){
canvasLogger.error("ERROR polygonObj.points",JSON.stringify(fabricObj.points));
return;
}

const transformedPoints=fabricObj.points.map(point=>{
return fabric.util.transformPoint({
x: point.x-fabricObj.pathOffset.x,
y: point.y-fabricObj.pathOffset.y
},matrix);
});

const clipPath=new fabric.Polygon(transformedPoints,{
absolutePositioned: true,
});

clipPath.set({
left:   clipPath.left+fabricObj.strokeWidth-(fabricObj.strokeWidth*0.5),
top:    clipPath.top+fabricObj.strokeWidth-(fabricObj.strokeWidth*0.5),
scaleX: 1-(fabricObj.strokeWidth)/(clipPath.width),
scaleY: 1-(fabricObj.strokeWidth)/(clipPath.height),
absolutePositioned: true,
});

if (!clipPath.initial) {
saveInitialState(clipPath);
}

imageObj.clipPath=clipPath;
}

function updatePathClipPath(imageObj,pathObj) {
const matrix=pathObj.calcTransformMatrix();

const transformedPath=fabric.util.transformPath(
pathObj.path,
fabric.util.multiplyTransformMatrices(
matrix,
[1,0,0,1,-pathObj.pathOffset.x,-pathObj.pathOffset.y]
)
);

const clipPath=new fabric.Path(transformedPath,{
absolutePositioned: true,
fill: true,
strokeWidth: 0
});

clipPath.set({
left:   clipPath.left+pathObj.strokeWidth-(pathObj.strokeWidth*0.5),
top:    clipPath.top+pathObj.strokeWidth-(pathObj.strokeWidth*0.5),
scaleX: 1-(pathObj.strokeWidth)/(clipPath.width),
scaleY: 1-(pathObj.strokeWidth)/(clipPath.height),
absolutePositioned: true,
});

if (!clipPath.initial) {
saveInitialState(clipPath);
}

imageObj.clipPath=clipPath;
}


canvas.on("object:added",(e)=>{
eventLogger.trace('17: object:added');
if(canvas.isDrawingMode){
return;
}
if(initMessageText){
canvas.remove(initMessageText);
updateLayerPanel();
initMessageText=null;
}
const obj=e.target;
if (isPanel(obj)) {
obj.set('fill','rgba(255,255,255,0.25)');
}
});

let lastCheckObject=null;
canvas.on('mouse:down',function(e) {
eventLogger.trace('18: mouse:down');
if(canvas.isDrawingMode||isKnifeMode){
return;
}
if (e.target) {
changeDoNotSaveHistory();
e.target.originalOpacity=e.target.opacity;
e.target.opacity=0.5;
canvas.renderAll();
lastCheckObject=e.target;
}
});

canvas.on('mouse:up',function(e) {
eventLogger.trace('19: mouse:up');
if (e.target&&e.target.originalOpacity!==undefined) {
e.target.opacity=e.target.originalOpacity;
delete e.target.originalOpacity;
canvas.renderAll();
changeDoSaveHistory();
highlightActiveLayerByCanvas(e.target);
}
});

canvas.on("mouse:down",function (options) {
eventLogger.trace('20: mouse:down');
if (!isKnifeMode||shiftTempDisabledKnife) return;

var pointer=canvas.getPointer(options.e);
var selectedPolygon=getPolygonAtPoint(pointer);

if (selectedPolygon) {
isKnifeDrawing=true;
currentKnifeObject=selectedPolygon;
startKnifeX=pointer.x;
startKnifeY=pointer.y;
drawLine(startKnifeX,startKnifeY,startKnifeX,startKnifeY);
} else {
isKnifeDrawing=false;
canvas.discardActiveObject().renderAll();
}
});

canvas.on("mouse:up",function (options) {
eventLogger.trace('21: mouse:up');
if (!isKnifeMode||!isKnifeDrawing||shiftTempDisabledKnife) return;

isKnifeDrawing=false;

if (currentKnifeLine) {
currentKnifeLine.bringToFront();
splitPolygon(currentKnifeObject);
}
currentKnifeObject=null;
currentKnifeLine=null;
});

canvas.on("mouse:move",function (options) {
if (!isKnifeMode||!isKnifeDrawing||shiftTempDisabledKnife) return;
eventLogger.trace('22: mouse:move');

var pointer=canvas.getPointer(options.e);
var endX=pointer.x;
var endY=pointer.y;

var dx=endX-startKnifeX;
var dy=endY-startKnifeY;
var angle=(Math.atan2(dy,dx)*180)/Math.PI;

if (
(angle>=0-knifeAssistAngle&&angle<=knifeAssistAngle)||
angle<=-180+knifeAssistAngle||
angle>=180-knifeAssistAngle
) {
endY=startKnifeY;
} else if (
(angle>=90-knifeAssistAngle&&angle<=90+knifeAssistAngle)||
(angle>=-90-knifeAssistAngle&&angle<=-90+knifeAssistAngle)
) {
endX=startKnifeX;
}

drawLine(startKnifeX,startKnifeY,endX,endY);
});







canvas.on('path:created',function (opt) {
eventLogger.trace('23: path:created');
canvasLogger.debug("push");
currentPaths.push(opt.path);
});

document.addEventListener('DOMContentLoaded',function () {
canvas.on('mouse:move',function (options) {
if (isMosaicBrushActive&&canvas.freeDrawingBrush&&!canvas.freeDrawingBrush.isDrawing) {
eventLogger.trace('24: mouse:move');
canvas.freeDrawingBrush.drawPreviewCircle(canvas.getPointer(options.e));
}
});
});






canvas.on("mouse:down",event=>{
eventLogger.trace('25: mouse:down');
isDrawing=true;
const pointer=canvas.getPointer(event.e);
if (currentMode==="point") {
points.push({x: pointer.x,y: pointer.y});
updateTemporaryShapes();
} else if (currentMode==="freehand") {
points=[{x: pointer.x,y: pointer.y}];
updateTemporaryShapes();
} else if (currentMode==="movePoint"||currentMode==="deletePoint") {
if (event.target&&event.target.isSpeechBubble) {
selectedObject=event.target;
createControlPoints(selectedObject);
} else if (currentMode==="deletePoint"&&event.target&&event.target.data&&event.target.data.index!==undefined) {
deletePoint(selectedObject,event.target.data.index);
} else if (event.target&&event.target.data) {
activePoint=event.target;
} else {
selectedObject=null;
createControlPoints(null);
activePoint=null;
}
}
});

canvas.on("mouse:move",event=>{
const currentTime=Date.now();
if (currentTime-lastRenderTime<16) return;
lastRenderTime=currentTime;

if (currentMode==="point") {
eventLogger.trace('26: mouse:move');
} else if (currentMode==="freehand"&&isDrawing) {
eventLogger.trace('26: mouse:move');
} else if (currentMode==="movePoint"&&isDrawing&&activePoint) {
eventLogger.trace('26: mouse:move');
}else{
return;
}

const pointer=canvas.getPointer(event.e);
if (currentMode==="point") {
mousePosition={x: pointer.x,y: pointer.y};
updateTemporaryShapes();
} else if (currentMode==="freehand"&&isDrawing) {
points.push({x: pointer.x,y: pointer.y});
updateTemporaryShapes();
} else if (currentMode==="movePoint"&&isDrawing&&activePoint) {
updateShape(selectedObject,activePoint.data.index,pointer.x,pointer.y);
activePoint.set({left: pointer.x,top: pointer.y});
requestAnimationFrame(()=>canvas.renderAll());
}
});

canvas.on("mouse:up",event=>{
eventLogger.trace('27: mouse:up');
isDrawing=false;
activePoint=null;
const pointer=canvas.getPointer(event.e);
if (currentMode==="point"&&points.length>=4) {
if (isNearStartPoint(pointer.x,pointer.y,points[0])) {
points.pop();
points.push({x: points[0].x,y: points[0].y});
points=processPoints(points);
const geometry=createJSTSPolygon(points);
if (geometry&&geometry.isValid()) {
createSpeechBubble(mergeOverlappingShapes(geometry));
} else {
canvasLogger.warn("jsts up error");
sbClear();
}

points=[];
mousePosition=null;

updateObjectSelectability();

} else {
updateTemporaryShapes();
}
} else if (currentMode==="freehand"&&points.length>=4) {
points.push({x: points[0].x,y: points[0].y});
points=processPoints(points);
const geometry=createJSTSPolygon(points);
if (geometry&&geometry.isValid()) {
createSpeechBubble(mergeOverlappingShapes(geometry));
points=[];
} else {
canvasLogger.warn("jsts up error");
sbClear();
}
updateObjectSelectability();
requestAnimationFrame(()=>canvas.renderAll());
}
});

canvas.on('object:moving',function(event)  {eventLogger.trace('28: object:moving');updateJSTSGeometry(event);});
canvas.on('object:scaling',function(event) {eventLogger.trace('29: object:scaling');updateJSTSGeometry(event);});










canvas.on("object:moving",function (event) {
if (isSpeechBubbleSVG(event.target)) {
eventLogger.trace('30: object:moving');
updateObjectPositions(event.target);
canvas.requestRenderAll();
}
});

canvas.on("mouse:up",function (event) {
eventLogger.trace('31: mouse:up');
if (isSpeechBubbleSVG(event.target)) {
updateObjectPositions(event.target,true);
}
});
canvas.on("text:changed",function (event) {
eventLogger.trace('32: text:changed');
requestAnimationFrame(()=>{
speechBubbleTextChaged(event.target);
});
});

canvas.on("object:scaling",function (event) {
eventLogger.trace('33: object:scaling');
if (isSpeechBubbleSVG(event.target)) {
event.target.baseScaleX=event.target.scaleX;
event.target.baseScaleY=event.target.scaleY;
updateShapeMetrics(event.target);
}
});

canvas.on("object:rotating",function (event) {
eventLogger.trace('34: object:rotating');
if (isSpeechBubbleSVG(event.target)) {
updateShapeMetrics(event.target);
}
});
canvas.on("object:removed",function(event) {
eventLogger.trace('35: object:removed');
if (isSpeechBubbleSVG(event.target)) {
const rect=getSpeechBubbleRectBySVG(event.target);
const textbox=getSpeechBubbleTextBySVG(event.target);
canvas.remove(rect);
canvas.remove(textbox);
canvas.requestRenderAll();
}
if (isSpeechBubbleText(event.target)) {
const rect=getSpeechBubbleRectBySVG(event.target.targetObject);
canvas.remove(rect);
event.target.targetObject.customType="";
canvas.requestRenderAll();
}
if (isFreehandBubblePath(event.target)) {
const rect=getFreehandBubbleRectByPath(event.target);
const textbox=getFreehandBubbleTextByPath(event.target);
canvas.remove(rect);
canvas.remove(textbox);
canvas.requestRenderAll();
}
if (isFreehandBubbleText(event.target)) {
const rect=getFreehandBubbleRectByPath(event.target.targetObject);
canvas.remove(rect);
event.target.targetObject.customType="";
canvas.requestRenderAll();
}
});

canvas.on("object:moving",function (event) {
if (isFreehandBubblePath(event.target)) {
eventLogger.trace('object:moving freehandBubble');
updateFreehandBubblePositions(event.target);
canvas.requestRenderAll();
}
});

canvas.on("mouse:up",function (event) {
if (isFreehandBubblePath(event.target)) {
eventLogger.trace('mouse:up freehandBubble');
updateFreehandBubblePositions(event.target);
}
});

canvas.on("text:changed",function (event) {
if (isFreehandBubbleText(event.target)) {
eventLogger.trace('text:changed freehandBubble');
requestAnimationFrame(()=>{
freehandBubbleTextChanged(event.target);
});
}
});

canvas.on("object:scaling",function (event) {
if (isFreehandBubblePath(event.target)) {
eventLogger.trace('object:scaling freehandBubble');
event.target.baseScaleX=event.target.scaleX;
event.target.baseScaleY=event.target.scaleY;
updateFreehandBubbleMetrics(event.target);
}
});






canvas.on('selection:created',()=>{
eventLogger.trace('36: selection:created');
closeMenu();
});
canvas.on('selection:updated',()=>{
eventLogger.trace('37: selection:updated');
closeMenu();
});

canvas.on("mouse:move",function (options) {
if (coordCheckbox.checked) {
// eventLogger.trace('38: mouse:move');
updateCoordinates(options);
}
});





canvas.on('selection:cleared',function () {
eventLogger.trace('39: selection:cleared');
closeMenu();
});