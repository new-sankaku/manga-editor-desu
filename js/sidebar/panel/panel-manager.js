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
// ファイル以外も落ちてくる（設定資料のサムネイルなど）。
// 素通しにすると file.type で落ちるため、ここで見る
if(!e.dataTransfer.files||!e.dataTransfer.files.length)return;
var file=e.dataTransfer.files[0];
var canvasElement=canvas.getElement();
var rect=canvasElement.getBoundingClientRect();
var x=e.clientX-rect.left;
var y=e.clientY-rect.top;


if (file.type==='image/svg+xml') {
var reader=new FileReader();
reader.onload=function(event) {
var svgText=event.target.result;
panelLogger.info("[drop SVG] stateStack.length="+stateStack.length+" contentObjectCount="+getContentObjectCount()+" canvasGUID="+getCanvasGUID());
if (stateStack.length>=2&&getContentObjectCount()>0) {
panelLogger.info("[drop SVG] putImageInFrame branch");
var canvasX=x/canvasContinerScale;
var canvasY=y/canvasContinerScale;
putImageInFrame(svgText,canvasX,canvasY);
} else {
panelLogger.info("[drop SVG] addInitialImageToCanvas branch");
fabric.loadSVGFromString(svgText,function(objects,options) {
var loadedObject=fabric.util.groupSVGElements(objects,options);
addInitialImageToCanvas(loadedObject);
panelLogger.info("[drop SVG] after addInitialImageToCanvas: stateStack.length="+stateStack.length);
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
panelLogger.error("Failed to convert to WebP",error);
return;
}

var reader=new FileReader();
reader.onload=function (f) {
var data=f.target.result;

fabric.Image.fromURL(data,function (img) {
panelLogger.info("[drop] stateStack.length="+stateStack.length+" contentObjectCount="+getContentObjectCount()+" canvasGUID="+getCanvasGUID()+" btmProjectsMap.size="+btmProjectsMap.size);
if (stateStack.length>=2&&getContentObjectCount()>0) {
panelLogger.info("[drop] putImageInFrame branch (existing content)");
var canvasX=x/canvasContinerScale;
var canvasY=y/canvasContinerScale;
putImageInFrame(img,canvasX,canvasY);
} else {
panelLogger.info("[drop] addInitialImageToCanvas branch (first image on canvas)");
addInitialImageToCanvas(img);
}
panelLogger.info("[drop] after image added: stateStack.length="+stateStack.length+" contentObjectCount="+getContentObjectCount());

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
setSave(img);
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

panelLogger.debug("newImageObject,",newImageObject);
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

// AI generation can be started from either the panel itself or an image that is
// already clipped to that panel.  Always resolve the real panel before deciding
// where the new content belongs.
var resolvedTargetLayer=targetLayer&&targetLayer.relatedPoly?targetLayer.relatedPoly:targetLayer;

if(notReplace){
//skip
}else{
canvas.add(obj);
}

var targetFrameIndex=resolvedTargetLayer?canvas.getObjects().indexOf(resolvedTargetLayer):findTargetFrame(x,y);
panelLogger.debug("targetFrameIndex",targetFrameIndex);
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
if(!notReplace){
stackFrameContentBelowOverlays(obj,targetFrame);
}
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
setSave(obj);
saveStateByManual();
return obj;
}

return obj;
}

// Fabric adds new objects at the very top of the canvas.  A generated panel
// image would therefore cover dialogue text and speech bubbles, which are not
// children of the panel.  Keep all clipped panel content together immediately
// above its panel, preserving the existing child order and placing the newest
// result on top of the older panel images but below independent overlays.
function stackFrameContentBelowOverlays(newObject,targetFrame) {
if(!isPanel(targetFrame)){
return;
}

var objects=canvas.getObjects().slice();
var insertIndex=objects.indexOf(targetFrame)+1;
if(insertIndex===0){
return;
}

objects
.filter(function(candidate){
return candidate!==newObject&&candidate.relatedPoly===targetFrame;
})
.forEach(function(candidate){
candidate.moveTo(insertIndex);
insertIndex++;
});

newObject.moveTo(insertIndex);
}


// 落とし先のコマを最前面から探す。外接矩形ではなくコマの実際の形で見る
// （isPointInShape）。矩形で見ると、斜めのコマや重なったコマでは
// ポインタが乗っていないコマに入る
function findTargetFrame(x,y) {
let objects=canvas.getObjects();
for (let i=objects.length-1;i>=0;i--) {
if (isShapes(objects[i])&&isPointInShape(objects[i],x,y)) {
return i;
}
}
return-1;
}

// 点の上にあるコマ。トーンや図形ではなくコマ（isPanel）だけを見る。
// 自分自身は除く
function findPanelUnderPoint(x,y,excludeObject) {
var objects=canvas.getObjects();
for (var i=objects.length-1;i>=0;i--) {
var obj=objects[i];
if (obj===excludeObject) {
continue;
}
if (isPanel(obj)&&isPointInShape(obj,x,y)) {
return obj;
}
}
return null;
}


// ロックの案内を出してよいのは、ふつうに選んで動かす状態のときだけ。
// ナイフ・ペン・吹き出しの各モードは、モードの都合で全件を選択不可にする
function isPlainSelectMode() {
if (isKnifeMode||canvas.isDrawingMode) {
return false;
}
if (ModeManager.getCurrent()!==ModeManager.MODE.SELECT) {
return false;
}
return true;
}


// ---- コマと中身のリンクの追随 ------------------------------------------
// clipPathは絶対座標で作られるため、置いた時のコマの形のまま固定される。
// 絵をコマの外へ動かしても、コマを消しても、その形の切り抜きだけが残り
// 画面から絵が消える。配置・移動・削除の各所へ直しを撒くと漏れるので、
// 「移動が確定した時」「オブジェクトが外れた時」のイベント1か所へ寄せる。

// 表示制限と親子リンクだけを外す。オブジェクトそのものは残す
function releasePanelLink(child) {
if (child.removeSettings) {
child.removeSettings();
}
child.clipPath=undefined;
child.dirty=true;
}

// 今いる場所から所属コマを判定し直す。別のコマへ入っていれば乗り換え、
// どのコマにも入っていなければ表示制限を外す
function relinkToPanelUnderObject(obj) {
if (!obj||!obj.relatedPoly) {
return false;
}
if (isPanel(obj)||!isPanel(obj.relatedPoly)) {
return false;
}
var center=getAbsoluteCenterPoint(obj);
var nextFrame=findPanelUnderPoint(center.x,center.y,obj);
if (nextFrame===obj.relatedPoly) {
return false;
}
panelLogger.debug("[relink] "+obj.name+" : "+obj.relatedPoly.name+" -> "+(nextFrame?nextFrame.name:"none"));
releasePanelLink(obj);
if (nextFrame) {
moveSettings(obj,nextFrame);
setGUID(nextFrame,obj);
}
return true;
}

// 複製されたオブジェクトのコマとのリンクを整える。**複製直後に必ず通す。**
// `clone()` は `relatedPoly` も `guid` も引き継がないのに、`clipPath` だけは
// 元のコマの位置と形を写した静的なコピーとして付いてくる。そのまま動かすと、
// リンクが無いので追随もせず、存在しない切り抜きの外へ出て画面から消える。
// 複製の入口が複数ある（右クリックの複製・Ctrl+C/V）ため、入口ごとに書かずここへ寄せる。
// sourceObj は複製元。分かるなら渡す（省略可）。分かる場合は元と同じコマを優先する
function relinkClonedObject(cloned,sourceObj) {
if (!cloned) {
return;
}
// 静的なコピーは必ず落とす。リンクを張り直せたときは moveSettings が作り直す
cloned.clipPath=undefined;
cloned.dirty=true;
if (isPanel(cloned)) {
return;
}
var center=getAbsoluteCenterPoint(cloned);
var frame=findPanelUnderPoint(center.x,center.y,cloned);
// 重なったコマの上では最前面のコマが返るため、複製だけ別のコマに入ることがある。
// 元がコマの中にあり、複製もそのコマの中に落ちているなら元と同じコマにする
if (sourceObj&&isPanel(sourceObj.relatedPoly)&&
canvas.getObjects().indexOf(sourceObj.relatedPoly)!==-1&&
isPointInShape(sourceObj.relatedPoly,center.x,center.y)) {
frame=sourceObj.relatedPoly;
}
if (!frame) {
return;
}
moveSettings(cloned,frame);
setGUID(frame,cloned);
}

// コマを消したとき、中に入れた絵・トーンは残す。ただし消えたコマの形の
// 表示制限と親子リンクは外す。外さないと、キャンバスに無いコマの形で
// 切り抜かれたまま残り、動かすと欠ける。
// 消す経路がDeleteキー・右クリック・レイヤーの✕と複数あるため、
// オブジェクトが外れたこの1か所で揃える
function releasePanelChildren(panel) {
if (!panel.guids||panel.guids.length===0) {
return;
}
panel.guids.slice().forEach(function (guid) {
var child=getObjectByGUID(guid);
if (!child||child.relatedPoly!==panel) {
return;
}
releasePanelLink(child);
});
}

document.addEventListener('DOMContentLoaded',function () {
canvas.on('object:modified',function (e) {
var target=e.target;
if (!target) {
return;
}
var changed=false;
if (target.type==='activeSelection') {
target.getObjects().forEach(function (obj) {
changed=relinkToPanelUnderObject(obj)||changed;
});
} else {
changed=relinkToPanelUnderObject(target);
}
if (changed) {
canvas.requestRenderAll();
updateLayerPanel();
// clipPath・relatedPolyは直接代入で書き換えるため、自動コミット網では拾えない
commitHistoryDebounced();
}
});

canvas.on('object:removed',function (e) {
// Undo/Redoの復元はキャンバスを一度空にしてから作り直す。
// そこで外すと、作り直しの元になるオブジェクトを触ることになる
if (isHistoryRestoreInProgress()) {
return;
}
if (!e.target||!isPanel(e.target)) {
return;
}
releasePanelChildren(e.target);
});

// コマは既定でロックされて生まれる（loadSVGPlusReset / panel-template.js）。
// 押しても選択枠が出ない理由が画面に何も出ないため、壊れているように見える。
// カーソルで示し、押されたらレイヤーの鍵を目立たせてそこから外せるようにする
canvas.on('mouse:over',function (e) {
var obj=e.target;
if (!obj) {
return;
}
if (!isPlainSelectMode()) {
// モード中は全件を一律に選択不可にする経路があるため、ロックとは区別する
obj.hoverCursor=null;
return;
}
obj.hoverCursor=obj.selectable?null:'not-allowed';
});

canvas.on('mouse:up',function (e) {
var obj=e.target;
if (!obj||obj.selectable) {
return;
}
if (!isPlainSelectMode()) {
return;
}
// 吹き出しの当たり判定用の矩形は、仕組みとして選択させないもの
if (obj.customType==="freehandBubbleRect") {
return;
}
hintLockedLayer(obj);
});
});

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
return new Promise(function(resolve,reject){
initImageHistory();
changeDoNotSaveHistory();
// console.log("svgPagging", svgPagging);

skipForcedAdjust=true;
fabric.loadSVGFromString(svgString,function (objects,options) {
try{
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
skipForcedAdjust=false;
canvas.renderAll();
resizeCanvas(canvas.width,canvas.height);
}catch(error){
reject(error);
return;
}finally{
skipForcedAdjust=false;
changeDoSaveHistory();
}
try{
// saveState()は次のtickへコミットするため、ページ登録より先に明示的に確定する。
// ここまで待って初めて呼び出し側へ完了を返す。
saveState();
flushHistory();
updateLayerPanel();
resolve();
}catch(error){
reject(error);
}
});
});
}






/** Disallow drag-on-drop. */
document.addEventListener("DOMContentLoaded",function () {
var svgPreviewArea=$("svg-container-template");
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


// コマは既定でロックされて生まれる。ロックが原因で選べないのか、
// そもそも選んでいないのかを言い分けるために使う
function getFirstLockedPanel() {
var objects=canvas.getObjects();
for (var i=0;i<objects.length;i++) {
if (isPanel(objects[i])&&!objects[i].selectable) {
return objects[i];
}
}
return null;
}

function Edit() {
var poly=canvas.getActiveObject();
var editButton=$("edit");
if (!poly) {
// ひな形直後のコマはロックされて生まれるため、キャンバスを押しても選べない。
// 「押しても何も起きない」で終わらせず、次の一手まで出す
var lockedPanel=getFirstLockedPanel();
if (lockedPanel) {
createToastError(getText("editModeNeedUnlockTitle"),getText("editModeNeedUnlockBody"));
hintLockedLayer(lockedPanel);
} else {
createToastError(getText("editModeNotPanel"),getText("editModeSelectPanelBody"));
}
return;
}
if (!isPanel(poly)) {
createToastError(getText("editModeNotPanel"),getText("editModeSelectPanelBody"));
return;
}
if (!poly.selectable&&!poly.edit) {
// ロックされたコマは点をつかめない。入っても操作できないモードには入れない
createToastError(getText("editModeNeedUnlockTitle"),getText("editModeNeedUnlockBody"));
hintLockedLayer(poly);
return;
}
if (!(poly instanceof fabric.Polygon)) {
createToastError(getText("editModeNotPolygon"),"");
return;
}
if (!poly.points||poly.points.length<3) {
createToastError(getText("editModeNoPoints"),"");
return;
}
// 「今どのモードか」「案内文」「モード解除ボタンの点灯」は ModeManager が持つ。
// clearAll() が走るので、点のコントロールを組み立てる前に呼ぶ。
// clearAll() は edit.clear() 経由で poly.edit を false へ戻すため、
// トグル（!poly.edit）ではなく先に決めた値を入れる
var willEdit=!poly.edit;
if (willEdit) {
ModeManager.edit.enable();
} else {
ModeManager.clearAll();
}
poly.edit=willEdit;
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
// モード解除ボタンの点灯と案内文は ModeManager が持つ（直呼びしない）
editButton.classList.add("selected");
editButton.querySelector("span").textContent=getText("editModeOff");
} else {
poly.cornerStyle="rect";
poly.controls=fabric.Object.prototype.controls;
editButton.classList.remove("selected");
editButton.querySelector("span").textContent=getText("editModeOn");
}
poly.hasBorders=!poly.edit;
canvas.requestRenderAll();
updateLayerPanel();
}

// コマ設定は選んでいるコマにだけ効く。未選択・コマ以外を選んでいるときは
// 何も起きず、壊れているように見える。4つの入口が同じ前提を持つので、
// ここ1か所で理由を出す。つまみを動かす間に積み上がらないよう、
// トーストが消えるまで（4秒）は出し直さない
var PANEL_TARGET_WARN_INTERVAL=4000;
var lastPanelTargetWarnAt=0;
function requirePanelTarget() {
var activeObject=canvas.getActiveObject();
if (isPanel(activeObject)) {
return activeObject;
}
var now=Date.now();
if (now-lastPanelTargetWarnAt>=PANEL_TARGET_WARN_INTERVAL) {
lastPanelTargetWarnAt=now;
createToastError(getText("panelSettingNoTargetTitle"),getText("panelSettingNoTargetBody"));
}
return null;
}

function changePanelStrokeWidth(value) {
var activeObject=requirePanelTarget();
if (activeObject) {
activeObject.set({
strokeWidth: parseFloat(value),
strokeUniform: true,
});
canvas.requestRenderAll();
afterPanelValueChange(activeObject);
}
}
function changePanelStrokeColor(value) {
var activeObject=requirePanelTarget();
if (activeObject) {
activeObject.set("stroke",value);
canvas.requestRenderAll();
afterPanelValueChange(activeObject);
}
}
function changePanelOpacity(value) {
var activeObject=requirePanelTarget();
if (activeObject) {
const opacity=value/100;
activeObject.set("opacity",opacity);
canvas.requestRenderAll();
afterPanelValueChange(activeObject);
}
}
function changePanelFillColor(value) {
var activeObject=requirePanelTarget();
if (activeObject) {
activeObject.set("fill",value);
canvas.requestRenderAll();
afterPanelValueChange(activeObject);
}
}

// 変更した値を他のパネル（共通コントロール等）にも反映し、履歴に残す
function afterPanelValueChange(activeObject){
updateControls(activeObject);
commitHistoryDebounced();
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


// 全てのコマを1回で書き換える。個別に戻す手立てが無いため、必ず確認を通す
async function panelAllChange() {
var panelCount=canvas.getObjects().filter(function (obj) {
return isPanel(obj);
}).length;
if (panelCount===0) {
createToastError(getText("panelAllChangeNoPanelTitle"),getText("panelAllChangeNoPanelBody"));
return;
}
var ok=await showConfirmDialog({
titleKey: 'panelAllChangeConfirmTitle',
message: i18next.t('panelAllChangeConfirmBody',{num: panelCount}),
danger: true
});
if (!ok) {
return;
}
// await の間にコマが増減している可能性があるため、値も対象も取り直す
var strokeWidthValue=$("panelStrokeWidth").value;
var strokeColorValue=$("panelStrokeColor").value;
var opacityValue=$("panelOpacity").value;
const opacity=opacityValue/100;
var fillValue=$("panelFillColor").value;
_dbgLogger.debug("[panelAllChange] inputs: sw="+strokeWidthValue+" stroke="+strokeColorValue+" fill="+fillValue+" opacity="+opacityValue);
canvas.getObjects().forEach(function (obj) {
if (isPanel(obj)) {
_dbgLogger.debug("[panelAllChange] BEFORE obj.strokeWidth="+obj.strokeWidth+" obj.stroke="+obj.stroke);
obj.set({
strokeWidth: parseFloat(strokeWidthValue),
strokeUniform: true,
});
obj.set("stroke",strokeColorValue);
obj.set("fill",fillValue);
obj.set("opacity",opacity);
_dbgLogger.debug("[panelAllChange] AFTER obj.strokeWidth="+obj.strokeWidth+" obj.stroke="+obj.stroke);
}
});
canvas.requestRenderAll();
// 確認ダイアログを閉じた後に値を書き換えるため、クリックに紐づく自動コミットには
// 間に合わない。ここで履歴に積んでUndoで戻せるようにする
commitHistoryDebounced();
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
$("view_controls_checkbox").addEventListener("change",function () {
changeView("controls",this.checked);
});
$("view_prompt_checkbox").addEventListener("change",function () {
if(this.checked!==areNamesVisible){
View();
}
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
let viewText=obj.name+"\n\n"+getText("viewPromptLabel")+"\n"+(obj.text2img_prompt||getText("viewPromptEmpty"));
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
