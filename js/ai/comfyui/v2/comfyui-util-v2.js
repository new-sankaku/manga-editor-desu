async function comfyui_apiHeartbeat_v2() {
var labelfwContainer=$('msLocalContainer');
var labelfw=labelfwContainer?labelfwContainer.querySelector('.comfui-connection-label'):null;
var pName=providerRegistry.getActive()?providerRegistry.getActive().name:'ComfyUI';
var tag=getComfyUIProviderTag();

try {
const response=await comfyuiFetch(comfyUIUrls.settings,{
method: "GET",
headers: {
"Content-Type": "application/json",
accept: "application/json",
},
});

if (response.ok) {
if (labelfw) {
labelfw.innerHTML=pName+" ON";
labelfw.style.color="green";
}

if (firstComfyConnection) {
comfyuiLogger.info('['+tag+'] 接続成功');
getDiffusionInformation();
firstComfyConnection=false;
}
return true;
} else {
comfyuiLogger.debug('['+tag+'] 接続失敗: HTTP '+response.status);
if (labelfw) {
labelfw.innerHTML=pName+" OFF";
labelfw.style.color="red";
}
}
} catch (error) {
comfyuiLogger.debug('['+tag+'] 接続エラー: '+error.message);
if (labelfw) {
labelfw.innerHTML=pName+" OFF";
labelfw.style.color="red";
}
}
return false;
}


let isOnline=false;
let comfyGuideShownThisSession=false;
let comfyMonitorStarted=false;

// 監視ループは1本だけ動かす。複数動くと接続状態の変化を取り合って
// ObjectInfoの更新が走らないことがある
async function comfyui_monitorConnection_v2(editor){
if(comfyMonitorStarted){
comfyuiLogger.debug("comfyui_monitorConnection_v2 already running");
return;
}
comfyMonitorStarted=true;
comfyuiLogger.debug("comfyui_monitorConnection_v2");
var targetEditor=(editor&&typeof editor.updateObjectInfoAndWorkflows==='function')?editor:null;
while(true){
var currentStatus=false;
try{
currentStatus=await comfyui_apiHeartbeat_v2();
}catch(error){
comfyuiLogger.error("heartbeat error: "+(error instanceof Error?error.name+" "+error.message:error));
}
if(currentStatus!==isOnline){
isOnline=currentStatus;
if(isOnline){
// 例外で監視ループごと止まるとObjectInfoが二度と更新されなくなる
try{
var target=targetEditor||comfyUIWorkflowEditor;
if(target){
await target.updateObjectInfoAndWorkflows();
}
}catch(error){
comfyuiLogger.error("updateObjectInfoAndWorkflows error: "+(error instanceof Error?error.name+" "+error.message:error));
}
}
if(typeof ComfyUIGuide!=='undefined'&&!comfyGuideShownThisSession){
comfyGuideShownThisSession=true;
setTimeout(function(){ComfyUIGuide.showSetupGuide(isOnline);},500);
}
}
var interval=isOnline?15000:5000;
await new Promise(function(resolve){setTimeout(resolve,interval);});
}
}

function generateTimestampFileNameV2(extension="png") {
const now=new Date();
const year=now.getFullYear();
const month=String(now.getMonth()+1).padStart(2,"0");
const day=String(now.getDate()).padStart(2,"0");
const hours=String(now.getHours()).padStart(2,"0");
const minutes=String(now.getMinutes()).padStart(2,"0");
const seconds=String(now.getSeconds()).padStart(2,"0");
const milliseconds=String(now.getMilliseconds()).padStart(3,"0");

return `${year}${month}${day}-${hours}${minutes}${seconds}-${milliseconds}.${extension}`;
}

async function comfyui_uploadImage_v2(file,fileName=null,overwrite=true,serverAddress,authHeaders) {
if (!file) {
throw new Error("ファイルが指定されていません");
}

if (!fileName) {
fileName=generateTimestampFileNameV2();
}

const formData=new FormData();
formData.append("image",file,fileName);
formData.append("overwrite",overwrite.toString());

if(!serverAddress)serverAddress=getComfyUIServerAddress();
if(!authHeaders)authHeaders=getComfyUIAuthHeaders();
var uploadUrl=serverAddress+'/upload/image';
var opts={method:"POST",body:formData};
if(authHeaders&&Object.keys(authHeaders).length>0){
opts.headers=Object.assign({},authHeaders);
}
const response=await fetch(uploadUrl,opts);

if (!response.ok) {
throw new Error(`アップロードエラー: ${response.status}`);
}

const result=await response.json();
return {
name: fileName,
subfolder: result.subfolder,
type: result.type,
success: true,
};
}

async function comfyui_handleFileUpload_v2(input) {
const file=input.files[0];
const nodeId=input.dataset.nodeId;
const inputName=input.dataset.inputName;
const previewTargetId=input.dataset.previewTarget;

if (!file) return;

try {
const uploadResult=await comfyui_uploadImage_v2(file);

if (uploadResult.success) {
const previewContainer=document.querySelector(
`[data-preview-id="${previewTargetId}"]`
);
const previewImage=previewContainer?.querySelector("img");

if (previewContainer&&previewImage) {
const reader=new FileReader();
reader.onload=(e)=>{
previewImage.src=e.target.result;
previewContainer.classList.remove("hidden");
};
reader.readAsDataURL(file);
}

if (workflow[nodeId]&&inputName) {
workflow[nodeId].inputs[inputName]=uploadResult.name;
}
}
} catch (error) {
comfyuiLogger.error('['+getComfyUIProviderTag()+'] ファイルアップロードエラー:',error);
}
}

//type=input output temp
//subfolder: <subfolder>
async function comfyui_view_image_v2(filename,type="input",serverAddress,authHeaders) {
try {
if(!serverAddress)serverAddress=getComfyUIServerAddress();
if(!authHeaders)authHeaders=getComfyUIAuthHeaders();
const params=new URLSearchParams({
filename: filename,
type: type,
});

var fetchOptions={};
if(authHeaders&&Object.keys(authHeaders).length>0){
fetchOptions.headers=authHeaders;
}
const response=await fetch(`${serverAddress}/view?${params.toString()}`,fetchOptions);
if (!response.ok) {
throw new Error(`HTTPエラー! ステータス: ${response.status}`);
}

const blob=await response.blob();
return URL.createObjectURL(blob);
} catch (error) {
comfyuiLogger.error('['+getComfyUIProviderTag()+'] 画像取得エラー:',error);
return null;
}
}

async function comfyui_fixWorkflowTypes_v2(workflow,objInfoRepo) {
const objectInfo=await (objInfoRepo||comfyObjectInfoRepo).getObjectInfo();
if (!objectInfo) {
comfyuiLogger.warn('['+getComfyUIProviderTag()+'] ObjectInfo not available, skipping type fix');
return workflow;
}
const fixed=JSON.parse(JSON.stringify(workflow));
for (const nodeId in fixed) {
const node=fixed[nodeId];
const classType=node.class_type;
const nodeInfo=objectInfo[classType];
if (!nodeInfo||!nodeInfo.input) continue;
const allInputDefs={...(nodeInfo.input.required||{}),...(nodeInfo.input.optional||{})};
for (const inputName in node.inputs) {
const inputDef=allInputDefs[inputName];
if (!inputDef) continue;
const currentValue=node.inputs[inputName];
if (Array.isArray(currentValue)) continue;
const expectedType=inputDef[0];
if (expectedType==='INT') {
const parsed=parseInt(currentValue,10);
node.inputs[inputName]=isNaN(parsed) ? currentValue : parsed;
} else if (expectedType==='FLOAT') {
const parsed=parseFloat(currentValue);
node.inputs[inputName]=isNaN(parsed) ? currentValue : parsed;
} else if (expectedType==='BOOLEAN') {
if (currentValue==='true'||currentValue===true) {
node.inputs[inputName]=true;
} else if (currentValue==='false'||currentValue===false) {
node.inputs[inputName]=false;
}
}
}
}
return fixed;
}

async function comfyui_put_queue_v2(workflow,providerCtx) {
const builder=new ComfyUIWorkflowBuilder(workflow);
builder.replaceDatePlaceholders();
var objInfoRepo=(providerCtx&&providerCtx.objectInfoRepo)||((_comfyUIExecProvider&&_comfyUIExecProvider.id==='runpodComfyUI')?comfyObjectInfoRepo_runpod:comfyObjectInfoRepo_local);
const fixedWorkflow=await comfyui_fixWorkflowTypes_v2(builder.build(),objInfoRepo);
var tag=(providerCtx&&providerCtx.tag)||getComfyUIProviderTag();
var serverAddress=(providerCtx&&providerCtx.serverAddress)||getComfyUIServerAddress();
var authHeaders=(providerCtx&&providerCtx.authHeaders)||getComfyUIAuthHeaders();
comfyuiLogger.info('['+tag+'] プロンプト送信開始');
comfyuiLogger.trace("comfyui_put_queue_v2 fixedWorkflow",fixedWorkflow);

var response=await comfyui_queue_prompt_v2(fixedWorkflow,serverAddress,authHeaders);
if (!response) return null;
processingPrompt=true;
var promptId=response.prompt_id;
aiProgressState.currentPromptId=promptId;
if(aiProgressState.currentTaskId){
updateAiTaskCancelInfo(aiProgressState.currentTaskId,{promptId:promptId});
}
var outputData=await comfyui_track_prompt_progress_v2(promptId);

if(!outputData||!outputData.images||!outputData.images["0"]){
comfyuiLogger.debug('['+tag+'] WebSocket outputData不足、history APIフォールバック');
var historyUrl=serverAddress+'/history/';
var maxRetries=10;
var retryDelay=500;
for(var retryCount=0;retryCount<maxRetries;retryCount++){
try{
var historyFetchOpts={method:"GET",headers:Object.assign({accept:"application/json"},authHeaders)};
var historyResp=await fetch(historyUrl+promptId,historyFetchOpts);
response=await historyResp.json();
}catch(e){
comfyuiLogger.debug('['+tag+'] history API取得失敗:',e.message);
response=null;
}
if(response&&response[promptId]){
if(comfyui_isError_v2(response)){
const errorMessage=comfyui_getErrorMessage_v2(response);
return {
error: true,
message: errorMessage.exception_message||"Unknown error",
details: errorMessage,
};
}
var outputs=response[promptId]["outputs"];
if(outputs&&Object.keys(outputs).length>0){
outputData=outputs[Object.keys(outputs)[0]];
break;
}
}
comfyuiLogger.debug('['+tag+'] history APIリトライ '+(retryCount+1)+'/'+maxRetries);
await new Promise(function(resolve){setTimeout(resolve,retryDelay);});
}
if(!outputData||!outputData.images||!outputData.images["0"]){
return {
error: true,
message: "Unknown error",
details: "Please check ComfyUI console.",
};
}
}

comfyuiLogger.debug('['+tag+'] outputData:',JSON.stringify(outputData));
var imageData=outputData.images["0"];
comfyuiLogger.debug('['+tag+'] imageData:',JSON.stringify(imageData));
var img=await comfyui_get_image_v2(imageData,serverAddress,authHeaders);
return img;
}

async function comfyui_get_image_v2(imageDataToReceive,serverAddress,authHeaders) {
var tag=getComfyUIProviderTag();
var viewUrl=serverAddress+'/view';
var fetchOptions={};
if(authHeaders&&Object.keys(authHeaders).length>0){
fetchOptions.headers=authHeaders;
}
var maxRetries=5;
var retryDelay=1000;
for(var retryCount=0;retryCount<=maxRetries;retryCount++){
try {
const params=new URLSearchParams({
filename: imageDataToReceive.filename,
subfolder: imageDataToReceive.subfolder,
type: imageDataToReceive.type,
});
var url=viewUrl+"?"+params.toString();
const response=await fetch(url,fetchOptions);
comfyuiLogger.debug('['+tag+'] 画像データ取得:',url);

if (!response.ok) {
if(response.status===404&&retryCount<maxRetries){
comfyuiLogger.debug('['+tag+'] 画像未準備、リトライ '+(retryCount+1)+'/'+maxRetries);
await new Promise(function(resolve){setTimeout(resolve,retryDelay);});
continue;
}
throw new Error(`HTTPエラー! ステータス: ${response.status}`);
}

const blob=await response.blob();
const imageSrc=URL.createObjectURL(blob);
comfyuiLogger.debug('['+tag+'] 画像ソース:',imageSrc);

return imageSrc;
} catch (error) {
if(retryCount<maxRetries&&error.message&&error.message.includes('404')){
comfyuiLogger.debug('['+tag+'] 画像取得リトライ '+(retryCount+1)+'/'+maxRetries);
await new Promise(function(resolve){setTimeout(resolve,retryDelay);});
continue;
}
comfyuiLogger.error('['+tag+'] 画像取得エラー:',error);
return null;
}
}
comfyuiLogger.error('['+tag+'] 画像取得失敗: リトライ上限到達');
return null;
}

function comfyui_getErrorMessage_v2(response) {
// console.log('comfyui_getErrorMessage_v2 called with:', JSON.stringify(response));

if (comfyui_isError_v2(response)) {
const promptId=Object.keys(response)[0];
const status=response[promptId].status;
const errorMessage={
status_str: status.status_str||"Unknown error",
completed: status.completed,
exception_type: "Unknown",
exception_message: "An error occurred",
traceback: [],
};

if (Array.isArray(status.messages)&&status.messages.length>0) {
const lastMessage=status.messages[status.messages.length-1];
if (
Array.isArray(lastMessage)&&
lastMessage.length>1&&
typeof lastMessage[1]==="object"
) {
const errorDetails=lastMessage[1];
errorMessage.exception_type=
errorDetails.exception_type||errorMessage.exception_type;
errorMessage.exception_message=
errorDetails.exception_message||errorMessage.exception_message;
errorMessage.traceback=Array.isArray(errorDetails.traceback)
? errorDetails.traceback
: errorMessage.traceback;
}
}

comfyuiLogger.debug("comfyui_getErrorMessage_v2 returning:",errorMessage);
return errorMessage;
}
comfyuiLogger.debug("comfyui_getErrorMessage_v2 returning null");
return null;
}

async function comfyui_queue_prompt_v2(prompt,serverAddress,authHeaders) {
var tag=getComfyUIProviderTag();
if(!serverAddress)serverAddress=getComfyUIServerAddress();
if(!authHeaders)authHeaders=getComfyUIAuthHeaders();
try {
const p={prompt: prompt,client_id: comfyUIuuid};
var promptUrl=serverAddress+'/prompt';
var fetchHeaders=Object.assign({"Content-Type":"application/json",accept:"application/json"},authHeaders);
const response=await fetch(promptUrl,{
method: "POST",
headers: fetchHeaders,
body: JSON.stringify(p),
});

if (!response.ok) {
const errorText=await response.text();
comfyuiLogger.error('['+tag+'] プロンプト送信失敗: HTTP '+response.status);
createToastError(
`HTTP error! status: ${response.status}, message: ${errorText}`
);
return null;
}

const responseData=await response.json();
comfyuiLogger.info('['+tag+'] プロンプト送信成功: promptId='+responseData.prompt_id);
return responseData;
} catch (error) {
let errorMessage="Text2Image Error. ";
if (error.name==="TypeError") {
errorMessage+="Network error or COMFYUI server is down.";
} else if (error.message.includes("HTTP error!")) {
errorMessage+=error.message;
} else {
errorMessage+="check COMFYUI!";
}

comfyuiLogger.error('['+tag+'] '+errorMessage,error);
createToastError(errorMessage);
return null;
}
}

async function comfyui_get_history_v2(promptId) {
var tag=getComfyUIProviderTag();
comfyuiLogger.debug(
'['+tag+'] comfyui_get_history_v2 プロンプトID:',
promptId
);
try {
const response=await comfyuiFetch(comfyUIUrls.history+promptId,{
method: "GET",
headers: {
accept: "application/json",
},
});
comfyuiLogger.debug('['+tag+'] 履歴データ取得完了');
const data=await response.json();
comfyuiLogger.debug('['+tag+'] 履歴データ:',data);
return data;
} catch (error) {
comfyuiLogger.error('['+tag+'] Text2Imageエラー:',error);
createToastError("Text2Image Error.","check COMFYUI!");
return null;
}
}

async function comfyui_track_prompt_progress_v2(promptId) {
if (!comfyuiGetSocket()) comfyuiConnect();
var ws=comfyuiGetSocket();
var outputData=null;

return new Promise((resolve,reject)=>{
ws.onmessage=(event)=>{
if (event.data instanceof Blob) {
//skip
} else {
const message=JSON.parse(event.data);
if(message.type==="progress"&&message.data){
var value=message.data.value||0;
var max=message.data.max||0;
if(typeof updateAiStepProgress==='function'){
updateAiStepProgress(value,max,promptId);
}
}
if(
message.type==="executed"&&
message.data&&
message.data.prompt_id===promptId
){
outputData=message.data.output;
}
if(
message.type==="executing"&&
message.data.node===null&&
message.data.prompt_id===promptId
){
if(typeof resetAiStepProgress==='function'){
resetAiStepProgress();
}
resolve(outputData);
}
}
};
ws.onerror=(error)=>{
if(typeof resetAiStepProgress==='function'){
resetAiStepProgress();
}
reject(`WebSocket error: ${error}`);
};
ws.onclose=()=>{
if(typeof resetAiStepProgress==='function'){
resetAiStepProgress();
}
reject("WebSocket closed before receiving stop message");
};
});
}

function comfyui_isError_v2(response) {
if (response&&typeof response==="object") {
const promptId=Object.keys(response)[0];
if (promptId&&response[promptId]&&response[promptId].status) {
const status=response[promptId].status;
const result=status.status_str==="error";
comfyuiLogger.debug("comfyui_isError_v2 return",result);
return result;
}
}
comfyuiLogger.debug("comfyui_isError_v2 return false");
return false;
}

