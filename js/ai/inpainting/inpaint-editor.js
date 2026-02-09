// Inpaintエディタ（別キャンバスオーバーレイ）
var inpaintLogger=new SimpleLogger('inpaint',LogLevel.DEBUG);

var InpaintEditor=(function(){
var isOpen=false;
var targetLayer=null;
var originalImageDataUrl=null;
var editorContainer=null;
var imageCanvas=null;
var maskOverlay=null;
var resultImageUrl=null;

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
editorContainer=document.getElementById('inpaint-editor');
if(!editorContainer){
inpaintLogger.error("inpaint-editor element not found");
return;
}
document.getElementById('intro_content').style.display='none';
editorContainer.style.display='flex';
var applyBtn=document.getElementById('inpaint-apply-btn');
var cancelBtn=document.getElementById('inpaint-cancel-btn');
var brushBtn=document.getElementById('inpaint-brush-btn');
var eraserBtn=document.getElementById('inpaint-eraser-btn');
var clearBtn=document.getElementById('inpaint-clear-btn');
var invertBtn=document.getElementById('inpaint-invert-btn');
var generateBtn=document.getElementById('inpaint-generate-btn');
var brushSlider=document.getElementById('inpaint-brush-size');
applyBtn.addEventListener('click',applyResult);
cancelBtn.addEventListener('click',close);
brushBtn.addEventListener('click',function(){setTool('brush');});
eraserBtn.addEventListener('click',function(){setTool('eraser');});
clearBtn.addEventListener('click',clearMask);
invertBtn.addEventListener('click',invertMask);
generateBtn.addEventListener('click',onGenerate);
brushSlider.addEventListener('input',function(e){
InpaintMask.setBrushSize(parseInt(e.target.value));
document.getElementById('inpaint-brush-size-label').textContent=e.target.value;
});
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

function invertMask(){
InpaintMask.invertMask();
}

async function onGenerate(){
if(!InpaintMask.hasMask()){
createToastError("Inpaint",getText("inpaintNoMask")||"Please draw a mask area first");
return;
}
var maskDataUrl=InpaintMask.getMaskAsBlackWhite();
var prompt=document.getElementById('inpaint-prompt').value;
var negative=document.getElementById('inpaint-negative').value;
var denoise=parseFloat(document.getElementById('inpaint-denoise').value);
var generateBtn=document.getElementById('inpaint-generate-btn');
generateBtn.disabled=true;
generateBtn.textContent=getText("generating")||"Generating...";
try{
var result=await InpaintWorkflow.generate(
originalImageDataUrl,
maskDataUrl,
prompt,
negative,
denoise
);
if(result){
resultImageUrl=result;
showPreview(result);
}
}finally{
generateBtn.disabled=false;
generateBtn.textContent=getText("inpaintGenerate")||"Generate";
}
}

function showPreview(imageUrl){
var beforeImg=document.getElementById('inpaint-before-img');
var afterImg=document.getElementById('inpaint-after-img');
var previewArea=document.getElementById('inpaint-preview-area');
beforeImg.src=originalImageDataUrl;
afterImg.src=imageUrl;
previewArea.style.display='flex';
document.getElementById('inpaint-apply-btn').disabled=false;
}

function applyResult(){
if(!resultImageUrl||!targetLayer) return;
fabric.Image.fromURL(resultImageUrl,function(newImg){
if(!newImg) return;
changeDoNotSaveHistory();
var layerRelatedPoly=targetLayer.relatedPoly;
var layerLeft=targetLayer.left;
var layerTop=targetLayer.top;
var layerScaleX=targetLayer.scaleX;
var layerScaleY=targetLayer.scaleY;
targetLayer.saveHistory=false;
canvas.remove(targetLayer);
newImg.set({
left:layerLeft,
top:layerTop,
scaleX:layerScaleX,
scaleY:layerScaleY
});
canvas.add(newImg);
if(layerRelatedPoly){
var center=calculateCenter(newImg);
putImageInFrame(newImg,center.centerX,center.centerY,false,false,true,layerRelatedPoly);
}
changeDoSaveHistory();
saveStateByManual();
canvas.renderAll();
updateLayerPanel();
close();
inpaintLogger.debug("Inpaint result applied");
});
}

function close(){
if(!isOpen) return;
isOpen=false;
InpaintMask.destroy();
if(editorContainer){
editorContainer.style.display='none';
}
document.getElementById('intro_content').style.display='';
var previewArea=document.getElementById('inpaint-preview-area');
if(previewArea) previewArea.style.display='none';
document.getElementById('inpaint-apply-btn').disabled=true;
document.getElementById('inpaint-prompt').value='';
document.getElementById('inpaint-negative').value='';
document.getElementById('inpaint-denoise').value='0.75';
document.getElementById('inpaint-denoise-label').textContent='0.75';
targetLayer=null;
originalImageDataUrl=null;
resultImageUrl=null;
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
