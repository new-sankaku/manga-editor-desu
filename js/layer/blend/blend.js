// ブレンドモードUI - カテゴリ分類・プレビュー・適用処理
const allBlendModes=['normal','add','screen','darken','lighten','color-dodge','color-burn','linear-burn','linear-dodge','linear-light','hard-light','soft-light','pin-light','difference','exclusion','overlay','saturation','color','luminosity','add-npm','subtract','divide','vivid-light','hard-mix','negation'];

const blendModeTranslationKeys={
'normal':'blendNormal',
'darken':'blendDarken',
'color-burn':'blendColorBurn',
'linear-burn':'blendLinearBurn',
'lighten':'blendLighten',
'screen':'blendScreen',
'color-dodge':'blendColorDodge',
'linear-dodge':'blendLinearDodge',
'add':'blendAdd',
'add-npm':'blendAddNpm',
'overlay':'blendOverlay',
'hard-light':'blendHardLight',
'soft-light':'blendSoftLight',
'pin-light':'blendPinLight',
'vivid-light':'blendVividLight',
'linear-light':'blendLinearLight',
'hard-mix':'blendHardMix',
'difference':'blendDifference',
'exclusion':'blendExclusion',
'negation':'blendNegation',
'subtract':'blendSubtract',
'divide':'blendDivide',
'saturation':'blendSaturation',
'color':'blendColor',
'luminosity':'blendLuminosity'
};

const blendCategories=[
{key:'blendCatDarken',modes:['darken','color-burn','linear-burn']},
{key:'blendCatLighten',modes:['lighten','screen','color-dodge','linear-dodge','add','add-npm']},
{key:'blendCatContrast',modes:['overlay','hard-light','soft-light','pin-light','vivid-light','linear-light','hard-mix']},
{key:'blendCatDifference',modes:['difference','exclusion','negation','subtract','divide']},
{key:'blendCatColor',modes:['normal','saturation','color','luminosity']}
];

const layerDisplaySize=150;
const blendDisplaySize=200;

var selectedBlendMode=null;
var selectedBlendCanvas=null;
var blendResultMap={};
var blendCheckedSet=new Set();
var blendVisibilityBackup=new Map();

function createFloatingWindow() {
const floatingWindow=document.createElement("div");
floatingWindow.id="blendFloatingWindow";
const header=document.createElement("div");
header.id="blendFloatingWindowHeader";
const headerTitle=document.createElement("span");
headerTitle.textContent=getText("blendResult");
header.appendChild(headerTitle);
const closeButton=document.createElement("button");
closeButton.id="blendCloseButton";
closeButton.textContent="\u2715";
closeButton.onclick=handleClose;
header.appendChild(closeButton);
const controls=document.createElement("div");
controls.id="blendControls";
const reblendButton=document.createElement("button");
reblendButton.id="reblendButton";
reblendButton.textContent=getText("reblend");
reblendButton.onclick=handleReblend;
const addFillButton=document.createElement("button");
addFillButton.textContent=getText("addFillLayer");
addFillButton.onclick=showFillLayerEditor;
const addGradientButton=document.createElement("button");
addGradientButton.textContent=getText("addGradientLayer");
addGradientButton.onclick=showGradientLayerEditor;
const selectedInfo=document.createElement("span");
selectedInfo.id="blendSelectedInfo";
selectedInfo.textContent=getText("blendSelectMode");
const applyButton=document.createElement("button");
applyButton.id="blendApplyButton";
applyButton.textContent=getText("blendApply");
applyButton.onclick=handleApplySelected;
var layerGroup=document.createElement("div");
layerGroup.className="blend-control-group";
layerGroup.appendChild(addFillButton);
layerGroup.appendChild(addGradientButton);
var applyGroup=document.createElement("div");
applyGroup.className="blend-control-group";
applyGroup.appendChild(selectedInfo);
applyGroup.appendChild(applyButton);
controls.appendChild(reblendButton);
controls.appendChild(layerGroup);
controls.appendChild(applyGroup);
const mainContent=document.createElement("div");
mainContent.id="blendMainContent";
const leftPanel=document.createElement("div");
leftPanel.id="blendLeftPanel";
const sourceImages=document.createElement("div");
sourceImages.id="sourceImages";
const blendModes=document.createElement("div");
blendModes.id="blendModes";
leftPanel.appendChild(sourceImages);
leftPanel.appendChild(blendModes);
const imageListPanel=document.createElement("div");
imageListPanel.id="blendImageList";
const imageListHeader=document.createElement("div");
imageListHeader.id="blendImageListHeader";
imageListHeader.textContent=getText("blendImageListTitle");
imageListPanel.appendChild(imageListHeader);
const imageListBody=document.createElement("div");
imageListBody.id="blendImageListBody";
imageListPanel.appendChild(imageListBody);
mainContent.appendChild(leftPanel);
mainContent.appendChild(imageListPanel);
floatingWindow.appendChild(header);
floatingWindow.appendChild(controls);
floatingWindow.appendChild(mainContent);
document.body.appendChild(floatingWindow);
setupInteractJS(floatingWindow);
}

function recreateFloatingWindow() {
const existingWindow=$("blendFloatingWindow");
if(existingWindow){
existingWindow.remove();
}
createFloatingWindow();
}

function setupInteractJS(element) {
interact(element)
.draggable({
allowFrom:'#blendFloatingWindowHeader',
listeners:{
move(event){
const target=event.target;
const x=(parseFloat(target.getAttribute("data-x"))||0)+event.dx;
const y=(parseFloat(target.getAttribute("data-y"))||0)+event.dy;
target.style.transform=`translate(${x}px, ${y}px)`;
target.setAttribute("data-x",x);
target.setAttribute("data-y",y);
},
},
inertia:true,
modifiers:[
interact.modifiers.restrictRect({
restriction:"parent",
endOnly:true,
}),
],
})
.resizable({
edges:{left:true,right:true,bottom:true,top:true},
listeners:{
move(event){
let {x,y}=event.target.dataset;
x=(parseFloat(x)||0)+event.deltaRect.left;
y=(parseFloat(y)||0)+event.deltaRect.top;
Object.assign(event.target.style,{
width:`${event.rect.width}px`,
height:`${event.rect.height}px`,
transform:`translate(${x}px, ${y}px)`,
});
Object.assign(event.target.dataset,{x,y});
},
},
modifiers:[
interact.modifiers.restrictEdges({
outer:"parent",
endOnly:true,
}),
interact.modifiers.restrictSize({
min:{width:100,height:100},
}),
],
inertia:true,
});
}

async function blendCanvasesWithPixi(canvases,blendMode) {
const maxWidth=Math.max(...canvases.map((c)=>c.width));
const maxHeight=Math.max(...canvases.map((c)=>c.height));
const app=new PIXI.Application();
await app.init({
width:maxWidth,
height:maxHeight,
antialias:false,
backgroundColor:"transparent",
backgroundAlpha:0,
useBackBuffer:true,
clearBeforeRender:false,
preserveDrawingBuffer:true,
});
canvases.forEach((canvas,index)=>{
const texture=PIXI.Texture.from(canvas);
const sprite=new PIXI.Sprite({
texture,
blendMode:index===0?"normal":blendMode,
});
app.stage.addChild(sprite);
});
app.render();
const blendedCanvas=document.createElement("canvas");
blendedCanvas.width=maxWidth;
blendedCanvas.height=maxHeight;
blendedCanvas.getContext("2d").drawImage(app.canvas,0,0);
app.destroy();
return blendedCanvas;
}

function selectBlendMode(mode,blendedCanvas,containerEl) {
var prev=document.querySelector(".blend-mode-selected");
if(prev)prev.classList.remove("blend-mode-selected");
containerEl.classList.add("blend-mode-selected");
selectedBlendMode=mode;
selectedBlendCanvas=blendedCanvas;
var info=$("blendSelectedInfo");
if(info){
var translationKey=blendModeTranslationKeys[mode]||mode;
info.textContent=getText(translationKey);
}
var applyBtn=$("blendApplyButton");
if(applyBtn)applyBtn.classList.add("active");
}

function getCheckedLayers() {
return imageLayerListTemp.filter(function(layer){
var id=getGUID(layer);
return blendCheckedSet.has(id);
});
}

var blendSessionId=0;

async function updateBlendModes(imageLayerList) {
var currentSession=++blendSessionId;
const blendModesContainer=$("blendModes");
blendModesContainer.innerHTML="";
selectedBlendMode=null;
selectedBlendCanvas=null;
blendResultMap={};
var applyBtn=$("blendApplyButton");
if(applyBtn)applyBtn.classList.remove("active");
var info=$("blendSelectedInfo");
if(info)info.textContent=getText("blendSelectMode");
const checkedLayers=getCheckedLayers();
if(checkedLayers.length<2)return;
const canvases=checkedLayers.map((layer)=>
createCanvasFromFabricImage(layer)
);
var modePlaceholders={};
for(var c=0;c<blendCategories.length;c++){
var cat=blendCategories[c];
var categoryDiv=document.createElement("div");
categoryDiv.className="blend-category";
var headerDiv=document.createElement("div");
headerDiv.className="blend-category-header";
var toggle=document.createElement("span");
toggle.className="blend-category-toggle";
toggle.textContent="\u25BC";
var catLabel=document.createElement("span");
catLabel.textContent=getText(cat.key);
headerDiv.appendChild(toggle);
headerDiv.appendChild(catLabel);
headerDiv.onclick=function(el){
return function(){
el.classList.toggle("collapsed");
};
}(categoryDiv);
categoryDiv.appendChild(headerDiv);
var gridDiv=document.createElement("div");
gridDiv.className="blend-category-grid";
for(var m=0;m<cat.modes.length;m++){
var mode=cat.modes[m];
var container=document.createElement("div");
container.className="blend-mode-container blend-mode-loading";
var label=document.createElement("div");
label.className="blend-mode-label";
var translationKey=blendModeTranslationKeys[mode]||mode;
label.textContent=getText(translationKey);
container.appendChild(label);
gridDiv.appendChild(container);
modePlaceholders[mode]=container;
}
categoryDiv.appendChild(gridDiv);
blendModesContainer.appendChild(categoryDiv);
}
var totalModes=allBlendModes.length;
for(let i=0;i<totalModes;i++){
if(currentSession!==blendSessionId)return;
const currentMode=allBlendModes[i];
const blendedCanvas=await blendCanvasesWithPixi(canvases,currentMode);
if(currentSession!==blendSessionId)return;
blendResultMap[currentMode]=blendedCanvas;
var placeholder=modePlaceholders[currentMode];
if(placeholder){
placeholder.classList.remove("blend-mode-loading");
var displayCanvas=createScaledCanvas(blendedCanvas,blendDisplaySize,blendDisplaySize);
placeholder.insertBefore(displayCanvas,placeholder.firstChild);
(function(md,bc,ct){
ct.onclick=function(){
selectBlendMode(md,bc,ct);
};
ct.ondblclick=function(){
showEnlargedImage(bc.toDataURL());
};
})(currentMode,blendedCanvas,placeholder);
}
await new Promise((resolve)=>setTimeout(resolve,0));
}
}

function createScaledCanvas(sourceCanvas,maxWidth,maxHeight){
return HtmlCanvasUtil.createScaledCanvas(sourceCanvas,maxWidth,maxHeight);
}

function isBlendChecked(layer) {
var id=getGUID(layer);
return blendCheckedSet.has(id);
}

function updateLayerPreviewStyle(layer,previewContainer) {
if(isBlendChecked(layer)){
previewContainer.classList.remove("unchecked");
previewContainer.classList.add("checked");
}else{
previewContainer.classList.add("unchecked");
previewContainer.classList.remove("checked");
}
}

var blendDragState=null;

function addImagePreviewsToFloatingWindow(imageLayerList) {
const sourceImagesContainer=$("sourceImages");
sourceImagesContainer.innerHTML="";
var checkedLayers=getCheckedLayers();
checkedLayers.forEach((layer,index)=>{
const previewContainer=document.createElement("div");
previewContainer.className="layer-preview-blend checked";
previewContainer.setAttribute("data-blend-index",index);
const previewCanvas=createCanvasFromFabricImage(layer);
const scaledPreviewCanvas=createScaledCanvas(
previewCanvas,
layerDisplaySize,
layerDisplaySize
);
var dragIndicator=document.createElement("div");
dragIndicator.className="blend-preview-drag-indicator";
dragIndicator.textContent="\u2B0C";
previewContainer.appendChild(dragIndicator);
previewContainer.appendChild(scaledPreviewCanvas);
const label=document.createElement("div");
label.textContent=(index===0?getText("blendLowerLayer"):getText("blendLayer"))+" "+(index+1);
previewContainer.appendChild(label);
previewContainer.onmousedown=function(e){
e.preventDefault();
blendDragState={
item:previewContainer,
index:index,
startIndex:index,
startX:e.clientX,
checkedLayers:checkedLayers
};
previewContainer.classList.add("blend-preview-dragging");
document.onmousemove=handlePreviewDragMove;
document.onmouseup=handlePreviewDragEnd;
};
sourceImagesContainer.appendChild(previewContainer);
});
}

function handlePreviewDragMove(e) {
if(!blendDragState)return;
var container=$("sourceImages");
var items=container.querySelectorAll(".layer-preview-blend");
var dragItem=blendDragState.item;
var dragRect=dragItem.getBoundingClientRect();
var dragMidX=dragRect.left+dragRect.width/2;
for(var i=0;i<items.length;i++){
if(items[i]===dragItem)continue;
var rect=items[i].getBoundingClientRect();
var midX=rect.left+rect.width/2;
if(dragMidX<midX&&blendDragState.index>i){
container.insertBefore(dragItem,items[i]);
reorderCheckedLayers(blendDragState.index,i);
blendDragState.index=i;
blendDragState.startX=e.clientX;
dragItem.style.transform="";
break;
}
if(dragMidX>midX&&blendDragState.index<i){
container.insertBefore(dragItem,items[i].nextSibling);
reorderCheckedLayers(blendDragState.index,i);
blendDragState.index=i;
blendDragState.startX=e.clientX;
dragItem.style.transform="";
break;
}
}
var dx=e.clientX-blendDragState.startX;
dragItem.style.transform="translateX("+dx+"px)";
}

function handlePreviewDragEnd() {
var changed=false;
if(blendDragState){
changed=blendDragState.index!==blendDragState.startIndex;
blendDragState.item.classList.remove("blend-preview-dragging");
blendDragState.item.style.transform="";
blendDragState=null;
}
document.onmousemove=null;
document.onmouseup=null;
if(changed){
addImagePreviewsToFloatingWindow(imageLayerListTemp);
handleReblend();
}
}

function reorderCheckedLayers(fromIndex,toIndex) {
var checkedLayers=getCheckedLayers();
var movedLayer=checkedLayers[fromIndex];
var targetLayer=checkedLayers[toIndex];
var fromGlobal=imageLayerListTemp.indexOf(movedLayer);
var toGlobal=imageLayerListTemp.indexOf(targetLayer);
if(fromGlobal===-1||toGlobal===-1)return;
imageLayerListTemp.splice(fromGlobal,1);
toGlobal=imageLayerListTemp.indexOf(targetLayer);
if(fromIndex<toIndex){
imageLayerListTemp.splice(toGlobal+1,0,movedLayer);
}else{
imageLayerListTemp.splice(toGlobal,0,movedLayer);
}
}

function populateImageList(allLayers) {
var listBody=$("blendImageListBody");
if(!listBody)return;
listBody.innerHTML="";
allLayers.forEach(function(layer){
var id=getGUID(layer);
var item=document.createElement("div");
item.className="blend-image-list-item";
if(blendCheckedSet.has(id)){
item.classList.add("checked");
}
var checkbox=document.createElement("input");
checkbox.type="checkbox";
checkbox.className="blend-image-checkbox";
checkbox.checked=blendCheckedSet.has(id);
checkbox.onchange=function(){
toggleBlendCheck(layer,checkbox.checked);
};
var thumb=document.createElement("div");
thumb.className="blend-image-thumb";
var thumbCanvas=createCanvasFromFabricImage(layer);
var scaledThumb=createScaledCanvas(thumbCanvas,50,50);
thumb.appendChild(scaledThumb);
var nameSpan=document.createElement("span");
nameSpan.className="blend-image-name";
nameSpan.textContent=layer.name||layer.type;
item.onclick=function(e){
if(e.target===checkbox)return;
checkbox.checked=!checkbox.checked;
toggleBlendCheck(layer,checkbox.checked);
};
item.appendChild(checkbox);
item.appendChild(thumb);
item.appendChild(nameSpan);
listBody.appendChild(item);
});
}

function toggleBlendCheck(layer,checked) {
var id=getGUID(layer);
if(checked){
blendCheckedSet.add(id);
}else{
blendCheckedSet.delete(id);
}
refreshBlendUI();
}

function refreshBlendUI() {
addImagePreviewsToFloatingWindow(imageLayerListTemp);
populateImageList(imageLayerListTemp);
handleReblend();
}

var imageLayerListTemp=null;

async function handleBlend() {
var imageLayerList=getImageObjectList();
if(imageLayerList.length<1){
var blendLowImages=getText("blendLowImages");
createToastError("Blend error",blendLowImages);
return;
}
blendCheckedSet=new Set();
blendVisibilityBackup=new Map();
imageLayerList.forEach(function(layer){
var id=getGUID(layer);
blendCheckedSet.add(id);
blendVisibilityBackup.set(id,layer.visible);
});
imageLayerListTemp=imageLayerList;
layerLogger.debug("handleBlend start",imageLayerList.length);
addImagePreviewsToFloatingWindow(imageLayerList);
populateImageList(imageLayerList);
$("blendFloatingWindow").style.display="flex";
await updateBlendModes(imageLayerList);
}

async function handleReblend() {
await updateBlendModes(imageLayerListTemp);
}

function handleApplySelected() {
if(!selectedBlendCanvas)return;
handleSubmit(selectedBlendCanvas);
}

function handleSubmit(blendedCanvas,quality=0.98) {
sendHtmlCanvas2FabricCanvas(blendedCanvas);
removeAdditionalLayers();
restoreVisibility();
$("blendFloatingWindow").style.display="none";
}

function restoreVisibility() {
blendVisibilityBackup.forEach(function(visible,id){
var layers=canvas.getObjects();
for(var i=0;i<layers.length;i++){
if(layers[i].guid===id){
layers[i].visible=visible;
break;
}
}
});
blendVisibilityBackup.clear();
canvas.renderAll();
}

function handleClose() {
removeAdditionalLayers();
restoreVisibility();
$("blendFloatingWindow").style.display="none";
}

createFloatingWindow();

let brendContainer,brendImg;

function initializeBrendImageViewer() {
brendContainer=document.createElement('div');
brendContainer.id='enlargedImageContainerBlend';
brendContainer.style.display='none';
brendImg=document.createElement('img');
brendImg.id='enlargedImage';
brendContainer.appendChild(brendImg);
document.body.appendChild(brendContainer);
brendContainer.addEventListener('click',hideEnlargedImage);
}

function showEnlargedImage(src) {
if(!brendImg)initializeBrendImageViewer();
brendImg.src=src;
brendContainer.style.display="block";
}

function hideEnlargedImage() {
brendContainer.style.display='none';
}

function showFillLayerEditor() {
const editor=createLayerEditor('fill');
editor.innerHTML=`
<h3>${getText("fillLayer")}</h3>
<label class="blend-editor-label">${getText("blendColorLabel")}</label>
<input id="blendFillColor" class="jscolor-color-picker" data-initial-color="rgba(0,0,0,1)">
<div class="blend-editor-buttons">
<button onclick="addFillLayer()">${getText("addLayer")}</button>
<button onclick="closeLayerEditor('fill')">${getText("op_cancel")}</button>
</div>
`;
document.body.appendChild(editor);
jsColorSetById("blendFillColor");
}

function showGradientLayerEditor() {
const editor=createLayerEditor('gradient');
editor.innerHTML=`
<h3>${getText("gradientLayer")}</h3>
<label class="blend-editor-label">${getText("blendStartColor")}</label>
<input id="gradientStart" class="jscolor-color-picker" data-initial-color="rgba(0,0,0,1)">
<label class="blend-editor-label">${getText("blendEndColor")}</label>
<input id="gradientEnd" class="jscolor-color-picker" data-initial-color="rgba(255,255,255,1)">
<label class="blend-editor-label">${getText("dragToSetDirection")}</label>
<canvas id="gradientDirection" width="200" height="200" style="border:1px solid var(--fjm-border-color);"></canvas>
<div class="blend-editor-buttons">
<button onclick="addGradientLayer()">${getText("addLayer")}</button>
<button onclick="closeLayerEditor('gradient')">${getText("op_cancel")}</button>
</div>
`;
document.body.appendChild(editor);
jsColorSetById("gradientStart");
jsColorSetById("gradientEnd");
setupGradientDirectionDrag();
}

function createLayerEditor(type) {
const editor=document.createElement('div');
editor.id=`${type}LayerEditor`;
editor.className='blend-layer-editor';
return editor;
}

let startX,startY,endX,endY;

function setupGradientDirectionDrag() {
const directionElement=$('gradientDirection');
directionElement.onmousedown=(e)=>{
startX=e.offsetX;
startY=e.offsetY;
document.onmousemove=(e)=>{
const rect=directionElement.getBoundingClientRect();
endX=e.clientX-rect.left;
endY=e.clientY-rect.top;
drawGradientPreview();
};
document.onmouseup=()=>{
document.onmousemove=null;
document.onmouseup=null;
};
};
endX=directionElement.width;
endY=directionElement.height;
}

function drawGradientPreview() {
const directionElement=$('gradientDirection');
const ctx=directionElement.getContext('2d');
const gradient=ctx.createLinearGradient(startX,startY,endX,endY);
layerLogger.debug("$('gradientStart').value:",$('gradientStart').value);
gradient.addColorStop(0,$('gradientStart').value);
gradient.addColorStop(1,$('gradientEnd').value);
ctx.fillStyle=gradient;
ctx.fillRect(0,0,directionElement.width,directionElement.height);
}

let additionalLayers=[];
function addFillLayer() {
const color=$('blendFillColor').value;
const fillLayer=new fabric.Rect({
width:canvas.width,
height:canvas.height,
fill:color,
selectable:false
});
canvas.add(fillLayer);
additionalLayers.push(fillLayer);
var id=getGUID(fillLayer);
blendCheckedSet.add(id);
canvas.renderAll();
updateLayerList();
closeLayerEditor('fill');
}

function addGradientLayer() {
const startColor=$('gradientStart').value;
const endColor=$('gradientEnd').value;
const gradientLayer=new fabric.Rect({
width:canvas.width,
height:canvas.height,
fill:new fabric.Gradient({
type:'linear',
gradientUnits:'percentage',
coords:{
x1:startX/200,
y1:startY/200,
x2:endX/200,
y2:endY/200
},
colorStops:[
{offset:0,color:startColor},
{offset:1,color:endColor}
]
}),
selectable:false
});
canvas.add(gradientLayer);
additionalLayers.push(gradientLayer);
var id=getGUID(gradientLayer);
blendCheckedSet.add(id);
canvas.renderAll();
updateLayerList();
closeLayerEditor('gradient');
}

function closeLayerEditor(type) {
const editor=$(`${type}LayerEditor`);
editor.remove();
}

function updateLayerList() {
let imageLayers=getImageObjectList();
let allLayers=[...imageLayers,...additionalLayers];
imageLayerListTemp=allLayers;
addImagePreviewsToFloatingWindow(allLayers);
populateImageList(allLayers);
handleReblend();
}

function removeAdditionalLayers() {
additionalLayers.forEach(layer=>{
canvas.remove(layer);
});
additionalLayers=[];
canvas.renderAll();
}
