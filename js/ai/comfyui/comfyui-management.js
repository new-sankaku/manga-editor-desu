var _comfyUIExecProvider=null;

async function comfyUIExecWithProvider(provider,fn){
_comfyUIExecProvider=provider;
try{
return await fn();
}finally{
_comfyUIExecProvider=null;
}
}

function getComfyUIServerAddress(){
var provider=_comfyUIExecProvider||providerRegistry.getActive();
if(provider&&provider.getEndpointUrl()){
return provider.getEndpointUrl().replace(/\/+$/,'');
}
return $('comfyUIPageUrl').value.replace(/\/+$/,'');
}

function getComfyUIAuthHeaders(){
var provider=_comfyUIExecProvider||providerRegistry.getActive();
if(provider&&provider.needsApiKey()){
var apiKey=provider.getApiKey();
if(apiKey){
return{Authorization:'Bearer '+apiKey};
}
}
return{};
}

function getComfyUIProviderTag(){
var provider=_comfyUIExecProvider||providerRegistry.getActive();
if(provider){
return provider.name||provider.id;
}
return 'ComfyUI';
}

function comfyuiFetch(url,options){
options=options||{};
var authHeaders=getComfyUIAuthHeaders();
if(Object.keys(authHeaders).length>0){
options.headers=Object.assign({},options.headers||{},authHeaders);
}
var tag=getComfyUIProviderTag();
return fetch(url,options);
}

class ComfyUIEndpoints {
#getUrlParts() {
const serverAddress=getComfyUIServerAddress();
const url=new URL(serverAddress);
return {
protocol: url.protocol.replace(':',''),
domain: url.hostname,
port: url.port||'',
wsProtocol: url.protocol==='https:' ? 'wss' : 'ws'
};
}

constructor() {
this.urls=this.setupUrlProxy();
}

setupUrlProxy() {
return new Proxy({},{
get: (target,prop)=>{
const {protocol,domain,port,wsProtocol}=this.#getUrlParts();
const baseUrl=`${protocol}://${domain}${port ? ':' + port : ''}`;
const wsUrl=`${wsProtocol}://${domain}${port ? ':' + port : ''}`;
const endpoint=this.getEndpoint(prop);

if (prop==='ws') {
return `${wsUrl}/ws`;
}
return `${baseUrl}${endpoint}`;
}
});
}

getEndpoint(key) {
const endpoints={
settings: '/settings',
prompt: '/prompt',
history: '/history/',
view: '/view',
uploadImage: '/upload/image',
objectInfo: '/object_info/',
objectInfoOnly: '/object_info',
queue: '/queue',
interrupt: '/interrupt'
};
return endpoints[key]||'';
}
}


let reader=new FileReader();

var comfyuiSockets=new Map();
const comfyUIuuid=crypto.randomUUID();
var selectedWorkflow=null;
var processingPrompt=false;
var workflowFileLoad="";

function getComfyUISocketKey(){
var provider=_comfyUIExecProvider||providerRegistry.getActive();
return provider?provider.id:'local';
}

function comfyuiGetSocket(){
return comfyuiSockets.get(getComfyUISocketKey())||null;
}

function comfyuiConnect() {
var key=getComfyUISocketKey();
try {
var wsUrl=comfyUIUrls.ws+'?clientId='+comfyUIuuid;
var authHeaders=getComfyUIAuthHeaders();
if(authHeaders.Authorization){
wsUrl+='&token='+encodeURIComponent(authHeaders.Authorization.replace('Bearer ',''));
}
var ws=new WebSocket(wsUrl);
comfyuiSockets.set(key,ws);
ws.addEventListener("open",(event)=>{
var tag=getComfyUIProviderTag();
comfyuiLogger.info('['+tag+'] WebSocket接続成功');
});
ws.addEventListener("close",(event)=>{
comfyuiSockets.delete(key);
});
ws.addEventListener("error",(event)=>{
comfyuiSockets.delete(key);
});
return;
} catch (error) {
comfyuiSockets.delete(key);
}
}

async function comfyuiCancelPrompt(promptId){
try{
await comfyuiFetch(comfyUIUrls.interrupt,{
method:"POST",
headers:{"Content-Type":"application/json"}
});
await comfyuiFetch(comfyUIUrls.queue,{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({delete:[promptId]})
});
var tag=getComfyUIProviderTag();
comfyuiLogger.info('['+tag+'] Cancelled prompt: '+promptId);
}catch(error){
var tag=getComfyUIProviderTag();
comfyuiLogger.error('['+tag+'] Cancel prompt error:',error);
}
}

async function comfyuiApiHeartbeat() {
const labelfw=$("ExternalService_Heartbeat_Label_fw");

try {
var providerName=providerRegistry.getActive()?providerRegistry.getActive().name:'ComfyUI';
const response=await comfyuiFetch(comfyUIUrls.settings,{
method: "GET",
headers: {
"Content-Type": "application/json",
accept: "application/json",
},
});

if (response.ok) {
if (labelfw) {
labelfw.innerHTML=providerName+" ON";
labelfw.style.color="green";
}

if (firstComfyConnection) {
getDiffusionInformation();
firstComfyConnection=false;
}
return true;
} else {
if (labelfw) {
labelfw.innerHTML=providerName+" OFF";
labelfw.style.color="red";
}
}
} catch (error) {
if (labelfw) {
labelfw.innerHTML=providerName+" OFF";
labelfw.style.color="red";
}
}
return false;
}

async function comfyuiHandleProcessQueue(layer,spinnerId,Type='T2I',extraData) {
var serverAddress=getComfyUIServerAddress();
var authHeaders=getComfyUIAuthHeaders();
if (!comfyuiGetSocket()) comfyuiConnect();
var requestData=baseRequestData(layer);
if (basePrompt.text2img_model!=""){
requestData["model"]=basePrompt.text2img_model;
}
if(extraData){
Object.assign(requestData,extraData);
}

var repo=(_comfyUIExecProvider&&_comfyUIExecProvider.id==='runpodComfyUI')
? comfyUIWorkflowRepo_runpod
: comfyUIWorkflowRepo_local;

if (Type=='T2I') {
selectedWorkflow=await repo.getEnabledWorkflowByType("T2I");
} else if(Type=='I2I') {
selectedWorkflow=await repo.getEnabledWorkflowByType("I2I");
} else if(Type=='Rembg') {
selectedWorkflow=await repo.getEnabledWorkflowByType("REMBG");
} else if(Type=='Upscaler') {
selectedWorkflow=await repo.getEnabledWorkflowByType("Upscaler");
} else if(Type=='Inpaint') {
selectedWorkflow=await repo.getEnabledWorkflowByType("Inpaint");
} else if(Type=='I2I_Angle') {
selectedWorkflow=await repo.getEnabledWorkflowByType("I2I_Angle");
} else{
removeSpinner(spinnerId);
return;
}

// 有効なワークフローが無いまま進むと getClassTypeOnlyByJson で例外になる
if(!selectedWorkflow){
createToastError(getText("comfyWorkflowMissingTitle"),getText("comfyWorkflowMissingMessage")+" "+Type,1000*10);
removeSpinner(spinnerId);
return;
}

var classTypeLists=getClassTypeOnlyByJson(selectedWorkflow);
var objInfoRepo=(_comfyUIExecProvider&&_comfyUIExecProvider.id==='runpodComfyUI')?comfyObjectInfoRepo_runpod:comfyObjectInfoRepo_local;
if(!await checkWorkflowNodeVsComfyUI(classTypeLists,objInfoRepo)){
removeSpinner(spinnerId);
return;
}


if (Type=='I2I'||Type=='Rembg'||Type=='Upscaler'||Type=='I2I_Angle') {
var uploadFilename=generateFilename();
await comfyuiUploadImage(layer,uploadFilename,true,serverAddress,authHeaders);
requestData["uploadFileName"]=uploadFilename;
}
if (Type=='Inpaint') {
var inpaintImageFilename=generateFilename();
await comfyuiUploadImage(layer,inpaintImageFilename,true,serverAddress,authHeaders);
requestData["uploadFileName"]=inpaintImageFilename;
if (requestData["inpaintMaskDataUrl"]) {
var maskFilename="mask_"+generateFilename();
await comfyuiUploadBase64Image(requestData["inpaintMaskDataUrl"],maskFilename,true,serverAddress,authHeaders);
requestData["maskFileName"]=maskFilename;
}
}

var workflow=comfyuiReplacePlaceholders(selectedWorkflow,requestData,Type);

var canvasGuid=getCanvasGUID();
var layerType='unknown';
var targetLayerGuid=null;
if(isPanel(layer)){
layerType='panel';
targetLayerGuid=getGUID(layer);
}else if(layer.clipPath){
layerType='clipPath';
targetLayerGuid=layer.relatedPoly?getGUID(layer.relatedPoly):getGUID(layer);
}else{
layerType='standalone';
}
var center=calculateCenter(layer);
await registerGenerationTask(canvasGuid,{
layerGuid:getGUID(layer),
layerType:layerType,
centerX:center.centerX,
centerY:center.centerY,
targetLayerGuid:targetLayerGuid
});

var providerCtx={
tag:getComfyUIProviderTag(),
serverAddress:serverAddress,
authHeaders:authHeaders,
objectInfoRepo:(_comfyUIExecProvider&&_comfyUIExecProvider.id==='runpodComfyUI')?comfyObjectInfoRepo_runpod:comfyObjectInfoRepo_local
};
var p=comfyuiQueue.add(async ()=>{
setCurrentAiTask(spinnerId);
const result=await comfyui_put_queue_v2(workflow,providerCtx);
if (!result||result.error) return result;
return new Promise((resolve,reject)=>{
fabric.Image.fromURL(result,(img)=>{
if (img) resolve(img);
else reject(new Error("Failed to create fabric.Image"));
});
});
});
updateAiTaskCancelInfo(spinnerId,{queueName:'comfyui',queueItemId:p._queueItemId});
return p
.then(async (result)=>{
if (result&&result.error) {
createToastError("Generation Error",result.message);
throw new Error(result.message);
} else if (result) {
if(isPageChanged(canvasGuid)){
var applied=await applyGeneratedImageToOriginalPage(canvasGuid,result);
if(applied){
return;
}
}
removeGenerationTask(canvasGuid);
if(isPanel(layer)){
var center=calculateCenter(layer);
putImageInFrame(result,center.centerX,center.centerY,false,false,true,layer);
}else if(layer.clipPath){
var center=calculateCenter(layer);
var targetParent=layer.relatedPoly||layer;
layer.saveHistory=false;
canvas.remove(layer);
putImageInFrame(result,center.centerX,center.centerY,false,false,true,targetParent);
}else{
layer.saveHistory=false;
canvas.remove(layer);
replaceImageObject(layer,result,Type);
}
} else {
throw new Error("Unexpected error: No result returned from comfyui_put_queue_v2");
}
})
.catch((error)=>{
removeGenerationTask(canvasGuid);
if(error.message==='Queue cancelled'||error.message==='Task cancelled'){
comfyuiLogger.debug("Generation cancelled by user");
return;
}
let help=getText("comfyUI_workflowErrorHelp");
createToastError("Generation Error",[error.message,help],8000);
comfyuiLogger.error("Error:",error);
})
.finally(()=>{
removeSpinner(spinnerId);
});
}

async function comfyuiUploadImage(layer,fileName="i2i_temp.png",overwrite=true,serverAddress,authHeaders) {
const base64Image=imageObject2Base64ImageEffectKeep(layer);
if (!base64Image||!base64Image.startsWith("data:image/")) {
throw new Error("Invalid base64 image data");
}

const byteCharacters=atob(base64Image.split(",")[1]);
const byteNumbers=new Array(byteCharacters.length);
for (let i=0;i<byteCharacters.length;i++) {
byteNumbers[i]=byteCharacters.charCodeAt(i);
}
const byteArray=new Uint8Array(byteNumbers);
const blob=new Blob([byteArray],{type: "application/octet-stream"});

const formData=new FormData();
formData.append("image",blob,fileName);
formData.append("overwrite",overwrite.toString());

try {
if(!serverAddress)serverAddress=getComfyUIServerAddress();
if(!authHeaders)authHeaders=getComfyUIAuthHeaders();
var uploadUrl=serverAddress+'/upload/image';
var opts={method:"POST",body:formData};
if(authHeaders&&Object.keys(authHeaders).length>0){
opts.headers=Object.assign({},authHeaders);
}
var response=await fetch(uploadUrl,opts);

if (!response.ok) {
throw new Error(`HTTP error! status: ${response.status}`);
}

const result=await response.json();
return result;
} catch (error) {
comfyuiLogger.error("Error uploading image:",error);
throw error;
}
}


async function comfyuiUploadBase64Image(base64DataUrl,fileName="mask_temp.png",overwrite=true,serverAddress,authHeaders) {
if (!base64DataUrl||!base64DataUrl.startsWith("data:image/")) {
throw new Error("Invalid base64 image data");
}
const byteCharacters=atob(base64DataUrl.split(",")[1]);
const byteNumbers=new Array(byteCharacters.length);
for (let i=0;i<byteCharacters.length;i++) {
byteNumbers[i]=byteCharacters.charCodeAt(i);
}
const byteArray=new Uint8Array(byteNumbers);
const blob=new Blob([byteArray],{type:"application/octet-stream"});
const formData=new FormData();
formData.append("image",blob,fileName);
formData.append("overwrite",overwrite.toString());
try {
if(!serverAddress)serverAddress=getComfyUIServerAddress();
if(!authHeaders)authHeaders=getComfyUIAuthHeaders();
var uploadUrl=serverAddress+'/upload/image';
var opts={method:"POST",body:formData};
if(authHeaders&&Object.keys(authHeaders).length>0){
opts.headers=Object.assign({},authHeaders);
}
var response=await fetch(uploadUrl,opts);
if (!response.ok) {
throw new Error(`HTTP error! status: ${response.status}`);
}
const result=await response.json();
return result;
} catch (error) {
comfyuiLogger.error("Error uploading mask image:",error);
throw error;
}
}

function extractComboOptions(inputDef) {
if (Array.isArray(inputDef)) {
if (Array.isArray(inputDef[0])) {
return inputDef[0];
}
if (inputDef[0]==="COMBO"&&inputDef[1]&&Array.isArray(inputDef[1].options)) {
return inputDef[1].options;
}
}
return [];
}

async function comfyuiFetchSampler() {
try {
const data=await comfyuiFetchObjectInfo("KSampler");
const options=extractComboOptions(data.KSampler.input.required.sampler_name);
const models=options.map((name)=>({name: name}));
updateSamplerDropdown(models);
} catch (error) {
comfyuiLogger.error("comfyuiFetchSampler: Fetch error",error);
}
}

async function comfyuiFetchUpscaler() {
try {
const data=await comfyuiFetchObjectInfo("UpscaleModelLoader");
const options=extractComboOptions(data.UpscaleModelLoader.input.required.model_name);
const models=options.map((name)=>({name: name}));
updateUpscalerDropdown(models);
} catch (error) {
comfyuiLogger.error("comfyuiFetchUpscaler: Fetch error",error);
}
}

async function comfyuiFetchModels() {
try {
const data=await comfyuiFetchObjectInfo("CheckpointLoaderSimple");
const ckptOptions=extractComboOptions(data.CheckpointLoaderSimple.input.required.ckpt_name);
const models=ckptOptions.map((name)=>({title: name,model_name: name}));

const dataUnet=await comfyuiFetchObjectInfo("UNETLoader");
const unetOptions=extractComboOptions(dataUnet.UNETLoader.input.required.unet_name);
const modelsUnet=unetOptions.map((name)=>({title: name,model_name: name}));

const allModels=[...models,...modelsUnet].sort((a,b)=>{
return a.title.localeCompare(b.title);
});

updateModelDropdown(allModels);
} catch (error) {
comfyuiLogger.error("comfyuiFetchModels: Fetch error",error);
}
}

async function comfyuiClipModels() {
try {
const data=await comfyuiFetchObjectInfo("DualCLIPLoader");
const options=extractComboOptions(data.DualCLIPLoader.input.required.clip_name1);
const results=options.map((name)=>({n: name,p: 0}));
updateTagifyDropdown("clipDropdownId",results);
} catch (error) {
comfyuiLogger.error("comfyuiClipModels: Fetch error",error);
}
}
async function comfyuiVaeLoader() {
try {
const dataUnet=await comfyuiFetchObjectInfo("VAELoader");
const options=extractComboOptions(dataUnet.VAELoader.input.required.vae_name);
const results=options.map((name)=>({name: name}));
updateVaeDropdown(results);
} catch (error) {
comfyuiLogger.error("comfyuiVaeLoader: Fetch error",error);
}
}



async function comfyuiFetchObjectInfo(nodeName) {
try {
const response=await comfyuiFetch(comfyUIUrls.objectInfo+nodeName);
if (!response.ok) {
throw new Error(`HTTP error! status: ${response.status}`);
}
const data=await response.json();
// console.log("comfyuiFetchObjectInfo:", data);
return data;
} catch (error) {
comfyuiLogger.error("Comfyui_Fetch: Fetch error",nodeName);
}
}

