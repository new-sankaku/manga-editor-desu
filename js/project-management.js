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

btmSaveProjectFile().then(async ()=>{
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
console.log("error",error);
console.log("error json,",JSON.stringify(error));
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
console.log("unsupported file");
}
}
} catch (error) {
console.error("error:",error);
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

function loadSettingsLocalStrage() {
createToast(
'Settings Load',[
'Canvas Background Color...',
'Api port/host/check...',
'Base Settings...',
'Dpi...',
'Grid, Layer, Controle...',
'Margin From Panel...',
'Knife Space Size...',
'Load Completed!!'
],1500);

const localSettingsData=localStorage.getItem('localSettingsData');

if (localSettingsData) {
const localSettings=JSON.parse(localSettingsData);
var bgColorInputElement=$('bg-color');
bgColorInputElement.value=localSettings.canvasBgColor||"#ffffff";

var event=new Event('input',{'bubbles': true,'cancelable': true});
bgColorInputElement.dispatchEvent(event);

$('view_layers_checkbox').checked=localSettings.view_layers_checkbox ?? true;
$('view_controles_checkbox').checked=localSettings.view_controles_checkbox ?? true;
$('knifePanelSpaceSize').value=localSettings.knifePanelSpaceSize||"20";
$('outputDpi').value=localSettings.canvasDpi||"450";
$('gridSizeInput').value=localSettings.canvasGridLineSize||"10";
$('marginFromPanel').value=localSettings.canvasMarginFromPanel||20;

$('sdWebUIPageUrl').value=localSettings.sdWebUIPageUrl||'http://127.0.0.1:7860';
$('comfyUIPageUrl').value=localSettings.comfyUIPageUrl||'http://127.0.0.1:8188';

$('apiHeartbeatCheckbox').checked=localSettings.apiHeartbeatCheckbox;
svgPagging=localSettings.canvasMarginFromPanel||20;
$('basePrompt_model').value=localSettings.basePrompt_text2img_model||basePrompt.text2img_model;
$('basePrompt_samplingMethod').value=localSettings.basePrompt_text2img_samplingMethod||basePrompt.text2img_samplingMethod;
$('basePrompt_prompt').value=localSettings.basePrompt_text2img_prompt||basePrompt.text2img_prompt;
$('basePrompt_negative').value=localSettings.basePrompt_text2img_negative||basePrompt.text2img_negative;
$('basePrompt_seed').value=localSettings.basePrompt_text2img_seed||basePrompt.text2img_seed;
$('basePrompt_cfg_scale').value=localSettings.basePrompt_text2img_cfg_scale||basePrompt.text2img_cfg_scale;
$('basePrompt_width').value=localSettings.basePrompt_text2img_width||basePrompt.text2img_width;
$('basePrompt_height').value=localSettings.basePrompt_text2img_height||basePrompt.text2img_height;
$('basePrompt_samplingSteps').value=localSettings.basePrompt_text2img_samplingSteps||basePrompt.text2img_samplingSteps;
$('text2img_hr_upscaler').value=localSettings.basePrompt_text2img_hr_upscaler||basePrompt.text2img_hr_upscaler;
$('text2img_hr_scale').value=localSettings.basePrompt_text2img_hr_scale||basePrompt.text2img_hr_scale;
$('text2img_hr_denoise').value=localSettings.basePrompt_text2img_hr_denoise||basePrompt.text2img_hr_denoise;
$('text2img_hr_step').value=localSettings.basePrompt_text2img_hr_step||basePrompt.text2img_hr_step;

$('basePrompt_height').addEventListener('blur',function() {
var value=parseInt(this.value);
if (value!==-1) {
this.value=Math.round(value/8)*8;
}
});
$('basePrompt_width').addEventListener('blur',function() {
var value=parseInt(this.value);
if (value!==-1) {
this.value=Math.round(value/8)*8;
}
});

var nowExternalMode=localSettings.externalAI||apis.COMFYUI;
console.log("nowExternalMode, "+nowExternalMode);
if(nowExternalMode===apis.A1111){
changeExternalAPI($("sdWebUIButton"));
}else{
changeExternalAPI($("comfyUIButton"));
}

basePrompt.text2img_prompt=$('basePrompt_prompt').value;
basePrompt.text2img_negative=$('basePrompt_negative').value;
basePrompt.text2img_model=$('basePrompt_model').value;
basePrompt.text2img_samplingSteps=$('basePrompt_samplingSteps').value;
basePrompt.text2img_samplingMethod=$('basePrompt_samplingMethod').value;
basePrompt.text2img_width=$('basePrompt_width').value;
basePrompt.text2img_height=$('basePrompt_height').value;
basePrompt.text2img_seed=$('basePrompt_seed').value;
basePrompt.text2img_cfg_scale=$('basePrompt_cfg_scale').value;
basePrompt.text2img_hr_upscaler=$('text2img_hr_upscaler').value;
basePrompt.text2img_hr_step=$('text2img_hr_step').value;
basePrompt.text2img_hr_denoise=$('text2img_hr_denoise').value;
basePrompt.text2img_hr_scale=$('text2img_hr_scale').value;
}
}

function saveSettingsLocalStrage() {
createToast('Settings Save',[
'Canvas Background Color...',
'Api port/host/check...',
'Base Settings...',
'Dpi...',
'Grid, Layer, Controle...',
'Margin From Panel...',
'Knife Space Size...',
'Save Completed!!'
],1500);

localSettingsData={
externalAI: apiMode,
view_layers_checkbox: $('view_layers_checkbox').checked,
view_controles_checkbox: $('view_controles_checkbox').checked,

knifePanelSpaceSize: $('knifePanelSpaceSize').value,
canvasBgColor: $('bg-color').value,
canvasDpi: $('outputDpi').value,
canvasGridLineSize: $('gridSizeInput').value,
canvasMarginFromPanel: $('marginFromPanel').value,

sdWebUIPageUrl:$('sdWebUIPageUrl').value,
comfyUIPageUrl:$('comfyUIPageUrl').value,

apiHeartbeatCheckbox : $('apiHeartbeatCheckbox').checked ,
basePrompt_text2img_prompt: basePrompt.text2img_prompt,
basePrompt_text2img_negative: basePrompt.text2img_negative,
basePrompt_text2img_seed: basePrompt.text2img_seed,
basePrompt_text2img_cfg_scale: basePrompt.text2img_cfg_scale,
basePrompt_text2img_width: basePrompt.text2img_width,
basePrompt_text2img_height: basePrompt.text2img_height,
basePrompt_text2img_samplingMethod: basePrompt.text2img_samplingMethod,
basePrompt_text2img_samplingSteps: basePrompt.text2img_samplingSteps,
basePrompt_text2img_scheduler: basePrompt.text2img_scheduler,
basePrompt_text2img_model: basePrompt.text2img_model,
basePrompt_text2img_hr_upscaler: basePrompt.text2img_hr_upscaler,
basePrompt_text2img_hr_scale: basePrompt.text2img_hr_scale,
basePrompt_text2img_hr_step: basePrompt.text2img_hr_step,
basePrompt_text2img_hr_denoise: basePrompt.text2img_hr_denoise
};
localStorage.setItem('localSettingsData',JSON.stringify(localSettingsData));
}

document.addEventListener('DOMContentLoaded',function() {
loadSettingsLocalStrage();
changeView("layer-panel",$('view_layers_checkbox').checked);
changeView("controls",$('view_controles_checkbox').checked);
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