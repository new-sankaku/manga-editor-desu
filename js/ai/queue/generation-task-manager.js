var generationTaskLogger=new SimpleLogger('generationTask',LogLevel.DEBUG);
var generationTaskMap=new Map();

function registerGenerationTask(taskId,taskInfo){
var canvasGuid=getCanvasGUID();
var info={
canvasGuid:canvasGuid,
layerGuid:taskInfo.layerGuid||null,
layerType:taskInfo.layerType||'unknown',
centerX:taskInfo.centerX||0,
centerY:taskInfo.centerY||0,
targetLayerGuid:taskInfo.targetLayerGuid||null,
createdAt:Date.now()
};
generationTaskMap.set(taskId,info);
generationTaskLogger.debug("registerGenerationTask",taskId,info);
return info;
}

function getGenerationTask(taskId){
return generationTaskMap.get(taskId);
}

function removeGenerationTask(taskId){
generationTaskMap.delete(taskId);
}

function isPageChanged(taskId){
var task=generationTaskMap.get(taskId);
if(!task)return false;
var currentGuid=getCanvasGUID();
return task.canvasGuid!==currentGuid;
}

function getActiveGenerationTasks(){
return Array.from(generationTaskMap.entries());
}

function hasActiveGenerationTasksForPage(canvasGuid){
for(var [taskId,task] of generationTaskMap){
if(task.canvasGuid===canvasGuid){
return true;
}
}
return false;
}

async function applyGeneratedImageToOriginalPage(taskId,fabricImage){
var task=generationTaskMap.get(taskId);
if(!task){
generationTaskLogger.error("Task not found:",taskId);
return false;
}
var currentCanvasGuid=getCanvasGUID();
if(task.canvasGuid===currentCanvasGuid){
generationTaskLogger.debug("Same page, no need for cross-page apply");
return false;
}
generationTaskLogger.debug("Cross-page generation detected. TaskPage:",task.canvasGuid,"CurrentPage:",currentCanvasGuid);
var projectData=btmProjectsMap.get(task.canvasGuid);
if(!projectData||!projectData.blob){
generationTaskLogger.error("Original page data not found:",task.canvasGuid);
return false;
}
try{
var result=await processImageOnOffscreenCanvas(projectData.blob,task,fabricImage);
if(result.success){
btmProjectsMap.set(task.canvasGuid,{
imageLink:result.previewLink,
blob:result.blob
});
btmUpdateThumbnail(task.canvasGuid,result.previewLink);
showGenerationCompleteNotification(task.canvasGuid);
}
return result.success;
}catch(error){
generationTaskLogger.error("Error applying image to original page:",error);
return false;
}finally{
removeGenerationTask(taskId);
}
}

async function processImageOnOffscreenCanvas(lz4Blob,task,fabricImage){
var offscreenContainer=document.createElement('div');
offscreenContainer.style.cssText='position:absolute;left:-9999px;top:-9999px;visibility:hidden;';
var offscreenCanvasEl=document.createElement('canvas');
offscreenCanvasEl.id='offscreen-canvas-'+Date.now();
offscreenContainer.appendChild(offscreenCanvasEl);
document.body.appendChild(offscreenContainer);
var offscreenCanvas=new fabric.Canvas(offscreenCanvasEl,{
renderOnAddRemove:false
});
try{
var files=await lz4Compressor.unLz4Files(lz4Blob);
var localImageMap=new Map();
var localStateStack=[];
var canvasInfoBuffer=getDataByName(files,"canvas_info.json");
var canvasInfoStr=ArrayBufferUtils.fromArrayBufferToString(canvasInfoBuffer);
var canvasInfo=canvasInfoStr?JSON.parse(canvasInfoStr):{width:750,height:850};
offscreenCanvas.setWidth(canvasInfo.width);
offscreenCanvas.setHeight(canvasInfo.height);
var sortedFiles=files.sort((a,b)=>{
var numA=a.name.match(/(\d+)/)?parseInt(a.name.match(/(\d+)/)[0]):-1;
var numB=b.name.match(/(\d+)/)?parseInt(b.name.match(/(\d+)/)[0]):-1;
if(numA===numB){
return a.name.localeCompare(b.name);
}
return numA-numB;
});
for(var file of sortedFiles){
if(file.name.endsWith(".img")){
var imgDataUrlStr=ArrayBufferUtils.fromArrayBufferToString(file.data);
var hash=file.name.split('.')[0];
localImageMap.set(hash,imgDataUrlStr);
}
}
for(var file of sortedFiles){
if(file.name.endsWith(".json")&&
file.name!=="text2img_basePrompt.json"&&
file.name!=="canvas_info.json"){
var jsonStr=ArrayBufferUtils.fromArrayBufferToString(file.data);
localStateStack.push(JSON.parse(jsonStr));
}
}
if(localStateStack.length===0){
throw new Error("No state found in project data");
}
var lastStateJson=localStateStack[localStateStack.length-1];
var restoredState=restoreImageForOffscreen(lastStateJson,localImageMap);
await new Promise((resolve,reject)=>{
offscreenCanvas.loadFromJSON(restoredState,function(){
offscreenCanvas.renderAll();
resolve();
});
});
var targetLayer=null;
if(task.targetLayerGuid){
targetLayer=offscreenCanvas.getObjects().find(obj=>obj.guid===task.targetLayerGuid);
}
placeImageOnOffscreenCanvas(offscreenCanvas,fabricImage,task,targetLayer,localImageMap);
offscreenCanvas.renderAll();
var newState=customToJSONForOffscreen(offscreenCanvas,localImageMap);
localStateStack.push(JSON.stringify(newState));
var newBlob=await generateBlobForOffscreen(localStateStack,localImageMap,canvasInfo,offscreenCanvas);
var previewLink=generatePreviewFromOffscreen(offscreenCanvas);
return{
success:true,
blob:newBlob,
previewLink:previewLink
};
}finally{
offscreenCanvas.dispose();
offscreenContainer.remove();
}
}

function restoreImageForOffscreen(jsonOrStr,localImageMap){
var parsed=typeof jsonOrStr==='string'?JSON.parse(jsonOrStr):jsonOrStr;
parsed.objects=parsed.objects.map(obj=>{
if(obj.type==='image'&&localImageMap.has(obj.src)){
obj.src=localImageMap.get(obj.src);
}
if(obj.speechBubbleGrid&&typeof obj.speechBubbleGrid==='string'){
var hash=obj.speechBubbleGrid.replace('GUID:','');
var gridData=localImageMap.get(hash);
if(gridData){
try{
obj.speechBubbleGrid=JSON.parse(gridData);
}catch(e){
obj.speechBubbleGrid=gridData;
}
}
}
if(obj.textBaseline==='alphabetical'){
obj.textBaseline='alphabetic';
}
return obj;
});
return parsed;
}

function customToJSONForOffscreen(offscreenCanvas,localImageMap){
var json=offscreenCanvas.toJSON(commonProperties);
json.objects=json.objects.map(obj=>{
if(obj.type==='image'&&obj.src&&typeof obj.src==='string'&&
(obj.src.startsWith('data:')||obj.src.startsWith('blob:'))){
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

function placeImageOnOffscreenCanvas(offscreenCanvas,fabricImage,task,targetLayer,localImageMap){
if(task.layerType==='panel'&&targetLayer){
placeInFrameOffscreen(offscreenCanvas,fabricImage,task.centerX,task.centerY,targetLayer);
}else if(task.layerType==='clipPath'&&targetLayer){
var oldLayer=offscreenCanvas.getObjects().find(obj=>obj.guid===task.layerGuid);
if(oldLayer){
offscreenCanvas.remove(oldLayer);
}
placeInFrameOffscreen(offscreenCanvas,fabricImage,task.centerX,task.centerY,targetLayer);
}else if(task.layerType==='standalone'){
var oldLayer=offscreenCanvas.getObjects().find(obj=>obj.guid===task.layerGuid);
if(oldLayer){
fabricImage.set({
left:oldLayer.left,
top:oldLayer.top,
scaleX:oldLayer.scaleX,
scaleY:oldLayer.scaleY
});
offscreenCanvas.remove(oldLayer);
}
offscreenCanvas.add(fabricImage);
}else{
placeInFrameOffscreen(offscreenCanvas,fabricImage,task.centerX,task.centerY,targetLayer);
}
}

function placeInFrameOffscreen(offscreenCanvas,img,x,y,targetFrame){
offscreenCanvas.add(img);
if(targetFrame){
var frameCenterX=targetFrame.left+(targetFrame.width*targetFrame.scaleX)/2;
var frameCenterY=targetFrame.top+(targetFrame.height*targetFrame.scaleY)/2;
var scaleToFitX=(targetFrame.width*targetFrame.scaleX)/img.width;
var scaleToFitY=(targetFrame.height*targetFrame.scaleY)/img.height;
var scaleToFit=Math.max(scaleToFitX,scaleToFitY);
img.set({
left:frameCenterX-(img.width*scaleToFit)/2,
top:frameCenterY-(img.height*scaleToFit)/2,
scaleX:scaleToFit*1.05,
scaleY:scaleToFit*1.05
});
var clipPath=createClipPathFromPoly(targetFrame);
img.clipPath=clipPath;
img.relatedPoly=targetFrame;
if(!targetFrame.guids){
targetFrame.guids=[];
}
var imgGuid=img.guid||generateGUID();
img.guid=imgGuid;
targetFrame.guids.push(imgGuid);
if(targetFrame.name){
img.name=targetFrame.name+" In Image";
}
}else{
var scaleToCanvasWidth=300/img.width;
var scaleToCanvasHeight=300/img.height;
var scaleToCanvas=Math.min(scaleToCanvasWidth,scaleToCanvasHeight);
img.set({
left:50,
top:50,
scaleX:scaleToCanvas,
scaleY:scaleToCanvas
});
}
}

function createClipPathFromPoly(poly){
if(!poly.points)return null;
var clipPath=new fabric.Polygon(poly.points,{
left:poly.left,
top:poly.top,
scaleX:poly.scaleX,
scaleY:poly.scaleY,
angle:poly.angle||0,
absolutePositioned:true,
objectCaching:false
});
return clipPath;
}

async function generateBlobForOffscreen(localStateStack,localImageMap,canvasInfo,offscreenCanvas){
var fileBufferList=[];
for(var i=0;i<localStateStack.length;i++){
var stateStr=typeof localStateStack[i]==='string'?localStateStack[i]:JSON.stringify(localStateStack[i]);
var buffer=await ArrayBufferUtils.toArrayBuffer(stateStr);
var paddedIndex=String(i).padStart(6,'0');
lz4Compressor.putDataListByArrayBuffer(fileBufferList,'state_'+paddedIndex+'.json',buffer);
}
for(var [hash,value] of localImageMap){
var buffer=await ArrayBufferUtils.toArrayBuffer(value);
lz4Compressor.putDataListByArrayBuffer(fileBufferList,hash+'.img',buffer);
}
var canvasInfoBuffer=await ArrayBufferUtils.toArrayBuffer(JSON.stringify(canvasInfo));
lz4Compressor.putDataListByArrayBuffer(fileBufferList,'canvas_info.json',canvasInfoBuffer);
var previewDataUrl=offscreenCanvas.toDataURL({format:'jpeg',quality:0.8});
var previewBuffer=await ArrayBufferUtils.toArrayBuffer(previewDataUrl);
lz4Compressor.putDataListByArrayBuffer(fileBufferList,'preview-image.jpeg',previewBuffer);
var lz4Blob=await lz4Compressor.buffersToLz4Blob(fileBufferList);
return lz4Blob;
}

function generatePreviewFromOffscreen(offscreenCanvas){
var dataUrl=offscreenCanvas.toDataURL({format:'jpeg',quality:0.8});
return{href:dataUrl};
}

function btmUpdateThumbnail(canvasGuid,previewLink){
var thumbnail=document.querySelector('.btm-image[data-index="'+canvasGuid+'"]');
if(thumbnail&&previewLink&&previewLink.href){
thumbnail.src=previewLink.href;
}
}

function showGenerationCompleteNotification(originalCanvasGuid){
var pageIndex=btmGetGuidIndex(originalCanvasGuid);
var pageNum=pageIndex>=0?pageIndex+1:'?';
var message=getText("generationCompletedOnOtherPage")||"Page "+pageNum+" generation completed";
message=message.replace("{page}",pageNum);
createToast(message,"",3000);
highlightPageThumbnail(originalCanvasGuid);
}

function highlightPageThumbnail(canvasGuid){
var thumbnail=document.querySelector('.btm-image[data-index="'+canvasGuid+'"]');
if(thumbnail){
thumbnail.classList.add('btm-generation-complete');
setTimeout(function(){
thumbnail.classList.remove('btm-generation-complete');
},3000);
}
}

function generateTaskId(){
return 'task_'+Date.now()+'_'+Math.random().toString(36).substr(2,9);
}
