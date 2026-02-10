// アングル変更エディタ（モーダルオーバーレイ）
var angleLogger=new SimpleLogger('angle',LogLevel.DEBUG);

var AngleEditor=(function(){
var isOpen=false;
var modal=null;
var cameraWidget=null;

function open(layer){
if(isOpen) return;
if(!layer||!isImage(layer)){
angleLogger.error("Invalid layer for angle");
return;
}
isOpen=true;
buildUI(layer);
loadImage(layer);
angleLogger.debug("Angle editor opened");
}

function buildUI(layer){
modal=document.getElementById('angle-modal');
if(!modal){
angleLogger.error("angle-modal element not found");
return;
}
modal.style.display='flex';
var cancelBtn=document.getElementById('angle-cancel-btn');
var generateBtn=document.getElementById('angle-generate-btn');
cancelBtn.onclick=close;
generateBtn.onclick=function(){onGenerate(layer);};
initCameraWidget();
}

function initCameraWidget(){
var container=document.getElementById('angle-camera-widget-container');
var promptDisplay=document.getElementById('angle-camera-prompt-display');
var resetBtn=document.getElementById('angle-camera-reset-btn');
if(!container) return;
container.innerHTML='';
try{
cameraWidget=new CameraWidget(container,{
promptEl:promptDisplay,
resetBtn:resetBtn,
onChange:function(prompt){
var textarea=document.getElementById('angle-prompt');
if(textarea) textarea.value=prompt;
}
});
}catch(e){
angleLogger.error("CameraWidget creation failed:",e);
}
}

function loadImage(layer){
var dataUrl=imageObject2Base64ImageEffectKeep(layer);
var imgEl=document.getElementById('angle-original-img');
if(imgEl){
imgEl.src=dataUrl;
}
if(cameraWidget){
cameraWidget.updateImage(dataUrl);
}
}

function onGenerate(layer){
var anglePrompt=document.getElementById('angle-prompt').value;
if(!anglePrompt||!anglePrompt.trim()){
createToastError("Angle",getText("angleNoPrompt")||"Please enter an angle prompt");
return;
}
close();
var spinner=createSpinner(100000);
AngleGenerate(layer,spinner,anglePrompt);
}

function close(){
if(!isOpen) return;
isOpen=false;
if(cameraWidget){
cameraWidget.destroy();
cameraWidget=null;
}
if(modal){
modal.style.display='none';
}
document.getElementById('angle-prompt').value='';
angleLogger.debug("Angle editor closed");
}

function getIsOpen(){
return isOpen;
}

return{
open:open,
close:close,
isOpen:getIsOpen
};
})();

function openAngleEditor(layer){
AngleEditor.open(layer);
}
