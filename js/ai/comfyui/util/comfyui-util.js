
function comfyuiReplacePlaceholders(workflow,requestData,Type='T2I') {
const builder=createWorkflowBuilder(workflow);

workflowLogger.trace("requestData[seed]",requestData["seed"]);

builder.updateNodesByInputName({
seed:       requestData["seed"]=="-1"||requestData["seed"]=="0" ? Math.floor(Math.random()*50000000) :        requestData["seed"],
noise_seed: requestData["seed"]=="-1"||requestData["seed"]=="0" ? Math.floor(Math.random()*537388471760656) : requestData["seed"],
width:      requestData["width"],
height:     requestData["height"]
});

if(Type=='I2I'||Type=='Rembg'||Type=='Upscaler'||Type=='I2I_Angle'){
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

if(requestData["anglePrompt"]){
builder.updateValueByTargetValue('%AnglePrompt%',requestData["anglePrompt"]);
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


// ObjectInfoはワークフロー設定ウィンドウを開いたときにしか取得されないため、
// 起動直後は空のまま。空のまま照合すると全ノードが「存在しない」と判定され、
// 背景削除や生成が一律に中断される。未取得ならここで取得する
async function fetchAndSaveComfyObjectInfo(repo){
try{
var response=await comfyuiFetch(comfyUIUrls.objectInfoOnly);
if(!response.ok){
comfyuiLogger.error("ObjectInfo fetch failed: HTTP "+response.status);
return null;
}
var objectInfo=await response.json();
await repo.saveObjectInfo(objectInfo);
comfyuiLogger.info("ObjectInfo fetched on demand: "+Object.keys(objectInfo).length+" nodes");
return Object.keys(objectInfo);
}catch(error){
comfyuiLogger.error("ObjectInfo fetch error: "+(error instanceof Error?error.name+" "+error.message:error));
return null;
}
}

async function checkWorkflowNodeVsComfyUI(workflowClassTypes,repo){
var nodeNames=await repo.getNodeNames();
if(nodeNames.length===0){
nodeNames=await fetchAndSaveComfyObjectInfo(repo);
if(nodeNames===null||nodeNames.length===0){
createToastError(getText("comfyObjectInfoErrorTitle"),getText("comfyObjectInfoErrorMessage"),1000*10);
return false;
}
}
var setB=new Set(nodeNames);
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

async function notExistsWorkflowNodeVsComfyUI(workflowClassType,repo){
var nodeNames=await repo.getNodeNames();
var setB=new Set(nodeNames);
return!setB.has(workflowClassType);
}
