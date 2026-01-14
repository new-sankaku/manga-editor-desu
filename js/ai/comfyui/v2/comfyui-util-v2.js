async function comfyui_apiHeartbeat_v2() {
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


let isOnline=false;
let comfyGuideShownThisSession=false;
async function comfyui_monitorConnection_v2(){
comfyuiLogger.debug("comfyui_monitorConnection_v2");
while(true){
var currentStatus=await comfyui_apiHeartbeat_v2();
if(currentStatus!==isOnline){
isOnline=currentStatus;
if(isOnline){
comfyUIWorkflowEditor.updateObjectInfoAndWorkflows();
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

async function comfyui_uploadImage_v2(file,fileName=null,overwrite=true) {
if (!file) {
throw new Error("ファイルが指定されていません");
}

if (!fileName) {
fileName=generateTimestampFileNameV2();
}

const formData=new FormData();
formData.append("image",file,fileName);
formData.append("overwrite",overwrite.toString());

const response=await fetch(comfyUIUrls.uploadImage,{
method: "POST",
body: formData,
});

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
comfyuiLogger.error("ファイルアップロードエラー:",error);
}
}

//type=input output temp
//subfolder: <subfolder>
async function comfyui_view_image_v2(filename,type="input") {
try {
const baseUrl=document.getElementById("comfyUIPageUrl").value;
const params=new URLSearchParams({
filename: filename,
type: type,
});

const response=await fetch(`${baseUrl}/view?${params.toString()}`);
if (!response.ok) {
throw new Error(`HTTPエラー! ステータス: ${response.status}`);
}

const blob=await response.blob();
return URL.createObjectURL(blob);
} catch (error) {
comfyuiLogger.error("画像取得エラー:",error);
return null;
}
}

async function comfyui_fixWorkflowTypes_v2(workflow) {
const objectInfo=await objectInfoRepository.getObjectInfo();
if (!objectInfo) {
comfyuiLogger.warn("ObjectInfo not available, skipping type fix");
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

async function comfyui_put_queue_v2(workflow) {
const builder=new ComfyUIWorkflowBuilder(workflow);
builder.replaceDatePlaceholders();
const fixedWorkflow=await comfyui_fixWorkflowTypes_v2(builder.build());
logger.trace("comfyui_put_queue_v2 fixedWorkflow",fixedWorkflow);

var response=await comfyui_queue_prompt_v2(fixedWorkflow);
if (!response) return null;
processingPrompt=true;
var promptId=response.prompt_id;
await comfyui_track_prompt_progress_v2(promptId);

response=await comfyui_get_history_v2(promptId);
if (!response)
return {
error: true,
message: "Unknown error",
details: "Please check ComfyUI console.",
};

if (comfyui_isError_v2(response)) {
const errorMessage=comfyui_getErrorMessage_v2(response);
return {
error: true,
message: errorMessage.exception_message||"Unknown error",
details: errorMessage,
};
} else {
var imageData=
response[promptId]["outputs"][
Object.keys(response[promptId]["outputs"])[0]
].images["0"];
var img=await comfyui_get_image_v2(imageData);

return new Promise((resolve)=>{
resolve(img);
});
}
}

async function comfyui_get_image_v2(imageDataToReceive) {
try {
const params=new URLSearchParams({
filename: imageDataToReceive.filename,
subfolder: imageDataToReceive.subfolder,
type: imageDataToReceive.type,
});
const response=await fetch(comfyUIUrls.view+"?"+params.toString());
comfyuiLogger.debug("画像データをサーバーから取得しました。",
imageDataToReceive.filename,
imageDataToReceive.subfolder,
imageDataToReceive.type,);

if (!response.ok) {
throw new Error(`HTTPエラー! ステータス: ${response.status}`);
}

const blob=await response.blob();
const imageSrc=URL.createObjectURL(blob);
comfyuiLogger.debug("画像ソース:",imageSrc);

return imageSrc;
} catch (error) {
comfyuiLogger.error("画像取得エラー:",error);
return null;
}
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

async function comfyui_queue_prompt_v2(prompt) {
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
createToastError(
`HTTP error! status: ${response.status}, message: ${errorText}`
);
return null;
}

const responseData=await response.json();
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

comfyuiLogger.error("Error details:",error);
createToastError(errorMessage);
return null;
}
}

async function comfyui_get_history_v2(promptId) {
comfyuiLogger.debug(
"comfyui_get_history_v2関数が呼び出されました。プロンプトID:",
promptId
);
try {
const response=await fetch(comfyUIUrls.history+promptId,{
method: "GET",
headers: {
accept: "application/json",
},
});
comfyuiLogger.debug("サーバーに履歴データをリクエストしました。");
const data=await response.json();
comfyuiLogger.debug("履歴データ:",data);
return data;
} catch (error) {
comfyuiLogger.error("Text2Imageエラー:",error);
createToastError("Text2Image Error.","check COMFYUI!");
return null;
}
}

async function comfyui_track_prompt_progress_v2(promptId) {
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

