let finalLayerOrder=[];
let lastHighlightGuid=null;
// ロックされたオブジェクトを押したときに、鍵を目立たせる行のGUID。
// キャンバス側にはロックされていることを示すものが無く、外す入口も
// この鍵しかないため、押された時だけここへ目を向けさせる
let lockHintGuid=null;
let lockHintTimer=null;
let lockHintScrollPending=false;
// 目立たせたままにすると点滅が居座る。トーストと同じ長さで畳む
const LOCK_HINT_DURATION=4000;
// 名前を編集中の行。パネルは選択のたびに作り直され、しかも作り直しが遅れて走ることも
// あるため、編集中かどうかをDOM側に置くと入力の途中でフォーカスごと消える
let layerNameEditGuid=null;
// 作り直しで行ごと消えるときも blur は飛ぶ。これを編集の終了と取ると、
// 作り直しのたびに編集が切れる
let layerPanelRebuilding=false;

function beginLayerNameEdit(nameTextArea) {
nameTextArea.readOnly=false;
nameTextArea.style.cursor="text";
// 作り直しのたびに選択し直すと、入力中の文字が消える
if (document.activeElement!==nameTextArea) {
nameTextArea.focus();
nameTextArea.select();
}
}

// 二重クリックは行ではなく #layer-content で受ける。1回目のクリックで行が
// 作り直されると2回のクリックの対象が別物になり、dblclickは行ではなく共通の祖先へ飛ぶ。
// どちらへ飛んでも拾えるよう、対象から辿れないときは座標から引き直す
function onLayerNameDblclick(e) {
var nameTextArea=e.target.closest ? e.target.closest(".layer-name") : null;
if (!nameTextArea) {
var under=document.elementFromPoint(e.clientX,e.clientY);
nameTextArea=under&&under.closest ? under.closest(".layer-name") : null;
}
if (!nameTextArea) {
return;
}
var row=nameTextArea.closest(".layer-item");
layerNameEditGuid=row ? row.getAttribute("data-guid") : null;
beginLayerNameEdit(nameTextArea);
}

// blur だけを終了の合図にしない。Enterでも確実に抜けられるようにする。
// readOnlyを見て二度目は何もしないので、blur()が呼び戻しても止まる
function endLayerNameEdit(nameTextArea) {
if (nameTextArea.readOnly) {
return;
}
layerNameEditGuid=null;
nameTextArea.readOnly=true;
nameTextArea.style.cursor="pointer";
nameTextArea.blur();
}

function isLockHintTarget(guid){
return lockHintGuid!==null&&String(guid)===String(lockHintGuid);
}

function clearLockHint(){
if(lockHintTimer){
clearTimeout(lockHintTimer);
lockHintTimer=null;
}
if(lockHintGuid===null){
return;
}
lockHintGuid=null;
updateLayerPanel();
}

// ロックされたオブジェクトが押されたときの案内。同じ相手を押し続けても
// トーストが積み上がらないよう、目立たせている間は出し直さない
function hintLockedLayer(obj){
if(!obj){
return;
}
var guid=getGUID(obj);
if(isLockHintTarget(guid)){
return;
}
if(lockHintTimer){
clearTimeout(lockHintTimer);
}
lockHintGuid=guid;
lockHintScrollPending=true;
lockHintTimer=setTimeout(clearLockHint,LOCK_HINT_DURATION);
createToastError(getText("lockedObjectTitle"),getText("lockedObjectBody"),LOCK_HINT_DURATION);
updateLayerPanel();
}

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
// 作り直す時点でフォーカスが名前欄から離れているなら編集は終わっている。
// ここで畳まないと、blurを取り逃したときに作り直しのたびに名前欄がフォーカスを
// 奪い続け、キャンバス上の文字入力ができなくなる
if (layerNameEditGuid&&!(document.activeElement&&document.activeElement.classList
&&document.activeElement.classList.contains("layer-name"))) {
layerNameEditGuid=null;
}

var layerContent=$("layer-content");
// 行は毎回作り直されるが入れ物は残る。ここに1回だけ付ける
if (!layerContent.dataset.nameEditBound) {
layerContent.dataset.nameEditBound="1";
layerContent.addEventListener("dblclick",onLayerNameDblclick);
}
layerPanelRebuilding=true;
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

var editingNameTextArea=null;

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

if(layer.guid){
renderAiTaskIndicators(detailsDiv,layer.guid);
}

putReferenceCountBadge(buttonsDiv,layer);
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
putActionButton(actionBar,"draw","actWhiteboard",function(){whiteboardOpen(layer);});
putActionButton(actionBar,"directions_run","actAiGenerate",function(){
var spinner=createSpinner(getGUID(layer),'T2I');T2I(layer,spinner);
},AI_ROLES.Image2Image);
putActionButton(actionBar,"recycling","actSeedApply",function(){
if(layer.tempSeed){layer.text2img_seed=layer.tempSeed;createToast("Recycling Seed",layer.text2img_seed);}else{createToastError("Nothing Seed","");}
},AI_ROLES.PutSeed);
putActionBarSeparator(actionBar);
putActionButton(actionBar,"download","actDownload",function(){
imageObject2DataURLByCrop(layer).then(function(croppedDataURL){if(croppedDataURL){var link=getLink(croppedDataURL);link.click();}});
});
putMoreMenuActionButton(actionBar,layer);
}
if(isImage(layer)){
putActionButton(actionBar,"draw","actWhiteboard",function(){whiteboardOpen(layer);});
putActionButton(actionBar,"directions_run","actAiGenerate",function(){
var spinner=createSpinner(getGUID(layer),'I2I');I2I(layer,spinner);
},AI_ROLES.Text2Image);
putActionButton(actionBar,"photo_size_select_large","actUpscale",function(){
var spinner=createSpinner(getGUID(layer),'UP');aiUpscale(layer,spinner);
},AI_ROLES.Upscaler);
putActionButton(actionBar,"wallpaper","actRemoveBg",function(){
var spinner=createSpinner(getGUID(layer),'BG');aiRembg(layer,spinner);
},AI_ROLES.RemoveBG);
putActionButton(actionBar,"3d_rotation","actAngleGen",function(){
openAngleEditor(layer);
},AI_ROLES.I2I_Angle);
putActionButton(actionBar,"inventory","actDeepDanbooru",function(){
var spinner=createSpinnerSuccess(getGUID(layer),'TAG');sdwebuiInterrogate(layer,"deepdanbooru",spinner.id);
},AI_ROLES.Image2Prompt_DEEPDOORU);
putActionButton(actionBar,"link","actClip",function(){
var spinner=createSpinnerSuccess(getGUID(layer),'TAG');sdwebuiInterrogate(layer,"clip",spinner.id);
},AI_ROLES.Image2Prompt_CLIP);
putActionButton(actionBar,"smart_toy","actLlmTag",function(){
var spinner=createSpinnerSuccess(getGUID(layer),'TAG');llmImage2Prompt(layer,spinner.id);
},AI_ROLES.Image2Prompt_LLM);
putActionBarSeparator(actionBar);
putActionButton(actionBar,"text_snippet","actPromptApply",function(){
if(layer.tempPrompt){layer.text2img_prompt=layer.tempPrompt;createToast("Apply Prompt",layer.text2img_prompt);}else{createToastError("Nothing Prompt","");}
if(layer.tempNegative){layer.text2img_negative=layer.tempNegative;createToast("Apply Negative Prompt",layer.text2img_negative);}else{createToastError("Nothing Negative Prompt","");}
},AI_ROLES.PutPrompt);
putActionButton(actionBar,"download","actDownload",function(){
var dataURL=imageObject2DataURL(layer);var link=getLink(dataURL);link.click();
});
putMoreMenuActionButton(actionBar,layer);
}
detailsDiv.appendChild(actionBar);
}

layerDiv.onclick=function () {
// 非表示のレイヤーは選択させない。選ぶと見えないままハンドルだけが出て、
// Deleteで何が消えるのかが画面から分からなくなる
if(!layer.visible){
canvas.discardActiveObject();
canvas.renderAll();
updateLayerPanel();
return;
}
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

// 鍵を目立たせている行は画面に入れる。レイヤーが多いと、点滅していても
// スクロールの外にあって気付けない
if(lockHintScrollPending&&isLockHintTarget(layer.guid)){
lockHintScrollPending=false;
layerDiv.scrollIntoView({block:"nearest"});
}

// data-guid は文字列。layer.guidと型が違うことがあるので揃えて比べる
if (layerNameEditGuid&&String(layer.guid)===layerNameEditGuid) {
editingNameTextArea=nameTextArea;
}
}
});

// 編集中だった行はDOMに入れ終えてから戻す。入れる前にfocus()しても効かない
if (layerNameEditGuid) {
if (editingNameTextArea) {
beginLayerNameEdit(editingNameTextArea);
} else {
layerNameEditGuid=null;
}
}
layerPanelRebuilding=false;

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
// 行のほとんどを名前の入力欄が占める。テキストレイヤーには見本画像も付かないため、
// 入力欄がクリックを止めると押して選択できる場所が行に残らない。
// 単一クリックは行の選択に通し、名前の編集はダブルクリックで始める
nameTextArea.readOnly=true;
nameTextArea.style.cursor="pointer";
// readOnlyでもクリックでフォーカスと文字選択が起きる。押した見た目が
// 「選択」ではなく「入力」になるため、編集中以外は取らせない
nameTextArea.onmousedown=function (e) {
if (nameTextArea.readOnly) {
e.preventDefault();
}
};
// 編集中のクリックは行の選択へ通さない。通すと作り直しが走り、
// カーソルを置き直すたびに全選択に戻る
nameTextArea.onclick=function (e) {
if (!nameTextArea.readOnly) {
e.stopPropagation();
}
};
nameTextArea.onblur=function () {
// 作り直しで外れた行のblurは、入れ替わった先の編集を打ち切らないよう無視する
if (layerPanelRebuilding||!document.contains(nameTextArea)) {
return;
}
endLayerNameEdit(nameTextArea);
};
nameTextArea.onkeydown=function (e) {
if (e.key==="Enter"||e.key==="Escape") {
endLayerNameEdit(nameTextArea);
}
};
nameTextArea.oninput=function () {
layer.name=nameTextArea.value;
// 名前を付けたことを覚える。覚えないとテキストレイヤーは下の同期で本文へ戻る
layer.nameEdited=true;
};

if (isText(layer)) {
// 名前を付けていないテキストは本文をそのまま名前にする。付けた名前があるならそれを出す。
// 表示に本文、書き込み先にnameを使うと、打った文字が作り直しのたびに本文へ戻る
if (!layer.nameEdited) {
layer.name=layer.text;
}
nameTextArea.value=layer.name;
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

// 行が狭く末尾は省略される。全文はカーソルを重ねれば読めるようにする
nameTextArea.title=nameTextArea.value;
}


function calculateCenter(layer) {
const centerX=layer.left+(layer.width/2)*layer.scaleX;
const centerY=layer.top+(layer.height/2)*layer.scaleY;
return {centerX,centerY};
}

// レイヤーパネルのサムネイル描画。コマ（rect/circle/polygon）のプレビューで呼ぶ
// fabricのtoCanvasElement()が内部でset()を実行するため、抑止しないと自動コミット網が
// 「キャンバスが変わった」と誤検知する。updateLayerPanel()は履歴の保存後と復元後に
// 毎回走るので、抑止しないと次のキー操作・クリックで空のコミットが積まれ、
// Undo直後のRedoが消える
function createPreviewImage(layer,layerDiv) {
withoutHistory(function(){
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
});
}

function removeLayer(layer) {
withoutHistory(function(){
canvas.remove(layer);
});
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





