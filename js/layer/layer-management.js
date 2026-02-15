let finalLayerOrder=[];
let lastHighlightGuid=null;

function getLayerTypeIcon(layer){
if(isSpeechBubbleSVG(layer)||isFreehandBubblePath(layer)){
return '<i class="material-icons">chat_bubble_outline</i>';
}
if(isPanel(layer)){
return '<i class="material-icons">crop_landscape</i>';
}
if(isImage(layer)){
return '<i class="material-icons">image</i>';
}
if(isVerticalText(layer)){
return '<i class="material-icons">text_rotation_none</i>';
}
if(isText(layer)){
return '<i class="material-icons">text_fields</i>';
}
if(isPath(layer)){
return '<i class="material-icons">gesture</i>';
}
if(isGroup(layer)){
return '<i class="material-icons">folder</i>';
}
return '<i class="material-icons">layers</i>';
}

function putLayerBtnSeparator(buttonsDiv){
var sep=document.createElement("span");
sep.className="layer-btn-separator";
buttonsDiv.appendChild(sep);
}

let lastUpdateTime=0;
let updateLayerPanelTimer=null;
let pendingUpdate=false;
let isExecuting=false;

function updateLayerPanel() {
if (isExecuting) {
pendingUpdate=true;
return;
}

const now=Date.now();
const timeSinceLastUpdate=now-lastUpdateTime;

if (updateLayerPanelTimer) {
clearTimeout(updateLayerPanelTimer);
updateLayerPanelTimer=null;
}

if (timeSinceLastUpdate>=60) {
executeUpdate();
} else {
updateLayerPanelTimer=setTimeout(()=>{
executeUpdate();
},60-timeSinceLastUpdate);
}
}

function executeUpdate() {
isExecuting=true;

var layers=canvas.getObjects().slice().reverse();
var layerContent=$("layer-content");
layerContent.innerHTML="";
var guidMap=createGUIDMap(layers);

layers.forEach((layer)=>{
if (!layer.guids||layer.guids.length===0) {
layer.guids=[];
}
});

let isEven=true;
finalLayerOrder=[];

function processLayerHierarchy(layer,processedLayers=new Set(),level=0) {
if (processedLayers.has(layer)) {
return;
}

processedLayers.add(layer);
finalLayerOrder.push({layer: layer,level: level});

if (layer.guids&&layer.guids.length>0) {
const childLayers=layer.guids
.map(guid=>guidMap.get(guid))
.filter(child=>child!==undefined)
.sort((a,b)=>{
const indexA=layers.indexOf(a);
const indexB=layers.indexOf(b);
return indexA-indexB;
});

childLayers.forEach(childLayer=>{
processLayerHierarchy(childLayer,processedLayers,level+1);
});
}
}

const topLevelLayers=layers.filter(layer=>{
const isChildOfAnotherLayer=layers.some(parentLayer=>
parentLayer.guids&&parentLayer.guids.includes(layer.guid)
);
return (layer.isPanel||isSpeechBubbleSVG(layer)||isFreehandBubblePath(layer))&&!isChildOfAnotherLayer;
});

topLevelLayers.forEach(layer=>{
processLayerHierarchy(layer);
});

const remainingLayers=layers.filter(layer=>
!finalLayerOrder.some(item=>item.layer===layer)
);

remainingLayers.forEach(layer=>{
finalLayerOrder.push({layer: layer,level: 0});
});

finalLayerOrder.forEach(({layer,level},index)=>{
if (!layer.excludeFromLayerPanel) {
var layerDiv=Object.assign(document.createElement("div"),{
className: "layer-item",
});
var previewDiv=Object.assign(document.createElement("div"),{
className: "layer-preview",
});
var detailsDiv=Object.assign(document.createElement("div"),{
className: "layer-details",
});
var nameTextArea=Object.assign(document.createElement("input"),{
className: "layer-name",
});
var buttonsDiv=Object.assign(document.createElement("div"),{
className: "layer-buttons",
});

if (isLayerPreview(layer)) {
createPreviewImage(layer,previewDiv);
} else if (isText(layer)) {
var fullText=layer.text;
nameTextArea.value=fullText.substring(0,20);
} else if (isVerticalText(layer)) {
var fullText=layer.name;
if (fullText) {
nameTextArea.value=fullText.substring(0,15);
} else {
layer.name="verticalText";
fullText=layer.name;
nameTextArea.value=fullText.substring(0,15);
}
}

setNameTextAreaProperties(layer,nameTextArea,index);

if (isText(layer)||isSpeechBubbleSVG(layer)||isFreehandBubblePath(layer)) {
detailsDiv.style.flexDirection="row";
detailsDiv.style.alignItems="center";
}

detailsDiv.appendChild(nameTextArea);

putViewButton(buttonsDiv,layer,index);
putMoveLockButton(buttonsDiv,layer,index);
putDeleteButton(buttonsDiv,layer,index);

layerDiv.setAttribute("data-guid",layer.guid);

if (isLayerPreview(layer)) {
layerDiv.appendChild(previewDiv);
}

layerDiv.appendChild(detailsDiv);
detailsDiv.appendChild(buttonsDiv);

const activeObject=canvas.getActiveObject();
var isActive=lastHighlightGuid&&lastHighlightGuid==layer.guid&&
(!activeObject||layer.guid==activeObject.guid);

if(isActive&&(isPanel(layer)||isImage(layer))){
var actionBar=document.createElement("div");
actionBar.className="layer-action-bar";
if(isPanel(layer)){
putActionButton(actionBar,"directions_run","actAiGenerate",function(){
var spinner=createSpinner(index);T2I(layer,spinner);
},AI_ROLES.Image2Image);
putActionButton(actionBar,"recycling","actSeedApply",function(){
if(layer.tempSeed){layer.text2img_seed=layer.tempSeed;createToast("Recycling Seed",layer.text2img_seed);}else{createToast("Nothing Seed","");}
},AI_ROLES.PutSeed);
putActionBarSeparator(actionBar);
putActionButton(actionBar,"download","actDownload",function(){
imageObject2DataURLByCrop(layer).then(function(croppedDataURL){if(croppedDataURL){var link=getLink(croppedDataURL);link.click();}});
});
}
if(isImage(layer)){
putActionButton(actionBar,"directions_run","actAiGenerate",function(){
var spinner=createSpinner(index);I2I(layer,spinner);
},AI_ROLES.Text2Image);
putActionButton(actionBar,"photo_size_select_large","actUpscale",function(){
var spinner=createSpinner(index);aiUpscale(layer,spinner);
},AI_ROLES.Upscaler);
putActionButton(actionBar,"wallpaper","actRemoveBg",function(){
var spinner=createSpinner(index);aiRembg(layer,spinner);
},AI_ROLES.RemoveBG);
putActionButton(actionBar,"3d_rotation","actAngleGen",function(){
openAngleEditor(layer);
},AI_ROLES.I2I_Angle);
putActionButton(actionBar,"inventory","actDeepDanbooru",function(){
var spinner=createSpinnerSuccess(index);sdwebuiInterrogate(layer,"deepdanbooru",spinner.id);
},AI_ROLES.Image2Prompt_DEEPDOORU);
putActionButton(actionBar,"link","actClip",function(){
var spinner=createSpinnerSuccess(index);sdwebuiInterrogate(layer,"clip",spinner.id);
},AI_ROLES.Image2Prompt_CLIP);
putActionBarSeparator(actionBar);
putActionButton(actionBar,"text_snippet","actPromptApply",function(){
if(layer.tempPrompt){layer.text2img_prompt=layer.tempPrompt;createToast("Apply Prompt",layer.text2img_prompt);}else{createToast("Nothing Prompt","");}
if(layer.tempNegative){layer.text2img_negative=layer.tempNegative;createToast("Apply Negative Prompt",layer.text2img_negative);}else{createToast("Nothing Negative Prompt","");}
},AI_ROLES.PutPrompt);
putActionButton(actionBar,"download","actDownload",function(){
var dataURL=imageObject2DataURL(layer);var link=getLink(dataURL);link.click();
});
}
detailsDiv.appendChild(actionBar);
}

layerDiv.onclick=function () {
canvas.setActiveObject(layer);
canvas.renderAll();
highlightActiveLayer(index);
updateControls(layer);
};

if (level>0) {
layerDiv.classList.add("layer-item-nested");
layerDiv.style.marginLeft=`${level * 16}px`;
layerDiv.style.paddingLeft="8px";
} else {
isEven=!isEven;
}

if(isActive){
layerDiv.classList.add("layer-active");
}else if(isEven) {
layerDiv.style.background=getCssValue('--odd-layer');
} else {
layerDiv.style.background=getCssValue('--even-layer');
}

layerContent.appendChild(layerDiv);
}
});

lastUpdateTime=Date.now();
isExecuting=false;

if (pendingUpdate) {
pendingUpdate=false;
setTimeout(updateLayerPanel,0);
}
}

function setNameTextAreaProperties(layer,nameTextArea,index) {
nameTextArea.value=layer.name||nameTextArea.value||layer.type+`${index + 1}`;

layer.name=nameTextArea.value;
nameTextArea.rows=1;
nameTextArea.style.resize="none";
nameTextArea.style.width="100%";
nameTextArea.style.boxSizing="border-box";
nameTextArea.style.color=getCssValue("--text-color-B");
nameTextArea.onclick=function(e){
e.stopPropagation();
};
nameTextArea.oninput=function () {
layer.name=nameTextArea.value;
};

if (isText(layer)) {
nameTextArea.value=layer.text;
nameTextArea.style.flex="1";
nameTextArea.style.width="auto";
nameTextArea.style.marginRight="5px";
}
if (isSpeechBubbleSVG(layer)||isFreehandBubblePath(layer)) {
nameTextArea.style.flex="1";
nameTextArea.style.width="auto";
nameTextArea.style.marginRight="5px";
}
if (isImage(layer)&&layer.text) {
nameTextArea.value=layer.text;
}
}


function calculateCenter(layer) {
const centerX=layer.left+(layer.width/2)*layer.scaleX;
const centerY=layer.top+(layer.height/2)*layer.scaleY;
return {centerX,centerY};
}

function createPreviewImage(layer,layerDiv) {
var previewDiv=document.createElement("div");
var canvasSize=120;

var tempCanvas=document.createElement("canvas");

tempCanvas.width=canvasSize;
tempCanvas.height=canvasSize;
var tempCtx=tempCanvas.getContext("2d");
tempCtx.fillStyle="#e0e0e0";
tempCtx.fillRect(0,0,canvasSize,canvasSize);

var nowVisible=layer.visible;
layer.visible=true;

if (isGroup(layer)) {
var boundingBox=layer.getBoundingRect();
var groupWidth=boundingBox.width;
var groupHeight=boundingBox.height;

var scale=Math.min(canvasSize/groupWidth,canvasSize/groupHeight);

var offsetX=(canvasSize-groupWidth*scale)/2;
var offsetY=(canvasSize-groupHeight*scale)/2;

tempCtx.save();
tempCtx.translate(offsetX,offsetY);
tempCtx.scale(scale,scale);
tempCtx.translate(-boundingBox.left,-boundingBox.top);

layer.getObjects().forEach(function (obj) {
obj.render(tempCtx);
});

tempCtx.restore();
} else if (layer.type==="path") {
var pathBounds=layer.getBoundingRect();
var pathWidth=pathBounds.width;
var pathHeight=pathBounds.height;

var scale=Math.min(canvasSize/pathWidth,canvasSize/pathHeight);
var offsetX=(canvasSize-pathWidth*scale)/2;
var offsetY=(canvasSize-pathHeight*scale)/2;

tempCtx.save();
tempCtx.translate(offsetX,offsetY);
tempCtx.scale(scale,scale);
tempCtx.translate(-pathBounds.left,-pathBounds.top);
layer.render(tempCtx);

tempCtx.restore();
} else if (isImage(layer)&&typeof layer.getElement==="function") {
var imgElement=layer.getElement();
var imgWidth=imgElement.width;
var imgHeight=imgElement.height;

var scale=Math.min(canvasSize/imgWidth,canvasSize/imgHeight);
var drawWidth=imgWidth*scale;
var drawHeight=imgHeight*scale;

var offsetX=(canvasSize-drawWidth)/2;
var offsetY=(canvasSize-drawHeight)/2;

tempCtx.drawImage(imgElement,offsetX,offsetY,drawWidth,drawHeight);
} else if (isPanelType(layer)) {
var layerCanvas=layer.toCanvasElement();
var layerWidth=layer.width;
var layerHeight=layer.height;

var layerScale=Math.min(
canvasSize/layerWidth,
canvasSize/layerHeight
);
var layerDrawWidth=layerWidth*layerScale;
var layerDrawHeight=layerHeight*layerScale;

var layerOffsetX=(canvasSize-layerDrawWidth)/2;
var layerOffsetY=(canvasSize-layerDrawHeight)/2;

tempCtx.drawImage(
layerCanvas,
layerOffsetX,
layerOffsetY,
layerDrawWidth,
layerDrawHeight
);
} else {
layer.render(tempCtx);
}
layer.visible=nowVisible;

var imageUrl=tempCanvas.toDataURL();
previewDiv.style.backgroundImage="url("+imageUrl+")";
previewDiv.style.backgroundSize="contain";
previewDiv.style.backgroundPosition="center";
previewDiv.style.backgroundRepeat="no-repeat";
previewDiv.className="layer-preview";
layerDiv.appendChild(previewDiv);
}

function removeLayer(layer) {
changeDoNotSaveHistory();
canvas.remove(layer);
changeDoSaveHistory();
saveStateByManual();
updateLayerPanel();

if (canvas.getActiveObject()===layer) {
canvas.discardActiveObject();
}
canvas.requestRenderAll();
}

function highlightClear() {
lastHighlightGuid=null;
updateLayerPanel();
}


function highlightActiveLayer(activeIndex) {
highlightActiveLayerByCanvas();
}

function highlightActiveLayerByCanvas(object=null) {

let activeObject;
if(object){
activeObject=object;
}else{
activeObject=canvas.getActiveObject();
}

updateControls(activeObject);
if(isPanel(activeObject)){
showT2IPrompts(activeObject);
}else if(isImage(activeObject)){
showI2IPrompts(activeObject);
}else{
noShowPrompt();
}

lastHighlightGuid=activeObject?activeObject.guid:null;
updateLayerPanel();
}


function getLayerIndexByActiveObject(targetObject) {
if (!targetObject||!finalLayerOrder||finalLayerOrder.length===0) return-1;

const normalIndex=finalLayerOrder.findIndex(item=>item.layer===targetObject);
const result=finalLayerOrder.length-normalIndex;
return result;
}

function LayersUp() {
var activeObject=canvas.getActiveObject();
if (activeObject) {
activeObject.bringForward();
canvas.renderAll();
updateLayerPanel();
saveState();
}
}

function LayersDown() {
var activeObject=canvas.getActiveObject();
if (activeObject) {
activeObject.sendBackwards();
canvas.renderAll();
updateLayerPanel();
saveState();
}
}





