const languageSelector=$('fabricjs-language-selector');
let lastClickType=null;
let objectMenu=null;
let canvasMenuIndex=100000;

function createObjectMenu() {
if (objectMenu) {
objectMenu.remove();
}
objectMenu=document.createElement('div');
objectMenu.className='fabricjs-object-menu';
objectMenu.style.display='none';
document.body.appendChild(objectMenu);
objectMenu.addEventListener('click',handleMenuClick);
objectMenu.addEventListener('input',handleSliderInput);
}


function updateObjectMenuPosition() {
if (!objectMenu) {
return;
}
const activeObject=canvas.getActiveObject();
if (!activeObject) {
return;
}

const boundingRect=activeObject.getBoundingRect(true,true);
const menuPadding=20;
const canvasRect=canvas.getElement().getBoundingClientRect();
const canvasOffsetLeft=canvasRect.left;
const canvasOffsetTop=canvasRect.top;
const canvasWidth=canvasRect.width;
const canvasHeight=canvasRect.height;

let left=canvasOffsetLeft+boundingRect.left*canvasContinerScale+boundingRect.width*canvasContinerScale+menuPadding;
let top=canvasOffsetTop+boundingRect.top*canvasContinerScale;

if (left+objectMenu.offsetWidth>canvasOffsetLeft+canvasWidth) {
left=Math.min(
canvasOffsetLeft+canvasWidth+5,
window.innerWidth-objectMenu.offsetWidth
);
} else if (left<canvasOffsetLeft) {
left=Math.max(canvasOffsetLeft-5,0);
}

top=Math.max(top,canvasOffsetTop-5);
if (top+objectMenu.offsetHeight>canvasOffsetTop+canvasHeight) {
top=Math.min(
canvasOffsetTop+canvasHeight+5,
window.innerHeight-objectMenu.offsetHeight
);
}

objectMenu.style.left=`${left}px`;
objectMenu.style.top=`${top}px`;
}

function createObjectMenuDiv(itemValue){
return {type:'div',value:itemValue};
}
function createObjectMenuButton(itemValue){
return {type:'button',value:itemValue};
}
function createObjectMenuSlider(itemValue,min,max,step,value){
return {type: 'slider',label: itemValue,
options: {id:itemValue,min: min,max:max,step:step,value:value}};
}
function createObjectMenuColor(itemValue,defaultColor,rgba) {
return {
type: 'colorpicker',label: itemValue,
options: {id: itemValue,
value: defaultColor||'#000000',
rgba:rgba
}
};
}


function showObjectMenu(clickType) {
const activeObject=canvas.getActiveObject();
if (!activeObject) {
return;
}
if (!objectMenu) {
createObjectMenu();
}

let menuItems=[];
var visible=createObjectMenuButton(activeObject.visible    ? 'visibleOff' : 'visibleOn');
var movement=createObjectMenuButton(!activeObject.selectable ? 'movementOn' : 'movementOff');
var edit=createObjectMenuButton(activeObject.edit       ? 'editOff' : 'editOn');
var knife=createObjectMenuButton(isKnifeMode             ? 'knifeOff' : 'knifeOn');
var deleteMenu=createObjectMenuButton('delete');
var generate=createObjectMenuButton('generate');
var panelIn=createObjectMenuButton('panelIn');
var panelInNotFit=createObjectMenuButton('panelInNotFit');
var canvasFit=createObjectMenuButton('canvasFit');
var selectClear=createObjectMenuButton('selectClear');
var rembg=createObjectMenuButton('rembg');
var clearAllClipPaths=createObjectMenuButton('clearAllClipPaths');

var clearTopClipPath=createObjectMenuButton('clearTopClipPath');
var clearBottomClipPath=createObjectMenuButton('clearBottomClipPath');
var clearRightClipPath=createObjectMenuButton('clearRightClipPath');
var clearLeftClipPath=createObjectMenuButton('clearLeftClipPath');

var flipHorizontal=createObjectMenuButton('flipHorizontal');
var flipVertical=createObjectMenuButton('flipVertical');

var font=createObjectMenuDiv('fontSelectorMenu');

let fillTemp=null;
let strokeWidthTemp=null;
let strokeTemp=null;
if(isSpeechBubbleSVG(activeObject)){
fillTemp=getSpeechBubbleTextFill(activeObject,"fill");
strokeWidthTemp=getSpeechBubbleTextFill(activeObject,"strokeWidth");
strokeTemp=getSpeechBubbleTextFill(activeObject,"stroke");
}else{
fillTemp=activeObject.fill;
strokeWidthTemp=activeObject.strokeWidth;
strokeTemp=activeObject.stroke;
}


let min=0,max=100,step=1,value=(activeObject.opacity*100),labelAndId='com-opacity';
let opacity=createObjectMenuSlider(labelAndId,min,max,step,value);

min=0,max=40,step=1,value=strokeWidthTemp,labelAndId='com-lineWidth';
let strokeWidth=createObjectMenuSlider(labelAndId,min,max,step,value);

min=7,max=150,step=1,value=activeObject.fontSize,labelAndId='com-fontSize';
let fontSize=createObjectMenuSlider(labelAndId,min,max,step,value);

uiLogger.debug("fillTemp",fillTemp);
let fillColor=createObjectMenuColor("com-fill",rgbaToHex(fillTemp),fillTemp);
uiLogger.debug("fillColor",fillColor);
let strokeColor=createObjectMenuColor("com-strokeColor",rgbaToHex(strokeTemp),strokeTemp);

if (isPanel(activeObject)) {
if (clickType!=='left') {
menuItems=[visible,movement,edit,knife];
if (hasRole(AI_ROLES.Text2Image)) menuItems.push(generate);
menuItems.push(deleteMenu);
}
} else if (isImage(activeObject)) {
if (clickType!=='left') {
menuItems=[visible,movement];
if (hasRole(AI_ROLES.Image2Image)) menuItems.push(generate);
if (hasRole(AI_ROLES.RemoveBG))    menuItems.push(rembg);
menuItems.push(deleteMenu);

if (haveClipPath(activeObject)) {
menuItems.push(clearAllClipPaths);

menuItems.push(clearTopClipPath);
menuItems.push(clearBottomClipPath);
menuItems.push(clearRightClipPath);
menuItems.push(clearLeftClipPath);

} else {
menuItems.push(panelIn);
menuItems.push(canvasFit);
}

menuItems.push(flipHorizontal);
menuItems.push(flipVertical);

}
}else if (isSpeechBubbleSVG(activeObject)||isSpeechBubbleText(activeObject)) {
menuItems=[visible];
menuItems.push(panelInNotFit);
}

if (isPanel(activeObject)||isSpeechBubbleSVG(activeObject)||isSpeechBubbleText(activeObject)||isText(activeObject)) {
menuItems.push(opacity);
menuItems.push(strokeWidth);
menuItems.push(fillColor);
menuItems.push(strokeColor);
}

if(isSpeechBubbleText(activeObject)||isText(activeObject)){
menuItems.push(fontSize);
menuItems.push(font);
}

menuItems.push(selectClear);
if (menuItems.length===0) {
return;
}

let menuContent='';
menuItems.forEach(item=>{
switch (item.type) {
case 'div':
menuContent+=`<div id="${item.value}"></div>`;
break;
case 'slider':
let label=getText(item.options.id);
menuContent+=`
          <div class="input-container-leftSpace" data-label="${label}">
            <input type="range" 
              id=   "${item.options.id}"
              name= "${item.options.id}"
              min=  "${item.options.min}"
              max=  "${item.options.max}"
              step= "${item.options.step}"
              value="${item.options.value}">
          </div>`;
break;
case 'colorpicker':
let labelColor=getText(item.options.id);
menuContent+=`
          <div class="input-group-multi" >
            <label for="${item.options.id}">${labelColor}</label>
            <input id=   "${item.options.id}"
              name= "${item.options.id}"
              value="${item.options.value}"
              class="jscolor-color-picker" data-initial-color="${item.options.rgba}">
          </div>`;
// console.log("menuContent",menuContent);
break;
case 'button':
menuContent+=`<button id="fabricjs-${item.value}-btn">${getText(item.value)}</button>`;
break;
}
});

objectMenu.innerHTML=menuContent;
jsColorSet();
objectMenu.classList.add('active');
objectMenu.style.display='flex';
updateObjectMenuPosition();
lastClickType=clickType;

const sliders2=document.querySelectorAll('.input-container-leftSpace input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container-leftSpace',false);
});
new FontSelector("fontSelectorMenu","Font");
}

function handleSliderInput(e) {
const activeObject=canvas.getActiveObject();
if (!activeObject) return;

// console.log("e.target.id:",e.target.id);
switch (e.target.id) {
case 'com-fontSize':
const fontSizeValue=parseInt(e.target.value);
activeObject.fontSize=fontSizeValue;

if(isSpeechBubbleText(activeObject)){
let newSettings=mainSpeechBubbleObjectResize(activeObject);
const svgObj=activeObject.targetObject;
svgObj.set(newSettings);
updateShapeMetrics(svgObj);
}
break
case 'com-opacity':
const opacityValue=parseInt(e.target.value);
activeObject.opacity=opacityValue/100;
break;
case 'com-lineWidth':
const strokeWidthValue=parseInt(e.target.value);
activeObject.set("strokeWidth",strokeWidthValue);
break;
case 'com-fill':
const fillColor=e.target.value;
activeObject.set("fill",fillColor);
break;
case 'com-strokeColor':
const strokeColor=e.target.value;
activeObject.set("stroke",strokeColor);
break;
}

if (isSpeechBubbleSVG(activeObject)) {
var bubbleStrokewidht=parseFloat($("com-lineWidth").value);
var fillColorsvg=$("com-fill").value;
var strokeColorsvg=$("com-strokeColor").value;
var opacity=$("com-opacity").value;
changeSpeechBubbleSVG(bubbleStrokewidht,fillColorsvg,strokeColorsvg,opacity);
}

canvas.requestRenderAll();
}


function handleMenuClick(e) {
const activeObject=canvas.getActiveObject();
if (!activeObject) {
return;
}

let clickedElement=e.target;
if (!clickedElement.matches('button')) {
return;
}

// console.log("handleMenuClick e.target.id:", e.target.id);
const action=e.target.id.replace('fabricjs-','').replace('-btn','');
if (!action) {
return;
}

switch (action) {
case 'flipHorizontal':
flipHorizontally();
break
case 'flipVertical':
flipVertically();
break
case 'fontSize':
const fontSizeValue=parseInt(e.target.value);
activeObject.fontSize=fontSizeValue;

if(isSpeechBubbleText(activeObject)){
let newSettings=mainSpeechBubbleObjectResize(activeObject);
const svgObj=activeObject.targetObject;
svgObj.set(newSettings);
updateShapeMetrics(svgObj);
}
break
case 'opacity':
const opacityValue=parseInt(e.target.value);
activeObject.opacity=opacityValue/100;
break;
case 'lineWidth':
const strokeWidthValue=parseInt(e.target.value);
activeObject.set("strokeWidth",strokeWidthValue);
break;
case 'canvasFit':
fitImageToCanvas(activeObject);
break;
case 'panelIn':
var canvasX=activeObject.left+(activeObject.width*activeObject.scaleX)/2;
var canvasY=activeObject.top+(activeObject.height*activeObject.scaleY)/2;
putImageInFrame(activeObject,canvasX,canvasY,true,true);
updateLayerPanel();
break;
case 'panelInNotFit':
var canvasX=activeObject.left+(activeObject.width*activeObject.scaleX)/2;
var canvasY=activeObject.top+(activeObject.height*activeObject.scaleY)/2;
putImageInFrame(activeObject,canvasX,canvasY,true,true,false);
updateLayerPanel();
break;
case 'visibleOn':
case 'visibleOff':
visibleChange(activeObject);
break;

case 'movementOn':
case 'movementOff':
moveLockChange(activeObject);
break;

case 'rembg':
var spinner=createSpinner(canvasMenuIndex);
aiRembg(activeObject,spinner);
break;
case 'generate':
if (isPanel(activeObject)) {
var spinner=createSpinner(canvasMenuIndex);
T2I(activeObject,spinner);
} else if (isImage(activeObject)) {
var spinner=createSpinner(canvasMenuIndex);
I2I(activeObject,spinner);
}
break;
case 'selectClear':
canvas.discardActiveObject();
canvas.requestRenderAll();
return;
case 'delete':
canvas.remove(activeObject);
canvas.renderAll();
updateLayerPanel();
return;
case 'copyAndPast':
activeObject.clone(function (cloned) {
cloned.set({
left: cloned.left+10,
top: cloned.top+10
});
canvas.add(cloned);
});
break;
case 'moveUp':
canvas.bringForward(activeObject);
break;
case 'moveDown':
canvas.sendBackwards(activeObject);
break;
case 'editOff':
case 'editOn':
if (isPanel(activeObject)) {
Edit();
}
break;

case 'knifeOff':
case 'knifeOn':
if (isPanel(activeObject)) {
changeKnifeMode();
}
break;
case 'addPoint':
if (activeObject instanceof fabric.Polygon) {
let points=activeObject.points;
let newPoint={
x: (points[0].x+points[1].x)/2,
y: (points[0].y+points[1].y)/2
};
points.splice(1,0,newPoint);
activeObject.set({points: points});
}
break;
case 'removePoint':
if (activeObject instanceof fabric.Polygon&&activeObject.points.length>3) {
let points=activeObject.points;
points.pop();
activeObject.set({points: points});
}
break;

case 'clearAllClipPaths':
case 'clearTopClipPath':
case 'clearBottomClipPath':
case 'clearRightClipPath':
case 'clearLeftClipPath':
removeClipPath(activeObject,action);
break;
}
canvas.requestRenderAll();
closeMenu();
}

function closeMenu() {
if (objectMenu) {
objectMenu.classList.remove('active');
objectMenu.style.display='none';
}
}

canvas.wrapperEl.addEventListener('contextmenu',function (e) {
e.preventDefault();
const pointer=canvas.getPointer(e);
const clickedObject=canvas.findTarget(e,false);
if (clickedObject) {
canvas.setActiveObject(clickedObject);
canvas.renderAll();
showObjectMenu('right');
} else {
canvas.discardActiveObject();
closeMenu();
}
});

canvas.wrapperEl.addEventListener('mousedown',function (e) {
if (e.button===0&&lastClickType==='right') {
closeMenu();
lastClickType='left';
}
});

createObjectMenu();