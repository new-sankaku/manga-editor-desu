// 履歴管理（Undo/Redo）: 保存抑止スコープ、コミット集約、復元処理の直列化

const imageMap=new Map();
var stateStack=[];
var currentStateIndex=-1;

var historyLockDepth=0;
var isHistoryRestoring=false;
var historyCommitPending=false;
var historyCommitTimerId=0;
var historyDebounceTimerId=0;
var historyRestoreQueueIndex=null;
var historyRestoreWatchdogId=0;
var historyChangeCounter=0;
var canvasDirtyUnlocked=false;

const HISTORY_COMMIT_DELAY=0;
const HISTORY_DEFAULT_DEBOUNCE=500;
const HISTORY_AUTO_COMMIT_DELAY=400;
const HISTORY_RESTORE_TIMEOUT=30000;
// 自動コミット判定から除外するキー（描画内容ではなく操作モード・制御用の属性）
const HISTORY_IGNORE_KEYS={
dirty:true,canvas:true,group:true,
selectable:true,evented:true,hasControls:true,hasBorders:true,
lockMovementX:true,lockMovementY:true,lockRotation:true,lockScalingX:true,lockScalingY:true,
hoverCursor:true,moveCursor:true,perPixelTargetFind:true,objectCaching:true,
borderColor:true,cornerColor:true,cornerStyle:true,cornerSize:true,transparentCorners:true,
borderScaleFactor:true,edit:true,targetObject:true
};


fabric.Object.prototype.toObject=(function (toObject) {
return function (propertiesToInclude) {
propertiesToInclude=(propertiesToInclude||[]).concat(["clipTo"]);
return toObject.apply(this,[propertiesToInclude]);
};
})(fabric.Object.prototype.toObject);

fabric.Object.prototype._set=(function (_set) {
return function (key,value) {
if(!HISTORY_IGNORE_KEYS[key]&&this[key]!==value&&historyLockDepth===0&&!isHistoryRestoring){
canvasDirtyUnlocked=true;
}
return _set.call(this,key,value);
};
})(fabric.Object.prototype._set);

function markCanvasDirty(){
if(historyLockDepth===0&&!isHistoryRestoring){
canvasDirtyUnlocked=true;
}
}

function isSave(){
return historyLockDepth===0&&!isHistoryRestoring;
}
function notSave(){
return!(isSave());
}

function setNotSave(activeObject){
activeObject.saveHistory=false;
return activeObject;
}
function setSave(activeObject){
activeObject.saveHistory=true;
return activeObject;
}


function isSaveObject(activeObject){
if(activeObject){
if(activeObject.saveHistory==true){
return true;
}
if(activeObject.saveHistory==false){
return false;
}
if(activeObject.target===undefined){
return true;
}

if(activeObject.target.saveHistory===undefined){
return true;
}
return false;
}else{
return false;
}
}

function isNotSaveObject(activeObject){
return!(isSaveObject(activeObject)) ;
}

function changeDoNotSaveHistory(){
historyLockDepth++;
}

function changeDoSaveHistory(){
if(historyLockDepth>0){
historyLockDepth--;
}else{
historyLogger.debug("changeDoSaveHistory called while depth is 0");
}
if(historyLockDepth===0&&historyCommitPending){
scheduleHistoryCommit();
}
}

function withoutHistory(fn){
changeDoNotSaveHistory();
try{
return fn();
}finally{
changeDoSaveHistory();
}
}

function resetHistoryLock(){
if(historyLockDepth!==0){
historyLogger.warn("history lock depth reset from "+historyLockDepth);
}
historyLockDepth=0;
}

function getHistoryChangeCounter(){
return historyChangeCounter;
}

function removeByNotSave(obj){
if (obj) {
withoutHistory(function(){
canvas.remove(obj);
});
}
}

function addByNotSave(obj){
if (obj) {
withoutHistory(function(){
canvas.add(obj);
});
}
}

function scheduleHistoryCommit(){
historyCommitPending=true;
if(historyCommitTimerId){
return;
}
historyCommitTimerId=window.setTimeout(function(){
historyCommitTimerId=0;
flushHistory();
},HISTORY_COMMIT_DELAY);
}

function commitHistory(){
if(notSave()){
return;
}
scheduleHistoryCommit();
}

function commitHistoryDebounced(delay){
if(isHistoryRestoring){
return;
}
if(historyDebounceTimerId){
window.clearTimeout(historyDebounceTimerId);
}
historyDebounceTimerId=window.setTimeout(function(){
historyDebounceTimerId=0;
scheduleHistoryCommit();
},delay||HISTORY_DEFAULT_DEBOUNCE);
}

function cancelPendingHistory(){
historyCommitPending=false;
if(historyCommitTimerId){
window.clearTimeout(historyCommitTimerId);
historyCommitTimerId=0;
}
if(historyDebounceTimerId){
window.clearTimeout(historyDebounceTimerId);
historyDebounceTimerId=0;
}
}

function flushHistory(){
if(historyDebounceTimerId){
window.clearTimeout(historyDebounceTimerId);
historyDebounceTimerId=0;
historyCommitPending=true;
}
if(historyCommitTimerId){
window.clearTimeout(historyCommitTimerId);
historyCommitTimerId=0;
}
if(!historyCommitPending){
return false;
}
if(notSave()){
return false;
}
historyCommitPending=false;
return captureState();
}

function captureState(){
if(isHistoryRestoring){
return false;
}
canvas.renderAll();
const json=JSON.stringify(customToJSON());
canvasDirtyUnlocked=false;
if(currentStateIndex>=0&&stateStack[currentStateIndex]===json){
return false;
}
if(currentStateIndex<stateStack.length-1){
stateStack.splice(currentStateIndex+1);
}
stateStack.push(json);
currentStateIndex=stateStack.length-1;
updateLayerPanel();
return true;
}

function saveStateByListener(event,eventType) {
if(!event){
return;
}
if(isNotSaveObject(event)){
return;
}
historyChangeCounter++;
markCanvasDirty();
if (notSave()) {
return;
}
scheduleHistoryCommit();
}

function saveState() {
commitHistory();
}

function saveStateByManual() {
commitHistory();
}

const imageHashCache=new Map();

function generateHash(imageData) {
const cached=imageHashCache.get(imageData);
if(cached!==undefined){
return cached;
}
const hash=CryptoJS.SHA256(imageData).toString(CryptoJS.enc.Hex);
imageHashCache.set(imageData,hash);
return hash;
}

async function blobUrlToDataUrl(blobUrl){
try{
const response=await fetch(blobUrl);
const blob=await response.blob();
return new Promise((resolve,reject)=>{
const reader=new FileReader();
reader.onloadend=()=>resolve(reader.result);
reader.onerror=reject;
reader.readAsDataURL(blob);
});
}catch(e){
layerLogger.error("Failed to convert blob URL:",blobUrl,e);
return null;
}
}

async function convertImageMapBlobUrls(){
const entries=Array.from(imageMap.entries());
for(const [hash,value] of entries){
if(typeof value==='string'&&value.startsWith('blob:')){
const dataUrl=await blobUrlToDataUrl(value);
if(dataUrl){
imageMap.set(hash,dataUrl);
}
}
}
}

function customToJSON() {
const json=canvas.toJSON(commonProperties);
const exportedObjects=canvas.getObjects().filter(obj=>!obj.excludeFromExport);
json.objects=json.objects.map((obj,index)=>{
const sourceObject=exportedObjects[index];
if(sourceObject&&sourceObject.originalOpacity!==undefined){
obj.opacity=sourceObject.originalOpacity;
}

if (obj.type==='image'&&obj.src&&typeof obj.src==='string'&&(obj.src.startsWith('data:')||obj.src.startsWith('blob:'))) {
const hash=generateHash(obj.src);
if (!imageMap.has(hash)) {
imageMap.set(hash,obj.src);
}
obj.src=hash;
}

if(obj.speechBubbleGrid&&typeof obj.speechBubbleGrid==='object'){
const gridStr=JSON.stringify(obj.speechBubbleGrid);
const hash=generateHash(gridStr);
if (!imageMap.has(hash)) {
imageMap.set(hash,gridStr);
}
obj.speechBubbleGrid="GUID:"+hash;
}

return obj;
});

return json;
}

function restoreImage(json) {
const parsedJson=JSON.parse(json);
parsedJson.objects=parsedJson.objects.map(obj=>{
if (obj.type==='image'&&imageMap.has(obj.src)) {
obj.src=imageMap.get(obj.src);
}
if (obj.speechBubbleGrid&&typeof obj.speechBubbleGrid==='string') {
const hash=obj.speechBubbleGrid.replace('GUID:','');
const gridData=imageMap.get(hash);
if(gridData){
if(typeof gridData==='string'){
try{
obj.speechBubbleGrid=JSON.parse(gridData);
}catch(e){
obj.speechBubbleGrid=gridData;
}
}else{
obj.speechBubbleGrid=gridData;
}
}
}
if (obj.textBaseline==='alphabetical') {
obj.textBaseline='alphabetic';
}
commonProperties.forEach(prop=>{
if (obj[prop]!==undefined) {
obj[prop]=obj[prop];
}
});
return obj;
});
return parsedJson;
}

function startRestoreWatchdog(){
stopRestoreWatchdog();
historyRestoreWatchdogId=window.setTimeout(function(){
historyRestoreWatchdogId=0;
if(isHistoryRestoring){
historyLogger.error("loadFromJSON callback did not finish. history restore lock released.");
isHistoryRestoring=false;
historyRestoreQueueIndex=null;
}
},HISTORY_RESTORE_TIMEOUT);
}

function stopRestoreWatchdog(){
if(historyRestoreWatchdogId){
window.clearTimeout(historyRestoreWatchdogId);
historyRestoreWatchdogId=0;
}
}

function finishRestore(){
stopRestoreWatchdog();
isHistoryRestoring=false;
canvasDirtyUnlocked=false;
cancelPendingHistory();
if(historyRestoreQueueIndex!==null){
const nextIndex=historyRestoreQueueIndex;
historyRestoreQueueIndex=null;
applyHistoryState(nextIndex);
}
}

function applyHistoryState(index,guid=null){
if(index<0||index>=stateStack.length){
return;
}
currentStateIndex=index;
isHistoryRestoring=true;
startRestoreWatchdog();

let state;
try{
state=restoreImage(stateStack[index]);
}catch(e){
historyLogger.error("Failed to parse state: "+(e instanceof Error?e.name+" "+e.message:e));
stopRestoreWatchdog();
isHistoryRestoring=false;
historyRestoreQueueIndex=null;
return;
}

canvas.loadFromJSON(state,function () {
try{
state.objects.forEach((stateObj,objectIndex)=>{
const canvasObj=canvas.getObjects()[objectIndex];
if (canvasObj) {
canvasObj.selectable=stateObj.selectable;
}
});
reSetSpeechBubbleText();
setCanvasGUID(guid||state.canvasGuid);
canvas.renderAll();
updateLayerPanel();
resetEventHandlers();
customSpeechBubbleAllRelocation();
}catch(e){
historyLogger.error("Failed to restore state: "+(e instanceof Error?e.name+" "+e.message:e));
}finally{
finishRestore();
}
});
clearJSTSGeometry();
}

function queueRestore(offset){
const base=historyRestoreQueueIndex!==null?historyRestoreQueueIndex:currentStateIndex;
const target=base+offset;
if(target<0||target>stateStack.length-1){
return;
}
historyRestoreQueueIndex=target;
}

function undo() {
if(isHistoryRestoring){
queueRestore(-1);
return;
}
flushHistory();
if (currentStateIndex>=1) {
applyHistoryState(currentStateIndex-1);
}
}

function redo() {
if(isHistoryRestoring){
queueRestore(1);
return;
}
flushHistory();
if (currentStateIndex<stateStack.length-1) {
applyHistoryState(currentStateIndex+1);
}
}

function lastRedo(guid=null) {
if(stateStack.length===0){
return;
}
cancelPendingHistory();
if(isHistoryRestoring){
historyRestoreQueueIndex=stateStack.length-1;
return;
}
applyHistoryState(stateStack.length-1,guid);
}

function reSetSpeechBubbleText(){
canvas.getObjects().forEach(obj=>{
if(isSpeechBubbleSVG(obj)||isFreehandBubblePath(obj)){
const childObjects=canvas.getObjects().filter((childObj)=>obj.guids.includes(childObj.guid));
childObjects.forEach(childObject=>{
childObject.targetObject=obj;
});
}
});
}


function allRemove() {
cancelPendingHistory();
withoutHistory(function(){
canvas.clear();
var bgColorInput=$("bg-color");
canvas.backgroundColor=bgColorInput.value;
});
currentImage=null;

imageMap.clear();
imageHashCache.clear();
stateStack=[];
currentStateIndex=-1;
captureState();
}
function initImageHistory(){
resetHistoryLock();
allRemove();
}

document.addEventListener('DOMContentLoaded',function() {
captureState();
});

// 個別ハンドラでのコミット漏れに対する保険。
// fabricのset()経由でオブジェクトが変化した場合のみ、操作の区切りで1回コミットする。
function autoCommitOnInteractionEnd(){
if(!canvasDirtyUnlocked){
return;
}
commitHistoryDebounced(HISTORY_AUTO_COMMIT_DELAY);
}
document.addEventListener('pointerup',autoCommitOnInteractionEnd,true);
document.addEventListener('keyup',autoCommitOnInteractionEnd,true);
document.addEventListener('change',autoCommitOnInteractionEnd,true);



function resetEventHandlers() {
const objectMap={};
canvas.getObjects().forEach(obj=>{
if (obj.guid) {
objectMap[obj.guid]=obj;
}
});
canvas.getObjects().forEach(obj=>{
if(isSpeechBubbleSVG(obj)||isFreehandBubblePath(obj)){
return;
}
if (obj.guids) {
obj.guids.forEach(guid=>{
if (objectMap[guid]) {
moveSettings(objectMap[guid],obj);
}
});
}
});
}
