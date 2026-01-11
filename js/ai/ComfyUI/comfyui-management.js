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
console.log("ComfyUIへの接続に成功しました。");
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

async function comfyuiQueuePrompt(prompt) {
try {
const p={prompt: prompt,client_id: comfyUIuuid};
const response=await fetch(comfyUIUrls.prompt,{
method: "POST",
headers: {
"Content-Type": "application/json",
accept: "application/json",
},
body: JSON.stringify(p),
});

if (!response.ok) {
const errorText=await response.text();
createToastError(`HTTP error! status: ${response.status}, message: ${errorText}`);
return null;
}

const responseData=await response.json();
return responseData;

} catch (error) {
let errorMessage="Error. ";
if (error.name==='TypeError') {
errorMessage+="Network error or COMFYUI server is down.";
} else if (error.message.includes('HTTP error!')) {
errorMessage+=error.message;
} else {
errorMessage+="check COMFYUI!";
}

console.error('Error details:',error);
createToastError(errorMessage);
return null;
}
}


async function comfyuiGetHistory(promptId) {
console.log(
"comfyuiGetHistory関数が呼び出されました。プロンプトID:",
promptId
);
try {
const response=await fetch(comfyUIUrls.history+promptId,
{
method: "GET",
headers: {
accept: "application/json",
},
}
);
console.log("サーバーに履歴データをリクエストしました。");
const data=await response.json();
console.log("履歴データ:",data);
return data;
} catch (error) {
console.log("Text2Imageエラー:",error);
createToastError("Text2Image Error.","check COMFYUI!");
return null;
}
}

async function comfyuiGetImage(imageDataToReceive) {
try {
const params=new URLSearchParams({
filename: imageDataToReceive.filename,
subfolder: imageDataToReceive.subfolder,
type: imageDataToReceive.type,
});
const response=await fetch(comfyUIUrls.view+'?'+params.toString());
console.log("画像データをサーバーから取得しました。v1");

if (!response.ok) {
throw new Error(`HTTPエラー! ステータス: ${response.status}`);
}

const blob=await response.blob();
var imageSrc=URL.createObjectURL(blob);
console.log("画像ソース:",imageSrc);
return new Promise((resolve,reject)=>{
fabric.Image.fromURL(imageSrc,(img)=>{
if (img) {
console.log("fabric.Imageオブジェクトの作成に成功しました。v1");
resolve(img);
} else {
console.log("fabric.Imageオブジェクトの作成に失敗しました。v1");
reject(new Error("Failed to create a fabric.Image object　v1"));
}
});
});
} catch (error) {
console.error("画像取得エラー　v1:",error);
return null;
}
}

async function comfyuiTrackPromptProgress(promptId) {
if (!socket) comfyuiConnect();

return new Promise((resolve,reject)=>{
socket.onmessage=(event)=>{
if (event.data instanceof Blob) {
//akip
} else {
const message=JSON.parse(event.data);
// console.log('WebSocketメッセージ:', message);
if (
message.type==="executing"&&
message.data.node===null&&
message.data.prompt_id===promptId
) {
resolve("Stop message received with matching promptId");
}
}
};
socket.onerror=(error)=>{
reject(`WebSocket error: ${error}`);
};
socket.onclose=()=>{
reject("WebSocket closed before receiving stop message");
};
});
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

return comfyuiQueue.add(async ()=>comfyui_put_queue(workflow))
.then(async (result)=>{
if (result&&result.error) {
createToastError("Generation Error",result.message);
throw new Error(result.message);
} else if (result) {

if(isPanel(layer)){
var center=calculateCenter(layer);
putImageInFrame(result,center.centerX,center.centerY);
}else if(layer.clipPath){
layer.visible=false;
var center=calculateCenter(layer);
putImageInFrame(result,center.centerX,center.centerY);
}else{
layer.visible=false;
replaceImageObject(layer,result,Type);
}
} else {
throw new Error("Unexpected error: No result returned from comfyui_put_queue");
}
})
.catch((error)=>{
let help=getText("comfyUI_workflowErrorHelp");
createToastError("Generation Error",[error.message,help],8000);
console.error("Error:",error);
})
.finally(()=>{
removeSpinner(spinnerId);
});
}

async function comfyui_put_queue(workflow) {
workflow=await comfyui_fixWorkflowTypes_v2(workflow);

var response=await comfyuiQueuePrompt(workflow);
if (!response) return null;
processingPrompt=true;
var promptId=response.prompt_id;
await comfyuiTrackPromptProgress(promptId);

response=await comfyuiGetHistory(promptId);
if (!response) return {error: true,message: "Unknown error",details: "Please check ComfyUI console.",};

workflowlLogger.trace("comfyui_put_queue response:",JSON.stringify(response));

if (comfyuiIsError(response)) {
const errorMessage=comfyuiGetErrorMessage(response);
return {
error: true,
message: errorMessage.exception_message||"Unknown error",
details: errorMessage,
};
} else {
var imageData=response[promptId]["outputs"][Object.keys(response[promptId]["outputs"])[0]].images["0"];
var img=await comfyuiGetImage(imageData);

return new Promise((resolve)=>{
resolve(img);
});
}
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
console.error("Error uploading image:",error);
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
console.error("comfyuiFetchSampler: Fetch error",error);
}
}

async function comfyuiFetchUpscaler() {
try {
const data=await comfyuiFetchObjectInfo("UpscaleModelLoader");
const options=extractComboOptions(data.UpscaleModelLoader.input.required.model_name);
const models=options.map((name)=>({name: name}));
updateUpscalerDropdown(models);
} catch (error) {
console.error("comfyuiFetchUpscaler: Fetch error",error);
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
console.error("comfyuiFetchModels: Fetch error",error);
}
}

async function comfyuiClipModels() {
try {
const data=await comfyuiFetchObjectInfo("DualCLIPLoader");
const options=extractComboOptions(data.DualCLIPLoader.input.required.clip_name1);
const results=options.map((name)=>({n: name,p: 0}));
updateTagifyDropdown("clipDropdownId",results);
} catch (error) {
console.error("comfyuiClipModels: Fetch error",error);
}
}
async function comfyuiVaeLoader() {
try {
const dataUnet=await comfyuiFetchObjectInfo("VAELoader");
const options=extractComboOptions(dataUnet.VAELoader.input.required.vae_name);
const results=options.map((name)=>({name: name}));
updateVaeDropdown(results);
} catch (error) {
console.error("comfyuiVaeLoader: Fetch error",error);
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
console.error("Comfyui_Fetch: Fetch error",nodeName);
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
console.error("comfyuiFetchObjectInfoOnly: Fetch error:",error);
return [];
}
}