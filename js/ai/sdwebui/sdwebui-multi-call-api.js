
function fetchSdAdModels() {
fetch(sdWebUIUrls.adetilerModel,{
method: 'GET',
headers: {
'accept': 'application/json'
}
})
.then(response=>response.json())
.then(data=>{
initTagify(data.ad_model);
})
.catch(error=>{
sdwebuiLogger.error('Error:',error);
createToastError("Fetch Error","APIからデータを取得できませんでした。");
});
}


async function sendClipToServer() {
const dualClip=getSelectedTagifyValues("clipDropdownId");

const data=JSON.stringify({
forge_additional_modules: dualClip
});

fetch(sdWebUIUrls.options,{
method: 'POST',
headers: {
'Accept': 'application/json',
'Content-Type': 'application/json'
},
body: data
})
.then(response=>response.json())
.then(data=>{})
.catch((error)=>{
sdwebuiLogger.error('Error:',error);
createToastError("Fetch Error","Failed to apply the model.");
});
}

async function sendModelToServer() {
const modelValue=basePrompt.text2img_model;
sdwebuiLogger.debug("sendModelToServer",$("basePrompt_model").value);

const data=JSON.stringify({
sd_model_checkpoint: modelValue
});

fetch(sdWebUIUrls.options,{
method: 'POST',
headers: {
'Accept': 'application/json',
'Content-Type': 'application/json'
},
body: data
})
.then(response=>response.json())
.then(data=>{})
.catch((error)=>{
sdwebuiLogger.error('Error:',error);
createToastError("Fetch Error","Failed to apply the model.");
});
}

async function fetchSDOptions() {
try {
const response=await fetch(sdWebUIUrls.options,{
method: 'GET',
headers: {
'Accept': 'application/json'
}
});
if (!response.ok) {
throw new Error(`HTTP error! Status: ${response.status}`);
}
const data=await response.json();
if ('sd_model_checkpoint' in data) {
basePrompt.text2img_model=data.sd_model_checkpoint;
}

if ('forge_additional_modules' in data) {
basePrompt.forge_additional_modules=data.forge_additional_modules.map(path=>{
return path.replace(/\\/g,'/').split('/').pop();
});
}

} catch (error) {
sdwebuiLogger.error('Failed to fetch data:',error);
}
}

async function fetchSdSampler() {
try{
const response=await fetch(sdWebUIUrls.sampler,{method: 'GET'});
const models=await response.json();
updateSamplerDropdown(models);
}catch(error){
sdwebuiLogger.error('fetchSdSampler:',error);
createToastError("Fetch Error","Failed to fetch samplers.");
}
}

async function fetchSdUpscaler() {
try{
const response=await fetch(sdWebUIUrls.upscaler,{method: 'GET'});
const models=await response.json();
updateUpscalerDropdown(models);
}catch(error){
sdwebuiLogger.error('fetchSdUpscaler:',error);
createToastError("Fetch Error","Failed to fetch upscalers.");
}
}

async function fetchSdModels() {
try{
const response=await fetch(sdWebUIUrls.sdModel,{method: 'GET'});
const models=await response.json();
updateModelDropdown(models);
}catch(error){
sdwebuiLogger.error('fetchSdModels:',error);
createToastError("Fetch Error","Failed to fetch models.");
}
}

async function fetchSdModules() {
try{
const response=await fetch(sdWebUIUrls.sdModules,{method: 'GET'});
const rawModels=await response.json();
const results=rawModels.map(model=>({
n: model.model_name,
p: 0
}));

updateTagifyDropdown("clipDropdownId",results,basePrompt.forge_additional_modules);
}catch(error){
sdwebuiLogger.error('fetchSdModules:',error);
createToastError("Fetch Error","Failed to fetch modules.");
}
}

function sdwebuiApiHeartbeat() {
if(!sdWebUIUrls||!sdWebUIUrls.ping){
return Promise.resolve(false);
}

return fetch(sdWebUIUrls.ping,{
method: 'GET',
headers: {'Accept': 'application/json'}
})
.then(function(response){
if (response.ok) {
if(firstSDConnection){
var provider=providerRegistry.get('localSDWebUI');
if(provider){
provider.fetchDiffusionInformation();
}
firstSDConnection=false;
}
return true;
}
return false;
})
.catch(function(){
return false;
});
}


async function sdwebuiInterrogate(layer,model,spinnerId) {
var p=sdQueue.add(async ()=>{
setCurrentAiTask(spinnerId);
let base64Image=imageObject2Base64Image(layer);
const requestBody={
image: base64Image,
model: model
};
const response=await fetch(sdWebUIUrls.interrogate,{
method: 'POST',
headers: {
'Content-Type': 'application/json'
},
body: JSON.stringify(requestBody)
});

if (!response.ok) {
const errorText=await response.text();
createToastError("Interrogate error",errorText);
return null;
}

const result=await response.json();
return result;
});
updateAiTaskCancelInfo(spinnerId,{queueName:'sd',queueItemId:p._queueItemId});
p.then(async (result)=>{
if (result) {
createToast("Interrogate Success. "+model,result.caption);
if (layer.text2img_prompt) {
layer.text2img_prompt=layer.text2img_prompt+", "+result.caption;
} else {
layer.text2img_prompt=result.caption;
}
}
})
.catch(error=>{
var checkSD=getText("checkSD_webUI_Text");
createToastError("Interrogate Error.",checkSD);
})
.finally(()=>{
removeSpinner(spinnerId);
});
}

