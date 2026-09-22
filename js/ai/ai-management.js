// AI機能の中央ルーター: プロバイダーレジストリ経由でディスパッチ
const sdQueue=new TaskQueue(1);
const comfyuiQueue=new TaskQueue(1);
const falaiQueue=new TaskQueue(1);
const googleImageQueue=new TaskQueue(1);
const grokQueue=new TaskQueue(1);
const ollamaQueue=new TaskQueue(1);

var firstSDConnection=true;
var firstComfyConnection=true;

document.addEventListener('DOMContentLoaded',function(){
var falConc=$('falaiConcurrency');
if(falConc&&parseInt(falConc.value)>1){
falaiQueue.setConcurrency(parseInt(falConc.value));
}
var googleImageConc=$('googleImageConcurrency');
if(googleImageConc&&parseInt(googleImageConc.value)>1){
googleImageQueue.setConcurrency(parseInt(googleImageConc.value));
}
var grokConc=$('grokConcurrency');
if(grokConc&&parseInt(grokConc.value)>1){
grokQueue.setConcurrency(parseInt(grokConc.value));
}
var ollamaConc=$('ollamaConcurrency');
if(ollamaConc&&parseInt(ollamaConc.value)>1){
ollamaQueue.setConcurrency(parseInt(ollamaConc.value));
}
});

$('falaiConcurrency').addEventListener('change',function(){
var val=parseInt(this.value)||1;
if(val<1)val=1;
if(val>10)val=10;
this.value=val;
falaiQueue.setConcurrency(val);
});

$('googleImageConcurrency').addEventListener('change',function(){
var val=parseInt(this.value)||1;
if(val<1)val=1;
if(val>10)val=10;
this.value=val;
googleImageQueue.setConcurrency(val);
});

$('grokConcurrency').addEventListener('change',function(){
var val=parseInt(this.value)||1;
if(val<1)val=1;
if(val>10)val=10;
this.value=val;
grokQueue.setConcurrency(val);
});

$('ollamaConcurrency').addEventListener('change',function(){
var val=parseInt(this.value)||1;
if(val<1)val=1;
if(val>10)val=10;
this.value=val;
ollamaQueue.setConcurrency(val);
});

$('sdWebUIPageUrlDefaultUrl').addEventListener('click',(event)=>{
event.stopPropagation();
const defaultUrl='http://127.0.0.1:7860';
$('sdWebUIPageUrl').value=defaultUrl;
});

$('comfyUIPageUrlDefaultUrl').addEventListener('click',(event)=>{
event.stopPropagation();
const defaultUrl='http://127.0.0.1:8188';
$('comfyUIPageUrl').value=defaultUrl;
});




function existsWaitQueue() {
const sdQueueStatus=sdQueue.getStatus();
if(sdQueueStatus.total>0){
return true;
}

const comfyuiQueueStatus=comfyuiQueue.getStatus();
if(comfyuiQueueStatus.total>0){
return true;
}
const falQueueStatus=falaiQueue.getStatus();
if(falQueueStatus.total>0){
return true;
}
const googleImageQueueStatus=googleImageQueue.getStatus();
if(googleImageQueueStatus.total>0){
return true;
}
const grokQueueStatus=grokQueue.getStatus();
if(grokQueueStatus.total>0){
return true;
}
const ollamaQueueStatus=ollamaQueue.getStatus();
if(ollamaQueueStatus.total>0){
return true;
}
return false;
}

function getAllQueues() {
return[sdQueue,comfyuiQueue,falaiQueue,googleImageQueue,grokQueue,ollamaQueue];
}

// 全キューが空になるまで待つ。キューの完了通知で起きるので非表示タブでも間引かれない。
// 通知漏れがあっても進行が止まらないよう保険のタイマーでも起こし、呼び出し側で再判定する
const QUEUE_IDLE_SAFETY_MS=5000;
async function waitAllQueuesIdle() {
const idle=Promise.all(getAllQueues().map(function(queue){return queue.whenIdle();}));
const safety=new Promise(function(resolve){setTimeout(resolve,QUEUE_IDLE_SAFETY_MS);});
await Promise.race([idle,safety]);
}

function clearAllQueues() {
const sdCleared=sdQueue.clearQueue();
const comfyCleared=comfyuiQueue.clearQueue();
const falCleared=falaiQueue.clearQueue();
const googleImageCleared=googleImageQueue.clearQueue();
const grokCleared=grokQueue.clearQueue();
const ollamaCleared=ollamaQueue.clearQueue();
logger.info(`All queues cleared: SD=${sdCleared}, ComfyUI=${comfyCleared}, Fal=${falCleared}, NanoBanana=${googleImageCleared}, Grok=${grokCleared}, Ollama=${ollamaCleared}`);
return sdCleared+comfyCleared+falCleared+googleImageCleared+grokCleared+ollamaCleared;
}


async function T2I(layer,spinner){
var provider=providerRegistry.getProviderForRole(AI_ROLES.Text2Image);
if(provider){
return provider.executeT2I(layer,spinner.id);
}
}
// キャンバスへ置かずに画像だけ作る。設定資料をその場で作るために使う
function getDetachedT2IProvider(){
return providerRegistry.getProviderForRole(AI_ROLES.Text2Image);
}
function canGenerateDetachedT2I(){
var provider=getDetachedT2IProvider();
return!!(provider&&provider.supportsDetachedT2I());
}
async function T2IDetached(request,spinner){
var provider=getDetachedT2IProvider();
if(!provider||!provider.supportsDetachedT2I())return null;
return provider.executeDetachedT2I(request,spinner.id);
}
function I2I(layer,spinner){
var provider=providerRegistry.getProviderForRole(AI_ROLES.Image2Image);
if(provider){
return provider.executeI2I(layer,spinner.id);
}
}

async function aiRembg(layer,spinner){
var provider=providerRegistry.getProviderForRole(AI_ROLES.RemoveBG);
if(provider){
return provider.executeRembg(layer,spinner.id);
}
}

async function aiUpscale(layer,spinner){
var provider=providerRegistry.getProviderForRole(AI_ROLES.Upscaler);
if(provider){
return provider.executeUpscale(layer,spinner.id);
}
}

function canUseInpaint(){
var provider=providerRegistry.getProviderForRole(AI_ROLES.Inpaint);
return provider!==null&&provider.canUseInpaint();
}

function canUseAngle(){
var provider=providerRegistry.getProviderForRole(AI_ROLES.I2I_Angle);
return provider!==null&&provider.canUseAngle();
}

function AngleGenerate(layer,spinner,anglePrompt){
var provider=providerRegistry.getProviderForRole(AI_ROLES.I2I_Angle);
if(provider){
return provider.executeAngle(layer,spinner.id,anglePrompt);
}
}


function getDiffusionInformation() {
var provider=providerRegistry.getProviderForRole(AI_ROLES.Text2Image)||providerRegistry.getActive();
if(provider){
provider.fetchDiffusionInformation();
}
}


// 使用サービス表で実際に選ばれているサービスだけを対象にする。
// 「なし」や未対応（—）の行のサービスは接続チェックしない
function getInUseProviders(){
var ids={};
ROLE_MATRIX_ROWS.forEach(function(row){
var provider=providerRegistry.getProviderForRole(row.role);
if(provider)ids[provider.id]=true;
});
return Object.keys(ids).map(function(id){
return providerRegistry.get(id);
}).filter(Boolean);
}

function isProviderInUse(providerId){
return getInUseProviders().some(function(provider){
return provider.id===providerId;
});
}

function renderProviderStatusChips(results){
var container=$('ExternalService_Heartbeat_Container');
if(!container)return;
container.innerHTML='';
results.forEach(function(r){
var chip=document.createElement('span');
chip.className='provider-status-chip';
if(r.reason)chip.title=r.name+': '+r.reason;
var dot=document.createElement('span');
dot.className='provider-status-dot '+(r.online?'on':'off');
var text=document.createTextNode(r.name);
chip.appendChild(dot);
chip.appendChild(text);
container.appendChild(chip);
});
}

async function apiHeartbeat(){

logger.trace("apiHeartbeat");

const pingCheck=$('apiHeartbeatCheckbox');
if (pingCheck.checked) {
} else {
return;
}

var providers=getInUseProviders();
var results=[];
for(var i=0;i<providers.length;i++){
var p=providers[i];
var online=false;
try{
online=await p.heartbeat();
}catch(e){
online=false;
}
results.push({id:p.id,name:p.name,online:!!online,reason:online?'':p.getStatusReason()});
}
renderProviderStatusChips(results);

var announce=$('checSD_WebUI_Announce');
var anyOnline=results.some(function(r){return r.online;});
if(anyOnline){
announce.style.display='none';
}
}


function updateUpscalerDropdown(models) {
const modelDropdown=$('text2img_hr_upscaler');
modelDropdown.innerHTML='';
models.forEach(model=>{
const option=document.createElement('option');
option.value=model.name;
option.textContent=model.name;

if (basePrompt.text2img_hr_upscaler===model.name) {
option.selected=true;
}
modelDropdown.appendChild(option);
});
}

function updateSamplerDropdown(models) {
const modelDropdown=$('basePrompt_samplingMethod');
modelDropdown.innerHTML='';
basePrompt.text2img_samplingMethod

models.forEach(model=>{
const option=document.createElement('option');
option.value=model.name;
option.textContent=model.name;

if (basePrompt.text2img_samplingMethod===model.name) {
option.selected=true;
}
modelDropdown.appendChild(option);
});
}

function updateModelDropdown(models) {
const modelDropdown=$('basePrompt_model');
modelDropdown.innerHTML='';
models.forEach(model=>{
const option=document.createElement('option');
option.value=model.title;
option.textContent=model.model_name;

if (basePrompt.text2img_model===removeHashStr(model.title)) {
option.selected=true;
}
modelDropdown.appendChild(option);
});
}

function updateVaeDropdown(models) {
const dropdown=$('vaeDropdownId');
dropdown.innerHTML='';
models.forEach(model=>{
logger.trace("updateVaeDropdown push ",model.name)
const option=document.createElement('option');
option.value=model.name;
option.textContent=model.name;
dropdown.appendChild(option);
});
}


//Before:ABC.safetensors [23e4fa2b6f]
//After :ABC.safetensors
function removeHashStr(str) {
return str.replace(/\s*\[[^\]]+\]\s*$/,'');
}

$('basePrompt_model').addEventListener('change',function(event){
if(isProviderInUse('localSDWebUI')){
sendModelToServer();
}
});

$('clipDropdownId').addEventListener('change',function(event){
if(isProviderInUse('localSDWebUI')){
sendClipToServer();
}
});
