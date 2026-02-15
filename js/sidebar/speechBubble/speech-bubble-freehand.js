function sbFreehandTextChange(alignment,button) {
changeSelected(button);
}

const sbPointButton=$("sbPointButton");
const sbFreehandButton=$("sbFreehandButton");
const sbSelectButton=$("sbSelectButton");
const sbMoveButton=$("sbMoveButton");
const sbDeleteButton=$("sbDeleteButton");

const sbSmoothing=$("sbSmoothing");
const sbFillColor=$("sbFillColor");
const sbStrokeColor=$("sbStrokeColor");
const sbStrokeWidth=$("sbStrokeWidth");
const sbFillOpacity=$("sbFillOpacity");
const sbSornerRadius=$("sbSornerRadius");
const sbPointSpace=$("sbPointSpace");
const geometryFactory=new jsts.geom.GeometryFactory();

let currentMode="select";
let points=[];
let mousePosition;
let temporaryLine;
let temporaryShape;
let isDrawing=false;
let editingGroup;
let selectedObject;
let controlPoints=[];
let activePoint;
let lastRenderTime=0;

function addTemporary(obj){
if(!obj)return;
obj.canvas=canvas;
canvas._objects.push(obj);
}
function removeTemporary(obj){
if(!obj)return;
var idx=canvas._objects.indexOf(obj);
if(idx!==-1)canvas._objects.splice(idx,1);
}

var nowLine="sb_a";
switchSBLine("sb_a");

function switchSBLine(type){
clearSBLine();
nowLine=type;
$(type+"Button").classList.add("selected");
}
function clearSBLine(){
[$("sb_aButton"),$("sb_bButton"),$("sb_cButton"),$("sb_dButton"),$("sb_eButton"),$("sb_fButton"),$("sb_gButton")].forEach(btn=>btn.classList.remove("selected"));
}

function getNowLineStyle(){
var sbopa=parseInt(sbFillOpacity.value)/100;
var sbstw=parseFloat(sbStrokeWidth.value);
switch (nowLine) {
case "sb_b":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeDashArray: [5,5]}
case "sb_c":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeLineCap: "round",strokeDashArray: [5,10]}
case "sb_d":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeDashArray: [1,3]}
case "sb_e":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeDashArray: [20,5,10,5]}
case "sb_f":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeDashArray: [15,3,3,3]}
case "sb_g":
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa,strokeDashArray: [10,5,2,5]}
default:
//sb_a
return {fill: sbFillColor.value,stroke: sbStrokeColor.value,strokeWidth: sbstw,opacity: sbopa}
}
}

function setSBActiveButton(button) {
[sbPointButton,sbFreehandButton,sbSelectButton,sbMoveButton,sbDeleteButton].forEach(btn=>btn.classList.remove("selected"));
button.classList.add("selected");
}

var MIN_BUBBLE_WIDTH=20;
var MIN_BUBBLE_HEIGHT=20;
var MIN_BUBBLE_AREA=500;

function createSpeechBubble(geometry) {
const coordinates=geometry.getCoordinates();
let minX=Infinity;
let minY=Infinity;
let maxX=-Infinity;
let maxY=-Infinity;
coordinates.forEach(coord=>{
minX=Math.min(minX,coord.x);
minY=Math.min(minY,coord.y);
maxX=Math.max(maxX,coord.x);
maxY=Math.max(maxY,coord.y);
});
const bubbleWidth=maxX-minX;
const bubbleHeight=maxY-minY;
const bubbleArea=bubbleWidth*bubbleHeight;
if(bubbleWidth<MIN_BUBBLE_WIDTH||bubbleHeight<MIN_BUBBLE_HEIGHT||bubbleArea<MIN_BUBBLE_AREA){
freehandBubbleLogger.debug("Bubble too small: "+bubbleWidth.toFixed(0)+"x"+bubbleHeight.toFixed(0)+" area="+bubbleArea.toFixed(0));
sbClear();
return null;
}
const adjustedCoordinates=coordinates.map(coord=>({
x: coord.x-minX,
y: coord.y-minY
}));

// const styles = {
//   fill: sbFillColor.value,
//   stroke: sbStrokeColor.value,
//   strokeWidth: parseInt(sbStrokeWidth.value),
//   opacity: parseInt(sbFillOpacity.value) / 100
// };

var styles=getNowLineStyle();

const path=adjustedCoordinates.map((coord,index)=>
(index===0 ? "M" : "L")+coord.x.toFixed(2)+" "+coord.y.toFixed(2)
).join("")+"Z";

const bubble=new fabric.Path(path,{
...styles,
left: minX,
top: minY,
selectable: currentMode==="select",
evented: true,
isSpeechBubble: true,
objectCaching: false,
jstsGeom: geometry,
perPixelTargetFind: true
});

sbClear();
changeDoNotSaveHistory();
skipForcedAdjust=true;
var tb0=performance.now();
canvas.add(bubble);
var tb1=performance.now();
createFreehandBubbleMetrics(bubble);
var tb2=performance.now();
skipForcedAdjust=false;
changeDoSaveHistory();
saveStateByManual();
forcedAdjustCanvasSize();
perfLogger.warn("[PERF:createSpeechBubble] canvas.add:"+Math.round(tb1-tb0)+"ms metrics:"+Math.round(tb2-tb1)+"ms");
return bubble;
}

function updateTemporaryShapes(){
perfCounters.updateTemp++;
removeTemporary(temporaryLine);
removeTemporary(temporaryShape);
temporaryLine=null;
temporaryShape=null;
if(currentMode==="point"&&points.length>0){
temporaryShape=new fabric.Polyline(points,{
fill:"rgba(0,0,255,0.2)",
stroke:"blue",
strokeWidth:parseInt(sbStrokeWidth.value),
selectable:false,
evented:false,
excludeFromLayerPanel:true
});
temporaryShape.saveHistory=false;
addTemporary(temporaryShape);
if(mousePosition){
temporaryLine=new fabric.Line([points[points.length-1].x,points[points.length-1].y,mousePosition.x,mousePosition.y],{
stroke:"blue",
strokeWidth:parseInt(sbStrokeWidth.value),
selectable:false,
evented:false,
excludeFromLayerPanel:true
});
temporaryLine.saveHistory=false;
addTemporary(temporaryLine);
}
}else if(currentMode==="freehand"&&points.length>0){
temporaryShape=new fabric.Path(points.map((point,index)=>(index===0?"M":"L")+point.x+" "+point.y).join(""),{
fill:"rgba(0,0,255,0.2)",
stroke:"blue",
strokeWidth:parseInt(sbStrokeWidth.value),
selectable:false,
evented:false,
excludeFromLayerPanel:true
});
temporaryShape.saveHistory=false;
addTemporary(temporaryShape);
}
requestAnimationFrame(()=>canvas.renderAll());
}

function createJSTSPolygon(points) {
if (points.length<3) return null;
let coordinates=points.map(point=>new jsts.geom.Coordinate(
Math.round(point.x*10)/10,
Math.round(point.y*10)/10
));
if (coordinates[0].x!==coordinates[coordinates.length-1].x||
coordinates[0].y!==coordinates[coordinates.length-1].y) {
coordinates.push(new jsts.geom.Coordinate(coordinates[0].x,coordinates[0].y));
}
if (coordinates.length<4) return null;
return geometryFactory.createPolygon(geometryFactory.createLinearRing(coordinates));
}

function unionGeometries(geometry1,geometry2) {
try {
const union=geometry1.union(geometry2);
const simplified=jsts.simplify.TopologyPreservingSimplifier.simplify(union,0.1);
return jsts.precision.GeometryPrecisionReducer.reduce(simplified,new jsts.geom.PrecisionModel(1000));
} catch (error) {
return geometry1;
}
}

function mergeOverlappingShapes(newGeometry) {
let envelope=newGeometry.getEnvelopeInternal();
let newLeft=envelope.getMinX();
let newTop=envelope.getMinY();
let newRight=envelope.getMaxX();
let newBottom=envelope.getMaxY();

canvas.getObjects().forEach(obj=>{
if (!obj.isSpeechBubble) return;

const objRect=obj.getBoundingRect(true,true);
const objLeft=objRect.left;
const objTop=objRect.top;
const objRight=objRect.left+objRect.width;
const objBottom=objRect.top+objRect.height;

if (newRight<objLeft||objRight<newLeft||newBottom<objTop||objBottom<newTop) return;

if(obj.isSpeechBubble&&!obj.jstsGeom){
textLogger.debug("mergeOverlappingShapes updateJSTSGeometryByObj 再作成");
updateJSTSGeometryByObj(obj);
}

var isIntersects=false;
try {
isIntersects=newGeometry.intersects(obj.jstsGeom)
}catch{
updateJSTSGeometryByObj(obj);
isIntersects=newGeometry.intersects(obj.jstsGeom);
}

if (isIntersects||newGeometry.touches(obj.jstsGeom)) {
const mergedGeometry=unionGeometries(newGeometry,obj.jstsGeom);
if (mergedGeometry&&mergedGeometry.isValid()) {
newGeometry=mergedGeometry;

envelope=newGeometry.getEnvelopeInternal();
newLeft=envelope.getMinX();
newTop=envelope.getMinY();
newRight=envelope.getMaxX();
newBottom=envelope.getMaxY();

removeByNotSave(obj);
}
}
});
return newGeometry;
}

function isNearStartPoint(x,y,startPoint) {
return Math.abs(x-startPoint.x)<=15&&Math.abs(y-startPoint.y)<=15;
}

function smoothPoints(points) {
if (points.length<3) return points;
const smoothingFactor=sbSmoothing.checked ? 1 : 100;
let smoothedPoints=[points[0]];
for (let i=1;i<points.length-1;i++) {
let prev=points[i-1];
let current=points[i];
let next=points[i+1];
smoothedPoints.push({
x: current.x*(1-smoothingFactor/100)+smoothingFactor/100*(prev.x+next.x)/2,
y: current.y*(1-smoothingFactor/100)+smoothingFactor/100*(prev.y+next.y)/2
});
}
smoothedPoints.push(points[points.length-1]);
return smoothedPoints;
}

function removeClosePoints(points) {
const threshold=parseInt(sbPointSpace.value);
if (threshold===0||points.length<3) return points;
let filteredPoints=[points[0]];
for (let i=1;i<points.length;i++) {
const lastPoint=filteredPoints[filteredPoints.length-1];
const currentPoint=points[i];
if (Math.hypot(currentPoint.x-lastPoint.x,currentPoint.y-lastPoint.y)>threshold) {
filteredPoints.push(currentPoint);
}
}
if (filteredPoints[filteredPoints.length-1]!==points[points.length-1]) {
filteredPoints.push(points[points.length-1]);
}
return filteredPoints;
}

function roundCorners(points,iterations) {
if (iterations===0||points.length<3) return points;
let roundedPoints=points;
for (let i=0;i<iterations;i++) {
let newPoints=[];
for (let j=0;j<roundedPoints.length-1;j++) {
const current=roundedPoints[j];
const next=roundedPoints[j+1];
newPoints.push({
x: 0.75*current.x+0.25*next.x,
y: 0.75*current.y+0.25*next.y
});
newPoints.push({
x: 0.25*current.x+0.75*next.x,
y: 0.25*current.y+0.75*next.y
});
}
if (roundedPoints[0].x===roundedPoints[roundedPoints.length-1].x&&
roundedPoints[0].y===roundedPoints[roundedPoints.length-1].y) {
newPoints.push(newPoints[0]);
} else {
newPoints.unshift(roundedPoints[0]);
newPoints.push(roundedPoints[roundedPoints.length-1]);
}
roundedPoints=newPoints;
}
return roundedPoints;
}

function processPoints(points) {
if (points[0].x!==points[points.length-1].x||points[0].y!==points[points.length-1].y) {
points.push({x: points[0].x,y: points[0].y});
}
points=removeClosePoints(points);
if (sbSmoothing.checked) {
points=smoothPoints(points);
}
points=roundCorners(points,parseInt(sbSornerRadius.value));
return removeClosePoints(points);
}

function updateObjectSelectability() {
canvas.forEachObject(obj=>{
if(obj.customType==="freehandBubbleRect") {
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:currentMode==="select",evented:true});
});
}
function createControlPoints(obj){
sbClearControlePoints();
if(!obj)return;
const path=obj.path;
for(let i=1;i<path.length-1;i++){
if(path[i][0]!=='L')continue;
const point=new fabric.Circle({
left:path[i][1]+obj.left,
top:path[i][2]+obj.top,
radius:5,
fill:currentMode==="deletePoint"?'red':'blue',
originX:'center',
originY:'center',
hasBorders:false,
hasControls:false,
selectable:false,
evented:true,
data:{index:i},
excludeFromLayerPanel:true
});
point.saveHistory=false;
controlPoints.push(point);
addTemporary(point);
}
requestAnimationFrame(()=>canvas.renderAll());
}

function updateShape(obj,pointIndex,newX,newY) {
const path=obj.path;
path[pointIndex][1]=newX-obj.left;
path[pointIndex][2]=newY-obj.top;
obj.set({path: path});
obj.setCoords();
obj.dirty=true;
requestAnimationFrame(()=>canvas.renderAll());
}

function deletePoint(obj,index) {
if (obj.path.length<=4) {
return;
}
const [deletedPoint]=obj.path.splice(index,1);
const firstPoint=obj.path[0];
if (deletedPoint[0]==='L'&&
deletedPoint[1]===firstPoint[1]&&
deletedPoint[2]===firstPoint[2]) {
obj.path.shift();
obj.path[0][0]='M';
const secondPoint=[...obj.path[0]];
secondPoint[0]='L';
obj.path.splice(obj.path.length-1,0,secondPoint);
} else {
for (let i=index;i<obj.path.length-1;i++) {
obj.path[i][0]=i===0 ? 'M' : 'L';
}
}

obj.dirty=true;
createControlPoints(obj);
requestAnimationFrame(()=>canvas.renderAll());
}

sbPointButton.addEventListener("click",()=>{
currentMode="point";
setDrawingMode(sbPointButton);
changeCursor("point");
});

sbFreehandButton.addEventListener("click",()=>{
currentMode="freehand";
setDrawingMode(sbFreehandButton);
changeCursor("freehand");
});

sbSelectButton.addEventListener("click",()=>{
currentMode="select";
setSelectionMode(sbSelectButton);
changeDefaultCursor();
});

sbMoveButton.addEventListener("click",()=>{
currentMode="movePoint";
setSelectionMode(sbMoveButton);
changeCursor("movePoint");
});

sbDeleteButton.addEventListener("click",()=>{
currentMode="deletePoint";
setSelectionMode(sbDeleteButton);
changeCursor("deletePoint");
});

function sbClear(){
removeTemporary(temporaryLine);
removeTemporary(temporaryShape);
temporaryLine=null;
temporaryShape=null;
}
function sbClearControlePoints(){
controlPoints.forEach(p=>removeTemporary(p));
controlPoints=[];
requestAnimationFrame(()=>canvas.renderAll());
}

function setDrawingMode(button) {
freehandBubbleLogger.debug("setDrawingMode called, currentMode="+currentMode);
if(isKnifeMode){
isKnifeMode=false;
updateKnifeMode();
}
canvas.selection=false;
setSBActiveButton(button);
sbClear();
points=[];
mousePosition=null;
updateObjectSelectability();
sbClearControlePoints();

canvas.selection=false;
canvas.forEachObject(obj=>{
obj.set({
selectable: false,
evented: false
});
});
canvas.renderAll();
activeClearButton();
freehandBubbleLogger.debug("setDrawingMode completed");
}

function setSelectionMode(button) {
if(isKnifeMode){
isKnifeMode=false;
updateKnifeMode();
}
setSBActiveButton(button);
canvas.selection=currentMode==="select";
if (editingGroup) canvas.remove(editingGroup);
editingGroup=null;
sbClear();
points=[];
updateObjectSelectability();
if (currentMode==="movePoint"||currentMode==="deletePoint") {
canvas.forEachObject(obj=>{
if(obj.customType==="freehandBubbleRect") {
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:false,evented:true});
});
selectedObject=null;
createControlPoints(null);
activeClearButton();
} else if (currentMode==="select") {
canvas.forEachObject(obj=>{
if(obj.customType==="freehandBubbleRect") {
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:true,evented:true});
});
nonActiveClearButton();
}
sbClearControlePoints();
}

setSelectionMode(sbSelectButton);

function updateJSTSGeometry(event) {
const obj=event.target;
updateJSTSGeometryByObj(obj);
}

function updateJSTSGeometryByObj(obj) {
if (obj.isSpeechBubble) {
const scaleX=obj.scaleX;
const scaleY=obj.scaleY;
const angle=fabric.util.degreesToRadians(obj.angle);

const updatedCoordinates=obj.path.filter(p=>p[0]!=='Z').map(p=>{
let x=p[1]-obj.pathOffset.x;
let y=p[2]-obj.pathOffset.y;

x*=scaleX;
y*=scaleY;

const rotatedX=x*Math.cos(angle)-y*Math.sin(angle);
const rotatedY=x*Math.sin(angle)+y*Math.cos(angle);
x=rotatedX+obj.left+obj.pathOffset.x*scaleX;
y=rotatedY+obj.top+obj.pathOffset.y*scaleY;

return new jsts.geom.Coordinate(x,y);
});

updatedCoordinates.push(updatedCoordinates[0]);

obj.jstsGeom=geometryFactory.createPolygon(
geometryFactory.createLinearRing(updatedCoordinates)
);
}
}




function clearJSTSGeometry() {
canvas.getObjects().forEach(obj=>{
obj.jstsGeom=null;
});
}

function createGridForFreehandBubble(bubble,pixelRatio=1) {
const rect=bubble.getBoundingRect(true,true);
const points=bubble.path.filter(function(p){return p[0]==='M'||p[0]==='L';});
if(points.length<3) return null;
const minX=Math.min.apply(null,points.map(function(p){return p[1];}));
const minY=Math.min.apply(null,points.map(function(p){return p[2];}));
const maxX=Math.max.apply(null,points.map(function(p){return p[1];}));
const maxY=Math.max.apply(null,points.map(function(p){return p[2];}));
const pathWidth=maxX-minX;
const pathHeight=maxY-minY;
if(pathWidth<=0||pathHeight<=0) return null;
const scaleToRect={x:rect.width/pathWidth,y:rect.height/pathHeight};
const pathD=bubble.path.map(function(p){
if(p[0]==='M'||p[0]==='L') return p[0]+((p[1]-minX)*scaleToRect.x)+' '+((p[2]-minY)*scaleToRect.y);
if(p[0]==='Z') return 'Z';
return '';
}).join(' ');
var svgData={
viewBox:{x:0,y:0,width:rect.width,height:rect.height},
pathData:{type:'path',d:pathD}
};
var gridResult=createGrid(svgData,pixelRatio);
freehandBubbleLogger.debug("createGrid: rectSize="+rect.width.toFixed(0)+"x"+rect.height.toFixed(0)+", gridSize="+gridResult.grid[0].length+"x"+gridResult.grid.length);
return {grid:gridResult.grid,scale:gridResult.scale,viewBox:{width:rect.width,height:rect.height},offset:{x:rect.left,y:rect.top}};
}

function createFreehandBubbleMetrics(bubble) {
freehandBubbleLogger.debug("createFreehandBubbleMetrics called for new bubble");
const gridData=createGridForFreehandBubble(bubble);
if(!gridData) return;
const {grid,scale,viewBox,offset}=gridData;
bubble.freehandBubbleGrid=grid;
bubble.freehandBubbleScale=scale;
bubble.freehandBubbleViewBoxWidth=viewBox.width;
bubble.freehandBubbleViewBoxHeight=viewBox.height;
bubble.freehandBubbleOffsetX=offset.x;
bubble.freehandBubbleOffsetY=offset.y;
freehandBubbleLogger.debug("createFreehandBubbleMetrics: viewBox="+viewBox.width.toFixed(1)+"x"+viewBox.height.toFixed(1)+", scale="+scale.toFixed(3)+", bubble.width="+bubble.width.toFixed(1)+", bubble.height="+bubble.height.toFixed(1));
const largestRect=findLargestRectangle(grid);
bubble.freehandBubbleRectX=largestRect.x;
bubble.freehandBubbleRectY=largestRect.y;
bubble.freehandBubbleRectWidth=largestRect.width;
bubble.freehandBubbleRectHeight=largestRect.height;
bubble.lockRotation=true;
bubble.setControlsVisibility({mtr:false});
const rectWidth=largestRect.width/scale;
const rectHeight=largestRect.height/scale;
const rectX=largestRect.x/scale+offset.x;
const rectY=largestRect.y/scale+offset.y;
freehandBubbleLogger.debug("createFreehandBubbleMetrics: largestRect(grid)=("+largestRect.x+","+largestRect.y+","+largestRect.width+","+largestRect.height+") -> textRect(canvas)=("+rectX.toFixed(1)+","+rectY.toFixed(1)+","+rectWidth.toFixed(1)+","+rectHeight.toFixed(1)+")");
const newRect=new fabric.Rect({
left:rectX,
top:rectY,
width:rectWidth,
height:rectHeight,
fill:"transparent",
stroke:"transparent",
selectable:false,
evented:false,
hasControls:false,
targetObject:bubble,
excludeFromLayerPanel:true,
lockRotation:true
});
let newTextbox=null;
const selectedValue=getSelectedValueByGroup("sbFreehandTextGroup");
const isSbVerticalText=selectedValue!=="Horizontal";
var selectedFont=fontManager.getSelectedFont("fontSelector");
var fontsize=$("fontSizeSlider").value;
var fontStrokeWidth=$("fontStrokeWidthSlider").value;
if(isSbVerticalText) {
let style={
left:rectX+rectWidth/2,
top:rectY+rectHeight/2,
fontFamily:selectedFont,
fontSize:parseInt(fontsize),
fill:$("textColorPicker").value,
stroke:$("textOutlineColorPicker").value,
strokeWidth:parseInt(fontStrokeWidth),
textAlign:"center",
originX:"center",
originY:"center",
height:rectHeight,
selectable:true,
movable:false,
hasControls:false,
lockMovementX:true,
lockMovementY:true,
lockRotation:true,
lockScalingX:true,
lockScalingY:true,
editable:true,
evented:true,
renderOnAddRemove:true,
targetObject:bubble
};
var initialText=Math.round(rectWidth)+"x"+Math.round(rectHeight);
newTextbox=new VerticalTextbox(initialText,style);
} else {
var initialText=Math.round(rectWidth)+"x"+Math.round(rectHeight);
newTextbox=new fabric.Textbox(initialText,{
left:rectX+rectWidth/2,
top:rectY+rectHeight/2,
fontFamily:selectedFont,
fontSize:parseInt(fontsize),
fill:$("textColorPicker").value,
stroke:$("textOutlineColorPicker").value,
strokeWidth:parseInt(fontStrokeWidth),
textAlign:"center",
originX:"center",
originY:"center",
width:rectWidth,
selectable:true,
movable:false,
hasControls:false,
lockMovementX:true,
lockMovementY:true,
lockRotation:true,
lockScalingX:true,
lockScalingY:true,
editable:true,
evented:true,
renderOnAddRemove:true,
targetObject:bubble
});
}
bubble.guid=generateGUID();
newTextbox.guid=generateGUID();
newRect.guid=generateGUID();
setGUID(bubble,newTextbox);
setGUID(bubble,newRect);
bubble.customType="freehandBubblePath";
bubble.set({selectable:true,evented:true});
newTextbox.customType="freehandBubbleText";
newRect.customType="freehandBubbleRect";
bubble.lastLeft=bubble.left;
bubble.lastTop=bubble.top;
bubble.baseScaleX=bubble.scaleX||1;
bubble.baseScaleY=bubble.scaleY||1;
canvas.add(newRect);
canvas.add(newTextbox);
newTextbox.bringToFront();
canvas.renderAll();
}

function getFreehandBubbleRectByPath(pathObj) {
return canvas.getObjects().find(obj=>obj.type==="rect"&&obj.targetObject===pathObj);
}

function getFreehandBubbleTextByPath(pathObj) {
return canvas.getObjects().find(obj=>isFreehandBubbleText(obj)&&obj.targetObject===pathObj);
}

function isFreehandBubbleText(obj) {
return obj&&obj.customType==="freehandBubbleText";
}

function isFreehandBubblePath(obj) {
return obj&&obj.customType==="freehandBubblePath";
}

function updateFreehandBubblePositions(pathObj) {
if(!isFreehandBubblePath(pathObj)) return;
const rect=getFreehandBubbleRectByPath(pathObj);
const textbox=getFreehandBubbleTextByPath(pathObj);
if(!rect||!textbox) return;
if(pathObj.freehandBubbleRectX===undefined) return;
const boundingRect=pathObj.getBoundingRect(true,true);
const scaleX=pathObj.scaleX||1;
const scaleY=pathObj.scaleY||1;
const viewBoxW=pathObj.freehandBubbleViewBoxWidth||boundingRect.width;
const viewBoxH=pathObj.freehandBubbleViewBoxHeight||boundingRect.height;
const scaleW=boundingRect.width/viewBoxW;
const scaleH=boundingRect.height/viewBoxH;
const scale=pathObj.freehandBubbleScale||1;
const rectWidth=pathObj.freehandBubbleRectWidth/scale*scaleW;
const rectHeight=pathObj.freehandBubbleRectHeight/scale*scaleH;
const rectX=pathObj.freehandBubbleRectX/scale*scaleW+boundingRect.left;
const rectY=pathObj.freehandBubbleRectY/scale*scaleH+boundingRect.top;
rect.set({left:rectX,top:rectY,width:rectWidth,height:rectHeight});
if(isVerticalText(textbox)){
textbox.set({left:rectX+rectWidth/2,top:rectY+rectHeight/2,height:rectHeight});
} else {
textbox.set({left:rectX+rectWidth/2,top:rectY+rectHeight/2,width:rectWidth});
}
saveInitialState(pathObj);
saveInitialState(rect);
saveInitialState(textbox);
textbox.setCoords();
canvas.renderAll();
}

function updateFreehandBubbleMetrics(pathObj) {
freehandBubbleLogger.debug("updateFreehandBubbleMetrics called guid="+pathObj.guid);
const rect=getFreehandBubbleRectByPath(pathObj);
const textbox=getFreehandBubbleTextByPath(pathObj);
if(!rect||!textbox) {
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: rect or textbox not found");
return;
}
if(pathObj.freehandBubbleViewBoxWidth===undefined) {
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: viewBox not set, skipping");
return;
}
const scale=pathObj.freehandBubbleScale;
const viewBox={
width:pathObj.freehandBubbleViewBoxWidth,
height:pathObj.freehandBubbleViewBoxHeight
};
const largestRect={
x:pathObj.freehandBubbleRectX,
y:pathObj.freehandBubbleRectY,
width:pathObj.freehandBubbleRectWidth,
height:pathObj.freehandBubbleRectHeight
};
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: viewBox="+viewBox.width.toFixed(1)+"x"+viewBox.height.toFixed(1)+", pathObj.scaleX="+pathObj.scaleX.toFixed(3)+", pathObj.scaleY="+pathObj.scaleY.toFixed(3));
const scaleWidth=pathObj.scaleX*(pathObj.width/viewBox.width);
const scaleHeight=pathObj.scaleY*(pathObj.height/viewBox.height);
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: scaleWidth="+scaleWidth.toFixed(3)+", scaleHeight="+scaleHeight.toFixed(3));
const rectWidth=largestRect.width/scale;
const rectHeight=largestRect.height/scale;
const rectX=largestRect.x/scale;
const rectY=largestRect.y/scale;
const newRectLeft=pathObj.left+rectX*scaleWidth;
const newRectTop=pathObj.top+rectY*scaleHeight;
const newRectWidth=rectWidth*scaleWidth;
const newRectHeight=rectHeight*scaleHeight;
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: rect pos=("+newRectLeft.toFixed(1)+","+newRectTop.toFixed(1)+") size="+newRectWidth.toFixed(1)+"x"+newRectHeight.toFixed(1));
rect.set({left:newRectLeft,top:newRectTop,width:newRectWidth,height:newRectHeight});
if(isVerticalText(textbox)) {
textbox.set({left:newRectLeft+newRectWidth/2,top:newRectTop+newRectHeight/2,height:newRectHeight});
textbox.updateDimensions();
} else {
textbox.set({left:newRectLeft+newRectWidth/2,top:newRectTop+newRectHeight/2,width:newRectWidth});
}
saveInitialState(pathObj);
saveInitialState(rect);
saveInitialState(textbox);
textbox.setCoords();
pathObj.lastLeft=pathObj.left;
pathObj.lastTop=pathObj.top;
canvas.renderAll();
freehandBubbleLogger.debug("updateFreehandBubbleMetrics: saved initial states");
}

function freehandBubbleTextChanged(textObj) {
if(!isFreehandBubbleText(textObj)) return;
freehandBubbleLogger.debug("freehandBubbleTextChanged called textGuid="+textObj.guid);
const pathObj=textObj.targetObject;
const rect=getFreehandBubbleRectByPath(pathObj);
if(!rect) {
freehandBubbleLogger.debug("freehandBubbleTextChanged: rect not found");
return;
}
freehandBubbleLogger.debug("freehandBubbleTextChanged: pathObj.guid="+pathObj.guid+", current scaleX="+pathObj.scaleX.toFixed(3)+", scaleY="+pathObj.scaleY.toFixed(3));
let newSettings=null;
if(isVerticalText(textObj)) {
const textHeight=textObj.calcTextHeight();
const textWidth=textObj.calcTextWidth();
let scaleX=pathObj.scaleX;
let scaleY=pathObj.scaleY;
const requiredHeight=Math.max(textHeight,rect.height*0.5);
const requiredWidth=Math.max(textWidth,rect.width*0.5);
const newScaleY=pathObj.scaleY*(requiredHeight/rect.height);
const newScaleX=pathObj.scaleX*(requiredWidth/rect.width);
scaleX=Math.max(newScaleX,pathObj.baseScaleX);
scaleY=Math.max(newScaleY,pathObj.baseScaleY);
freehandBubbleLogger.debug("freehandBubbleTextChanged(vertical): requiredSize="+requiredWidth.toFixed(1)+"x"+requiredHeight.toFixed(1)+", newScale="+scaleX.toFixed(3)+"x"+scaleY.toFixed(3));
if(scaleX!==pathObj.scaleX||scaleY!==pathObj.scaleY) {
const centerX=pathObj.left+(pathObj.width*pathObj.scaleX)/2;
const centerY=pathObj.top+(pathObj.height*pathObj.scaleY)/2;
newSettings={scaleX:scaleX,scaleY:scaleY,left:centerX-(pathObj.width*scaleX)/2,top:centerY-(pathObj.height*scaleY)/2};
freehandBubbleLogger.debug("freehandBubbleTextChanged: scale changed to "+scaleX.toFixed(3)+"x"+scaleY.toFixed(3));
}
} else {
const chars=Math.max(textObj.text.length,1);
const charWidth=textObj.calcTextWidth()/Math.max(textObj.text.length,1);
const singleLineHeight=textObj.height/Math.max(textObj.textLines.length,1);
let scaleX=pathObj.scaleX;
let scaleY=pathObj.scaleY;
const requiredWidth=Math.max(chars*charWidth+charWidth,rect.width*0.5);
const requiredHeight=Math.max(textObj.height+singleLineHeight,rect.height*0.5);
const newScaleX=pathObj.scaleX*(requiredWidth/rect.width);
const newScaleY=pathObj.scaleY*(requiredHeight/rect.height);
scaleX=Math.max(newScaleX,pathObj.baseScaleX);
scaleY=Math.max(newScaleY,pathObj.baseScaleY);
freehandBubbleLogger.debug("freehandBubbleTextChanged(horizontal): requiredSize="+requiredWidth.toFixed(1)+"x"+requiredHeight.toFixed(1)+", newScale="+scaleX.toFixed(3)+"x"+scaleY.toFixed(3));
if(scaleX!==pathObj.scaleX||scaleY!==pathObj.scaleY) {
const centerX=pathObj.left+(pathObj.width*pathObj.scaleX)/2;
const centerY=pathObj.top+(pathObj.height*pathObj.scaleY)/2;
newSettings={scaleX:scaleX,scaleY:scaleY,left:centerX-(pathObj.width*scaleX)/2,top:centerY-(pathObj.height*scaleY)/2};
freehandBubbleLogger.debug("freehandBubbleTextChanged: scale changed to "+scaleX.toFixed(3)+"x"+scaleY.toFixed(3));
}
}
if(newSettings) {
freehandBubbleLogger.debug("freehandBubbleTextChanged: applying newSettings and calling updateFreehandBubbleMetrics");
pathObj.set(newSettings);
updateFreehandBubbleMetrics(pathObj);
} else {
freehandBubbleLogger.debug("freehandBubbleTextChanged: no scale change needed");
}
}
