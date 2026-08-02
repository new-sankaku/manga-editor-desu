
let comfyUI=null;
let comfyUIUrls=null;

let sdWebUI=null;
let sdWebUIUrls=null;


document.addEventListener('DOMContentLoaded',()=>{
sdWebUI=new SDWebUIEndpoints();
sdWebUIUrls=sdWebUI.urls;

comfyUI=new ComfyUIEndpoints();
comfyUIUrls=comfyUI.urls;

providerRegistry.register(new LocalComfyUIProvider());
providerRegistry.register(new LocalSDWebUIProvider());
providerRegistry.register(new RunPodComfyUIProvider());
providerRegistry.register(new FalAIProvider());
providerRegistry.register(new GrokProvider());
providerRegistry.register(new OllamaProvider());
providerRegistry.mapApiMode(apis.COMFYUI,'localComfyUI');
providerRegistry.mapApiMode(apis.A1111,'localSDWebUI');
providerRegistry.mapApiMode(apis.RUNPOD_COMFYUI,'runpodComfyUI');
providerRegistry.mapApiMode(apis.FAL_AI,'falai');
providerRegistry.syncFromApiMode(apiMode);

$('runpodComfyUIUrlClear').addEventListener('click',function(event){
event.stopPropagation();
$('runpodComfyUIUrl').value='';
});
$('falaiApiKeyToggle').addEventListener('click',function(event){
event.stopPropagation();
var input=$('falaiApiKey');
input.type=input.type==='password'?'text':'password';
});

var falaiProvider=providerRegistry.get('falai');
$('falaiApiKey').addEventListener('change',function(){
if(!falaiProvider)return;
if(this.value.trim()){
falaiProvider.clearModelCache();
falaiProvider.fetchModels();
}else{
falaiProvider.clearModelCache();
falaiProvider._enableSelects(false);
}
});
$('falaiReloadModels').addEventListener('click',function(event){
event.stopPropagation();
if(!falaiProvider)return;
if($('falaiApiKey').value.trim()){
falaiProvider.fetchModels();
}
});
var falaiSearchUrls={
falaiModelT2I:'https://fal.ai/explore/search?categories=text-to-image',
falaiModelI2I:'https://fal.ai/explore/search?categories=image-to-image',
falaiModelUpscale:'https://fal.ai/explore/search?q=upscale&categories=image-to-image',
falaiModelRembg:'https://fal.ai/explore/search?q=remove+background&categories=image-to-image'
};
var allowedFalaiSelectIds=['falaiModelT2I','falaiModelI2I','falaiModelUpscale','falaiModelRembg'];
document.querySelectorAll('.falai-list-btn').forEach(function(btn){
btn.addEventListener('click',function(event){
event.stopPropagation();
var selectId=btn.getAttribute('data-select');
window.open(falaiSearchUrls[selectId]||'https://fal.ai/explore','_blank');
});
});
document.querySelectorAll('.falai-model-btn').forEach(function(btn){
btn.addEventListener('click',function(event){
event.stopPropagation();
var selectId=btn.getAttribute('data-select');
if(allowedFalaiSelectIds.indexOf(selectId)===-1)return;
var el=$(selectId);
if(el&&el.value){
window.open('https://fal.ai/models/'+el.value.split('/').map(encodeURIComponent).join('/'),'_blank');
}
});
});
function updateFalaiModelBtnVisibility(selectId){
var el=$(selectId);
var btn=document.querySelector('.falai-model-btn[data-select="'+selectId+'"]');
if(!btn)return;
btn.style.display=el&&el.value?'inline-block':'none';
}
allowedFalaiSelectIds.forEach(function(id){
$(id).addEventListener('change',function(){updateFalaiModelBtnVisibility(id);});
updateFalaiModelBtnVisibility(id);
});

var grokProvider=providerRegistry.get('grok');
var ollamaProvider=providerRegistry.get('ollama');
$('grokApiKeyToggle').addEventListener('click',function(event){
event.stopPropagation();
var input=$('grokApiKey');
input.type=input.type==='password'?'text':'password';
});
$('grokApiKey').addEventListener('change',function(){
if(this.value.trim()){
grokProvider.fetchModels();
}else{
grokProvider._populateSelects([]);
}
});
$('grokReloadModels').addEventListener('click',function(event){
event.stopPropagation();
grokProvider.fetchModels();
});
$('ollamaUrlDefaultUrl').addEventListener('click',function(event){
event.stopPropagation();
$('ollamaUrl').value='http://127.0.0.1:11434';
$('ollamaUrl').dispatchEvent(new Event('change'));
});
$('ollamaUrl').addEventListener('change',function(){
if(this.value.trim()){
ollamaProvider.fetchModels();
}else{
ollamaProvider._populateSelects([]);
}
});
$('ollamaReloadModels').addEventListener('click',function(event){
event.stopPropagation();
ollamaProvider.fetchModels();
});
llmFetchModelsIfInUse();

setInterval(apiHeartbeat,1000*15);
$('apiHeartbeatCheckbox').addEventListener('change',function () {
apiHeartbeat();
});
apiHeartbeat();
});
