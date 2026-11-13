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
PART_SCALE:'partScale',
PANEL_EDIT:'panelEdit',
TONE:'Tone',
TONE_NOISE:'ToneNoise',
TONE_SNOW:'ToneSnow',
SPEED_LINE:'SpeedLine',
FOCUSING_LINE:'FocusingLine',
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
case ModeManager.MODE.PANEL_EDIT:
ModeManager.edit._enable();
break;
default:
if(ModeManager._isPenMode(mode)){
ModeManager.pencil._enable(mode);
}else if(ModeManager._isToneMode(mode)){
ModeManager.tone._enable(mode);
}
}
if(mode!==ModeManager.MODE.SELECT){
ModeManager.button.activeClear();
}
ModeManager.cursor.update(mode);
ModeManager.help.show(mode);
uiLogger.debug("ModeManager.change:",prev,"->",mode);
},

_enableSpeechBubbleMode:function(mode){
currentMode=mode;
canvas.selection=false;
ModeManager.lock.apply({selectable:false,evented:false});
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

_isToneMode:function(mode){
var toneModes=[
ModeManager.MODE.TONE,
ModeManager.MODE.TONE_NOISE,
ModeManager.MODE.TONE_SNOW,
ModeManager.MODE.SPEED_LINE,
ModeManager.MODE.FOCUSING_LINE
];
return toneModes.indexOf(mode)!==-1;
},

_isImageBrush:function(type){
return type===ModeManager.MODE.PEN_MOSAIC||
type===ModeManager.MODE.PEN_CRAYON||
type===ModeManager.MODE.PEN_INK||
type===ModeManager.MODE.PEN_MARKER||
type===ModeManager.MODE.PEN_OUTLINE;
},

// モードに入るときに書き換えるプロパティを、オブジェクトごとに1か所へ退避し、
// 抜けるときは退避値へ戻す。退避が無いオブジェクト（モード中に増えたもの）は触らない。
// 「退避が無ければ selectable:true」にすると、ロックされたコマまで動かせるようになる（監査 #07）
lock:{
_BACKUP_KEY:'_modeLockBackup',

// ナイフの分割線・吹き出しの下描きと当たり判定用の矩形・切り抜き枠は、
// 利用者が掴む対象ではないためロックの対象にもしない
// （excludeFromLayerPanel が付く。レイヤーパネルにも出ない）。
// 除外はここ1か所に置く。呼び出し側ごとに書くと書き忘れた経路で
// 分割線や切り抜き枠が掴めるようになる
_isTarget:function(obj){
return !obj.excludeFromLayerPanel;
},

apply:function(props){
canvas.forEachObject(function(obj){
if(!ModeManager.lock._isTarget(obj))return;
if(!obj[ModeManager.lock._BACKUP_KEY]){
var backup={};
Object.keys(props).forEach(function(name){
backup[name]=obj[name];
});
obj[ModeManager.lock._BACKUP_KEY]=backup;
}
obj.set(props);
});
},

// 退避が付いているものだけを戻す。除外対象は apply が退避を付けないので
// ここで excludeFromLayerPanel は見ない。見てしまうと、モード中に
// そのフラグが付いたオブジェクトの退避が戻らずに残り続ける
restore:function(){
canvas.forEachObject(function(obj){
var backup=obj[ModeManager.lock._BACKUP_KEY];
if(!backup)return;
obj.set(backup);
delete obj[ModeManager.lock._BACKUP_KEY];
});
},

// モード中に増えたオブジェクトへ、元になったオブジェクトのロック状態を引き継ぐ。
// 「今の値」と「退避」の両方を渡す。退避を渡さないと、モードを抜けたときに
// 増えた分だけ元へ戻らず、分割元の兄弟とロック状態が食い違う（監査 #07 #12）。
//
// source に退避が無い（＝モードの外）ときは引き継ぐものが無いので、
// target の selectable などは呼び出し側が source から写すこと。
// ここで既定値を当てると元のロックが消える
inherit:function(source,target){
var backup=source[ModeManager.lock._BACKUP_KEY];
if(!backup){
delete target[ModeManager.lock._BACKUP_KEY];
return;
}
var copy={};
var current={};
Object.keys(backup).forEach(function(name){
copy[name]=backup[name];
current[name]=source[name];
});
target[ModeManager.lock._BACKUP_KEY]=copy;
target.set(current);
}
},

// キャンバス上の案内文（#canvas-help-text）。
// 「今どのモードか」「何をすればよいか」「どう抜けるか」をここ1か所で持つ。
// モードごとに表示処理を書き足すと、案内が出ないモードが残る（監査 #10）
help:{
// 吹き出しの4モード（freehand/point/movePoint/deletePoint）はここに登録しない。
// 座標モードは「4点以上打ってから始点をクリック」という確定条件を出す必要があり、
// 打った点数で文言が変わる（監査 #22）。1つの固定文では足りないため、
// speech-bubble-freehand.js の updateFreehandPointHelpText() が持っている。
// ここにも定義を置くと同じ場所を2か所から書くことになる
_defs:{
knife:{key:'knifeHelpText',highlight:'ESC'},
crop:{key:'cropHelpText',highlight:'Enter'},
panelEdit:{key:'panelEditHelpText',highlight:'ESC'}
},
_penDef:{key:'penHelpText',highlight:'ESC'},
_toneDef:{key:'toneHelpText',highlight:'ESC'},

_def:function(mode){
if(ModeManager._isPenMode(mode))return ModeManager.help._penDef;
if(ModeManager._isToneMode(mode))return ModeManager.help._toneDef;
return ModeManager.help._defs[mode];
},

show:function(mode){
var def=ModeManager.help._def(mode);
if(!def){
ModeManager.help.hide();
return;
}
showCanvasHelpText(getText(def.key),def.highlight);
},

hide:function(){
hideCanvasHelpText();
}
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
setKnifeModeButtonState(true);
},

// clearAll からだけでなく単独でも呼ばれる（knife-mode.js の updateKnifeMode）。
// 「ナイフだけを畳んで別のモードへ移る」経路のため、ここで抜けた状態まで揃える。
// clearAll から呼ばれたときは同じことを二度やるだけで害はない
disable:function(){
// isKnifeMode を先に false にしてから解除を頼む呼び出し元（speech-bubble-freehand.js）が
// あるため、ModeManager 側の現在モードでも入り中かどうかを見る
if(!isKnifeMode&&ModeManager._current!==ModeManager.MODE.KNIFE)return;
isKnifeMode=false;
// nonActiveClear は「まだ別モードが動いていれば消さない」ため、先に現在モードを戻す
if(ModeManager._current===ModeManager.MODE.KNIFE){
ModeManager._current=ModeManager.MODE.SELECT;
}
ModeManager.button.nonActiveClear();
ModeManager.help.hide();
ModeManager.cursor.reset();
if(typeof currentKnifeLine!=='undefined'&&currentKnifeLine){
if(typeof stopKnifeLineAnimation==='function')stopKnifeLineAnimation();
if(typeof setNotSave==='function')setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}
ModeManager.knife._updateMovement();
setKnifeModeButtonState(false);
},

toggle:function(){
if(ModeManager.knife.isActive()){
ModeManager.clearAll();
}else{
ModeManager.knife.enable();
}
},

isActive:function(){
return isKnifeMode;
},

// 元の selectable を捨てずに退避・復元する。全件を selectable:true に書き戻すと
// テンプレートのコマのロックまで外れる（監査 #07）
_updateMovement:function(){
canvas.discardActiveObject();
canvas.selection=!isKnifeMode;
if(isKnifeMode){
ModeManager.lock.apply({selectable:false});
}else{
ModeManager.lock.restore();
}
canvas.renderAll();
}
},

// クロップの入り口。切り抜き枠の組み立ては mode-change.js の startCropMode() が持ち、
// 他モードの解除・案内文・現在モードの記録はここが持つ。
// startCropMode() は対象が画像でないとトーストを出して枠を作らずに戻るため、
// 枠ができなかったときは select へ戻す（案内文とボタンだけ残さない）。
//
// クロップの入り口はここ1つ（js/ui/canvas-object-menu.js の 'cropImage'）。
// startCropMode() を直接呼ぶと clearAll() を通らず、動いていたモードが残ったまま
// 案内文だけ差し替わる（例: トーン適用中に右クリック→切り抜き）
crop:{
enable:function(targetImage){
ModeManager.change(ModeManager.MODE.CROP);
startCropMode(targetImage);
if(!ModeManager.crop.isActive()){
ModeManager.clearAll();
}
},

_enable:function(){
},

disable:function(){
if(!cropFrame)return;
removeByNotSave(cropFrame);
cropFrame=null;
// 切り抜き対象の selectable は誰も false にしていない（crop._enable() は空で、
// lock.apply() も通らない）。ここで true を当てると、ロックしてある画像を
// 切り抜いただけでロックが外れる。元の値をそのまま残す（監査 #07 と同じ形）
ModeManager.help.hide();
},

isActive:function(){
return cropFrame!==null&&cropFrame!==undefined;
}
},

// 範囲を拡大縮小の入り口。中身は part-scale.js の PartScale が持つ。
// ESC・別モード・選択を外す、のどれで抜けても clearAll() → disable() を通り、確定前なら画像を元に戻す
partScale:{
enable:function(targetImage){
ModeManager.change(ModeManager.MODE.PART_SCALE);
PartScale.start(targetImage);
if(!PartScale.isActive()){
ModeManager.clearAll();
}
},

disable:function(){
if(typeof PartScale==='undefined')return;
PartScale.cancel();
},

isActive:function(){
return typeof PartScale!=='undefined'&&PartScale.isActive();
}
},

pencil:{
enable:function(type){
ModeManager.change(type);
},

_enable:function(type){
applyPencilType(type);
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
endPencil();
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

// トーン・効果線。実処理は tone-manager.js の applyMangaTone / endMangaTone。
// ここを通すことで Esc・「モード解除」・パネル切替のどれからでも終われる（監査 #25）
tone:{
enable:function(type){
ModeManager.change(type);
},

_enable:function(type){
applyMangaTone(type);
},

disable:function(){
if(!ModeManager.tone.isActive())return;
endMangaTone();
},

getCurrentType:function(){
return nowTone;
},

isActive:function(){
return nowTone!==null&&nowTone!==undefined;
}
},

speechBubble:{
setMode:function(mode){
ModeManager.change(mode);
},

clear:function(){
if(typeof sbClear==='function')sbClear();
if(typeof sbClearControlPoints==='function')sbClearControlPoints();
if(typeof points!=='undefined')points=[];
},

isActive:function(){
return currentMode===ModeManager.MODE.FREEHAND||
currentMode===ModeManager.MODE.POINT||
currentMode===ModeManager.MODE.MOVE_POINT||
currentMode===ModeManager.MODE.DELETE_POINT;
}
},

// コマ編集モード。頂点コントロールの組み立て自体は panel-manager.js の Edit() が持ち、
// 「他モードの解除」「案内文」「モード解除ボタンの点灯」「現在モードの記録」はここが持つ。
// panel-manager.js からは、対象コマの検証が通った直後・poly.edit を立てる前に
// ModeManager.edit.enable() を呼ぶ（先に呼ばないと clearAll が組み立て直後の状態を戻してしまう）
edit:{
enable:function(){
ModeManager.change(ModeManager.MODE.PANEL_EDIT);
},

_enable:function(){
},

isActive:function(){
var active=false;
canvas.getObjects().forEach(function(obj){
if(obj.edit)active=true;
});
return active;
},

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
updateLayerPanel();
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

// 「モード解除(ESC)」ボタンの点灯。ナイフだけを見ていたため、トーンなど
// 他のモードでは点灯しなかった（監査 #10 #25）。点灯条件は現在モードだけで決める
button:{
activeClear:function(){
if(typeof selectedById==='function')selectedById("clearMode");
},

nonActiveClear:function(){
// まだ別のモードが動いているうちは消さない。
// 以前はナイフだけを見ていたため、トーンやコマ編集を抜けても点いたまま／
// 点かないままになっていた
if(ModeManager._current!==ModeManager.MODE.SELECT)return;
if(typeof unSelectedById==='function')unSelectedById("clearMode");
},

updateClear:function(){
if(ModeManager._current!==ModeManager.MODE.SELECT){
ModeManager.button.activeClear();
}else{
ModeManager.button.nonActiveClear();
}
}
},

clearAll:function(){
uiLogger.debug("ModeManager.clearAll start");
ModeManager.crop.disable();
ModeManager.partScale.disable();
ModeManager.knife.disable();
ModeManager.edit.clear();
ModeManager.pencil.disable();
ModeManager.tone.disable();
currentMode=ModeManager.MODE.SELECT;
ModeManager._current=ModeManager.MODE.SELECT;
ModeManager.button.nonActiveClear();
ModeManager.help.hide();
if(typeof setSBActiveButton==='function'&&typeof sbSelectButton!=='undefined'){
setSBActiveButton(sbSelectButton);
}
ModeManager.speechBubble.clear();
// 吹き出しモードも ModeManager.lock で退避するようになったので
// （speech-bubble-freehand.js の updateObjectSelectability）、
// どのモードから抜けるときも戻すのはこの1行だけでよい
ModeManager.lock.restore();
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
