
function comfyuiIsError(response) {
if (response&&typeof response==='object') {
const promptId=Object.keys(response)[0];
if (promptId&&response[promptId]&&response[promptId].status) {
const status=response[promptId].status;
const result=status.status_str==="error";
console.log('comfyuiIsError return',result);
return result;
}
}
console.log('comfyuiIsError return false');
return false;
}
function comfyuiGetErrorMessage(response) {
console.log('comfyuiGetErrorMessage called with:',JSON.stringify(response));

if (comfyuiIsError(response)) {
const promptId=Object.keys(response)[0];
const status=response[promptId].status;
const errorMessage={
status_str: status.status_str||'Unknown error',
completed: status.completed,
exception_type: 'Unknown',
exception_message: 'An error occurred',
traceback: []
};

if (Array.isArray(status.messages)&&status.messages.length>0) {
const lastMessage=status.messages[status.messages.length-1];
if (Array.isArray(lastMessage)&&lastMessage.length>1&&typeof lastMessage[1]==='object') {
const errorDetails=lastMessage[1];
errorMessage.exception_type=errorDetails.exception_type||errorMessage.exception_type;
errorMessage.exception_message=errorDetails.exception_message||errorMessage.exception_message;
errorMessage.traceback=Array.isArray(errorDetails.traceback) ? errorDetails.traceback : errorMessage.traceback;
}
}

console.log('comfyuiGetErrorMessage returning:',errorMessage);
return errorMessage;
}
console.log('comfyuiGetErrorMessage returning null');
return null;
}




function comfyuiReplacePlaceholders(workflow,requestData,Type='T2I') {
const builder=createWorkflowBuilder(workflow);

workflowlLogger.trace("requestData[seed]",requestData["seed"]);

builder.updateNodesByInputName({
seed:       requestData["seed"]=="-1"||requestData["seed"]=="0" ? Math.floor(Math.random()*50000000) :        requestData["seed"],
noise_seed: requestData["seed"]=="-1"||requestData["seed"]=="0" ? Math.floor(Math.random()*537388471760656) : requestData["seed"],
width:      requestData["width"],
height:     requestData["height"]
});

if(Type=='I2I'||Type=='Rembg'||Type=='Upscaler'){
builder.updateNodesByInputName({
image: requestData["uploadFileName"]
});
}

builder.updateValueByTargetValue("%prompt%",requestData["prompt"]);
builder.updateValueByTargetValue("%negative%",requestData["negative_prompt"]);

const newWorkflow=builder.build();
return newWorkflow;
}

function comfyuiGetValueById(id) {
const el=$(id);
if (!el) return "";
return el.type==="checkbox" ? el.checked : el.value;
}


function comfyuiGetUrl(){
const serverAddress=hostInput.value+":"+portInput.value;
return `http://${serverAddress}/`;
}

var generateFilenameIndex=0;
function generateFilename() {
const now=new Date();
const year=now.getFullYear();
const month=String(now.getMonth()+1).padStart(2,'0');
const day=String(now.getDate()).padStart(2,'0');
const hours=String(now.getHours()).padStart(2,'0');
const minutes=String(now.getMinutes()).padStart(2,'0');
const seconds=String(now.getSeconds()).padStart(2,'0');
const milliseconds=String(now.getMilliseconds()).padStart(3,'0');

var filename=`temp_${year}${month}${day}${hours}${minutes}${seconds}_${milliseconds}_${generateFilenameIndex}.png`;
generateFilenameIndex++;
console.log("filename:",filename);
return filename;
}


function getClassTypeOnlyByJson(jsonData) {
const classTypes=Object.values(jsonData).map(item=>item.class_type);
return classTypes;
}


function checkWorkflowNodeVsComfyUI(workflowClassTypes) {
const setB=new Set(comfyObjectInfoList);
const result=[];

for (const item of workflowClassTypes) {
if (!setB.has(item)) {
result.push(item);
}
}
if (result.length>0) {
result.unshift("---");
result.push("---");
createToastError('Check ComfyUI Node! Not Exists!',result,1000*10);
return false;
}else{
return true;
}
}

function notExistsWorkflowNodeVsComfyUI(workflowClassType) {
const setB=new Set(comfyObjectInfoList);
if (!setB.has(workflowClassType)) {
return true;
}else{
return false;
}
}
