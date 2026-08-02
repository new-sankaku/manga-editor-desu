// AI進捗表示（レイヤー上インジケータ、キャンセル）

var aiProgressState={
currentPromptId:null,
currentTaskId:null,
onStepProgress:null
};

function createSpinner(layerGuid,taskType){
return registerAiTask(layerGuid,taskType);
}

function createSpinnerSuccess(layerGuid,taskType){
return registerAiTask(layerGuid,taskType);
}

function removeSpinner(taskId){
removeAiTask(taskId);
if(aiProgressState.currentTaskId===taskId){
aiProgressState.currentPromptId=null;
aiProgressState.currentTaskId=null;
}
}

function setCurrentAiTask(taskId){
aiProgressState.currentTaskId=taskId;
updateAiTaskStatus(taskId,'running');
}

function updateAiStepProgress(value,max,promptId){
aiProgressState.currentPromptId=promptId;
if(aiProgressState.currentTaskId){
updateAiTaskProgress(aiProgressState.currentTaskId,value,max);
}
if(aiProgressState.onStepProgress){
aiProgressState.onStepProgress(value,max);
}
}

function resetAiStepProgress(){
if(aiProgressState.currentTaskId){
updateAiTaskProgress(aiProgressState.currentTaskId,0,0);
}
aiProgressState.currentPromptId=null;
aiProgressState.currentTaskId=null;
}

function _getQueueByName(name){
if(name==='comfyui'&&typeof comfyuiQueue!=='undefined')return comfyuiQueue;
if(name==='sd'&&typeof sdQueue!=='undefined')return sdQueue;
if(name==='falai'&&typeof falaiQueue!=='undefined')return falaiQueue;
if(name==='grok'&&typeof grokQueue!=='undefined')return grokQueue;
if(name==='ollama'&&typeof ollamaQueue!=='undefined')return ollamaQueue;
return null;
}

function cancelAiTask(taskId){
spinnerLogger.debug("cancelAiTask:"+taskId);
var task=getAiTask(taskId);
if(!task){
spinnerLogger.debug("cancelAiTask: task not found, removing spinner only");
removeAiTask(taskId);
return;
}

var queue=task.queueName?_getQueueByName(task.queueName):null;

if(task.status==='waiting'&&queue&&task.queueItemId){
queue.removeItem(task.queueItemId);
}else if(task.status==='running'){
if(task.queueName==='comfyui'||task.queueName===undefined){
var pid=task.promptId||aiProgressState.currentPromptId;
if(pid&&typeof comfyuiCancelPrompt==='function'){
comfyuiCancelPrompt(pid);
}
}
}

removeAiTask(taskId);
if(aiProgressState.currentTaskId===taskId){
aiProgressState.currentPromptId=null;
aiProgressState.currentTaskId=null;
}
}

function updateAiProgressDisplay(){
}

function renderAiTaskIndicators(detailsDiv,layerGuid){
var currentCanvasGuid=getCanvasGUID();
var tasks=getAiTasksForLayer(layerGuid,currentCanvasGuid);
if(tasks.length===0)return;
var container=document.createElement('div');
container.className='ai-task-indicators';
for(var i=0;i<tasks.length;i++){
var task=tasks[i];
var indicator=document.createElement('div');
indicator.className='ai-task-indicator';
indicator.setAttribute('data-ai-task-id',task.taskId);
if(task.status==='running'){
indicator.classList.add('ai-task-running');
}else{
indicator.classList.add('ai-task-waiting');
}
var dot=document.createElement('span');
dot.className='ai-task-dot';
indicator.appendChild(dot);
var text=document.createElement('span');
text.className='ai-task-text';
var label=task.order+'. '+task.taskType;
if(task.status==='running'&&task.stepMax>0){
label+=' '+task.stepValue+'/'+task.stepMax;
}
text.textContent=label;
indicator.appendChild(text);
var cancelBtn=document.createElement('span');
cancelBtn.className='ai-task-cancel';
cancelBtn.textContent='\u2715';
cancelBtn.title=getText('aiCancelTask');
cancelBtn.setAttribute('data-task-id',task.taskId);
cancelBtn.onclick=function(e){
e.stopPropagation();
var tid=this.getAttribute('data-task-id');
cancelAiTask(tid);
};
indicator.appendChild(cancelBtn);
container.appendChild(indicator);
}
detailsDiv.appendChild(container);
}
