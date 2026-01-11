var neonIntensity=2;
var isNeonEnabled=false;

function updateTextControls(object) {

// console.log("isVerticalText ", typeof window.isVerticalText); 

if (isVerticalText(object)) {
if (object.fill) {
return;
} else {
let hexColor=rgbToHex(object.fill);
$('textColorPicker').value=hexColor;
}
} else if (isText(object)) {
if (object.fill) {
return;
} else {
let hexColor=rgbToHex(object.fill);
$('textColorPicker').value=hexColor;
}
$('fontSizeSlider').value=object.fontSize;
}
}

function applyCSSTextEffect() {
var firstTextEffectColorPicker=$('firstTextEffectColorPicker').value;
var secondTextEffectColorPicker=$('secondTextEffectColorPicker').value;

const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
if (!activeObject.shadow) {
// Apply a shadow using the first color picker's value
activeObject.set("shadow",firstTextEffectColorPicker+" 5px 5px 10px");
} else {
// Toggle shadow off
activeObject.set("shadow",null);
}
canvas.renderAll();
}
}


function applyVividGradientEffect() {
const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
var firstTextEffectColorPicker=$('firstTextEffectColorPicker').value;
var secondTextEffectColorPicker=$('secondTextEffectColorPicker').value;

const gradient=new fabric.Gradient({
type: "linear",
gradientUnits: "pixels",
coords: {x1: 0,y1: activeObject.height/2,x2: activeObject.width,y2: activeObject.height/2},
colorStops: [
{offset: 0,color: firstTextEffectColorPicker},
{offset: 0.5,color: secondTextEffectColorPicker,opacity: 0.5},
{offset: 1,color: firstTextEffectColorPicker}
]
});

if (isVerticalText(activeObject)) {
activeObject.set("fill",gradient);
canvas.renderAll();
} else {
activeObject.set("fill",gradient);
canvas.renderAll();
}
}
}

function applyInnerShadow() {
const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
if (!activeObject.shadow) {
activeObject.set({
shadow: {
color: "rgba(0, 0, 0, 0.8)",
blur: 10,
offsetX: 5,
offsetY: 5,
},
});
} else {
activeObject.set("shadow",null);
}
canvas.renderAll();
}
}


function drawNeonJitterEffect(textObject) {
const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
const gradient=new fabric.Gradient({
type: "linear",
gradientUnits: "pixels",
coords: {x1: 0,y1: 0,x2: canvas.width,y2: 0},
colorStops: [
{offset: 0,color: "red"},
{offset: 0.15,color: "orange"},
{offset: 0.3,color: "yellow"},
{offset: 0.5,color: "green"},
{offset: 0.65,color: "blue"},
{offset: 0.8,color: "indigo"},
{offset: 1,color: "violet"},
],
});
activeObject.set("fill",gradient);

// Jitter Effect
activeObject.initDimensions();
for (let i=0;i<10;i++) {
activeObject.clone(function (clonedText) {
clonedText.set({
shadow: `rgba(${255 * Math.random()}, ${255 * Math.random()}, ${255 * Math.random()
            }, 0.5) 10px 10px 10px`,
});
clonedText.set({
left: activeObject.left+Math.random()*5,
top: activeObject.top+Math.random()*5,
});
canvas.add(clonedText);
});
}
}
}



function applyInnerShadow() {
const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
activeObject.set({
shadow: {
color: "rgba(0, 0, 0, 0.8)",
blur: 10,
offsetX: 5,
offsetY: 5,
},
});
canvas.renderAll();
}
}

function applyNeonEffect() {
const activeObject=canvas.getActiveObject();
if (isText(activeObject)) {

var firstTextEffectColorPicker=$('firstTextEffectColorPicker').value;
var secondTextEffectColorPicker=$('secondTextEffectColorPicker').value;

if (!activeObject.fill||!activeObject.shadow) {
activeObject.set({
fill: firstTextEffectColorPicker,
shadow: {
color: secondTextEffectColorPicker,
blur: 20,
},
});
}
canvas.renderAll();
}
}

function alignText(alignment,button) {
var textAlignment=getSelectedValueByButton(button);
var activeObject=canvas.getActiveObject();

if(isVerticalText(activeObject)){
switch(alignment){
case "left":
textAlignment="top";
break
case "center":
textAlignment="middle";
break
case "right":
textAlignment="bottom";
break
}
activeObject.set('verticalAlign',textAlignment);
activeObject.set('dirty',true);
}else if(isText(activeObject)){
activeObject.set('textAlign',alignment);
}
canvas.renderAll();

changeSelected(button);
}

function createTextbox() {
var selectedFont=fontManager.getSelectedFont("fontSelector");
var fontsize=$("fontSizeSlider").value
var fontStrokeWidth=$("fontStrokeWidthSlider").value

console.log("selectedFont",selectedFont)
const selectedValue=getSelectedValueByGroup("align_group");
var textbox=new fabric.Textbox("New",{
top: 50,
left: 50,
fontSize: parseInt(fontsize),
fontFamily: selectedFont,
fill: $("textColorPicker").value,
stroke: $("textOutlineColorPicker").value,
strokeWidth: parseInt(fontStrokeWidth),
textAlign: selectedValue,

cornerSize: 8,
transparentCorners: false,
cornerStyle: 'circle',
borderScaleFactor: 2,
padding: 10,
});

textbox.on('text:changed',function () {
textbox.set({fontFamily: selectedFont});
canvas.requestRenderAll();
});

canvas.add(textbox);
canvas.setActiveObject(textbox);
canvas.requestRenderAll();
// updateLayerPanel();
}

function toggleShadow() {
var activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
var hasShadow=activeObject.shadow!=null;
activeObject.set(
"shadow",
hasShadow ? null : "rgba(0,0,0,0.3) 5px 5px 5px"
);
canvas.renderAll();
}
}

function toggleBold() {
var activeObject=canvas.getActiveObject();

if (isVerticalText(activeObject)) {
activeObject.getObjects().forEach(function (obj) {
if (obj.type==='text') {
var isBold=obj.fontWeight==="bold";
obj.set("fontWeight",isBold ? "" : "bold");
}
});
canvas.renderAll();
} else if (isText(activeObject)) {
var isBold=activeObject.fontWeight==="bold";
activeObject.set("fontWeight",isBold ? "" : "bold");
canvas.renderAll();
}
}

function changeFontSize(size) {
var activeObject=canvas.getActiveObject();
if(isSpeechBubbleText(activeObject)){
activeObject.set("fontSize",parseInt(size));
let newSettings=mainSpeechBubbleObjectResize(activeObject);
const svgObj=activeObject.targetObject;
svgObj.set(newSettings);
updateShapeMetrics(svgObj);
}else if (isText(activeObject)) {
activeObject.set("fontSize",parseInt(size));
}
canvas.renderAll();
}

function changeStrokeWidthSize(size) {
var activeObject=canvas.getActiveObject();
if (isVerticalText(activeObject)) {
activeObject.set("strokeWidth",parseInt(size));
canvas.renderAll();
} else if (isText(activeObject)) {
activeObject.set("strokeWidth",parseInt(size));
canvas.renderAll();
}
}


function changeTextColor(color) {
var activeObject=canvas.getActiveObject();

if (isVerticalText(activeObject)) {
activeObject.set("fill",color);
canvas.renderAll();
} else if (isText(activeObject)) {
activeObject.set("fill",color);
canvas.renderAll();
}
}
function changeOutlineTextColor(color) {
var activeObject=canvas.getActiveObject();

if (isVerticalText(activeObject)) {
activeObject.set("stroke",color);
canvas.renderAll();
} else if (isText(activeObject)) {
activeObject.set("stroke",color);
canvas.renderAll();
}
}

function changeNeonColor(color) {
neonColor=color;
var activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
updateNeonEffect(activeObject);
}
}

function changeNeonIntensity(intensity) {
neonIntensity=parseFloat(intensity);
var activeObject=canvas.getActiveObject();
if (isText(activeObject)) {
updateNeonEffect(activeObject);
}
}

function updateNeonEffect(activeObject) {
if (isText(activeObject)) {
if (!isNeonEnabled) {
activeObject.set("shadow",null);
activeObject.set("stroke",null);
} else {
var neonColor=$("firstTextEffectColorPicker").value;
activeObject.set(
"shadow",
new fabric.Shadow({
color: neonColor,
blur: neonIntensity,
offsetX: 0,
offsetY: 0,
affectStroke: false,
opacity: neonIntensity,
})
);
activeObject.set("stroke",neonColor);
activeObject.set("strokeWidth",2);
}
canvas.renderAll();
}
}



function changeFont(font) {
$("text-preview-area").style.fontFamily=font;
}



function isFontAvailableForLanguage(font,text) {
const canvas=document.createElement('canvas');
const context=canvas.getContext('2d');
context.font='72px monospace';
const baselineSize=context.measureText(text).width;
context.font=`72px ${font}, monospace`;
const newSize=context.measureText(text).width;
return newSize!==baselineSize;
}
