// 選択中オブジェクトの値を各パネルへ反映する。
// 同じ設定が複数のパネルに存在するため、1箇所で変更した値が他のパネルに
// 反映されないと、次にそのパネルを触ったときに表示されている古い値へ飛ぶ

function setSyncedColorPicker(id,color){
var picker=$(id);
if(!picker||!color||typeof color!=='string'){
return;
}
if(picker.jscolor){
picker.jscolor.fromString(color);
}else{
picker.value=rgbToHex(color);
}
}

function setSyncedValue(id,value){
var element=$(id);
if(!element||value===undefined||value===null){
return;
}
element.value=value;
}

function syncPanelControls(activeObject){
if(!isPanel(activeObject)){
return;
}
setSyncedColorPicker('panelStrokeColor',activeObject.stroke);
setSyncedColorPicker('panelFillColor',activeObject.fill);
setSyncedValue('panelStrokeWidth',activeObject.strokeWidth);
if(activeObject.opacity!==undefined){
setSyncedValue('panelOpacity',Math.round(activeObject.opacity*100));
}
}

function syncSpeechBubbleControls(activeObject){
if(!isSpeechBubbleSVG(activeObject)){
return;
}
setSyncedColorPicker('sbStrokeColor',activeObject.stroke);
setSyncedColorPicker('sbFillColor',activeObject.fill);
setSyncedValue('sbStrokeWidth',activeObject.strokeWidth);
}

// 選択変更時と、いずれかのパネルで値を変更した直後に呼ぶ
function syncObjectControls(activeObject){
if(!activeObject){
activeObject=canvas.getActiveObject();
}
if(!activeObject){
return;
}
updateControls(activeObject);
updateTextControls(activeObject);
syncPanelControls(activeObject);
syncSpeechBubbleControls(activeObject);
syncImageTextControls(activeObject);
}
