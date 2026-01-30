class ComfyUIEndpoints {
#getUrlParts() {
const serverAddress=$('comfyUIPageUrl').value;
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
objectInfoOnly: '/object_info'
};
return endpoints[key]||'';
}
}


let reader=new FileReader();

var socket=null;
const comfyUIuuid=crypto.randomUUID();
var selectedWorkflow=null;
var processingPrompt=false;
var workflowFileLoad="";

function comfyuiConnect() {
try {
socket=new WebSocket(comfyUIUrls.ws+'?clientId='+comfyUIuuid);
socket.addEventListener("open",(event)=>{
comfyuiLogger.info("ComfyUIへの接続に成功しました。");
});
socket.addEventListener("close",(event)=>{
socket=null;
});
socket.addEventListener("error",(event)=>{
socket=null;
});
return;
} catch (error) {
socket=null;
}
}

async function comfyuiApiHeartbeat() {
const label=$("ExternalService_Heartbeat_Label");
const labelfw=$("ExternalService_Heartbeat_Label_fw");

try {
const response=await fetch(comfyUIUrls.settings,{
method: "GET",
headers: {
"Content-Type": "application/json",
accept: "application/json",
},
});

if (response.ok) {
if (label) {
label.innerHTML="ComufyUI ON";
label.style.color="green";
}
if (labelfw) {
labelfw.innerHTML="ComufyUI ON";
labelfw.style.color="green";
}

if (firstComfyConnection) {
getDiffusionInfomation();
firstComfyConnection=false;
}
return true;
} else {
if (label) {
label.innerHTML="ComufyUI OFF";
label.style.color="red";
}
if (labelfw) {
labelfw.innerHTML="ComufyUI OFF";
labelfw.style.color="red";
}
}
} catch (error) {
if (label) {
label.innerHTML="ComufyUI OFF";
label.style.color="red";
}
if (labelfw) {
labelfw.innerHTML="ComufyUI OFF";
labelfw.style.color="red";
}
}
return false;
}

async function comfyuiHandleProcessQueue(layer,spinnerId,Type='T2I') {
if (!socket) comfyuiConnect();
var requestData=baseRequestData(layer);
if (basePrompt.text2img_model!=""){
requestData["model"]=basePrompt.text2img_model;
}

if (Type=='T2I') {
selectedWorkflow=await comfyUIWorkflowRepository.getEnabledWorkflowByType("T2I");
} else if(Type=='I2I') {
selectedWorkflow=await comfyUIWorkflowRepository.getEnabledWorkflowByType("I2I");
} else if(Type=='Rembg') {
selectedWorkflow=await comfyUIWorkflowRepository.getEnabledWorkflowByType("REMBG");
} else if(Type=='Upscaler') {
selectedWorkflow=await comfyUIWorkflowRepository.getEnabledWorkflowByType("Upscaler");
} else{
removeSpinner(spinnerId);
return;
}

var classTypeLists=getClassTypeOnlyByJson(selectedWorkflow);
if(checkWorkflowNodeVsComfyUI(classTypeLists)){
}else{
removeSpinner(spinnerId);
return;
}


if (Type=='I2I'||Type=='Rembg'||Type=='Upscaler') {
var uploadFilename=generateFilename();
await comfyuiUploadImage(layer,uploadFilename);
requestData["uploadFileName"]=uploadFilename;
}

var workflow=comfyuiReplacePlaceholders(selectedWorkflow,requestData,Type);

var taskId=generateTaskId();
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
registerGenerationTask(taskId,{
layerGuid:getGUID(layer),
layerType:layerType,
centerX:center.centerX,
centerY:center.centerY,
targetLayerGuid:targetLayerGuid
});

return comfyuiQueue.add(async ()=>{
const result=await comfyui_put_queue_v2(workflow);
if (!result||result.error) return result;
return new Promise((resolve,reject)=>{
fabric.Image.fromURL(result,(img)=>{
if (img) resolve(img);
else reject(new Error("Failed to create fabric.Image"));
});
});
})
.then(async (result)=>{
if (result&&result.error) {
createToastError("Generation Error",result.message);
throw new Error(result.message);
} else if (result) {
if(isPageChanged(taskId)){
var applied=await applyGeneratedImageToOriginalPage(taskId,result);
if(applied){
return;
}
}
removeGenerationTask(taskId);
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
removeGenerationTask(taskId);
let help=getText("comfyUI_workflowErrorHelp");
createToastError("Generation Error",[error.message,help],8000);
comfyuiLogger.error("Error:",error);
})
.finally(()=>{
removeSpinner(spinnerId);
});
}

async function comfyuiUploadImage(layer,fileName="i2i_temp.png",overwrite=true) {
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
const response=await fetch(comfyUIUrls.uploadImage,{
method: "POST",
body: formData,
});

if (!response.ok) {
throw new Error(`HTTP error! status: ${response.status}`);
}

const result=await response.json();
// console.log("Upload successful:", result);
return result;
} catch (error) {
comfyuiLogger.error("Error uploading image:",error);
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
const response=await fetch(comfyUIUrls.objectInfo+nodeName);
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

var comfyObjectInfoList;
async function comfyuiFetchObjectInfoOnly() {
try {
const response=await fetch(comfyUIUrls.objectInfoOnly);
if (!response.ok) {
throw new Error(`HTTP error! status: ${response.status}`);
}
const data=await response.json();

const nodeNames=Object.keys(data);
// console.log("Node names:", nodeNames);
comfyObjectInfoList=nodeNames;
return nodeNames;
} catch (error) {
comfyuiLogger.error("comfyuiFetchObjectInfoOnly: Fetch error:",error);
return [];
}
}