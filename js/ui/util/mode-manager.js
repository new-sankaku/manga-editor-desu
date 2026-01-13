/**
* mode-manager.js
* モード管理の統合ユーティリティ
* 各種モード（ナイフ、ペン、吹き出し、クロップ等）を統合管理
*/

var ModeManager={
// === モード定数 ===
MODE:{
SELECT:'select',
FREEHAND:'freehand',
POINT:'point',
MOVE_POINT:'movePoint',
DELETE_POINT:'deletePoint',
KNIFE:'knife',
CROP:'crop',
// ペンモード
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

// === 状態管理 ===
_current:'select',
_previous:null,
_knifeActive:false,
_cropActive:false,
_pencilActive:null,

/**
* 現在のモードを取得
* @returns {string}
*/
getCurrent:function(){
return ModeManager._current;
},

/**
* 前のモードを取得
* @returns {string|null}
*/
getPrevious:function(){
return ModeManager._previous;
},

// === モード変更 ===

/**
* モードを変更
* @param {string} mode - 変更先モード
* @param {Object} options - オプション
*/
change:function(mode,options){
options=options||{};
var prev=ModeManager._current;
// 前のモードをクリア
if(!options.skipClear){
ModeManager._clearCurrentMode();
}
ModeManager._previous=prev;
ModeManager._current=mode;
// モード別の初期化
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
// ペンモードの場合
if(ModeManager._isPenMode(mode)){
ModeManager._enablePencilMode(mode);
}
}
// カーソル更新
ModeManager.updateCursor(mode);
uiLogger.debug("ModeManager.change:",prev,"->",mode);
},

/**
* 全モードをクリアしてセレクトモードに戻る
*/
clear:function(){
ModeManager._clearCurrentMode();
ModeManager._current=ModeManager.MODE.SELECT;
ModeManager._enableSelectMode();
ModeManager.updateCursor(ModeManager.MODE.SELECT);
uiLogger.debug("ModeManager.clear: reset to select mode");
},

/**
* 現在のモードをクリア（内部用）
*/
_clearCurrentMode:function(){
var current=ModeManager._current;
// クロップモードのクリア
if(ModeManager._cropActive){
ModeManager.crop.disable();
}
// ナイフモードのクリア
if(ModeManager._knifeActive){
ModeManager.knife.disable();
}
// ペンシルモードのクリア
if(ModeManager._pencilActive){
ModeManager.pencil.disable();
}
// 吹き出しモードのクリア
if(current===ModeManager.MODE.FREEHAND||
current===ModeManager.MODE.POINT||
current===ModeManager.MODE.MOVE_POINT||
current===ModeManager.MODE.DELETE_POINT){
ModeManager.speechBubble.clear();
}
},

/**
* セレクトモードを有効化（内部用）
*/
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

/**
* 吹き出しモードを有効化（内部用）
*/
_enableSpeechBubbleMode:function(mode){
currentMode=mode;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
ModeManager.updateCursor(mode);
},

/**
* ナイフモードを有効化（内部用）
*/
_enableKnifeMode:function(){
ModeManager._knifeActive=true;
isKnifeMode=true;
updateKnifeMode();
},

/**
* クロップモードを有効化（内部用）
*/
_enableCropMode:function(){
ModeManager._cropActive=true;
// cropModeの処理はimage-util.jsのDOMイベントで処理
},

/**
* ペンシルモードを有効化（内部用）
*/
_enablePencilMode:function(mode){
ModeManager._pencilActive=mode;
if(typeof switchPencilType==='function'){
switchPencilType(mode);
}
},

/**
* ペンモードかどうかを判定（内部用）
*/
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

// === カーソル管理 ===

/**
* カーソルを更新
* @param {string} mode - モード
*/
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

// === 個別モード制御 ===

knife:{
/**
* ナイフモードを有効化
*/
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

/**
* ナイフモードを無効化
*/
disable:function(){
ModeManager._knifeActive=false;
isKnifeMode=false;
if(typeof nonActiveClearButton==='function')nonActiveClearButton();
if(typeof changeDefaultCursor==='function')changeDefaultCursor();
// ナイフ線の削除
if(currentKnifeLine){
if(typeof stopKnifeLineAnimation==='function')stopKnifeLineAnimation();
if(typeof setNotSave==='function')setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}
ModeManager._updateKnifeMovement();
},

/**
* ナイフモードをトグル
*/
toggle:function(){
if(ModeManager._knifeActive){
ModeManager.knife.disable();
}else{
ModeManager.knife.enable();
}
},

/**
* ナイフモードが有効かどうか
* @returns {boolean}
*/
isActive:function(){
return ModeManager._knifeActive;
}
},

/**
* ナイフモード時のオブジェクト移動設定を更新（内部用）
*/
_updateKnifeMovement:function(){
canvas.discardActiveObject();
canvas.selection=!ModeManager._knifeActive;
canvas.forEachObject(function(obj){
obj.set({selectable:!ModeManager._knifeActive});
});
canvas.renderAll();
},

crop:{
/**
* クロップモードを有効化
*/
enable:function(){
ModeManager._cropActive=true;
$("crop").style.display="inline";
$("cropMode").style.display="none";
},

/**
* クロップモードを無効化
*/
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

/**
* クロップモードが有効かどうか
* @returns {boolean}
*/
isActive:function(){
return ModeManager._cropActive;
}
},

pencil:{
/**
* ペンシルモードを有効化
* @param {string} type - ペンタイプ
*/
enable:function(type){
ModeManager._pencilActive=type;
if(typeof switchPencilType==='function'){
switchPencilType(type);
}
},

/**
* ペンシルモードを無効化
*/
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

/**
* 現在のペンシルタイプを取得
* @returns {string|null}
*/
getCurrentType:function(){
return ModeManager._pencilActive;
},

/**
* ペンシルモードが有効かどうか
* @returns {boolean}
*/
isActive:function(){
return ModeManager._pencilActive!==null;
}
},

speechBubble:{
/**
* 吹き出しモードを変更
* @param {string} mode - freehand, point, movePoint, deletePoint
*/
setMode:function(mode){
currentMode=mode;
ModeManager._current=mode;
canvas.selection=false;
canvas.forEachObject(function(obj){
obj.set({selectable:false,evented:false});
});
ModeManager.updateCursor(mode);
// UIボタンの更新
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

/**
* 吹き出しモードをクリア
*/
clear:function(){
if(typeof sbClear==='function')sbClear();
if(typeof sbClearControlePoints==='function')sbClearControlePoints();
if(typeof points!=='undefined')points=[];
},

/**
* 吹き出しモードが有効かどうか
* @returns {boolean}
*/
isActive:function(){
return currentMode===ModeManager.MODE.FREEHAND||
currentMode===ModeManager.MODE.POINT||
currentMode===ModeManager.MODE.MOVE_POINT||
currentMode===ModeManager.MODE.DELETE_POINT;
}
},

edit:{
/**
* 編集モードをクリア
*/
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

// === ユーティリティ ===

/**
* 全モードをクリア（operationModeClearの代替）
*/
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

// 既存コードとの互換性のため
// operationModeClearをModeManager.clearAllに委譲するオプション
// 注: 既存のoperationModeClear関数は残して、必要に応じてModeManager.clearAll()を呼び出す
