/**
 * knife-mode.js
 * ナイフモードの切替とUI管理
 */

/**
 * DOMContentLoadedイベントでボタンにイベントリスナーを設定
 */
document.addEventListener("DOMContentLoaded",function () {
$("knifeModeButton").addEventListener("click",function () {
changeKnifeMode();
});
});

/**
 * ナイフモードを切り替え
 */
function changeKnifeMode() {
isKnifeMode=!isKnifeMode;
updateKnifeMode();
}

/**
 * ナイフモードのUIを更新
 */
function updateKnifeMode() {
var knifeModeButton=$("knifeModeButton");
knifeModeButton.textContent=isKnifeMode
? getText("knifeOff")
: getText("knifeOn");

if (isKnifeMode) {
if(currentMode==="freehand"||currentMode==="point"){
sbClear();
sbClearControlePoints();
points=[];
}
currentMode="select";
activeClearButton();
knifeModeButton.classList.add("selected");
changeCursor("knife");
knifeModeButton.textContent=getText("knifeOff");
} else {
nonActiveClearButton();
knifeModeButton.classList.remove("selected");
changeDefaultCursor();
knifeModeButton.textContent=getText("knifeOn");
// ナイフモード解除時にアニメーションを停止し線を削除
if (currentKnifeLine) {
stopKnifeLineAnimation();
setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}
}
changeMovement();
}

/**
 * オブジェクトの移動可否を切り替え
 */
function changeMovement() {
canvas.discardActiveObject();
canvas.selection=!isKnifeMode;

canvas.forEachObject(function (obj) {
if (isKnifeMode) {
obj.set({
selectable: false,
});
} else {
obj.set({
selectable: true,
});
}
});
canvas.renderAll();
}
