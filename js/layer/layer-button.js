
function putActionButton(container,icon,labelKey,onclick,requiredRole){
if(requiredRole&&hasNotRole(requiredRole)){return;}
var button=document.createElement("button");
button.className="layer-action-btn";
var label=document.createElement("span");
label.setAttribute("data-i18n",labelKey);
label.textContent=i18next.t(labelKey);
button.appendChild(label);
button.onclick=function(e){e.stopPropagation();onclick();};
container.appendChild(button);
}

function putActionBarSeparator(container){
var sep=document.createElement("span");
sep.className="layer-action-sep";
container.appendChild(sep);
}

function putCropImageDownloadButton(buttonsDiv,layer,index) {
var button=document.createElement("button");
button.innerHTML='<i class="material-icons">download</i>';

button.onclick=function (e) {
e.stopPropagation();

imageObject2DataURLByCrop(layer)
.then((croppedDataURL)=>{
if (croppedDataURL) {
link=getLink(croppedDataURL);
link.click();
} else {
layerLogger.warn("No valid activeObject");
}
})
.catch((err)=>{
layerLogger.error("Error cropping image:",err);
});
};

addTooltipByElement(button,"imageCropDownloadButton");
buttonsDiv.appendChild(button);
}


function putRembgButton(buttonsDiv,layer,index) {

if(hasNotRole(AI_ROLES.RemoveBG)){return;}

var button=document.createElement("button");
button.innerHTML='<i class="material-icons">wallpaper</i>';

button.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinner(index);
aiRembg(layer,spinner);
};

addTooltipByElement(button,"rembg");
buttonsDiv.appendChild(button);
}

function putTempButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Temp)){return;}

var button=document.createElement("button");
button.innerHTML='<i class="material-icons">pets</i>';

button.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinner(index);
sdWebUI_RembgProcessQueue(layer,spinner.id);
};

buttonsDiv.appendChild(button);
}



function putImageDownloadButton(buttonsDiv,layer,index) {
var button=document.createElement("button");
button.innerHTML='<i class="material-icons">download</i>';

button.onclick=function (e) {
e.stopPropagation();
dataURL=imageObject2DataURL(layer);
link=getLink(dataURL);
link.click();
};

addTooltipByElement(button,"imageDownloadButton");
buttonsDiv.appendChild(button);
}


function putInterrogateDanbooruButtons(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Image2Prompt_DEEPDOORU)){return;}

var deepDooruButton=document.createElement("button");
deepDooruButton.innerHTML="📦";
deepDooruButton.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinnerSuccess(index);
sdwebuiInterrogate(layer,"deepdanbooru",spinner.id);
};
addTooltipByElement(deepDooruButton,"deepDooruButton");
buttonsDiv.appendChild(deepDooruButton);
}


function putInterrogateClipButtons(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Image2Prompt_CLIP)){return;}

var clipButton=document.createElement("button");
clipButton.innerHTML="📎";

clipButton.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinnerSuccess(index);
sdwebuiInterrogate(layer,"clip",spinner.id);
};
addTooltipByElement(clipButton,"clipButton");

buttonsDiv.appendChild(clipButton);
}


function putPromptButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.PutPrompt)){return;}

var promptButton=document.createElement("button");
promptButton.innerHTML='<i class="material-icons">text_snippet</i>';
promptButton.onclick=function (e) {
e.stopPropagation();
if (layer.tempPrompt) {
layer.text2img_prompt=layer.tempPrompt;
createToast("Apply Prompt",layer.text2img_prompt);
} else {
createToast("Nothing Prompt","");
}
if (layer.tempNegative) {
layer.text2img_negative=layer.tempNegative;
createToast("Apply Negative Prompt",layer.text2img_negative);
} else {
createToast("Nothing Negative Prompt","");
}
};

addTooltipByElement(promptButton,"promptButton");
buttonsDiv.appendChild(promptButton);
}


function putUpscalerButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Upscaler)){return;}

var button=document.createElement("button");
button.innerHTML='<i class="material-icons">photo_size_select_large</i>';
button.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinner(index);
aiUpscale(layer,spinner);
};

addTooltipByElement(button,"upscaleButton");
buttonsDiv.appendChild(button);
}




function visibleChange(obj){
obj.visible=!obj.visible;
updateLayerPanel();
canvas.requestRenderAll();
}

function putViewButton(buttonsDiv,layer,index) {
var viewButton=document.createElement("button");
viewButton.id="viewButton-"+index;
if(layer.visible){
viewButton.innerHTML='<i class="material-icons">visibility</i>';
}else{
viewButton.innerHTML='<i class="material-icons">visibility_off</i>';
}

viewButton.onclick=function (e) {
visibleChange(layer);
};

addTooltipByElement(viewButton,"viewButton");
buttonsDiv.appendChild(viewButton);
}


function putRunI2IButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Text2Image)){return;}

var runButton=document.createElement("button");
runButton.id="runButton-"+index;
runButton.innerHTML='<i class="material-icons">directions_run</i>';
runButton.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinner(index);
I2I(layer,spinner);
};

addTooltipByElement(runButton,"runButton");

buttonsDiv.appendChild(runButton);
}



function putDeleteButton(buttonsDiv,layer,index) {
var deleteButton=document.createElement("button");
deleteButton.textContent="✕";
deleteButton.className="delete-layer-button";
deleteButton.onclick=function (e) {
e.stopPropagation();
removeLayer(layer);
};
addTooltipByElement(deleteButton,"deleteButton");
buttonsDiv.appendChild(deleteButton);
}

function putSeedButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.PutSeed)){return;}

var seedButton=document.createElement("button");
seedButton.innerHTML='<i class="material-icons">recycling</i>';
seedButton.onclick=function (e) {
e.stopPropagation();
if (layer.tempSeed) {
layer.text2img_seed=layer.tempSeed;
createToast("Recycling Seed",layer.text2img_seed);
} else {
createToast("Nothing Seed","");
}
};

addTooltipByElement(seedButton,"seedButton");
buttonsDiv.appendChild(seedButton);
}

function putRunT2IButton(buttonsDiv,layer,index) {
if(hasNotRole(AI_ROLES.Image2Image)){return;}

var runButton=document.createElement("button");
runButton.id="runButton-"+index;
runButton.innerHTML='<i class="material-icons">directions_run</i>';
runButton.onclick=function (e) {
e.stopPropagation();
var spinner=createSpinner(index);
T2I(layer,spinner);
};
addTooltipByElement(runButton,"runButton");
buttonsDiv.appendChild(runButton);
}



var indexAllRunDummy=10000;
function AllRun(){
var objescts=getPanelObjectList();
objescts.forEach(layer=>{
var spinner=createSpinner(indexAllRunDummy);
T2I(layer,spinner);
indexAllRunDummy++;
});
}




function moveLockChange(obj){
obj.selectable=!obj.selectable;
canvas.discardActiveObject();
canvas.renderAll();
updateLayerPanel();
}

function putMoveLockButton(buttonsDiv,layer,index) {
var button=document.createElement("button");
button.id="moveLock-"+index;
if(!layer.selectable){
button.innerHTML='<i class="material-icons">lock</i>';
}else{
button.innerHTML='<i class="material-icons">control_camera</i>';
}

button.onclick=function (e) {
e.stopPropagation();
moveLockChange(layer);
};
addTooltipByElement(button,"moveLockButton");
buttonsDiv.appendChild(button);
}
