const sdQueue=new TaskQueue(1);
const comfyuiQueue=new TaskQueue(1);

var firstSDConnection=true;
var firstComfyConnection=true;

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
return false;
}

function clearAllQueues() {
const sdCleared=sdQueue.clearQueue();
const comfyCleared=comfyuiQueue.clearQueue();
logger.info(`All queues cleared: SD=${sdCleared}, ComfyUI=${comfyCleared}`);
return sdCleared+comfyCleared;
}


async function T2I(layer,spinner){
if (apiMode==apis.A1111) {
sdwebuiT2IProcessQueue(layer,spinner.id);
}else if (apiMode==apis.COMFYUI){
return comfyuiHandleProcessQueue(layer,spinner.id);
}
}
function I2I(layer,spinner){
if (apiMode==apis.A1111) {
sdwebuiI2IProcessQueue(layer,spinner.id);
}else if (apiMode==apis.COMFYUI){
comfyuiHandleProcessQueue(layer,spinner.id,'I2I');
}
}

async function aiRembg(layer,spinner){
if (apiMode==apis.A1111) {
sdwebuiRembgProcessQueue(layer,spinner.id);
}else if (apiMode==apis.COMFYUI){
return comfyuiHandleProcessQueue(layer,spinner.id,'Rembg');
}
}

async function aiUpscale(layer,spinner){
if (apiMode==apis.A1111) {
//TODO
}else if (apiMode==apis.COMFYUI){
return comfyuiHandleProcessQueue(layer,spinner.id,'Upscaler');
}
}


function getDiffusionInfomation() {
if (apiMode==apis.A1111) {
fetchSDOptions().then(()=>{
fetchSdModels();
fetchSdSampler();
fetchSdUpscaler();
fetchSdAdModels();
fetchSdModules();
});

}else if(apiMode==apis.COMFYUI){
comfyuiFetchModels();
comfyuiFetchSampler();
comfyuiFetchUpscaler();
comfyuiVaeLoader();
comfyuiClipModels();
comfyuiFetchObjectInfoOnly();
}
}


function apiHeartbeat(){

logger.trace("apiHeartbeat");

const pingCheck=$('apiHeartbeatCheckbox');
if (pingCheck.checked) {
} else {
return;
}

if (apiMode==apis.A1111) {
sdwebuiApiHeartbeat();
} else if(apiMode==apis.COMFYUI) {
comfyuiApiHeartbeat();
}

const label=$('ExternalService_Heartbeat_Label');
let announce=$('checSD_WebUI_Announce');
if(label.style.color==='green') {
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
// console.log("updateVaeDropdown", JSON.stringify(models))

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
if (apiMode==apis.A1111) {
sendModelToServer();
}else if(apiMode==apis.COMFYUI){
//TODO
}
});

$('clipDropdownId').addEventListener('change',function(event){
if (apiMode==apis.A1111) {
sendClipToServer();
}else if(apiMode==apis.COMFYUI){
//TODO
}
});
