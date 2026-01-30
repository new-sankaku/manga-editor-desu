var generationTaskLogger=new SimpleLogger('generationTask',LogLevel.DEBUG);
var generationTaskMap=new Map();

async function registerGenerationTask(canvasGuid,taskInfo){
if(!btmProjectsMap.has(canvasGuid)){
await btmSaveProjectFile(canvasGuid,false);
}
var info={
canvasGuid:canvasGuid,
layerGuid:taskInfo.layerGuid||null,
layerType:taskInfo.layerType||'unknown',
centerX:taskInfo.centerX||0,
centerY:taskInfo.centerY||0,
targetLayerGuid:taskInfo.targetLayerGuid||null
};
generationTaskMap.set(canvasGuid,info);
generationTaskLogger.debug("registerGenerationTask",canvasGuid,info);
return info;
}

function getGenerationTask(canvasGuid){
return generationTaskMap.get(canvasGuid);
}

function removeGenerationTask(canvasGuid){
generationTaskMap.delete(canvasGuid);
}

function isPageChanged(canvasGuid){
return canvasGuid!==getCanvasGUID();
}

async function applyGeneratedImageToOriginalPage(canvasGuid,fabricImage){
var task=generationTaskMap.get(canvasGuid);
if(!task){
generationTaskLogger.error("Task not found:",canvasGuid);
return false;
}
var projectData=btmProjectsMap.get(canvasGuid);
if(!projectData||!projectData.blob){
generationTaskLogger.error("Original page data not found:",canvasGuid);
return false;
}
try{
var result=await processImageOnOffscreenCanvas(projectData.blob,task,fabricImage);
if(result.success){
btmProjectsMap.set(canvasGuid,{
imageLink:result.previewLink,
blob:result.blob
});
var thumbnail=document.querySelector('.btm-image[data-index="'+canvasGuid+'"]');
if(thumbnail&&result.previewLink){
thumbnail.src=result.previewLink.href;
}
}
return result.success;
}catch(error){
generationTaskLogger.error("Error applying image:",error);
return false;
}finally{
removeGenerationTask(canvasGuid);
}
}

async function processImageOnOffscreenCanvas(lz4Blob,task,fabricImage){
var container=document.createElement('div');
container.style.cssText='position:absolute;left:-9999px;top:-9999px;visibility:hidden;';
var canvasEl=document.createElement('canvas');
container.appendChild(canvasEl);
document.body.appendChild(container);
var offCanvas=new fabric.Canvas(canvasEl,{renderOnAddRemove:false});
try{
var files=await lz4Compressor.unLz4Files(lz4Blob);
var localImageMap=new Map();
var localStateStack=[];
var canvasInfoBuffer=getDataByName(files,"canvas_info.json");
var canvasInfo=canvasInfoBuffer?JSON.parse(ArrayBufferUtils.fromArrayBufferToString(canvasInfoBuffer)):{width:750,height:850};
var basePromptBuffer=getDataByName(files,"text2img_basePrompt.json");
var basePromptData=basePromptBuffer?JSON.parse(ArrayBufferUtils.fromArrayBufferToString(basePromptBuffer)):{};
offCanvas.setWidth(canvasInfo.width);
offCanvas.setHeight(canvasInfo.height);
var sortedFiles=files.sort((a,b)=>{
var numA=a.name.match(/(\d+)/)?parseInt(a.name.match(/(\d+)/)[0]):-1;
var numB=b.name.match(/(\d+)/)?parseInt(b.name.match(/(\d+)/)[0]):-1;
return numA===numB?a.name.localeCompare(b.name):numA-numB;
});
for(var file of sortedFiles){
if(file.name.endsWith(".img")){
localImageMap.set(file.name.split('.')[0],ArrayBufferUtils.fromArrayBufferToString(file.data));
}
}
for(var file of sortedFiles){
if(file.name.endsWith(".json")&&file.name!=="text2img_basePrompt.json"&&file.name!=="canvas_info.json"){
localStateStack.push(JSON.parse(ArrayBufferUtils.fromArrayBufferToString(file.data)));
}
}
if(localStateStack.length===0){
throw new Error("No state found");
}
var lastState=localStateStack[localStateStack.length-1];
var restored=restoreImageLocal(lastState,localImageMap);
await new Promise(resolve=>{
offCanvas.loadFromJSON(restored,function(){
offCanvas.renderAll();
resolve();
});
});
var targetLayer=task.targetLayerGuid?offCanvas.getObjects().find(obj=>obj.guid===task.targetLayerGuid):null;
placeImageLocal(offCanvas,fabricImage,task,targetLayer);
offCanvas.renderAll();
var newState=customToJSONLocal(offCanvas,localImageMap);
localStateStack.push(JSON.stringify(newState));
var previewDataUrl=offCanvas.toDataURL({format:'jpeg',quality:0.8});
var fileBufferList=await generateProjectFileBufferListCore(localStateStack,localImageMap,canvasInfo,basePromptData,previewDataUrl);
var newBlob=await lz4Compressor.buffersToLz4Blob(fileBufferList);
return{success:true,blob:newBlob,previewLink:{href:previewDataUrl}};
}finally{
offCanvas.dispose();
container.remove();
}
}

function restoreImageLocal(jsonOrStr,localImageMap){
var parsed=typeof jsonOrStr==='string'?JSON.parse(jsonOrStr):jsonOrStr;
parsed.objects=parsed.objects.map(obj=>{
if(obj.type==='image'&&localImageMap.has(obj.src)){
obj.src=localImageMap.get(obj.src);
}
if(obj.speechBubbleGrid&&typeof obj.speechBubbleGrid==='string'){
var hash=obj.speechBubbleGrid.replace('GUID:','');
var gridData=localImageMap.get(hash);
if(gridData){
try{obj.speechBubbleGrid=JSON.parse(gridData);}catch(e){obj.speechBubbleGrid=gridData;}
}
}
if(obj.textBaseline==='alphabetical'){
obj.textBaseline='alphabetic';
}
return obj;
});
return parsed;
}

function customToJSONLocal(offCanvas,localImageMap){
var json=offCanvas.toJSON(commonProperties);
json.objects=json.objects.map(obj=>{
if(obj.type==='image'&&obj.src&&typeof obj.src==='string'&&(obj.src.startsWith('data:')||obj.src.startsWith('blob:'))){
var hash=generateHash(obj.src);
if(!localImageMap.has(hash)){
localImageMap.set(hash,obj.src);
}
obj.src=hash;
}
if(obj.speechBubbleGrid&&typeof obj.speechBubbleGrid==='object'){
var gridStr=JSON.stringify(obj.speechBubbleGrid);
var hash=generateHash(gridStr);
if(!localImageMap.has(hash)){
localImageMap.set(hash,gridStr);
}
obj.speechBubbleGrid="GUID:"+hash;
}
return obj;
});
return json;
}

function placeImageLocal(offCanvas,img,task,targetFrame){
offCanvas.add(img);
if(targetFrame){
var frameCenterX=targetFrame.left+(targetFrame.width*targetFrame.scaleX)/2;
var frameCenterY=targetFrame.top+(targetFrame.height*targetFrame.scaleY)/2;
var scaleX=(targetFrame.width*targetFrame.scaleX)/img.width;
var scaleY=(targetFrame.height*targetFrame.scaleY)/img.height;
var scale=Math.max(scaleX,scaleY)*1.05;
img.set({
left:frameCenterX-(img.width*scale)/2,
top:frameCenterY-(img.height*scale)/2,
scaleX:scale,
scaleY:scale
});
if(targetFrame.points){
img.clipPath=new fabric.Polygon(targetFrame.points,{
left:targetFrame.left,
top:targetFrame.top,
scaleX:targetFrame.scaleX,
scaleY:targetFrame.scaleY,
angle:targetFrame.angle||0,
absolutePositioned:true
});
}
if(!targetFrame.guids)targetFrame.guids=[];
var imgGuid=img.guid||generateGUID();
img.guid=imgGuid;
targetFrame.guids.push(imgGuid);
img.relatedPoly=targetFrame;
if(targetFrame.name)img.name=targetFrame.name+" In Image";
}else{
img.set({left:50,top:50,scaleX:0.5,scaleY:0.5});
}
}
