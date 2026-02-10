// 自動保存機能：IndexedDBへの定期保存と起動時の復元
var AutoSaveManager=(function(){
var autoSaveLogger=new SimpleLogger('autoSave',LogLevel.INFO);
var store=localforage.createInstance({name:'autoSaveStorage',storeName:'projectAutoSave'});
var timerId=null;
var isSaving=false;
var enabled=true;
var intervalSeconds=60;
var lastSavedHash=null;
var lastSavedGuid=null;

function computeStateHash(){
if(typeof stateStack==='undefined'||typeof currentStateIndex==='undefined')return null;
if(currentStateIndex<0||currentStateIndex>=stateStack.length)return null;
var str=stateStack[currentStateIndex];
if(!str)return null;
var h=5381;
for(var i=0,len=str.length;i<len;i++){
h=((h<<5)+h)+str.charCodeAt(i);
h|=0;
}
return h+':'+str.length;
}

function loadSettings(){
var stored=localStorage.getItem('localSettingsData');
if(!stored)return;
var data=JSON.parse(stored);
if(data.autoSaveEnabled!==undefined)enabled=data.autoSaveEnabled;
if(data.autoSaveInterval!==undefined){
var val=parseInt(data.autoSaveInterval);
if(val>=10&&val<=600)intervalSeconds=val;
}
}

function start(){
stop();
if(!enabled)return;
timerId=setInterval(function(){
if(typeof requestIdleCallback==='function'){
requestIdleCallback(function(){save();});
}else{
save();
}
},intervalSeconds*1000);
autoSaveLogger.info("Timer started, interval="+intervalSeconds+"sec");
}

function stop(){
if(timerId){
clearInterval(timerId);
timerId=null;
autoSaveLogger.info("Timer stopped");
}
}

function restart(){
loadSettings();
start();
}

async function save(){
if(isSaving)return;
if(typeof stateStack==='undefined'||stateStack.length<2)return;
var guid=getCanvasGUID();
var hash=computeStateHash();
if(hash!==null&&hash===lastSavedHash&&guid===lastSavedGuid){
autoSaveLogger.debug("Skip auto-save: no changes");
return;
}
isSaving=true;
autoSaveLogger.info("Auto-save starting...");
try{
await btmSaveProjectFile(null,false);
lastSavedHash=computeStateHash();
lastSavedGuid=guid;
var pages=[];
btmProjectsMap.forEach(function(data,guid){
pages.push({guid:guid,blob:data.blob});
});
await store.setItem('pages',pages);
await store.setItem('metadata',{
timestamp:Date.now(),
currentPageGuid:getCanvasGUID(),
pageOrder:btmGetGuids()
});
var msg=getText('autoSaveComplete')||'Auto-saved';
createToast(msg,'',1000);
autoSaveLogger.info("Auto-save complete, pages="+pages.length);
}catch(e){
autoSaveLogger.error("Auto-save failed:",e);
}finally{
isSaving=false;
}
}

async function clearAutoSave(){
try{
await store.removeItem('pages');
await store.removeItem('metadata');
autoSaveLogger.info("Auto-save data cleared");
}catch(e){
autoSaveLogger.error("Failed to clear auto-save data:",e);
}
}

function setEnabled(val){
enabled=!!val;
if(enabled)start();
else stop();
}

function setIntervalSeconds(val){
var v=parseInt(val);
if(v>=10&&v<=600)intervalSeconds=v;
if(enabled)start();
}

async function checkRecovery(){
try{
var metadata=await store.getItem('metadata');
if(!metadata)return;
var pages=await store.getItem('pages');
if(!pages||pages.length===0){
await clearAutoSave();
return;
}
showRecoveryDialog(metadata,pages);
}catch(e){
autoSaveLogger.error("Recovery check failed:",e);
}
}

function showRecoveryDialog(metadata,pages){
var date=new Date(metadata.timestamp);
var dateStr=date.toLocaleString();
var title=getText('autoSaveRecoveryTitle')||'Recover Auto-save';
var msg=(getText('autoSaveRecoveryMessage')||'Auto-save data found. Recover?')+'\n'+dateStr;
var recoverText=getText('autoSaveRecover')||'Recover';
var discardText=getText('autoSaveDiscard')||'Discard';
var overlay=document.createElement('div');
overlay.id='autoSaveRecoveryDialog';
overlay.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:10000;';
var dialog=document.createElement('div');
dialog.style.cssText='background:#1e1e1e;color:#fff;border-radius:8px;padding:24px;min-width:320px;max-width:400px;text-align:center;';
var titleEl=document.createElement('h3');
titleEl.style.cssText='margin:0 0 12px 0;font-size:16px;';
titleEl.textContent=title;
var msgEl=document.createElement('p');
msgEl.style.cssText='margin:0 0 20px 0;font-size:13px;white-space:pre-line;color:#ccc;';
msgEl.textContent=msg;
var btnWrap=document.createElement('div');
btnWrap.style.cssText='display:flex;gap:12px;justify-content:center;';
var recoverBtn=document.createElement('button');
recoverBtn.textContent=recoverText;
recoverBtn.style.cssText='padding:8px 20px;background:#ff6b00;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;';
var discardBtn=document.createElement('button');
discardBtn.textContent=discardText;
discardBtn.style.cssText='padding:8px 20px;background:#444;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;';
btnWrap.appendChild(recoverBtn);
btnWrap.appendChild(discardBtn);
dialog.appendChild(titleEl);
dialog.appendChild(msgEl);
dialog.appendChild(btnWrap);
overlay.appendChild(dialog);
document.body.appendChild(overlay);
recoverBtn.addEventListener('click',async function(){
overlay.remove();
await recoverPages(metadata,pages);
});
discardBtn.addEventListener('click',async function(){
overlay.remove();
await clearAutoSave();
});
}

async function recoverPages(metadata,pages){
autoSaveLogger.info("Recovering "+pages.length+" pages...");
try{
btmProjectsMap.clear();
var btmImageContainer=$("btm-image-container");
if(btmImageContainer)btmImageContainer.innerHTML='';
for(var i=0;i<pages.length;i++){
var page=pages[i];
var previewLink='';
btmProjectsMap.set(page.guid,{imageLink:previewLink,blob:page.blob});
}
var targetGuid=metadata.currentPageGuid||metadata.pageOrder[0];
if(!btmProjectsMap.has(targetGuid))targetGuid=btmProjectsMap.keys().next().value;
await loadLz4BlobProjectFile(btmProjectsMap.get(targetGuid).blob,targetGuid);
for(var j=0;j<metadata.pageOrder.length;j++){
var g=metadata.pageOrder[j];
if(btmProjectsMap.has(g)){
var pd=btmProjectsMap.get(g);
var link=pd.imageLink;
if(!link&&g===targetGuid){
link=getCropAndDownloadLinkByMultiplier(1,"jpeg")||'';
btmProjectsMap.set(g,{imageLink:link,blob:pd.blob});
}
btmAddImage(link,pd.blob,g,false);
}
}
await clearAutoSave();
autoSaveLogger.info("Recovery complete");
createToast(getText('autoSaveRecoveryTitle')||'Recovery','OK',2000);
}catch(e){
autoSaveLogger.error("Recovery failed:",e);
createToastError('Recovery Error',e.message||'Failed',3000);
}
}

async function init(){
loadSettings();
await checkRecovery();
lastSavedHash=computeStateHash();
lastSavedGuid=(typeof getCanvasGUID==='function')?getCanvasGUID():null;
start();
var chk=$('autoSaveCheckbox');
if(chk){
chk.addEventListener('change',function(){
setEnabled(this.checked);
});
}
var intInput=$('autoSaveInterval');
if(intInput){
intInput.addEventListener('change',function(){
setIntervalSeconds(this.value);
});
}
}

return{
init:init,
start:start,
stop:stop,
restart:restart,
save:save,
clearAutoSave:clearAutoSave,
setEnabled:setEnabled,
setInterval:setIntervalSeconds,
checkRecovery:checkRecovery
};
})();
