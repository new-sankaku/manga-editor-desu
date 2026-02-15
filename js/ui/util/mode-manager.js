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

getCurrent:function(){
return ModeManager._current;
},

getPrevious:function(){
return ModeManager._previous;
},

change:function(mode){
var prev=ModeManager._current;
ModeManager.clearAll();
ModeManager._previous=prev;
ModeManager._current=mode;
switch(mode){
case ModeManager.MODE.SELECT:
break;
case ModeManager.MODE.FREEHAND:
case ModeManager.MODE.POINT:
case ModeManager.MODE.MOVE_POINT:
case ModeManager.MODE.DELETE_POINT:
ModeManager._enableSpeechBubbleMode(mode);
break;
case ModeManager.MODE.KNIFE:
ModeManager.knife._enable();
break;
case ModeManager.MODE.CROP:
ModeManager.crop._enable();
break;
default:
if(ModeManager._isPenMode(mode)){
ModeManager.pencil._enable(mode);
}
}
if(mode!==ModeManager.MODE.SELECT){
ModeManager.button.activeClear();
}
ModeManager.cursor.update(mode);
uiLogger.debug("ModeManager.change:",prev,"->",mode);
},

_enableSpeechBubbleMode:function(mode){
currentMode=mode;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
var buttons={
freehand:typeof sbFreehandButton!=='undefined'?sbFreehandButton:null,
point:typeof sbPointButton!=='undefined'?sbPointButton:null,
movePoint:typeof sbMoveButton!=='undefined'?sbMoveButton:null,
deletePoint:typeof sbDeleteButton!=='undefined'?sbDeleteButton:null
};
if(buttons[mode]&&typeof setSBActiveButton==='function'){
setSBActiveButton(buttons[mode]);
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

_isImageBrush:function(type){
return type===ModeManager.MODE.PEN_MOSAIC||
type===ModeManager.MODE.PEN_CRAYON||
type===ModeManager.MODE.PEN_INK||
type===ModeManager.MODE.PEN_MARKER||
type===ModeManager.MODE.PEN_OUTLINE;
},

cursor:{
_svgs:{
movePoint:'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#F19E39"><path d="M468-240q-96-5-162-74t-66-166q0-100 70-170t170-70q97 0 166 66t74 162l-84-25q-13-54-56-88.5T480-640q-66 0-113 47t-47 113q0 57 34.5 100t88.5 56l25 84ZM821-60 650-231 600-80 480-480l400 120-151 50 171 171-79 79Z"/></svg>',
deletePoint:'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#F19E39"><path d="M200-440v-80h560v80H200Z"/></svg>',
freehand:'<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="2" fill="#F19E39" /><line x1="12" y1="12" x2="24" y2="24" stroke="#F19E39" stroke-width="2" /></svg>',
editPen:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 24 24"><path d="M3,3 L3,12 L12.2,6 Z" fill="#FFA500" stroke="black" stroke-width="0.5"/></svg>',
point:'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#F19E39"><path d="M170-228q-38-45-61-99T80-440h82q6 43 22 82.5t42 73.5l-56 56ZM80-520q8-59 30-113t60-99l56 56q-26 34-42 73.5T162-520H80ZM438-82q-59-6-112.5-28.5T226-170l56-58q35 26 74 43t82 23v80ZM284-732l-58-58q47-37 101-59.5T440-878v80q-43 6-82.5 23T284-732Zm196 372q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm38 278v-80q44-6 83.5-22.5T676-228l58 58q-47 38-101.5 60T518-82Zm160-650q-35-26-75-43t-83-23v-80q59 6 113.5 28.5T734-790l-56 58Zm112 504-56-56q26-34 42-73.5t22-82.5h82q-8 59-30 113t-60 99Zm8-292q-6-43-22-82.5T734-676l56-56q38 45 61 99t29 113h-82Z"/></svg>',
knife:'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#F19E39"><path d="M496-346 346-496l332-332q12-12 28.5-12t28.5 12l93 93q12 12 12 28.5T828-678L496-346Zm0-114 248-247-37-37-247 248 36 36Zm-56 340 80-80h360v80H440Zm-237 0q-46 0-88.5-18T40-188l265-264 104 104q14 14 22 32t8 38q0 20-8 38.5T409-207l-19 19q-32 32-74.5 50T227-120h-24Zm0-80h24q30 0 58-11.5t49-32.5l19-19q6-6 6-14t-6-14l-48-48-136 135q8 2 17 3t17 1Zm541-507-37-37 37 37ZM305-339Z"/></svg>'
},

_svgToBase64:function(svg){
return btoa(encodeURIComponent(svg).replace(/%([0-9A-F]{2})/g,function(match,p1){
return String.fromCharCode('0x'+p1);
}));
},

_create:function(type){
if(!ModeManager.cursor._svgs[type])return 'default';
return "url('data:image/svg+xml;base64,"+ModeManager.cursor._svgToBase64(ModeManager.cursor._svgs[type])+"') 12 12, crosshair";
},

update:function(mode){
var cursor;
switch(mode){
case ModeManager.MODE.FREEHAND:
cursor=ModeManager.cursor._create('freehand');
break;
case ModeManager.MODE.POINT:
cursor=ModeManager.cursor._create('point');
break;
case ModeManager.MODE.MOVE_POINT:
cursor=ModeManager.cursor._create('movePoint');
break;
case ModeManager.MODE.DELETE_POINT:
cursor=ModeManager.cursor._create('deletePoint');
break;
case ModeManager.MODE.KNIFE:
cursor=ModeManager.cursor._create('knife');
break;
default:
if(ModeManager._isPenMode(mode)&&mode!==ModeManager.MODE.PEN_MOSAIC){
cursor=ModeManager.cursor._create('editPen');
}else{
ModeManager.cursor.reset();
return;
}
}
canvas.freeDrawingCursor=cursor;
canvas.defaultCursor=cursor;
var objectList=getObjectList();
objectList.forEach(function(object){
object.hoverCursor=cursor;
object.moveCursor=cursor;
});
},

updateObject:function(type,object){
var cursor=ModeManager.cursor._create(type);
object.hoverCursor=cursor;
object.moveCursor=cursor;
},

reset:function(){
canvas.freeDrawingCursor='default';
canvas.defaultCursor='default';
var objectList=getObjectList();
objectList.forEach(function(object){
object.hoverCursor='default';
object.moveCursor='default';
});
}
},

knife:{
enable:function(){
ModeManager.change(ModeManager.MODE.KNIFE);
},

_enable:function(){
isKnifeMode=true;
ModeManager.button.activeClear();
ModeManager.cursor.update(ModeManager.MODE.KNIFE);
ModeManager.knife._updateMovement();
var knifeModeButton=$("knifeModeButton");
if(knifeModeButton){
knifeModeButton.classList.add("selected");
if(typeof getText==='function')knifeModeButton.textContent=getText("knifeOff");
}
},

disable:function(){
if(!isKnifeMode)return;
isKnifeMode=false;
ModeManager.button.nonActiveClear();
ModeManager.cursor.reset();
if(typeof currentKnifeLine!=='undefined'&&currentKnifeLine){
if(typeof stopKnifeLineAnimation==='function')stopKnifeLineAnimation();
if(typeof setNotSave==='function')setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}
ModeManager.knife._updateMovement();
var knifeModeButton=$("knifeModeButton");
if(knifeModeButton){
knifeModeButton.classList.remove("selected");
if(typeof getText==='function')knifeModeButton.textContent=getText("knifeOn");
}
},

toggle:function(){
if(isKnifeMode){
ModeManager.clearAll();
}else{
ModeManager.knife.enable();
}
},

isActive:function(){
return isKnifeMode;
},

_updateMovement:function(){
canvas.discardActiveObject();
canvas.selection=!isKnifeMode;
canvas.forEachObject(function(obj){
obj.set({selectable:!isKnifeMode});
});
canvas.renderAll();
}
},

crop:{
enable:function(){
ModeManager.change(ModeManager.MODE.CROP);
},

_enable:function(){
},

disable:function(){
if(!cropFrame)return;
canvas.remove(cropFrame);
cropFrame=null;
if(cropActiveObject){
cropActiveObject.set({selectable:true});
}
hideCanvasHelpText();
},

isActive:function(){
return cropFrame!==null&&cropFrame!==undefined;
}
},

pencil:{
enable:function(type){
ModeManager.change(type);
},

_enable:function(type){
if(typeof switchPencilType==='function'){
switchPencilType(type);
}
},

disable:function(){
if(!nowPencil)return;
ModeManager.cursor.reset();
if(canvas.isDrawingMode&&ModeManager._isImageBrush(nowPencil)){
canvas.isDrawingMode=false;
isMosaicBrushActive=false;
if(canvas.freeDrawingBrush&&typeof canvas.freeDrawingBrush.mergeDrawings==='function'){
canvas.freeDrawingBrush.mergeDrawings();
}
canvas.freeDrawingBrush=null;
canvas.contextTop.clearRect(0,0,canvas.width,canvas.height);
nowPencil="";
if(typeof finalizeGroup==='function')finalizeGroup();
}else if(canvas.isDrawingMode){
canvas.isDrawingMode=false;
if(typeof finalizeGroup==='function')finalizeGroup();
nowPencil="";
}
if(typeof clearPenActiveButton==='function')clearPenActiveButton();
ModeManager.button.nonActiveClear();
},

getCurrentType:function(){
return nowPencil;
},

isActive:function(){
return nowPencil!=="";
}
},

speechBubble:{
setMode:function(mode){
ModeManager.change(mode);
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
var hasEditMode=false;
canvas.getObjects().forEach(function(obj){
if(obj.edit){
hasEditMode=true;
obj.edit=false;
obj.cornerStyle="rect";
obj.controls=fabric.Object.prototype.controls;
obj.hasBorders=true;
canvas.requestRenderAll();
if(typeof updateLayerPanel==='function')updateLayerPanel();
}
});
if(hasEditMode){
var editButton=$("edit");
if(editButton){
editButton.classList.remove("selected");
var span=editButton.querySelector("span");
if(span)span.textContent=getText("editModeOn");
}
}
}
},

button:{
activeClear:function(){
if(typeof selectedById==='function')selectedById("clearMode");
},

nonActiveClear:function(){
if(isKnifeMode)return;
if(typeof unSelectedById==='function')unSelectedById("clearMode");
},

updateClear:function(){
if(isKnifeMode){
if(typeof selectedById==='function')selectedById("clearMode");
}else{
if(typeof unSelectedById==='function')unSelectedById("clearMode");
}
}
},

clearAll:function(){
uiLogger.debug("ModeManager.clearAll start");
ModeManager.crop.disable();
ModeManager.knife.disable();
ModeManager.edit.clear();
ModeManager.pencil.disable();
ModeManager.button.nonActiveClear();
currentMode=ModeManager.MODE.SELECT;
ModeManager._current=ModeManager.MODE.SELECT;
if(typeof setSBActiveButton==='function'&&typeof sbSelectButton!=='undefined'){
setSBActiveButton(sbSelectButton);
}
ModeManager.speechBubble.clear();
canvas.forEachObject(function(obj){
if(obj.customType==="freehandBubbleRect"){
obj.set({selectable:false,evented:false});
return;
}
obj.set({selectable:true,evented:true});
});
canvas.selection=true;
ModeManager.cursor.reset();
uiLogger.debug("ModeManager.clearAll: all modes cleared");
}
};

var operationModeClear=ModeManager.clearAll;
var cropModeClear=ModeManager.crop.disable;
var knifeModeClear=ModeManager.knife.disable;
var editModeClear=ModeManager.edit.clear;
var activeClearButton=ModeManager.button.activeClear;
var nonActiveClearButton=ModeManager.button.nonActiveClear;
var updateClearButton=ModeManager.button.updateClear;
var changeCursor=ModeManager.cursor.update;
var changeObjectCursor=ModeManager.cursor.updateObject;
var changeDefaultCursor=ModeManager.cursor.reset;

function pencilModeClear(type){
ModeManager.pencil.disable();
}
