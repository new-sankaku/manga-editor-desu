// mode-manager.js - モード管理の統合（ナイフ、ペン、吹き出し、クロップ等）

var ModeManager={
MODE:{
SELECT:'select',
FREEHAND:'freehand',
POINT:'point',
MOVE_POINT:'movePoint',
DELETE_POINT:'deletePoint',
KNIFE:'knife',
CROP:'crop',
PEN_PENCIL:'Pencil',
PEN_OUTLINE:'OutlinePen',
PEN_CIRCLE:'Circle',
PEN_SQUARE:'Square',
PEN_TEXTURE:'Texture',
PEN_CRAYON:'Crayon',
PEN_INK:'Ink',
PEN_MARKER:'Marker',
PEN_ERASER:'Eraser',
PEN_HLINE:'Hline',
PEN_VLINE:'Vline',
PEN_MOSAIC:'Mosaic'
},

_current:'select',
_previous:null,
_knifeActive:false,
_cropActive:false,
_pencilActive:null,

getCurrent:function(){
return ModeManager._current;
},

getPrevious:function(){
return ModeManager._previous;
},

change:function(mode,options){
options=options||{};
var prev=ModeManager._current;
if(!options.skipClear){
ModeManager._clearCurrentMode();
}
ModeManager._previous=prev;
ModeManager._current=mode;
switch(mode){
case ModeManager.MODE.SELECT:
ModeManager._enableSelectMode();
break;
case ModeManager.MODE.FREEHAND:
case ModeManager.MODE.POINT:
case ModeManager.MODE.MOVE_POINT:
case ModeManager.MODE.DELETE_POINT:
ModeManager._enableSpeechBubbleMode(mode);
break;
case ModeManager.MODE.KNIFE:
ModeManager._enableKnifeMode();
break;
case ModeManager.MODE.CROP:
ModeManager._enableCropMode();
break;
default:
if(ModeManager._isPenMode(mode)){
ModeManager._enablePencilMode(mode);
}
}
ModeManager.updateCursor(mode);
uiLogger.debug("ModeManager.change:",prev,"->",mode);
},

clear:function(){
ModeManager._clearCurrentMode();
ModeManager._current=ModeManager.MODE.SELECT;
ModeManager._enableSelectMode();
ModeManager.updateCursor(ModeManager.MODE.SELECT);
uiLogger.debug("ModeManager.clear: reset to select mode");
},

_clearCurrentMode:function(){
var current=ModeManager._current;
if(ModeManager._cropActive){
ModeManager.crop.disable();
}
if(ModeManager._knifeActive){
ModeManager.knife.disable();
}
if(ModeManager._pencilActive){
ModeManager.pencil.disable();
}
if(current===ModeManager.MODE.FREEHAND||
current===ModeManager.MODE.POINT||
current===ModeManager.MODE.MOVE_POINT||
current===ModeManager.MODE.DELETE_POINT){
ModeManager.speechBubble.clear();
}
},

_enableSelectMode:function(){
canvas.selection=true;
canvas.forEachObject(function(obj){
if(obj.excludeFromLayerPanel)return;
if(obj.customType==="freehandBubbleRect"){
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:true,evented:true});
});
changeDefaultCursor();
},

_enableSpeechBubbleMode:function(mode){
currentMode=mode;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
ModeManager.updateCursor(mode);
},

_enableKnifeMode:function(){
ModeManager._knifeActive=true;
isKnifeMode=true;
updateKnifeMode();
},

_enableCropMode:function(){
ModeManager._cropActive=true;
},

_enablePencilMode:function(mode){
ModeManager._pencilActive=mode;
if(typeof switchPencilType==='function'){
switchPencilType(mode);
}
},

_isPenMode:function(mode){
var penModes=[
ModeManager.MODE.PEN_PENCIL,
ModeManager.MODE.PEN_OUTLINE,
ModeManager.MODE.PEN_CIRCLE,
ModeManager.MODE.PEN_SQUARE,
ModeManager.MODE.PEN_TEXTURE,
ModeManager.MODE.PEN_CRAYON,
ModeManager.MODE.PEN_INK,
ModeManager.MODE.PEN_MARKER,
ModeManager.MODE.PEN_ERASER,
ModeManager.MODE.PEN_HLINE,
ModeManager.MODE.PEN_VLINE,
ModeManager.MODE.PEN_MOSAIC
];
return penModes.indexOf(mode)!==-1;
},

updateCursor:function(mode){
if(typeof changeCursor==='function'){
switch(mode){
case ModeManager.MODE.FREEHAND:
changeCursor('freehand');
break;
case ModeManager.MODE.POINT:
changeCursor('point');
break;
case ModeManager.MODE.MOVE_POINT:
changeCursor('movePoint');
break;
case ModeManager.MODE.DELETE_POINT:
changeCursor('deletePoint');
break;
case ModeManager.MODE.KNIFE:
changeCursor('knife');
break;
default:
if(ModeManager._isPenMode(mode)&&mode!==ModeManager.MODE.PEN_MOSAIC){
changeCursor('editPen');
}else{
changeDefaultCursor();
}
}
}
},

knife:{
enable:function(){
ModeManager._knifeActive=true;
isKnifeMode=true;
if(currentMode===ModeManager.MODE.FREEHAND||currentMode===ModeManager.MODE.POINT){
if(typeof sbClear==='function')sbClear();
if(typeof sbClearControlePoints==='function')sbClearControlePoints();
points=[];
}
currentMode=ModeManager.MODE.SELECT;
if(typeof activeClearButton==='function')activeClearButton();
if(typeof changeCursor==='function')changeCursor('knife');
ModeManager._updateKnifeMovement();
},

disable:function(){
ModeManager._knifeActive=false;
isKnifeMode=false;
if(typeof nonActiveClearButton==='function')nonActiveClearButton();
if(typeof changeDefaultCursor==='function')changeDefaultCursor();
if(currentKnifeLine){
if(typeof stopKnifeLineAnimation==='function')stopKnifeLineAnimation();
if(typeof setNotSave==='function')setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}
ModeManager._updateKnifeMovement();
},

toggle:function(){
if(ModeManager._knifeActive){
ModeManager.knife.disable();
}else{
ModeManager.knife.enable();
}
},

isActive:function(){
return ModeManager._knifeActive;
}
},

_updateKnifeMovement:function(){
canvas.discardActiveObject();
canvas.selection=!ModeManager._knifeActive;
canvas.forEachObject(function(obj){
obj.set({selectable:!ModeManager._knifeActive});
});
canvas.renderAll();
},

crop:{
enable:function(){
ModeManager._cropActive=true;
$("crop").style.display="inline";
$("cropMode").style.display="none";
},

disable:function(){
ModeManager._cropActive=false;
if(cropFrame){
$("crop").style.display="none";
$("cropMode").style.display="inline";
canvas.remove(cropFrame);
cropFrame=null;
if(cropActiveObject){
cropActiveObject.set({selectable:true});
}
}
},

isActive:function(){
return ModeManager._cropActive;
}
},

pencil:{
enable:function(type){
ModeManager._pencilActive=type;
if(typeof switchPencilType==='function'){
switchPencilType(type);
}
},

disable:function(){
if(ModeManager._pencilActive){
if(typeof pencilModeClear==='function'){
pencilModeClear(ModeManager._pencilActive);
}
ModeManager._pencilActive=null;
if(typeof clearPenActiveButton==='function')clearPenActiveButton();
if(typeof nonActiveClearButton==='function')nonActiveClearButton();
}
},

getCurrentType:function(){
return ModeManager._pencilActive;
},

isActive:function(){
return ModeManager._pencilActive!==null;
}
},

speechBubble:{
setMode:function(mode){
currentMode=mode;
ModeManager._current=mode;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
ModeManager.updateCursor(mode);
var buttons={
freehand:typeof sbFreehandButton!=='undefined'?sbFreehandButton:null,
point:typeof sbPointButton!=='undefined'?sbPointButton:null,
movePoint:typeof sbMoveButton!=='undefined'?sbMoveButton:null,
deletePoint:typeof sbDeleteButton!=='undefined'?sbDeleteButton:null,
select:typeof sbSelectButton!=='undefined'?sbSelectButton:null
};
if(buttons[mode]&&typeof setSBActiveButton==='function'){
setSBActiveButton(buttons[mode]);
}
},

clear:function(){
if(typeof sbClear==='function')sbClear();
if(typeof sbClearControlePoints==='function')sbClearControlePoints();
if(typeof points!=='undefined')points=[];
},

isActive:function(){
return currentMode===ModeManager.MODE.FREEHAND||
currentMode===ModeManager.MODE.POINT||
currentMode===ModeManager.MODE.MOVE_POINT||
currentMode===ModeManager.MODE.DELETE_POINT;
}
},

edit:{
clear:function(){
canvas.getObjects().forEach(function(obj){
if(obj.edit){
obj.edit=false;
obj.cornerStyle="rect";
obj.controls=fabric.Object.prototype.controls;
obj.hasBorders=true;
canvas.requestRenderAll();
if(typeof updateLayerPanel==='function')updateLayerPanel();
}
});
}
},

clearAll:function(){
ModeManager.crop.disable();
ModeManager.knife.disable();
ModeManager.edit.clear();
ModeManager.pencil.disable();
ModeManager.speechBubble.clear();
ModeManager._current=ModeManager.MODE.SELECT;
currentMode=ModeManager.MODE.SELECT;
if(typeof setSBActiveButton==='function'&&typeof sbSelectButton!=='undefined'){
setSBActiveButton(sbSelectButton);
}
canvas.forEachObject(function(obj){
if(obj.customType==="freehandBubbleRect"){
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:true,evented:true});
});
canvas.selection=true;
changeDefaultCursor();
uiLogger.debug("ModeManager.clearAll: all modes cleared");
}
};
