// Inpaintエディタ（モーダルオーバーレイ）
var inpaintLogger=new SimpleLogger('inpaint',LogLevel.DEBUG);

var InpaintEditor=(function(){
var isOpen=false;
var targetLayer=null;
var originalImageDataUrl=null;
var modal=null;
var imageCanvas=null;
var maskOverlay=null;

function open(layer){
if(isOpen) return;
if(!layer||!isImage(layer)){
inpaintLogger.error("Invalid layer for inpaint");
return;
}
targetLayer=layer;
originalImageDataUrl=imageObject2Base64ImageEffectKeep(layer);
isOpen=true;
buildUI();
loadImage();
inpaintLogger.debug("Inpaint editor opened");
}

function buildUI(){
modal=document.getElementById('inpaint-modal');
if(!modal){
inpaintLogger.error("inpaint-modal element not found");
return;
}
modal.style.display='flex';
var cancelBtn=document.getElementById('inpaint-cancel-btn');
var brushBtn=document.getElementById('inpaint-brush-btn');
var eraserBtn=document.getElementById('inpaint-eraser-btn');
var clearBtn=document.getElementById('inpaint-clear-btn');
var fillAllBtn=document.getElementById('inpaint-fillall-btn');
var generateBtn=document.getElementById('inpaint-generate-btn');
var brushSlider=document.getElementById('inpaint-brush-size');
cancelBtn.onclick=close;
brushBtn.onclick=function(){setTool('brush');};
eraserBtn.onclick=function(){setTool('eraser');};
clearBtn.onclick=clearMask;
fillAllBtn.onclick=fillAllMask;
generateBtn.onclick=onGenerate;
brushSlider.oninput=function(e){
InpaintMask.setBrushSize(parseInt(e.target.value));
document.getElementById('inpaint-brush-size-label').textContent=e.target.value;
};
setTool('brush');
}

function loadImage(){
var canvasArea=document.getElementById('inpaint-canvas-area');
imageCanvas=document.getElementById('inpaint-image-canvas');
maskOverlay=document.getElementById('inpaint-mask-canvas');
var img=new Image();
img.onload=function(){
var maxW=canvasArea.clientWidth-20;
var maxH=canvasArea.clientHeight-20;
var scale=Math.min(maxW/img.width,maxH/img.height,1);
var w=Math.floor(img.width*scale);
var h=Math.floor(img.height*scale);
imageCanvas.width=img.width;
imageCanvas.height=img.height;
imageCanvas.style.width=w+'px';
imageCanvas.style.height=h+'px';
maskOverlay.width=img.width;
maskOverlay.height=img.height;
maskOverlay.style.width=w+'px';
maskOverlay.style.height=h+'px';
var ctx=imageCanvas.getContext('2d');
ctx.drawImage(img,0,0);
InpaintMask.init(maskOverlay);
};
img.src=originalImageDataUrl;
}

function setTool(tool){
InpaintMask.setMode(tool);
var brushBtn=document.getElementById('inpaint-brush-btn');
var eraserBtn=document.getElementById('inpaint-eraser-btn');
brushBtn.classList.toggle('inpaint-tool-active',tool==='brush');
eraserBtn.classList.toggle('inpaint-tool-active',tool==='eraser');
}

function clearMask(){
InpaintMask.clearMask();
}

function fillAllMask(){
InpaintMask.fillAll();
}

function onGenerate(){
if(!InpaintMask.hasMask()){
createToastError("Inpaint",getText("inpaintNoMask")||"Please draw a mask area first");
return;
}
var maskDataUrl=InpaintMask.getMaskAsBlackWhite();
var prompt=document.getElementById('inpaint-prompt').value;
var negative=document.getElementById('inpaint-negative').value;
var denoise=parseFloat(document.getElementById('inpaint-denoise').value);
var imageDataUrl=originalImageDataUrl;
var layer=targetLayer;
close();
var spinner=createSpinner(canvasMenuIndex);
var spinnerId=spinner.id;
var startTime=Date.now();
InpaintWorkflow.generate(imageDataUrl,maskDataUrl,prompt,negative,denoise)
.then(function(result){
if(!result) return;
return new Promise(function(resolve,reject){
fabric.Image.fromURL(result,function(img){
if(img) resolve(img);
else reject(new Error("Failed to create fabric.Image"));
});
});
})
.then(function(newImg){
if(!newImg) return;
DashboardUI.recordGeneration('Inpaint',Date.now()-startTime,prompt);
if(layer.clipPath){
var center=calculateCenter(layer);
var targetParent=layer.relatedPoly||layer;
layer.saveHistory=false;
canvas.remove(layer);
putImageInFrame(newImg,center.centerX,center.centerY,false,false,true,targetParent);
}else{
layer.saveHistory=false;
canvas.remove(layer);
replaceImageObject(layer,newImg,'I2I');
}
inpaintLogger.debug("Inpaint result applied");
})
.catch(function(error){
var help=getText("comfyUI_workflowErrorHelp");
createToastError("Inpaint Error",[error.message,help],8000);
inpaintLogger.error("Inpaint error:",error);
})
.finally(function(){
removeSpinner(spinnerId);
});
}

function close(){
if(!isOpen) return;
isOpen=false;
InpaintMask.destroy();
if(modal){
modal.style.display='none';
}
document.getElementById('inpaint-prompt').value='';
document.getElementById('inpaint-negative').value='';
document.getElementById('inpaint-denoise').value='0.75';
document.getElementById('inpaint-denoise-label').textContent='0.75';
targetLayer=null;
originalImageDataUrl=null;
inpaintLogger.debug("Inpaint editor closed");
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

function openInpaintEditor(layer){
InpaintEditor.open(layer);
}
