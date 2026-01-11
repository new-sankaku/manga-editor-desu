function avtive(object) {
canvas.setActiveObject(object).requestRenderAll();
}

function notAvtive(object) {
canvas.discardActiveObject().requestRenderAll();
}





function isPanel(activeObject) {
return (activeObject&&activeObject.isPanel);
}
function isPanelType(activeObject) {
return (activeObject&&["rect","circle","polygon"].includes(activeObject.type));
}

function isImage(activeObject) {
return (activeObject&&(activeObject.type==="image"));
}
function haveClipPath(activeObject){
if (activeObject.clipPath) {
return true;
}
return false;
}

function isText(activeObject) {
return (activeObject&&(activeObject.type==='i-text'||activeObject.type==="text"||
activeObject.type==="textbox"||activeObject.type==="vertical-textbox"));
}

function isVerticalText(activeObject) {
return (activeObject&&(activeObject.type==="vertical-textbox"));
}


function isHorizontalText(activeObject) {
return (activeObject&&(activeObject.type==='i-text'||activeObject.type==="text"||activeObject.type==="textbox"));
}
function isPath(activeObject) {
return (activeObject&&activeObject.type==='path');
}

function isLine(activeObject) {
return (activeObject&&activeObject.type==='line');
}

function isGroup(activeObject) {
return (activeObject&&activeObject.type==='group');
}

function isShapes(activeObject) {
return (activeObject&&['path','rect','circle','triangle','polygon'].includes(activeObject.type));
}

function isPutImage(activeObject) {

if (activeObject.isIcon) {
return true;
}

return (activeObject&&["image","rect","circle","path","group","polygon"].includes(activeObject.type));
}

function isLayerPreview(activeObject) {
if (activeObject.isIcon) {
return true;
}
return (activeObject&&["image","rect","circle","group","polygon"].includes(activeObject.type));
}


function saveInitialState(obj) {
logger.traceWithStack('saveInitialState:obj.name:'+obj.name);
if(!obj.name){
logger.trace('saveInitialState:obj.name:'+obj.name,"obj:",obj);
}

if (isImage(obj)&&(!obj.initial)) {
setImage2ImageInitPrompt(obj);
}

if (isPanel(obj)&&(!obj.initial)) {
setText2ImageInitPrompt(obj);
}

logger.trace('saveInitialState:obj.name:'+obj.name,"obj.initial",obj.initial);

obj.initial={
left: obj.left,
top: obj.top,
scaleX: obj.scaleX,
scaleY: obj.scaleY,
strokeWidth: obj.strokeWidth,
canvasWidth: canvas.getWidth(),
canvasHeight: canvas.getHeight(),
};

if (obj.clipPath) {
logger.trace('saveInitialState:obj.name:'+obj.name,"obj.clipPath",obj.clipPath);

obj.clipPath.initial={
left: obj.clipPath.left,
top: obj.clipPath.top,
scaleX: obj.clipPath.scaleX,
scaleY: obj.clipPath.scaleY,
canvasWidth: canvas.getWidth(),
canvasHeight: canvas.getHeight(),
};
}
}

function setText2ImageInitPrompt(object) {
object.isPanel=t2iInit.isPanel;
object.text2img_prompt=t2iInit.t2i_prompt;
object.text2img_negative=t2iInit.t2i_negativePrompt;
object.text2img_seed=t2iInit.t2i_seed;
object.text2img_width=t2iInit.t2i_width;
object.text2img_height=t2iInit.t2i_height;
object.text2img_samplingSteps=t2iInit.t2i_samplingSteps;
}
function setImage2ImageInitPrompt(object) {
object.text2img_prompt=i2iInit.i2i_prompt;
object.text2img_negative=i2iInit.i2i_negativePrompt;
object.text2img_seed=i2iInit.i2i_seed;
object.text2img_width=i2iInit.i2i_width;
object.text2img_height=i2iInit.i2i_height;
object.text2img_samplingSteps=i2iInit.i2i_samplingSteps;
object.img2img_denoise=i2iInit.i2i_denoise;
object.img2imgScale=i2iInit.i2i_scale;
}

function deepCopy(obj) {
var copyObject={};

if (obj) {
for (var prop in obj) {
if (obj.hasOwnProperty(prop)) {
if (obj[prop] instanceof Object) {
copyObject[prop]=deepCopy(obj[prop]);
} else {
copyObject[prop]=obj[prop];
}
}
}
}

if (obj.clipPath) {
copyObject.clipPath=deepCopy(obj.clipPath);
}

return copyObject;
}

function copy(srcObject,object) {
object.name=srcObject.name;
object.isPanel=srcObject.isPanel;
object.text2img_prompt=srcObject.text2img_prompt;
object.text2img_negative=srcObject.text2img_negative;
object.text2img_seed=srcObject.text2img_seed;
object.text2img_width=srcObject.text2img_width;
object.text2img_height=srcObject.text2img_height;
object.text2img_samplingSteps=srcObject.text2img_samplingSteps;

object.img2img_prompt=srcObject.img2img_prompt;
object.img2img_negative=srcObject.img2img_negative;
object.img2img_seed=srcObject.img2img_seed;
object.img2img_width=srcObject.img2img_width;
object.img2img_height=srcObject.img2img_height;
object.img2img_samplingSteps=srcObject.img2img_samplingSteps;
object.img2img_denoise=srcObject.img2img_denoise;
object.img2imgScale=srcObject.img2imgScale;

object.top=srcObject.top;
object.left=srcObject.left;
object.scaleX=srcObject.scaleX;
object.scaleY=srcObject.scaleY;
object.width=srcObject.width;
object.height=srcObject.height

object.guid=srcObject.guid
object.guids=srcObject.guids
object.tempPrompt=srcObject.tempPrompt
object.tempNegative=srcObject.tempNegative
object.tempSeed=srcObject.tempSeed

object.clipPath=srcObject.clipPath ? srcObject.clipPath : undefined;

if (srcObject.clipPath&&srcObject.clipPath.initial) {
object.clipPath.initial=srcObject.clipPath.initial ? srcObject.clipPath.initial : undefined;
}
object.initial=srcObject.initial ? srcObject.initial : undefined;
}



function setCanvasGUID(guid=null) {
if(guid){
//ok
}else{
guid=generateGUID();
}
canvas.set('canvasGuid',guid);
return guid;
}

function getCanvasGUID() {
let guid=canvas.get('canvasGuid');
if(guid){
return guid;
}
return setCanvasGUID();
}


// set targetFram.guids
function setGUID(personObject,childObject) {
if (!personObject.guids) {
personObject.guids=[];
}
guid=getGUID(childObject);
// console.log(personObject.name + " : setGUID", guid);
personObject.guids.push(guid);
}

function removeGUID(personObject,childObject) {
var guid=childObject.guid;

if (!personObject.guids) {
personObject.guids=[];
childObject.guid=null;
return;
}

if (!guid) {
childObject.guid=null;
return;
}
var index=personObject.guids.indexOf(guid);

if (index!==-1) {
personObject.guids.splice(index,1);
}
updateLayerPanel();
}



function getGUID(activeObject) {
if (!activeObject) {
canvasLogger.error("ERROR, getGUID activeObject is null.")
return null;
}

if (activeObject.guid) {
return activeObject.guid;
}
let guid=generateGUID();
activeObject.guid=guid;
return guid;
}

function generateGUID() {
const array=new Uint8Array(16);
window.crypto.getRandomValues(array);
array[6]=(array[6]&0x0f)|0x40;
array[8]=(array[8]&0x3f)|0x80;
const guid=Array.from(array).map(b=>('00'+b.toString(16)).slice(-2)).join('');
return `${guid.slice(0, 8)}-${guid.slice(8, 12)}-${guid.slice(12, 16)}-${guid.slice(16, 20)}-${guid.slice(20)}`;
}

function createGUIDMap(layers) {
var layerMap=new Map();
layers.forEach(function (layer) {
layer.guid=getGUID(layer);
layerMap.set(layer.guid,layer);
});
return layerMap;
}



function replaceGuids(searchGuid,nextObject) {
if (!searchGuid) {
return;
}
if (!nextObject) {
return;
}

var parentObject=haveGuidsObjectByGuid(searchGuid);

if (parentObject&&Array.isArray(parentObject.guids)) {
parentObject.guids=parentObject.guids.filter(guid=>guid!==searchGuid);
var nextGuid=getGUID(nextObject);
parentObject.guids.push(nextGuid);
} else {
}
}

function haveGuidsObjectByGuid(searchGuid) {
if(!searchGuid){
return null;
}

var layers=canvas.getObjects();
var matchingObject=layers.find(layer=>layer.guids&&layer.guids.includes(searchGuid));
return matchingObject;
}

function getObjectByGUID(searchGuid) {
if(!searchGuid){
return;
}

var layers=canvas.getObjects();
var matchingObject=layers.find(layer=>layer.guid===guid);
return matchingObject;
}







function removeClipPath(activeObject,action) {
let canvas=activeObject.canvas;

logger.trace("BEFORE",`Starting ${action} process for shape "${activeObject.name}"`,activeObject.name);

let clipPath=activeObject.clipPath;
if (!clipPath||!clipPath.points) {
logger.trace("ERROR",`ClipPath or clipPath.points not found for shape "${activeObject.name}"`);
canvasLogger.error('ClipPath or clipPath.points not found');
return;
}

const canvasWidth=canvas.getWidth();
const canvasHeight=canvas.getHeight();

logger.trace("BEFORE",`${action} process for shape "${activeObject.name}" - ClipPath Before`,{
left: clipPath.left,
top: clipPath.top,
scaleX: clipPath.scaleX,
scaleY: clipPath.scaleY,
points: clipPath.points
});

function calculatePoint(point) {
return {
x: clipPath.left+point.x*clipPath.scaleX,
y: clipPath.top+point.y*clipPath.scaleY
};
}

let points=[];
for (let i=0;i<clipPath.points.length;i++) {
points.push(calculatePoint(clipPath.points[i]));
}

logger.trace("INFO",`Calculated absolute coordinate points for shape "${activeObject.name}":`,points);

let minX=points[0].x,maxX=points[0].x;
let minY=points[0].y,maxY=points[0].y;
for (let i=1;i<points.length;i++) {
minX=Math.min(minX,points[i].x);
maxX=Math.max(maxX,points[i].x);
minY=Math.min(minY,points[i].y);
maxY=Math.max(maxY,points[i].y);
}

logger.trace("INFO",`Bounding box for shape "${activeObject.name}": X(${minX}~${maxX}), Y(${minY}~${maxY})`);

function detectEdgesWithJSTS(points) {
logger.trace("INFO",`Starting edge detection using JSTS for shape "${activeObject.name}"`);

const sortedByX=[...points].sort((a,b)=>a.x-b.x);
const leftMost=sortedByX[0].x;
const rightMost=sortedByX[sortedByX.length-1].x;

const geometryFactory=new jsts.geom.GeometryFactory();
const coordinates=points.map(p=>new jsts.geom.Coordinate(p.x,p.y));
coordinates.push(coordinates[0]);

const shell=geometryFactory.createLinearRing(coordinates);
const polygon=geometryFactory.createPolygon(shell);
const convexHull=polygon.convexHull();
const hullCoordinates=convexHull.getCoordinates();

logger.trace("INFO",`Left edge X: ${leftMost}, Right edge X: ${rightMost} for shape "${activeObject.name}"`);

const tolerance=1;

const topEdgePoints=[];
const bottomEdgePoints=[];
const leftEdgePoints=[];
const rightEdgePoints=[];

for (let i=0;i<hullCoordinates.length-1;i++) {
const p1=hullCoordinates[i];
const p2=hullCoordinates[i+1];

const dx=p2.x-p1.x;
const dy=p2.y-p1.y;
const length=Math.sqrt(dx*dx+dy*dy);

if (length<0.001) continue;

const nx=-dy/length;
const ny=dx/length;

if (Math.abs(ny)>Math.abs(nx)) {
if (ny<0) {
topEdgePoints.push({p1: {x: p1.x,y: p1.y},p2: {x: p2.x,y: p2.y}});
logger.trace("INFO",`Added to top edge for shape "${activeObject.name}": (${p1.x},${p1.y}) → (${p2.x},${p2.y})`);
} else {
bottomEdgePoints.push({p1: {x: p1.x,y: p1.y},p2: {x: p2.x,y: p2.y}});
logger.trace("INFO",`Added to bottom edge for shape "${activeObject.name}": (${p1.x},${p1.y}) → (${p2.x},${p2.y})`);
}
} else {
logger.trace("INFO",`Edge detection for shape "${activeObject.name}": (${p1.x},${p1.y}) → (${p2.x},${p2.y}), nx=${nx}, ny=${ny}`);
if (nx>0) {
rightEdgePoints.push({p1: {x: p1.x,y: p1.y},p2: {x: p2.x,y: p2.y}});
logger.trace("INFO",`Added to right edge for shape "${activeObject.name}": (${p1.x},${p1.y}) → (${p2.x},${p2.y})`);
} else {
leftEdgePoints.push({p1: {x: p1.x,y: p1.y},p2: {x: p2.x,y: p2.y}});
logger.trace("INFO",`Added to left edge for shape "${activeObject.name}": (${p1.x},${p1.y}) → (${p2.x},${p2.y})`);
}
}
}

const result={
top: topEdgePoints,
bottom: bottomEdgePoints,
left: leftEdgePoints,
right: rightEdgePoints
};

logger.trace("INFO",`Edge detection results for shape "${activeObject.name}"`,{
top: topEdgePoints.length,
bottom: bottomEdgePoints.length,
left: leftEdgePoints.length,
right: rightEdgePoints.length
});

return result;
}

function getPointsFromEdge(edgePoints) {
logger.trace("INFO",`Starting point detection from edges for shape "${activeObject.name}"`);
const indices=[];
const tolerance=1;

for (const edge of edgePoints) {
for (let i=0;i<points.length;i++) {
const point=points[i];
const distToEdge=pointToLineDistance(point,edge.p1,edge.p2);
if (distToEdge<tolerance) {
indices.push(i);
logger.trace("INFO",`Point ${i} (${point.x}, ${point.y}) for shape "${activeObject.name}" is included in the edge, distance: ${distToEdge}`);
}
}
}

const uniqueIndices=[...new Set(indices)];
logger.trace("INFO",`Detected edge points for shape "${activeObject.name}": ${uniqueIndices.length} points`,uniqueIndices);

return uniqueIndices;
}

function pointToLineDistance(point,lineStart,lineEnd) {
const A=point.x-lineStart.x;
const B=point.y-lineStart.y;
const C=lineEnd.x-lineStart.x;
const D=lineEnd.y-lineStart.y;

const dot=A*C+B*D;
const lenSq=C*C+D*D;
let param=-1;

if (lenSq!==0) {
param=dot/lenSq;
}

let xx,yy;

if (param<0) {
xx=lineStart.x;
yy=lineStart.y;
} else if (param>1) {
xx=lineEnd.x;
yy=lineEnd.y;
} else {
xx=lineStart.x+param*C;
yy=lineStart.y+param*D;
}

const dx=point.x-xx;
const dy=point.y-yy;

return Math.sqrt(dx*dx+dy*dy);
}

let newPoints=[];
let newLeft=clipPath.left;
let newTop=clipPath.top;

logger.trace("BEFORE",`Starting ${action} process for shape "${activeObject.name}": newLeft=${newLeft}, newTop=${newTop}`);

switch (action) {
case 'clearAllClipPaths':
logger.trace("INFO",`Clearing all ClipPaths for shape "${activeObject.name}"`);
activeObject.clipPath=undefined;
break;
case 'clearTopClipPath':
logger.trace("INFO",`Starting top edge ClipPath clearing process for shape "${activeObject.name}"`);
const edges=detectEdgesWithJSTS(points);
const topIndices=getPointsFromEdge(edges.top);

for (let i=0;i<clipPath.points.length;i++) {
let point={};
point.x=clipPath.points[i].x;
if (topIndices.includes(i)) {
point.y=0;
logger.trace("INFO",`Point ${i} for shape "${activeObject.name}" is on top edge: Setting Y coordinate to 0`);
} else {
point.y=clipPath.points[i].y;
}
newPoints.push(point);
}

newTop=0;
logger.trace("INFO",`Top edge clearing process completed for shape "${activeObject.name}"`,newPoints);

reconstructClipPath(activeObject,newPoints,clipPath,newLeft,newTop);
break;
case 'clearBottomClipPath':
logger.trace("INFO",`Starting bottom edge ClipPath clearing process for shape "${activeObject.name}"`);
const edgesBottom=detectEdgesWithJSTS(points);
const bottomIndices=getPointsFromEdge(edgesBottom.bottom);

for (let i=0;i<clipPath.points.length;i++) {
let point={};
point.x=clipPath.points[i].x;
if (bottomIndices.includes(i)) {
point.y=canvasHeight;
logger.trace("INFO",`Point ${i} for shape "${activeObject.name}" is on bottom edge: Setting Y coordinate to ${point.y}`);
} else {
point.y=clipPath.points[i].y;
}
newPoints.push(point);
}

logger.trace("INFO",`Bottom edge clearing process completed for shape "${activeObject.name}"`,newPoints);

reconstructClipPath(activeObject,newPoints,clipPath,newLeft,newTop);
break;
case 'clearLeftClipPath':
logger.trace("INFO",`Starting left edge ClipPath clearing process for shape "${activeObject.name}"`);
const edgesLeft=detectEdgesWithJSTS(points);
const leftIndices=getPointsFromEdge(edgesLeft.left);

for (let i=0;i<clipPath.points.length;i++) {
let point={};
point.y=clipPath.points[i].y;
if (leftIndices.includes(i)) {
point.x=0;
logger.trace("INFO",`Point ${i} for shape "${activeObject.name}" is on left edge: Setting X coordinate to 0`);
} else {
point.x=clipPath.points[i].x;
}
newPoints.push(point);
}
newLeft=0;

logger.trace("INFO",`Left edge clearing process completed for shape "${activeObject.name}"`,newPoints);

reconstructClipPath(activeObject,newPoints,clipPath,newLeft,newTop);
break;
case 'clearRightClipPath':
logger.trace("INFO",`Starting right edge ClipPath clearing process for shape "${activeObject.name}"`);
const edgesRight=detectEdgesWithJSTS(points);
const rightIndices=getPointsFromEdge(edgesRight.right);

for (let i=0;i<clipPath.points.length;i++) {
let point={};
if (rightIndices.includes(i)) {
point.x=canvasWidth;
logger.trace("INFO",`Point ${i} for shape "${activeObject.name}" is on right edge: Setting X coordinate to ${point.x}`);
} else {
point.x=clipPath.points[i].x;
}
point.y=clipPath.points[i].y;
newPoints.push(point);
}

logger.trace("INFO",`Right edge clearing process completed for shape "${activeObject.name}"`,newPoints);

reconstructClipPath(activeObject,newPoints,clipPath,newLeft,newTop);
break;
default:
logger.trace("ERROR",`Unknown action "${action}" for shape "${activeObject.name}"`);
canvasLogger.error(`[removeClipPath] Error: Unknown action "${action}"`);
return;
}
if(activeObject.removeSettings){
activeObject.removeSettings();
}

if (canvas) {
canvas.requestRenderAll();
}

logger.trace("AFTER",`${action} process completed for shape "${activeObject.name}"`);
}

function reconstructClipPath(activeObject,points,oldClipPath,newLeft,newTop) {
logger.trace("BEFORE",`Starting ClipPath reconstruction for shape "${activeObject.name}"`,{
ObjectName: activeObject.name,
PointCount: points.length,
OldLeft: oldClipPath.left,
OldTop: oldClipPath.top,
NewLeft: newLeft,
NewTop: newTop
});

let canvas=activeObject.canvas;
newLeft=newLeft!==undefined ?
newLeft+activeObject.strokeWidth-(activeObject.strokeWidth*0.5) :
oldClipPath.left;

newTop=newTop!==undefined ?
newTop+activeObject.strokeWidth-(activeObject.strokeWidth*0.5) :
oldClipPath.top;

logger.trace("INFO",`Adjusted coordinates for shape "${activeObject.name}"`,{
AdjustedLeft: newLeft,
AdjustedTop: newTop
});

let newClipPath=new fabric.Polygon(points,{
left: newLeft,
top:  newTop,
objectCaching: false,
absolutePositioned: true,
name: activeObject.name+'_clipPath'
});

newClipPath.scaleX=1-(oldClipPath.strokeWidth)/(newClipPath.width);
newClipPath.scaleY=1-(oldClipPath.strokeWidth)/(newClipPath.height);

logger.trace("INFO",`New ClipPath details for shape "${activeObject.name}"`,{
Width: newClipPath.width,
Height: newClipPath.height,
ScaleX: newClipPath.scaleX,
ScaleY: newClipPath.scaleY
});

activeObject.clipPath=newClipPath;

activeObject.initial={
left: activeObject.left,
top: activeObject.top,
scaleX: activeObject.scaleX,
scaleY: activeObject.scaleY,
strokeWidth: activeObject.strokeWidth,
canvasWidth: activeObject.canvas.getWidth(),
canvasHeight: activeObject.canvas.getHeight(),
};

activeObject.clipPath.initial={
left: activeObject.clipPath.left,
top: activeObject.clipPath.top,
scaleX: activeObject.clipPath.scaleX,
scaleY: activeObject.clipPath.scaleY,
canvasWidth: activeObject.canvas.getWidth(),
canvasHeight: activeObject.canvas.getHeight(),
};

if(activeObject.clipPath.initial){
logger.trace("INFO",`activeObject.clipPath.initial has been set for shape "${activeObject.name}"`);
}

logger.trace("AFTER",`ClipPath reconstruction completed for shape "${activeObject.name}"`,{
Name: newClipPath.name,
Left: newClipPath.left,
Top: newClipPath.top,
ScaleX: newClipPath.scaleX,
ScaleY: newClipPath.scaleY
});
}






function getPathPoints(path) {
return path.path.map(cmd=>cmd[0]==="M"||cmd[0]==="L" ? {x: cmd[1],y: cmd[2]} : null).filter(point=>point!==null);
}

function calculateTransformedPath(originalPoints,transform) {
const angleRad=transform.angle*Math.PI/180;
const sin=Math.sin(angleRad);
const cos=Math.cos(angleRad);

const matrix=[
transform.scaleX*cos,-transform.scaleY*sin,
transform.scaleX*sin,transform.scaleY*cos,
0,0
];

var top=0;
var left=0;
if(transform.left!=transform.initLeft){
left=transform.left;
}
if(transform.top!=transform.initTop){
top=transform.top;
}
canvasLogger.debug("calculateTransformedPath transform.initLeft, transform.initTop",transform.initLeft,transform.initTop);
canvasLogger.debug("calculateTransformedPath transform.left, transform.top",transform.left,transform.top);
canvasLogger.debug("calculateTransformedPath left, top",left,top);

return {
fullTransformMatrix: transform.calcTransformMatrix(),
transformedPoints: originalPoints.map(point=>({
x: point.x*matrix[0]+point.y*matrix[2]+left,
y: point.x*matrix[1]+point.y*matrix[3]+top
})),
transformMatrix: matrix
};
}

function getObjectCount() {
var objescts=canvas.getObjects();
if(objescts){
return objescts.length;
}else{
return 0;
}
}


function getObjectList(){
var objescts=canvas.getObjects();
var resultList=[];
if(objescts){
return objescts;
}else{
return resultList;
}
}



function getImageObjectList(){
var objescts=canvas.getObjects();
var resultList=[];
if(objescts){
objescts.forEach(element=>{
if(isImage(element)){
resultList.push(element);
}
});
return resultList;
}
}

function getPanelObjectList(){
var objescts=canvas.getObjects();
var resultList=[];
if(objescts){
objescts.forEach(element=>{
if(isPanel(element)){
resultList.push(element);
}
});
return resultList;
}
}

function getRandomPanel(){
var panelList=getPanelObjectList();
if (!panelList||panelList.length===0) {
return null;
}
var randomIndex=Math.floor(Math.random()*panelList.length);
return panelList[randomIndex];
}

function getPanelCoordinates(panel) {
const points=panel.points;
const coords=points.map(point=>{
const scaledX=point.x*panel.scaleX;
const scaledY=point.y*panel.scaleY;

let rotatedX=scaledX;
let rotatedY=scaledY;
if (panel.angle) {
const radian=panel.angle*Math.PI/180;
rotatedX=scaledX*Math.cos(radian)-scaledY*Math.sin(radian);
rotatedY=scaledX*Math.sin(radian)+scaledY*Math.cos(radian);
}

return {
x: rotatedX+panel.left,
y: rotatedY+panel.top
};
});


return coords;
}



function getImageObjectListByLayerChecked(){
var resultList=getImageObjectList();
return resultList.filter(layer=>layer.layerCheck);
}


function fitImageToCanvas(fabricImage) {
const canvasWidth=canvas.width;
const canvasHeight=canvas.height;

const imageWidth=fabricImage.width;
const imageHeight=fabricImage.height;

let scale=Math.min((canvasWidth/imageWidth),(canvasHeight/imageHeight));

fabricImage.scaleX=scale;
fabricImage.scaleY=scale;

fabricImage.set({
left: 0,
top:  0
});

saveInitialState(fabricImage);
canvas.renderAll();
}

function getCenterXByFabricObject(obj) {
return obj.left+(obj.width*obj.scaleX)/2;
}

function getCenterYByFabricObject(obj) {
return obj.top+(obj.height*obj.scaleY)/2;
}

function getPointAtDistance(startX,startY,angle,distance){
const x=startX+Math.cos(angle)*distance;
const y=startY+Math.sin(angle)*distance;
return {x,y};
};


function getLastObject(){
var activeObject=canvas.getActiveObject();
if(activeObject){
return activeObject;
}else{
return lastCheckObject;
}
}


let initMessageText=null;
function initMessage(){
// const message = "Drop or Generate";
const message=getText("canvasInitMessage");
const text=new fabric.IText(message,{
left: canvas.width/2,
top: canvas.height/2,
fontSize: 30,
opacity: 0.25,
fontFamily: 'Arial',
originX: 'center',
originY: 'center',
selectable: false,
hoverCursor: 'default'
});

setNotSave(text);
canvas.add(text);
initMessageText=text;
canvas.renderAll();
}

function isSpeechBubbleSVG(obj){
if (obj&&obj.customType&&obj.customType==='speechBubbleSVG') {
return true;
}
return false;
}
function isSpeechBubbleText(obj){
if (obj&&obj.customType&&obj.customType==='speechBubbleText') {
return true;
}
return false;
}

function isSpeechBubbleRect(obj){
if (obj&&obj.customType&&obj.customType==='speechBubbleRect') {
return true;
}
return false;
}

function getRectTargetObject(obj){
const targetObj=obj.targetObject;
const rect=canvas.getObjects().find(obj=>obj.type==='rect'&&obj.targetObject===targetObj);
return rect;
}
