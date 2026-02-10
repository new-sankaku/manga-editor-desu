function changeSpeechBubble() {
// console.log("-------------");
var bubbleStrokewidht=parseFloat($("bubbleStrokewidht").value);
var fillColor=$("bubbleFillColor").value;
var strokeColor=$("bubbleStrokeColor").value;
var opacity=$("speechBubbleOpacity").value;
changeSpeechBubbleSVG(bubbleStrokewidht,fillColor,strokeColor,opacity);

}
function changeSpeechBubbleSVG(bubbleStrokewidht,fillColor,strokeColor,opacity){
opacity=opacity/100;
var fillColorRgba=hexToRgba(fillColor,opacity);
var strokeColorRgba=hexToRgba(strokeColor,1.0);

textLogger.debug("changeSpeechBubbleSVG:",bubbleStrokewidht,fillColorRgba,strokeColorRgba,opacity);

var activeObject=canvas.getActiveObject();
if (activeObject) {

let isExistsFillArea=false;
if(isPath(activeObject)){
activeObject.set({
stroke: strokeColorRgba,
strokeWidth: bubbleStrokewidht,
fill: fillColorRgba
});
}else{
activeObject.forEachObject((obj)=>{

if(obj.data?.originalId==="fillArea"||obj.id==="fillArea"){
isExistsFillArea=true;
return;
}
});

textLogger.debug("isExistsFillArea:",isExistsFillArea)

activeObject.forEachObject((obj)=>{
if(isExistsFillArea){
if(obj.data?.originalId==="fillArea"||obj.id==="fillArea"){
obj.set({
stroke: strokeColorRgba,
fill:fillColorRgba,
strokeWidth:bubbleStrokewidht
});
}else{
obj.set({
stroke: strokeColorRgba ,
fill:strokeColorRgba,
strokeWidth:bubbleStrokewidht
});
textLogger.debug("obj.fill:",obj.fill);

}
}else{
obj.set({stroke: strokeColorRgba ,
fill:fillColorRgba,
strokeWidth:bubbleStrokewidht});
}
});
}
canvas.requestRenderAll();
}
}

function getSpeechBubbleTextFill(activeObject,type){
let isExistsFillArea=false;
if(isPath(activeObject)){
if(type=='fill'){
return activeObject.fill;
}
if(type=='stroke'){
return activeObject.stroke;
}
if(type=='strokeWidth'){
return activeObject.strokeWidth;
}
}else{
activeObject.forEachObject((obj)=>{
if(obj.data?.originalId==="fillArea"){
isExistsFillArea=true;
return;
}
});
activeObject.forEachObject((obj)=>{
if(isExistsFillArea){
if(obj.data?.originalId==="fillArea"){

if(type=='fill'){
return obj.fill;
}
if(type=='stroke'){
return obj.stroke;
}
if(type=='strokeWidth'){
return obj.strokeWidth;
}
}else{
if(type=='fill'){
return obj.fill;
}
if(type=='stroke'){
return obj.stroke;
}
if(type=='strokeWidth'){
return obj.strokeWidth;
}
}
}else{
if(type=='fill'){
return obj.fill;
}
if(type=='stroke'){
return obj.stroke;
}
if(type=='strokeWidth'){
return obj.strokeWidth;
}
}
});
}

if(type=='fill'){
return "rgba(255, 255, 255, 1.0)";
}
if(type=='stroke'){
return "rgba(0, 0, 0, 1.0)";
}
if(type=='strokeWidth'){
return 10;
}
return null;
}

function loadSpeechBubbleSVGReadOnly(svgString,name) {
fabric.loadSVGFromString(svgString,function (objects,options) {

const svgObject=fabric.util.groupSVGElements(objects,options);

let svgData=null;
if (name.startsWith("90_focus_")) {
//skip
}else{
svgData=parseSvg(svgString);
}


let initialWidth=canvas.width*0.35

svgObject.scaleToWidth(initialWidth);
svgObject.baseScaleX=svgObject.scaleX;
svgObject.baseScaleY=svgObject.scaleY;

svgObject.set({
left: 50,
selectable: true,
hasControls: true,
hasBorders: true
});

const selectedValue=getSelectedValueByGroup("sbTextGroup");
if (name.startsWith("90_focus_")||selectedValue==="Nothing") {
canvas.add(svgObject);
}else{
changeDoNotSaveHistory();
canvas.add(svgObject);
changeDoSaveHistory();
createSpeechBubbleMetrics(svgObject,svgData);
}
canvas.setActiveObject(svgObject);
changeSpeechBubble();
canvas.discardActiveObject();
canvas.renderAll();
updateLayerPanel();
});
}

const previewAreaVertical=$("svg-preview-area-vertical");
const previewAreaLandscape=$("svg-preview-area-landscape");
const speechBubbleArea=$("speech-bubble-preview");
var svgDataLoaded={vertical:false,landscape:false,speechBubble:false};

function loadSvgScript(src){
return new Promise(function(resolve,reject){
var script=document.createElement("script");
script.src=src;
script.onload=resolve;
script.onerror=reject;
document.head.appendChild(script);
});
}

function populateVerticalPanels(){
previewAreaVertical.innerHTML="";
MangaPanelsImage_Vertical.forEach((item)=>{
const img=document.createElement("img");
img.src="data:image/svg+xml;utf8,"+encodeURIComponent(item.svg);
img.classList.add("svg-preview");
img.alt=item.name;
img.addEventListener("click",async function(){
panelLogger.debug("new panel");
const loading=OP_showLoading({
icon:'process',step:'Step1',substep:'New Page',progress:0
});
try{
if(stateStack.length>2){
OP_updateLoadingState(loading,{
icon:'process',step:'Step2',substep:'Zip Start',progress:20
});
await btmSaveProjectFile().then(()=>{
setCanvasGUID();
loadSVGPlusReset(item.svg);
});
}else{
setCanvasGUID();
loadSVGPlusReset(item.svg);
}
}finally{
OP_hideLoading(loading);
}
});
previewAreaVertical.appendChild(img);
});
}

function populateLandscapePanels(){
previewAreaLandscape.innerHTML="";
MangaPanelsImage_Landscape.forEach((item)=>{
const img=document.createElement("img");
img.src="data:image/svg+xml;utf8,"+encodeURIComponent(item.svg);
img.classList.add("svg-preview");
img.alt=item.name;
img.addEventListener("click",async function(){
panelLogger.debug("new panel");
const loading=OP_showLoading({
icon:'process',step:'Step1',substep:'New Page',progress:0
});
try{
if(stateStack.length>2){
OP_updateLoadingState(loading,{
icon:'process',step:'Step2',substep:'Zip Start',progress:20
});
await btmSaveProjectFile().then(()=>{
setCanvasGUID();
loadSVGPlusReset(item.svg,true);
});
}else{
setCanvasGUID();
loadSVGPlusReset(item.svg,true);
}
}finally{
OP_hideLoading(loading);
}
});
previewAreaLandscape.appendChild(img);
});
}

function populateSpeechBubbles(){
speechBubbleArea.innerHTML="";
SpeechBubble.forEach((item)=>{
const img=document.createElement("img");
img.src="data:image/svg+xml;utf8,"+encodeURIComponent(item.svg);
img.classList.add("svg-preview");
img.alt=item.name;
img.addEventListener("click",function(){
loadSpeechBubbleSVGReadOnly(item.svg,item.name);
});
speechBubbleArea.appendChild(img);
});
}

function lazyLoadVerticalPanels(){
if(svgDataLoaded.vertical) return;
svgDataLoaded.vertical=true;
previewAreaVertical.textContent="Loading...";
loadSvgScript("js/svg/manga-panels-image-vertical.js?v=7.2").then(function(){
populateVerticalPanels();
}).catch(function(){
svgDataLoaded.vertical=false;
previewAreaVertical.textContent="";
});
}

function lazyLoadLandscapePanels(){
if(svgDataLoaded.landscape) return;
svgDataLoaded.landscape=true;
previewAreaLandscape.textContent="Loading...";
loadSvgScript("js/svg/manga-panels-image-landscape.js?v=7.2").then(function(){
populateLandscapePanels();
}).catch(function(){
svgDataLoaded.landscape=false;
previewAreaLandscape.textContent="";
});
}

function lazyLoadSpeechBubbles(){
if(svgDataLoaded.speechBubble) return;
svgDataLoaded.speechBubble=true;
speechBubbleArea.textContent="Loading...";
loadSvgScript("js/svg/speechbubble.js?v=7.2").then(function(){
populateSpeechBubbles();
}).catch(function(){
svgDataLoaded.speechBubble=false;
speechBubbleArea.textContent="";
});
}

function lazyLoadSvgData(id){
if(id==="svg-container-vertical") lazyLoadVerticalPanels();
if(id==="svg-container-landscape") lazyLoadLandscapePanels();
if(id==="speech-bubble-area1") lazyLoadSpeechBubbles();
}