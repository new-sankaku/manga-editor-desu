// Fal.aiクラウドAIプロバイダー: Queue APIで非同期実行（T2I/I2I/Upscale/RemoveBG）
class FalAIProvider extends AIProvider{
constructor(){
super('falai','Fal.ai');
this._modelCache=null;
}
getSupportedRoles(){
return[
AI_ROLES.Text2Image,
AI_ROLES.Image2Image,
AI_ROLES.Upscaler,
AI_ROLES.RemoveBG
];
}
needsApiKey(){
return true;
}
getApiKey(){
var el=$('falaiApiKey');
return el?el.value:'';
}
getEndpointUrl(){
return'https://fal.run';
}
_getModelId(role){
var map={
t2i:'falaiModelT2I',
i2i:'falaiModelI2I',
upscale:'falaiModelUpscale',
rembg:'falaiModelRembg'
};
var id=map[role];
if(!id)return'';
var el=$(id);
return el?el.value:'';
}
async fetchModelsIfNeeded(){
var apiKey=this.getApiKey();
if(!apiKey){
this._enableSelects(false);
return;
}
if(this._modelCache){
this._applyCache();
return;
}
return this.fetchModels();
}
async fetchModels(){
var apiKey=this.getApiKey();
if(!apiKey){
this._enableSelects(false);
return;
}
this._showFetchingState();
var queries={
falaiModelT2I:'category=text-to-image&status=active&limit=50',
falaiModelI2I:'category=image-to-image&status=active&limit=50',
falaiModelUpscale:'q=upscale&status=active&limit=50',
falaiModelRembg:'q=background+removal&status=active&limit=50'
};
var headers={
'Authorization':'Key '+apiKey
};
var entries=Object.entries(queries);
var results=await Promise.allSettled(entries.map(function(entry){
return fetch('https://api.fal.ai/v1/models?'+entry[1],{headers:headers}).then(function(r){
if(!r.ok)throw new Error(r.status+'');
return r.json();
});
}));
var categoryFilter={
falaiModelT2I:'text-to-image',
falaiModelI2I:'image-to-image',
falaiModelUpscale:'image-to-image',
falaiModelRembg:'image-to-image'
};
var cache={};
var hasAny=false;
for(var i=0;i<entries.length;i++){
var selectId=entries[i][0];
var result=results[i];
if(result.status==='fulfilled'&&result.value&&result.value.models){
cache[selectId]={models:result.value.models,filter:categoryFilter[selectId]};
this._populateSelect(selectId,result.value.models,categoryFilter[selectId]);
hasAny=true;
}else{
this._populateSelect(selectId,[]);
}
}
if(hasAny)this._modelCache=cache;
}
clearModelCache(){
this._modelCache=null;
}
_showFetchingState(){
var ids=['falaiModelT2I','falaiModelI2I','falaiModelUpscale','falaiModelRembg'];
var msg=i18next.t('falaiFetchingModels');
for(var i=0;i<ids.length;i++){
var el=$(ids[i]);
if(!el)continue;
el.disabled=true;
el.innerHTML='<option value="">'+msg+'</option>';
}
}
_applyCache(){
var keys=Object.keys(this._modelCache);
for(var i=0;i<keys.length;i++){
var selectId=keys[i];
var cached=this._modelCache[selectId];
this._populateSelect(selectId,cached.models,cached.filter);
}
}
_enableSelects(enabled){
var labels={falaiModelT2I:'T2I',falaiModelI2I:'I2I',falaiModelUpscale:'Upscale',falaiModelRembg:'RemoveBG'};
var ids=Object.keys(labels);
for(var i=0;i<ids.length;i++){
var el=$(ids[i]);
if(!el)continue;
el.disabled=!enabled;
if(!enabled){
el.innerHTML='<option value="">'+labels[ids[i]]+'</option>';
}
}
}
_populateSelect(selectId,models,filterCategory){
var el=$(selectId);
if(!el)return;
var prev=el.value;
if(!prev){
var stored=localStorage.getItem('localSettingsData');
if(stored){
var data=JSON.parse(stored);
if(data[selectId])prev=data[selectId];
}
}
el.innerHTML='<option value="">-- select --</option>';
for(var i=0;i<models.length;i++){
var m=models[i];
var cat=m.metadata&&m.metadata.category||'';
if(filterCategory&&cat!==filterCategory)continue;
var opt=document.createElement('option');
opt.value=m.endpoint_id||'';
opt.textContent=m.metadata&&m.metadata.display_name?m.metadata.display_name:m.endpoint_id;
el.appendChild(opt);
}
if(prev){
el.value=prev;
}
el.disabled=false;
el.dispatchEvent(new Event('change'));
}
_authHeaders(){
var apiKey=this.getApiKey();
if(!apiKey)return{};
return{
'Authorization':'Key '+apiKey,
'Content-Type':'application/json'
};
}
async heartbeat(){
var apiKey=this.getApiKey();
if(!apiKey){
this._verifiedApiKey=null;
this._updateLabel(false);
return false;
}
if(this._verifiedApiKey===apiKey){
this._updateLabel(true);
return true;
}
try{
var response=await fetch('https://api.fal.ai/v1/models?limit=1',{
headers:{'Authorization':'Key '+apiKey}
});
if(response.ok){
this._verifiedApiKey=apiKey;
this._updateLabel(true);
return true;
}
this._verifiedApiKey=null;
this._updateLabel(false);
return false;
}catch(e){
this._verifiedApiKey=null;
this._updateLabel(false);
return false;
}
}
_updateLabel(isOn){
var labelfw=$('ExternalService_Heartbeat_Label_fw');
var text=this.name+(isOn?' ON':' OFF');
var color=isOn?'green':'red';
if(labelfw){
labelfw.innerHTML=text;
labelfw.style.color=color;
}
}
async _runSync(modelId,inputData){
var apiKey=this.getApiKey();
if(!apiKey)throw new Error('Fal.ai API Key is not set');
var url='https://fal.run/'+modelId;
var response=await fetch(url,{
method:'POST',
headers:this._authHeaders(),
body:JSON.stringify(inputData)
});
if(!response.ok){
var errorText=await response.text();
var err=new Error('Fal.ai failed: '+response.status+' '+errorText);
try{
var errorJson=JSON.parse(errorText);
if(errorJson.detail)err.detail=errorJson.detail;
}catch(e){}
throw err;
}
return response.json();
}
async _imageUrlToFabric(imageUrl){
var response=await fetch(imageUrl);
if(!response.ok)throw new Error('Image fetch failed: '+response.status);
var blob=await response.blob();
return new Promise((resolve,reject)=>{
var reader=new FileReader();
reader.onload=function(){
fabric.Image.fromURL(reader.result,(img)=>{
if(img)resolve(img);
else reject(new Error('Failed to create fabric.Image'));
});
};
reader.onerror=()=>reject(new Error('FileReader error'));
reader.readAsDataURL(blob);
});
}
async _outputToFabricImage(output){
if(output.images&&output.images.length>0){
var img=output.images[0];
if(img.url)return this._imageUrlToFabric(img.url);
}
if(output.image&&output.image.url){
return this._imageUrlToFabric(output.image.url);
}
throw new Error('Fal.ai returned no images');
}
_registerTask(layer){
var canvasGuid=getCanvasGUID();
var layerType='unknown';
var targetLayerGuid=null;
if(isPanel(layer)){
layerType='panel';
targetLayerGuid=getGUID(layer);
}else if(layer.clipPath){
layerType='clipPath';
targetLayerGuid=layer.relatedPoly?getGUID(layer.relatedPoly):getGUID(layer);
}else{
layerType='standalone';
}
var center=calculateCenter(layer);
registerGenerationTask(canvasGuid,{
layerGuid:getGUID(layer),
layerType:layerType,
centerX:center.centerX,
centerY:center.centerY,
targetLayerGuid:targetLayerGuid
});
return canvasGuid;
}
_placeResult(result,layer,canvasGuid,Type){
if(isPageChanged(canvasGuid)){
return applyGeneratedImageToOriginalPage(canvasGuid,result).then(applied=>{
if(!applied){
removeGenerationTask(canvasGuid);
this._placeOnCanvas(result,layer,Type);
}
});
}
removeGenerationTask(canvasGuid);
this._placeOnCanvas(result,layer,Type);
}
_placeOnCanvas(result,layer,Type){
if(isPanel(layer)){
var c=calculateCenter(layer);
putImageInFrame(result,c.centerX,c.centerY,false,false,true,layer);
}else if(layer.clipPath){
var c=calculateCenter(layer);
var targetParent=layer.relatedPoly||layer;
layer.saveHistory=false;
canvas.remove(layer);
putImageInFrame(result,c.centerX,c.centerY,false,false,true,targetParent);
}else{
layer.saveHistory=false;
canvas.remove(layer);
replaceImageObject(layer,result,Type);
}
}
async _execute(layer,spinnerId,Type,modelId,buildInput){
var canvasGuid=this._registerTask(layer);
var p=falaiQueue.add(async()=>{
setCurrentAiTask(spinnerId);
var inputData=buildInput();
var output=await this._runSync(modelId,inputData);
return this._outputToFabricImage(output);
});
updateAiTaskCancelInfo(spinnerId,{queueName:'falai',queueItemId:p._queueItemId});
return p
.then(async(result)=>{
if(result){
this._placeResult(result,layer,canvasGuid,Type);
}
})
.catch((error)=>{
removeGenerationTask(canvasGuid);
if(error.message==='Queue cancelled'||error.message==='Task cancelled'){
this._logger.debug("Generation cancelled by user");
return;
}
var msg=error.message||'';
var detail=typeof error.detail==='string'?error.detail:JSON.stringify(error.detail||'');
var displayMsg=msg;
if(detail.indexOf('Exhausted balance')!==-1){
displayMsg=i18next.t('falaiBalanceExhausted');
}else if(detail.indexOf('content_policy_violation')!==-1){
displayMsg=i18next.t('falaiContentPolicy');
}
createToastError('Fal.ai',displayMsg,8000);
this._logger.error(Type+' error:',msg);
})
.finally(()=>{
removeSpinner(spinnerId);
});
}
async executeT2I(layer,spinnerId){
var modelId=this._getModelId('t2i');
if(!modelId){
removeSpinner(spinnerId);
createToastError('Fal.ai','T2I model not selected',5000);
return;
}
return this._execute(layer,spinnerId,'T2I',modelId,()=>{
var rd=baseRequestData(layer);
if(basePrompt.text2img_model!=''){
rd['model']=basePrompt.text2img_model;
}
return{
prompt:rd.prompt,
negative_prompt:rd.negative_prompt,
image_size:{width:rd.width,height:rd.height},
num_inference_steps:rd.steps,
guidance_scale:rd.cfg_scale,
seed:rd.seed>0?rd.seed:undefined
};
});
}
async executeI2I(layer,spinnerId){
var modelId=this._getModelId('i2i');
if(!modelId){
removeSpinner(spinnerId);
createToastError('Fal.ai','I2I model not selected',5000);
return;
}
return this._execute(layer,spinnerId,'I2I',modelId,()=>{
var rd=baseRequestData(layer);
var base64Image=imageObject2Base64ImageEffectKeep(layer);
return{
prompt:rd.prompt,
negative_prompt:rd.negative_prompt,
image_url:base64Image,
strength:layer.img2img_denoise||0.75,
image_size:{width:rd.width,height:rd.height},
num_inference_steps:rd.steps,
guidance_scale:rd.cfg_scale,
seed:rd.seed>0?rd.seed:undefined
};
});
}
async executeUpscale(layer,spinnerId){
var modelId=this._getModelId('upscale');
if(!modelId){
removeSpinner(spinnerId);
createToastError('Fal.ai','Upscale model not selected',5000);
return;
}
return this._execute(layer,spinnerId,'Upscaler',modelId,()=>{
var base64Image=imageObject2Base64ImageEffectKeep(layer);
return{
image_url:base64Image
};
});
}
async executeRembg(layer,spinnerId){
var modelId=this._getModelId('rembg');
if(!modelId){
removeSpinner(spinnerId);
createToastError('Fal.ai','RemoveBG model not selected',5000);
return;
}
return this._execute(layer,spinnerId,'Rembg',modelId,()=>{
var base64Image=imageObject2Base64ImageEffectKeep(layer);
return{
image_url:base64Image
};
});
}
}
