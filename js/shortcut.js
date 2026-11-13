// simple check if the user is using a mac os , not the best way to detect the OS
var isMacOs=navigator.userAgent.indexOf('Mac OS')!==-1;;

var hotkeysMap={
toggleGrid: 'ctrl+g',
undo:!isMacOs ? 'ctrl+z' : 'command+z',
redo:!isMacOs ? 'ctrl+y' : 'command+y',
toggleLayer: 'ctrl+l',
toggleControls: 'ctrl+k',
zoomIn: 'ctrl+8',
zoomOut: 'ctrl+9',
zoomFit: 'ctrl+0',
copy:!isMacOs ? 'ctrl+c' : "command+c",
paste:!isMacOs ? 'ctrl+v' : "command+v",
delete: 'delete, backspace',
moveLeft: 'left',
moveRight: 'right',
moveUp: 'up',
moveDown: 'down',
deselect: 'escape',
layerUp:!isMacOs ? 'ctrl+up' : 'command+up',
layerDown:!isMacOs ? 'ctrl+down' : 'command+down',
moveLeftFast: 'shift+left',
moveRightFast: 'shift+right',
moveUpFast: 'shift+up',
moveDownFast: 'shift+down',
projectSave:!isMacOs ? 'ctrl+s' : 'command+s',
projectLoad:!isMacOs ? 'ctrl+o' : 'command+o',
toggleBottomBar:!isMacOs ? 'ctrl+b' : 'command+b',
imageDownload:!isMacOs ? 'ctrl+d' : 'command+d',
settingsSave:!isMacOs ? 'ctrl+shift+s' : 'command+shift+s',
promptView:!isMacOs ? 'ctrl+p' : 'command+p',
shortcutPage:'f1',
newPage:'alt+n',
prevPage:'alt+left',
nextPage:'alt+right',
}

var isLongPressDirection=false;
var longPressTimer=0;
var activeObjectMoveStep=0;

// ショートカットごとに「入力欄にフォーカスがあるとき」の扱いが違い、
// Ctrl+Z/Ctrl+S などは isEditableTagsActive()、Ctrl+C/V・Delete・矢印・Esc は
// ライブラリ既定のフィルタ任せだった。判定をここ1か所に寄せて全ショートカットで揃える
hotkeys.filter=function (event) {
return!isEditableTagsActive(event.target);
};


// bind toggle grid shortcut
hotkeys(hotkeysMap.toggleGrid,'all' ,function (e) {
toggleGrid();
e.preventDefault();
});

// Undo/Redoの入口はキーとツールバーのボタンの2つ。どちらもここを通す。
// 履歴はページごとに持つ（仕様）ため、押しても何も起きないとき、
// 端まで戻り切ったのか、別ページでの操作なので戻せないのかが利用者から区別できない。
// 何も起きなかったときだけ理由を出す
function undoByUser() {
if (isHistoryRestoreInProgress()) {
undo();
return;
}
var beforeIndex=currentStateIndex;
undo();
if (currentStateIndex===beforeIndex) {
createToast(getText('historyUndoNone'),[getText('historyPageScope')]);
}
updateHistoryButtonState();
}

function redoByUser() {
if (isHistoryRestoreInProgress()) {
redo();
return;
}
var beforeIndex=currentStateIndex;
redo();
if (currentStateIndex===beforeIndex) {
createToast(getText('historyRedoNone'),[getText('historyPageScope')]);
}
updateHistoryButtonState();
}

// 履歴の端では押しても何も起きない。押せる見た目のままだと
// 「効かない」のか「もう戻れない」のかが区別できないため、端では無効表示にする。
// 呼ぶのは履歴が実際に変わる場所（image-history-management.js の
// notifyHistoryChanged()）。ここから履歴を見張らないこと
function updateHistoryButtonState() {
setHistoryButtonState($('undo'),currentStateIndex>=1);
setHistoryButtonState($('redo'),currentStateIndex<stateStack.length-1);
}

function setHistoryButtonState(button,enabled) {
if (!button) {
return;
}
button.disabled=!enabled;
}

// bind undo shortcut
hotkeys(hotkeysMap.undo,'all' ,function (e) {
undoByUser();
e.preventDefault();
});

// bind redo shortcut
hotkeys(hotkeysMap.redo,'all' ,function (e) {
redoByUser();
e.preventDefault();
});

// bind toggle layer panel shortcut
hotkeys(hotkeysMap.toggleLayer,'all',function (e) {
changeView('layer-panel',$('view_layers_checkbox').checked);
$('view_layers_checkbox').click();
e.preventDefault();
});

// bind toggle controls shortcut
hotkeys(hotkeysMap.toggleControls,'all',function (e) {
changeView('controls',$('view_controls_checkbox').checked);
$('view_controls_checkbox').click();
e.preventDefault();
});

// bind zoom in shortcut
hotkeys(hotkeysMap.zoomIn,'all',function (e) {
zoomIn();
e.preventDefault();
});

// bind zoom out shortcut
hotkeys(hotkeysMap.zoomOut,'all',function (e) {
zoomOut();
e.preventDefault();
});

// bind zoom fit shortcut
hotkeys(hotkeysMap.zoomFit,'all',function (e) {
zoomFit();
e.preventDefault();
});

// bind copy shortcut
hotkeys(hotkeysMap.copy,'all',function (e) {
var activeObject=canvas.getActiveObject();
if (activeObject) {
activeObject.clone(function(cloned) {
window._clipboard=cloned;
// コマとのリンク（relatedPoly）は複製に付いてこない。
// 貼り付けで張り直すときに元と同じコマを優先できるよう、コピー元を覚えておく
window._clipboardSource=activeObject;
});
}
e.preventDefault();
});

// bind paste shortcut
hotkeys(hotkeysMap.paste,'all',function (e) {
if (!window._clipboard||!(window._clipboard instanceof fabric.Object)) {
return;
}
window._clipboard.clone(function(clonedObj) {
clonedObj.set({
left: clonedObj.left+10,
top: clonedObj.top+10
});
canvas.add(clonedObj);
// 複製は relatedPoly も guid も持たず、clipPath だけが元コマ位置の静的コピーとして残る。
// リンクの張り直しは複製の入口（右クリックの複製・ここ）ごとに書かず、
// panel-manager.js の1か所に寄せてある
relinkClonedObject(clonedObj,window._clipboardSource);
canvas.setActiveObject(clonedObj);
canvas.requestRenderAll();
updateLayerPanel();
saveStateByManual();
});
e.preventDefault();
});

// bind delete shortcut
hotkeys(hotkeysMap.delete,'all',function (e) {
var activeObject=canvas.getActiveObject();
if (activeObject) {
removeLayer(activeObject);
canvas.renderAll();
e.preventDefault();
}
});

// bind move object shortcuts
hotkeys(hotkeysMap.moveLeft,'all',function (e) {
moveActiveObject('left',e);
});

hotkeys(hotkeysMap.moveRight,'all',function (e) {
moveActiveObject('right',e);
});

hotkeys(hotkeysMap.moveUp,'all',function (e) {
moveActiveObject('up',e);
});

hotkeys(hotkeysMap.moveDown,'all',function (e) {
moveActiveObject('down' ,e);
});

// bind deselect shortcut
hotkeys(hotkeysMap.deselect,'all',function (e) {
if (isNotVisibleFloatingWindow()) {
ModeManager.clearAll();
canvas.discardActiveObject();
canvas.requestRenderAll();
e.preventDefault();
}
});

// bind layer up shortcut
hotkeys(hotkeysMap.layerUp,'all',function (e) {
if (canvas.getActiveObject()) {
LayersUp();
e.preventDefault();
}
});

// bind layer down shortcut
hotkeys(hotkeysMap.layerDown,'all',function (e) {
if (canvas.getActiveObject()) {
LayersDown();
e.preventDefault();
}
});

// bind project save shortcut
hotkeys(hotkeysMap.projectSave,'all',function (e) {
$('projectSave').click();
e.preventDefault();
});

// bind project load shortcut
hotkeys(hotkeysMap.projectLoad,'all',function (e) {
$('projectLoad').click();
e.preventDefault();
});

// bind toggle bottom bar shortcut
hotkeys(hotkeysMap.toggleBottomBar,'all',function (e) {
btmToggleDrawer();
e.preventDefault();
});

// bind image download shortcut
hotkeys(hotkeysMap.imageDownload,'all',function (e) {
cropAndDownload();
e.preventDefault();
});

// bind settings save shortcut
hotkeys(hotkeysMap.settingsSave,'all',function (e) {
$('settingsSave').click();
e.preventDefault();
});

// bind prompt view shortcut
hotkeys(hotkeysMap.promptView,'all',function (e) {
View();
var cb=$("view_prompt_checkbox");
if(cb)cb.checked=areNamesVisible;
e.preventDefault();
});

// bind shortcut page shortcut
hotkeys(hotkeysMap.shortcutPage,'all',function (e) {
openShortcutModal();
e.preventDefault();
});

// bind new page shortcut
hotkeys(hotkeysMap.newPage,'all',function (e) {
loadBookSize(canvas.width,canvas.height,true,true);
return false;
});

hotkeys(hotkeysMap.prevPage,'all',function (e) {
btmNavigatePage(-1);
e.preventDefault();
});

hotkeys(hotkeysMap.nextPage,'all',function (e) {
btmNavigatePage(1);
e.preventDefault();
});

var shortcutCategories=[
{category:'sc_cat_file',items:[
{win:'Alt + N',mac:'Alt + N',i18n:'sc_newPage'},
{win:'Alt + \u2190',mac:'Alt + \u2190',i18n:'sc_prevPage'},
{win:'Alt + \u2192',mac:'Alt + \u2192',i18n:'sc_nextPage'},
{win:'Ctrl + S',mac:'⌘ + S',i18n:'sc_projectSave'},
{win:'Ctrl + O',mac:'⌘ + O',i18n:'sc_projectLoad'},
{win:'Ctrl + D',mac:'⌘ + D',i18n:'sc_imageDownload'},
{win:'Ctrl + Shift + S',mac:'⌘ + Shift + S',i18n:'sc_settingsSave'},
]},
{category:'sc_cat_edit',items:[
{win:'Ctrl + Z',mac:'⌘ + Z',i18n:'sc_undo'},
{win:'Ctrl + Y',mac:'⌘ + Y',i18n:'sc_redo'},
{win:'Ctrl + C',mac:'⌘ + C',i18n:'sc_copy'},
{win:'Ctrl + V',mac:'⌘ + V',i18n:'sc_paste'},
{win:'Delete / Backspace',mac:'Delete / Backspace',i18n:'sc_deleteLayer'},
]},
{category:'sc_cat_view',items:[
{win:'Ctrl + G',mac:'Ctrl + G',i18n:'sc_toggleGrid'},
{win:'Ctrl + L',mac:'Ctrl + L',i18n:'sc_toggleLayerPanel'},
{win:'Ctrl + K',mac:'Ctrl + K',i18n:'sc_toggleControls'},
{win:'Ctrl + B',mac:'Ctrl + B',i18n:'sc_toggleBottomBar'},
{win:'Ctrl + P',mac:'⌘ + P',i18n:'sc_promptView'},
{win:'Ctrl + 8',mac:'Ctrl + 8',i18n:'sc_zoomIn'},
{win:'Ctrl + 9',mac:'Ctrl + 9',i18n:'sc_zoomOut'},
{win:'Ctrl + 0',mac:'Ctrl + 0',i18n:'sc_zoomReset'},
]},
{category:'sc_cat_object',items:[
{winI18n:'sc_arrowKeys',macI18n:'sc_arrowKeys',i18n:'sc_moveObject'},
{winI18n:'sc_shiftArrow',macI18n:'sc_shiftArrow',i18n:'sc_moveObjectFast'},
{win:'Ctrl + ↑',mac:'⌘ + ↑',i18n:'sc_layerUp'},
{win:'Ctrl + ↓',mac:'⌘ + ↓',i18n:'sc_layerDown'},
]},
{category:'sc_cat_other',items:[
{win:'Escape',mac:'Escape',i18n:'sc_deselect'},
{win:'F1',mac:'F1',i18n:'sc_shortcutPage'},
]},
];

var shortcutFocusTrap=null;
function openShortcutModal(){
var container=$('shortcutGrid');
container.innerHTML='';
var leftCol=document.createElement('div');
leftCol.className='shortcut-column';
var rightCol=document.createElement('div');
rightCol.className='shortcut-column';
shortcutCategories.forEach(function(cat,idx){
var catDiv=document.createElement('div');
catDiv.className='sc-category';
var title=document.createElement('div');
title.className='sc-category-title';
title.textContent=i18next.t(cat.category);
catDiv.appendChild(title);
var items=document.createElement('div');
items.className='sc-category-items';
cat.items.forEach(function(item){
var itemDiv=document.createElement('div');
itemDiv.className='sc-item';
var keySpan=document.createElement('span');
keySpan.className='sc-key';
if(item.winI18n){
keySpan.textContent=i18next.t(isMacOs?item.macI18n:item.winI18n);
}else{
keySpan.textContent=isMacOs?item.mac:item.win;
}
var funcSpan=document.createElement('span');
funcSpan.className='sc-func';
funcSpan.textContent=i18next.t(item.i18n);
itemDiv.appendChild(keySpan);
itemDiv.appendChild(funcSpan);
items.appendChild(itemDiv);
});
catDiv.appendChild(items);
if(idx<3){
leftCol.appendChild(catDiv);
}else{
rightCol.appendChild(catDiv);
}
});
container.appendChild(leftCol);
container.appendChild(rightCol);
var modal=$('shortcutModal');
modal.style.display='flex';
shortcutFocusTrap=FocusTrap.create(modal,closeShortcutModal);
FocusTrap.activate(shortcutFocusTrap);
}

function closeShortcutModal(){
FocusTrap.deactivate(shortcutFocusTrap);
shortcutFocusTrap=null;
$('shortcutModal').style.display='none';
}

// bind enter key for crop / part scale completion
hotkeys('enter','all',function (e) {
if (cropFrame) {
completeCrop();
e.preventDefault();
}else if (ModeManager.partScale.isActive()) {
PartScale.next();
e.preventDefault();
}
});

// bind fast move shortcuts (10px)
hotkeys(hotkeysMap.moveLeftFast,'all',function (e) {
moveActiveObjectFast('left',e);
});

hotkeys(hotkeysMap.moveRightFast,'all',function (e) {
moveActiveObjectFast('right',e);
});

hotkeys(hotkeysMap.moveUpFast,'all',function (e) {
moveActiveObjectFast('up',e);
});

hotkeys(hotkeysMap.moveDownFast,'all',function (e) {
moveActiveObjectFast('down',e);
});



/**
 * @description Move the active object in the canvas
 * @param {*} direction 
 */
function moveActiveObject(direction,e) {
var activeObject=canvas.getActiveObject();
if (activeObject&&isNotVisibleFloatingWindow()) {
if (!isLongPressDirection) {
activeObjectMoveStep=isGridVisible ? gridSize : 1;
} else {
// increase the step by 1 each time the long press is detected
activeObjectMoveStep=activeObjectMoveStep+=1;
}
if (!longPressTimer) {
longPressTimer=window.setTimeout(function () {
isLongPressDirection=true;
},500);
}
switch (direction) {
case 'left':
activeObject.left-=activeObjectMoveStep;
break;
case 'up':
activeObject.top-=activeObjectMoveStep;
break;
case 'right':
activeObject.left+=activeObjectMoveStep;
break;
case 'down':
activeObject.top+=activeObjectMoveStep;
break;
}
activeObject.setCoords();
canvas.renderAll();
commitHistoryDebounced();
e.preventDefault();
}
}

/**
 * @description Move the active object fast (10px) in the canvas
 * @param {*} direction
 */
function moveActiveObjectFast(direction,e) {
var activeObject=canvas.getActiveObject();
if (activeObject&&isNotVisibleFloatingWindow()) {
var step=10;
switch (direction) {
case 'left':
activeObject.left-=step;
break;
case 'up':
activeObject.top-=step;
break;
case 'right':
activeObject.left+=step;
break;
case 'down':
activeObject.top+=step;
break;
}
activeObject.setCoords();
canvas.renderAll();
commitHistoryDebounced();
e.preventDefault();
}
}

document.addEventListener('keyup',function (event) {
if (longPressTimer) {
window.clearTimeout(longPressTimer);
longPressTimer=0;
activeObjectMoveStep=0;
}
});

// 文字を打っている最中かどうかの判定。ショートカットの効く条件はこれ1つに揃える。
// DIV を丸ごと除外していたため、フォーカスがDIVにあると Ctrl+Z だけ効かなかった。
// 実際に文字が入るのは編集可能なとき（contentEditable、readOnlyでない入力欄）だけなので、
// タグ名ではなく編集できるかどうかで判定する
function isEditableTagsActive(element) {
const activeElement=element||document.activeElement;
if (!activeElement) {
return false;
}
if (activeElement.isContentEditable) {
return true;
}
const tagName=activeElement.tagName;
if (tagName==='INPUT'||tagName==='TEXTAREA'||tagName==='SELECT') {
// レイヤー名の欄はダブルクリックするまで readOnly。読むだけの状態は打鍵中ではない
return!activeElement.readOnly;
}
return false;
}

// 今画面に見えている範囲の中央を、キャンバス座標で返す。
// #canvas-container は transform:scale で拡大され、スクロールするのは
// #resizable-container なので、画面上の矩形どうしの重なりから求める
function getVisibleCanvasCenter() {
const canvasRect=canvas.getElement().getBoundingClientRect();
const viewportRect=getScrollContainer().getBoundingClientRect();
const scale=getCanvasDisplayScale();
const left=Math.max(canvasRect.left,viewportRect.left);
const right=Math.min(canvasRect.right,viewportRect.right);
const top=Math.max(canvasRect.top,viewportRect.top);
const bottom=Math.min(canvasRect.bottom,viewportRect.bottom);
// 拡大してキャンバスが画面の外まで送られていると重なりが無くなる。その時はキャンバスの中央
if (!(right>left)||!(bottom>top)) {
return {x: canvas.getWidth()/2,y: canvas.getHeight()/2};
}
return {
x: ((left+right)/2-canvasRect.left)/scale,
y: ((top+bottom)/2-canvasRect.top)/scale
};
}

// コマに入れない貼り付け。キャンバス左上1/4に置いていたため、
// 拡大やスクロールをしていると画面の外に出て見つけられなかった
function placePastedImageOnCanvas(img) {
const center=getVisibleCanvasCenter();
const scaleToFit=Math.min((canvas.getWidth()/2)/img.width,(canvas.getHeight()/2)/img.height);
img.set({
scaleX: scaleToFit,
scaleY: scaleToFit,
left: center.x-(img.width*scaleToFit)/2,
top: center.y-(img.height*scaleToFit)/2,
});
canvas.add(img);
canvas.setActiveObject(img);
canvas.renderAll();
updateLayerPanel();
saveStateByManual();
}

document.addEventListener("paste",function (event) {
const items=event.clipboardData.items;
for (let i=0;i<items.length;i++) {
if (items[i].kind==="file"&&items[i].type.startsWith("image/")) {
const blob=items[i].getAsFile();
const reader=new FileReader();

reader.onload=function (event) {
const data=event.target.result;
fabric.Image.fromURL(data,function (img) {
const activeObject=canvas.getActiveObject();
// 選択中が何であってもその中へ入れようとしていたため、テキストや吹き出しを
// 選んだまま貼ると、コマでないものの形で切り抜かれてリンクが張られた。
// コマを選んでいるときだけコマへ入れる
if (activeObject&&isPanel(activeObject)) {
const x=
activeObject.left+
(activeObject.width*activeObject.scaleX)/2;
const y=
activeObject.top+
(activeObject.height*activeObject.scaleY)/2;
putImageInFrame(img,x,y,false,false,true,activeObject);
return;
}
placePastedImageOnCanvas(img);
});
};
reader.readAsDataURL(blob);
}
}
});

canvas.on('mouse:down',function(options) {
if (!options.target) {
canvas.discardActiveObject();
canvas.requestRenderAll();
}
});
