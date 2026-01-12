// Available api models
const apis={
A1111: "A1111",
COMFYUI: "comfyui"
};


const getDataByName=(files,fileName)=>{
const file=files.find(file=>file.name===fileName);
return file ? file.data : null;
};



// Variable to keep track of selected api model to use
var apiMode=apis.A1111;

document.addEventListener("DOMContentLoaded",function () {
var settingsSave=$("settingsSave");
var settingsLoad=$("settingsLoad");
settingsSave.addEventListener("click",function () {saveSettingsLocalStrage();});
settingsLoad.addEventListener("click",function () {loadSettingsLocalStrage();});

var saveButton=$("projectSave");
var loadButton=$("projectLoad");

saveButton.addEventListener("click",async function () {
if (stateStack.length===0) {
createToast("Save Error","Not Found.");
return;
}

const loading=OP_showLoading({icon: 'process',step: 'Step1',substep: 'Save Project',progress: 0});

btmSaveProjectFile(null,false).then(async ()=>{
OP_updateLoadingState(loading,{icon: 'process',step: 'Step2',substep: 'Process 1',progress: 20});

const lz4BlobList=Array.from(btmProjectsMap.values()).map(data=>data.blob);
let mergeLz4Blob=await lz4Compressor.mergeLz4Blobs(lz4BlobList);

OP_updateLoadingState(loading,{icon: 'process',step: 'Step3',substep: 'Process 2',progress: 20});

var url=window.URL.createObjectURL(mergeLz4Blob);
var a=document.createElement("a");
a.href=url;
a.download="DESU-Project.lz4";

document.body.appendChild(a);
a.click();
document.body.removeChild(a);
window.URL.revokeObjectURL(url);
})
.catch((error)=>{
projectLogger.error("error",error);
projectLogger.error("error json,",JSON.stringify(error));
})
.finally(()=>{
OP_hideLoading(loading);
});
});



loadButton.addEventListener("click",function () {
var fileInput=document.createElement("input");
fileInput.type="file";
fileInput.style.display="none";
document.body.appendChild(fileInput);
fileInput.click();

fileInput.onchange=async function () {
const loading=OP_showLoading({icon: 'process',step: 'Step1',substep: 'Load Project',progress: 0});

try {
var file=this.files[0];
if (file) {
const fileBuffer=await file.arrayBuffer();
const fileName=file.name.toLowerCase();
const isZip=fileName.endsWith('.zip');
const isLz4=fileName.endsWith('.lz4');

if (isZip) {
OP_updateLoadingState(loading,{icon: 'process',step: 'Step2',substep: 'UnZip',progress: 20});

const zip=await JSZip.loadAsync(file);
var hasNestedZip=false;
var fileCount=0;

zip.forEach(function (relativePath,zipEntry) {
fileCount++;
OP_updateLoadingState(loading,{icon: 'process',step: 'Step3',substep: 'UnZip file:'+fileCount,progress: 30});
if (zipEntry.name.toLowerCase().endsWith('.zip')) {
hasNestedZip=true;
}
});

if (hasNestedZip) {
OP_updateLoadingState(loading,{icon: 'process',step: 'Step4',substep: 'UnZip:',progress: 40});
await processZip(zip);
document.body.removeChild(fileInput);
} else {
OP_updateLoadingState(loading,{icon: 'process',step: 'Step4',substep: 'UnZip:',progress: 40});
await multiLoadZip(zip);
}
} else if (isLz4) {
//fileList is {name, data}
OP_updateLoadingState(loading,{icon: 'process',step: 'Step2',substep: 'UnLz4',progress: 20});
let bufferFileLz4List=await lz4Compressor.unLz4FilesByBuffer(fileBuffer);

OP_updateLoadingState(loading,{icon: 'process',step: 'Step3',substep: 'UnLz4',progress: 25});
await multiLoadLz4(bufferFileLz4List);

OP_updateLoadingState(loading,{icon: 'process',step: 'Step4',substep: 'UnLz4',progress: 85});
} else {
let title=getText("unsupportedProjectFileFormat");
let message=getText("unsupportedProjectFileFormatMessage");
createToastError(title,message,4000);
}
}
} catch (error) {
projectLogger.error("error:",error);
} finally {
OP_hideLoading(loading);
}
};
});
});


function findCanvasGuid(obj) {
if (typeof obj==='string') {
try {
obj=JSON.parse(obj);
} catch (error) {
return null;
}
}
if (typeof obj!=='object'||obj===null) {
return null;
}

if (obj.canvasGuid) {
return obj.canvasGuid;
}

for (let key in obj) {
if (typeof obj[key]==='object') {
const result=findCanvasGuid(obj[key]);
if (result) return result;
}
}
return null;
}

var localSettingsData=null;

function toggleSettingsHighlight(enable){
var flag=(enable!==undefined)?enable:!DEBUG_FLAGS.settingsHighlight;
DEBUG_FLAGS.settingsHighlight=flag;
var styleId='settings-highlight-style';
var existingStyle=$(styleId);
if(flag){
if(!existingStyle){
var style=document.createElement('style');
style.id=styleId;
style.textContent='.settings-highlight{outline:3px solid #ff6b00 !important;box-shadow:0 0 10px #ff6b00 !important;animation:settings-pulse 1s ease-in-out infinite !important;}@keyframes settings-pulse{0%,100%{outline-color:#ff6b00;box-shadow:0 0 10px #ff6b00;}50%{outline-color:#ffaa00;box-shadow:0 0 20px #ffaa00;}}';
document.head.appendChild(style);
}
applyHighlightClass(true);
projectLogger.debug('Settings highlight: ON');
}else{
if(existingStyle)existingStyle.remove();
applyHighlightClass(false);
projectLogger.debug('Settings highlight: OFF');
}
return flag;
}

function applyHighlightClass(add){
var allIds=[];
Object.values(SETTINGS_SCHEMA).forEach(function(cfg){if(cfg.id)allIds.push(cfg.id);});
Object.values(BASEPROMPT_SCHEMA).forEach(function(cfg){if(cfg.id)allIds.push(cfg.id);});
allIds.forEach(function(id){
var el=$(id);
if(el){
if(add)el.classList.add('settings-highlight');
else el.classList.remove('settings-highlight');
}
});
}

var SETTINGS_SCHEMA={
view_layers_checkbox:{id:'view_layers_checkbox',default:true,type:'checkbox'},
view_controles_checkbox:{id:'view_controles_checkbox',default:true,type:'checkbox'},
knifePanelSpaceSize:{id:'knifePanelSpaceSize',default:'20'},
canvasBgColor:{id:'bg-color',default:'#ffffff'},
canvasDpi:{id:'outputDpi',default:'450'},
canvasGridLineSize:{id:'gridSizeInput',default:'10'},
canvasMarginFromPanel:{id:'marginFromPanel',default:20},
sdWebUIPageUrl:{id:'sdWebUIPageUrl',default:'http://127.0.0.1:7860'},
comfyUIPageUrl:{id:'comfyUIPageUrl',default:'http://127.0.0.1:8188'},
apiHeartbeatCheckbox:{id:'apiHeartbeatCheckbox',default:true,type:'checkbox'}
};

var BASEPROMPT_SCHEMA={
basePrompt_text2img_prompt:{id:'basePrompt_prompt',key:'text2img_prompt'},
basePrompt_text2img_negative:{id:'basePrompt_negative',key:'text2img_negative'},
basePrompt_text2img_seed:{id:'basePrompt_seed',key:'text2img_seed'},
basePrompt_text2img_cfg_scale:{id:'basePrompt_cfg_scale',key:'text2img_cfg_scale'},
basePrompt_text2img_width:{id:'basePrompt_width',key:'text2img_width'},
basePrompt_text2img_height:{id:'basePrompt_height',key:'text2img_height'},
basePrompt_text2img_samplingMethod:{id:'basePrompt_samplingMethod',key:'text2img_samplingMethod'},
basePrompt_text2img_samplingSteps:{id:'basePrompt_samplingSteps',key:'text2img_samplingSteps'},
basePrompt_text2img_scheduler:{id:null,key:'text2img_scheduler'},
basePrompt_text2img_model:{id:'basePrompt_model',key:'text2img_model'},
basePrompt_text2img_hr_upscaler:{id:'text2img_hr_upscaler',key:'text2img_hr_upscaler'},
basePrompt_text2img_hr_scale:{id:'text2img_hr_scale',key:'text2img_hr_scale'},
basePrompt_text2img_hr_step:{id:'text2img_hr_step',key:'text2img_hr_step'},
basePrompt_text2img_hr_denoise:{id:'text2img_hr_denoise',key:'text2img_hr_denoise'}
};

function loadSettingsLocalStrage(){
createToast('Settings Load',['Loading settings...','Load Completed!!'],1500);
var stored=localStorage.getItem('localSettingsData');
if(!stored)return;
var data=JSON.parse(stored);
Object.keys(SETTINGS_SCHEMA).forEach(function(key){
var cfg=SETTINGS_SCHEMA[key];
var el=$(cfg.id);
if(!el)return;
var val=(data[key]!==undefined)?data[key]:cfg.default;
if(cfg.type==='checkbox')el.checked=val;
else el.value=val;
});
var bgEl=$('bg-color');
bgEl.dispatchEvent(new Event('input',{bubbles:true,cancelable:true}));
svgPagging=data.canvasMarginFromPanel||20;
Object.keys(BASEPROMPT_SCHEMA).forEach(function(key){
var cfg=BASEPROMPT_SCHEMA[key];
var val=(data[key]!==undefined)?data[key]:basePrompt[cfg.key];
if(cfg.id){
var el=$(cfg.id);
if(el)el.value=val;
}
basePrompt[cfg.key]=val;
});
['basePrompt_height','basePrompt_width'].forEach(function(elId){
$(elId).addEventListener('blur',function(){
var v=parseInt(this.value);
if(v!==-1)this.value=Math.round(v/8)*8;
});
});
var mode=data.externalAI||apis.COMFYUI;
if(mode===apis.A1111)changeExternalAPI($('sdWebUIButton'));
else changeExternalAPI($('comfyUIButton'));
}

function saveSettingsLocalStrage(){
createToast('Settings Save',['Saving settings...','Save Completed!!'],1500);
var data={externalAI:apiMode};
Object.keys(SETTINGS_SCHEMA).forEach(function(key){
var cfg=SETTINGS_SCHEMA[key];
var el=$(cfg.id);
if(!el)return;
data[key]=(cfg.type==='checkbox')?el.checked:el.value;
});
Object.keys(BASEPROMPT_SCHEMA).forEach(function(key){
var cfg=BASEPROMPT_SCHEMA[key];
data[key]=basePrompt[cfg.key];
});
localStorage.setItem('localSettingsData',JSON.stringify(data));
}

document.addEventListener('DOMContentLoaded',function() {
loadSettingsLocalStrage();
changeView("layer-panel",$('view_layers_checkbox').checked);
changeView("controls",$('view_controles_checkbox').checked);
if(DEBUG_FLAGS.settingsHighlight)toggleSettingsHighlight(true);
});

document.addEventListener('DOMContentLoaded',function() {
$('svgDownload').onclick=function () {
var svg=canvas.toSVG();
svgDownload('canvas.svg',svg);
};
});


function svgDownload(filename,content) {
var element=document.createElement('a');
element.setAttribute('href','data:image/svg+xml;charset=utf-8,'+encodeURIComponent(content));
element.setAttribute('download',filename);
element.style.display='none';
document.body.appendChild(element);
element.click();
document.body.removeChild(element);
}