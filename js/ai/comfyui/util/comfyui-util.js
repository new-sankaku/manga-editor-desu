
function comfyuiReplacePlaceholders(workflow,requestData,Type='T2I') {
const builder=createWorkflowBuilder(workflow);

workflowLogger.trace("requestData[seed]",requestData["seed"]);

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
if(Type=='Inpaint'){
builder.updateNodesByInputName({
image: requestData["uploadFileName"]
});
if(requestData["maskFileName"]){
builder.updateValueByTargetValue("inpaint_mask.png",requestData["maskFileName"]);
}
if(requestData["inpaintDenoise"]!==undefined){
builder.updateNodesByInputName({
denoise: parseFloat(requestData["inpaintDenoise"])
});
}
}

builder.updateValueByTargetValue("%prompt%",requestData["prompt"]);
builder.updateValueByTargetValue("%negative%",requestData["negative_prompt"]);
builder.replaceDatePlaceholders();

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
comfyuiLogger.debug("filename:",filename);
return filename;
}


function getClassTypeOnlyByJson(jsonData) {
const classTypes=Object.values(jsonData).map(item=>item.class_type);
return classTypes;
}


function checkWorkflowNodeVsComfyUI(workflowClassTypes){
var setB=new Set(comfyObjectInfoList);
var result=[];
for(var i=0;i<workflowClassTypes.length;i++){
var item=workflowClassTypes[i];
if(!setB.has(item)){
result.push(item);
}
}
if(result.length>0){
result.unshift("---");
result.push("---");
createToastError('Check ComfyUI Node! Not Exists!',result,1000*10);
if(typeof ComfyUIGuide!=='undefined'){
ComfyUIGuide.showNodeErrorGuide(result);
}
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
