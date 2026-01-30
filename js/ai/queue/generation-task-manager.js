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
await btmSaveProjectFile(currentCanvasGuid,false);
var projectData=btmProjectsMap.get(task.canvasGuid);
if(!projectData||!projectData.blob){
generationTaskLogger.error("Original page data not found:",task.canvasGuid);
return false;
}
try{
await loadLz4BlobProjectFile(projectData.blob,task.canvasGuid);
var targetLayer=null;
if(task.targetLayerGuid){
targetLayer=canvas.getObjects().find(obj=>obj.guid===task.targetLayerGuid);
}
if(task.layerType==='panel'&&targetLayer){
putImageInFrame(fabricImage,task.centerX,task.centerY,true,false,true,targetLayer);
}else if(task.layerType==='clipPath'&&targetLayer){
var oldLayer=canvas.getObjects().find(obj=>obj.guid===task.layerGuid);
if(oldLayer){
oldLayer.saveHistory=false;
canvas.remove(oldLayer);
}
var targetParent=targetLayer;
putImageInFrame(fabricImage,task.centerX,task.centerY,true,false,true,targetParent);
}else if(task.layerType==='standalone'){
var oldLayer=canvas.getObjects().find(obj=>obj.guid===task.layerGuid);
if(oldLayer){
saveInitialState(fabricImage);
fabricImage.set({
left:oldLayer.left,
top:oldLayer.top,
scaleX:oldLayer.scaleX,
scaleY:oldLayer.scaleY
});
oldLayer.saveHistory=false;
canvas.remove(oldLayer);
canvas.add(fabricImage);
}else{
putImageInFrame(fabricImage,task.centerX,task.centerY,true,false,true,null);
}
}else{
putImageInFrame(fabricImage,task.centerX,task.centerY,true,false,true,targetLayer);
}
canvas.renderAll();
saveStateByManual();
await btmSaveProjectFile(task.canvasGuid,false);
var currentProjectData=btmProjectsMap.get(currentCanvasGuid);
if(currentProjectData&&currentProjectData.blob){
await loadLz4BlobProjectFile(currentProjectData.blob,currentCanvasGuid);
}
showGenerationCompleteNotification(task.canvasGuid);
return true;
}catch(error){
generationTaskLogger.error("Error applying image to original page:",error);
var currentProjectData=btmProjectsMap.get(currentCanvasGuid);
if(currentProjectData&&currentProjectData.blob){
await loadLz4BlobProjectFile(currentProjectData.blob,currentCanvasGuid);
}
return false;
}finally{
removeGenerationTask(taskId);
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
