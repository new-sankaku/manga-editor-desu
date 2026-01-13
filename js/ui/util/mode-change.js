// mode-change.js - グローバル変数、ダークモード切替、cropモードUI

var nowMode="";

var isKnifeDrawing=false;
var isKnifeMode=false;

const MODE_PEN_PENCIL='Pencil';
const MODE_PEN_OUTLINE='OutlinePen';
const MODE_PEN_CIRCLE='Circle';
const MODE_PEN_SQUARE='Square';
const MODE_PEN_TEXTURE='Texture';
const MODE_PEN_CRAYON='Crayon';
const MODE_PEN_INK='Ink';
const MODE_PEN_MARKER='Marker';
const MODE_PEN_ERASER='Eraser';
const MODE_PEN_HLINE='Hline';
const MODE_PEN_VLINE='Vline';
const MODE_PEN_MOSAIC='Mosaic';

var isMosaicBrushActive=false;
var cropFrame;
var cropActiveObject;
let nowPencil="";

function toggleMode() {
const isDarkMode=document.body.classList.toggle('dark-mode');
const logo=$('navbar-logo');

document.body.classList.remove('light-mode');
document.body.classList.add('dark-mode');
localStorage.setItem('mode','dark-mode');
logo.src='02_images_svg/Logo/black_mode_logo.webp';

updateLayerPanel();
}

document.addEventListener('DOMContentLoaded',function() {
$('mode-toggle').addEventListener('change',toggleMode);
});

function initializeMode() {
const mode='dark-mode';
document.body.classList.add(mode);
const logo=$('navbar-logo');
if (mode==='dark-mode') {
$('mode-toggle').checked=true;
logo.src='02_images_svg/Logo/black_mode_logo.webp';
} else {
logo.src='02_images_svg/Logo/light_mode_logo.webp';
}
}

document.addEventListener('DOMContentLoaded',function() {
initializeMode();
});

function getCssValue(key){
var currentModeElement=document.body;
var rootStyles=getComputedStyle(currentModeElement);
return rootStyles.getPropertyValue(key).trim();
}

document.addEventListener("DOMContentLoaded",function(){
$("crop").style.display="none";
$("cropMode").style.display="inline";
$("crop").addEventListener("click",function(event){
$("crop").style.display="none";
$("cropMode").style.display="inline";
var left=cropFrame.left-cropActiveObject.left;
var top=cropFrame.top-cropActiveObject.top;
left*=1;
top*=1;
var width=cropFrame.width*1;
var height=cropFrame.height*1;
ImageUtil.cropImage(
cropActiveObject,
cropFrame.left,
cropFrame.top,
parseInt(cropFrame.scaleY*height),
parseInt(width*cropFrame.scaleX)
);
if(cropModeClear()){
return true;
}
});
$("cropMode").addEventListener("click",function(){
$("crop").style.display="inline";
$("cropMode").style.display="none";
$("crop").classList.add("toggled");
if(canvas.getActiveObject()){
if(cropModeClear()){
return true;
}
if(isImage(canvas.getActiveObject())){
imageLogger.debug("canvas.getActiveObject().type",canvas.getActiveObject().type);
}else{
createToast("Select Image!",canvas.getActiveObject().type);
$("crop").style.display="none";
$("cropMode").style.display="inline";
return;
}
cropActiveObject=canvas.getActiveObject();
cropFrame=new fabric.Rect({
fill:"rgba(0,0,0,0)",
originX:"left",
originY:"top",
stroke:"rgba(0,0,0,0)",
strokeWidth:0,
width:1,
height:1,
borderColor:"#36fd00",
cornerColor:"green",
hasRotatingPoint:false,
selectable:true,
});
cropFrame.left=canvas.getActiveObject().left;
cropFrame.top=canvas.getActiveObject().top;
cropFrame.width=canvas.getActiveObject().width*canvas.getActiveObject().scaleX;
cropFrame.height=canvas.getActiveObject().height*canvas.getActiveObject().scaleY;
canvas.add(cropFrame);
canvas.setActiveObject(cropFrame);
canvas.renderAll();
}else{
createToast("Select Image!","");
$("crop").style.display="none";
$("cropMode").style.display="inline";
}
});
});
