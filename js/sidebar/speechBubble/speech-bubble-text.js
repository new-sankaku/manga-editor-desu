function sbTextChange(alignment,button) {
changeSelected(button);
}

let textFrameScaling=1.0;

function parseSvg(svgString) {
const parser=new DOMParser();
const doc=parser.parseFromString(svgString,"text/xml");
const svg=doc.querySelector("svg");

const viewBoxValues=svg.getAttribute("viewBox").split(" ").map(Number);
const viewBox={
x: viewBoxValues[0],
y: viewBoxValues[1],
width: viewBoxValues[2],
height: viewBoxValues[3],
};
const canvas=document.createElement("canvas");
const ctx=canvas.getContext("2d",{willReadFrequently: true});
canvas.width=viewBox.width;
canvas.height=viewBox.height;

const totalArea=viewBox.width*viewBox.height;
const elements=svg.querySelectorAll("path, polygon");
const paths=Array.from(elements).map((element)=>{
ctx.clearRect(0,0,canvas.width,canvas.height);

let pathD;
if (element.tagName==="polygon") {
const points=element.getAttribute("points").trim().split(/\s+/);
pathD=`M ${points[0]} ${points[1]} `+
points.slice(2).reduce((acc,point,i)=>
acc+(i%2===0 ? `L ${point} ` : `${point} `),'')+'Z';
} else {
pathD=element.getAttribute("d");
}

const pathObj=new Path2D(pathD);
ctx.fill(pathObj);

const imageData=ctx.getImageData(0,0,canvas.width,canvas.height);
const filledPixels=imageData.data.filter(
(_,i)=>i%4===3&&imageData.data[i]>0
).length;
const area=filledPixels;

return {
type: "path",
d: pathD,
class: element.getAttribute("class"),
area: area,
};
});

const threshold=totalArea*0.3;
const validPaths=paths.filter((path)=>path.area>=threshold);
if (validPaths.length===0) {
throw new Error("No paths with sufficient area found");
}

const selectedPath=validPaths.reduce((min,current)=>
current.area<min.area ? current : min
);

return {
viewBox,
pathData: {
type: "path",
d: selectedPath.d
},
};
}


let lastRequest=null;

function updateShapeMetrics(svgObj) {
// console.log("updateShapeMetrics call");
const rect=getSpeechBubbleRectBySVG(svgObj);
const textbox=getSpeechBubbleTextBySVG(svgObj);

let grid,scale,viewBox,largestRect;
grid=svgObj.speechBubbleGrid;
scale=svgObj.speechBubbleScale;
viewBox={
width: svgObj.speechBubbleViewBoxWidth,
height: svgObj.speechBubbleViewBoxHeight,
};
largestRect={
x: svgObj.speechBubbleRectX,
y: svgObj.speechBubbleRectY,
width: svgObj.speechBubbleRectWidth,
height: svgObj.speechBubbleRectHeight,
};

const scaleWidth=svgObj.scaleX*(svgObj.width/viewBox.width);
const scaleHeight=svgObj.scaleY*(svgObj.height/viewBox.height);

const rectWidth=largestRect.width/scale;
const rectHeight=largestRect.height/scale;
const rectX=largestRect.x/scale;
const rectY=largestRect.y/scale;

rect.set({
left: svgObj.left+rectX*scaleWidth,
top: svgObj.top+rectY*scaleHeight,
width: rectWidth*scaleWidth,
height: rectHeight*scaleHeight,
});

if (isVerticalText(textbox)) {
let left=0;
left=svgObj.left+rectX*scaleWidth+(rectWidth*scaleWidth)/2;

textbox.set({
left: left,
height: rectHeight*scaleHeight
});
textbox.updateDimensions();
textbox.set({left: left});
} else if (isHorizontalText(textbox)) {
textbox.set({
left: svgObj.left+rectX*scaleWidth+(rectWidth*scaleWidth)/2,
top: svgObj.top+rectY*scaleHeight+(rectHeight*scaleHeight)/2,
width: rectWidth*scaleWidth,
evented: true,
selectable: true,
editable: true,

});
}
saveInitialState(rect);
saveInitialState(textbox);
// console.log("updateShapeMetrics", textbox.guid, textbox.left);

textbox.setCoords();
svgObj.lastLeft=svgObj.left;
svgObj.lastTop=svgObj.top;
canvas.renderAll();
}

function createSpeechBubbleMetrics(svgObj,svgData) {
// console.log("createSpeechBubbleMetrics call");

let grid,scale,viewBox,largestRect;
({grid,scale,viewBox}=createGrid(svgData));
svgObj.speechBubbleGrid=grid;
svgObj.speechBubbleScale=scale;
svgObj.speechBubbleViewBoxWidth=viewBox.width;
svgObj.speechBubbleViewBoxHeight=viewBox.height;

largestRect=findLargestRectangle(grid);
svgObj.speechBubbleRectX=largestRect.x;
svgObj.speechBubbleRectY=largestRect.y;
svgObj.speechBubbleRectWidth=largestRect.width;
svgObj.speechBubbleRectHeight=largestRect.height;

svgObj.lockRotation=true;
svgObj.hasControls=true;
svgObj.setControlsVisibility({
mt: true,
mb: true,
ml: true,
mr: true,
bl: true,
br: true,
tl: true,
tr: true,
mtr: false
});

const scaleWidth=svgObj.scaleX*(svgObj.width/viewBox.width);
const scaleHeight=svgObj.scaleY*(svgObj.height/viewBox.height);

const rectWidth=largestRect.width/scale;
const rectHeight=largestRect.height/scale;
const rectX=largestRect.x/scale;
const rectY=largestRect.y/scale;

const newRect=new fabric.Rect({
left: svgObj.left+rectX*scaleWidth,
top: svgObj.top+rectY*scaleHeight,
width: rectWidth*scaleWidth,
height: rectHeight*scaleHeight,
fill: "transparent",
stroke: "transparent",
selectable: false,
hasControls: true,
targetObject: svgObj,
excludeFromLayerPanel: true,
evented: false,
lockRotation: true

});

let newTextbox=null;
const selectedValue=getSelectedValueByGroup("sbTextGroup");
let isSbVerticalText=false;
if (selectedValue==="Horizontal") {
isSbVerticalText=false;
} else {
isSbVerticalText=true;
}

var selectedFont=fontManager.getSelectedFont("fontSelector");
var fontsize=$("fontSizeSlider").value
var fontStrokeWidth=$("fontStrokeWidthSlider").value

if (isSbVerticalText) {
let style={
left: svgObj.left+rectX*scaleWidth+(rectWidth*scaleWidth)/2,
top: svgObj.top+rectY*scaleHeight+(rectHeight*scaleHeight)/2,

fontFamily: selectedFont,
fontSize: parseInt(fontsize),
fill: $("textColorPicker").value,
stroke: $("textOutlineColorPicker").value,
strokeWidth: parseInt(fontStrokeWidth),

textAlign: "center",
originX: "center",
originY: "center",
height: rectWidth*scaleWidth,
selectable: true,
movable: false,
hasControls: false,
lockMovementX: true,
lockMovementY: true,
lockRotation: true,
lockScalingX: true,
lockScalingY: true,
lockRotation: true,
editable: true,
evented: true,
renderOnAddRemove: true,
targetObject: svgObj,
};
newTextbox=new VerticalTextbox("new",style);
} else {
newTextbox=new fabric.Textbox(
`${Math.round(rectWidth * scaleWidth)}x${Math.round(
        rectHeight * scaleHeight
      )}`,
{
left: svgObj.left+rectX*scaleWidth+(rectWidth*scaleWidth)/2,
top: svgObj.top+rectY*scaleHeight+(rectHeight*scaleHeight)/2,

fontFamily: selectedFont,
fontSize: parseInt(fontsize),
fill: $("textColorPicker").value,
stroke: $("textOutlineColorPicker").value,
strokeWidth: parseInt(fontStrokeWidth),

textAlign: "center",
originX: "center",
originY: "center",
width: rectWidth*scaleWidth,
selectable: true,
movable: false,
hasControls: false,
lockMovementX: true,
lockMovementY: true,
lockRotation: true,
lockScalingX: true,
lockScalingY: true,
lockRotation: true,
editable: true,
evented: true,
renderOnAddRemove: true,
targetObject: svgObj,
}
);
}

svgObj.guid=generateGUID();
newTextbox.guid=generateGUID();
newRect.guid=generateGUID();

setGUID(svgObj,newTextbox);
setGUID(svgObj,newRect);

svgObj.customType="speechBubbleSVG";
newTextbox.customType="speechBubbleText";
newRect.customType="speechBubbleRect";

// console.log("createSpeechBubbleMetrics", newTextbox.guid, newTextbox.left);

svgObj.lastLeft=svgObj.left;
svgObj.lastTop=svgObj.top;

changeDoNotSaveHistory();
// canvas.sendToBack(svgObj);
canvas.add(newRect);
changeDoSaveHistory();

canvas.add(newTextbox);

// canvas.bringToFront(newTextbox);
canvas.renderAll();
}

function updateObjectPositions(svgObject,immediate=false) {
if (!immediate) {
if (lastRequest) cancelAnimationFrame(lastRequest);
lastRequest=requestAnimationFrame(()=>
updateObjectPositionsImpl(svgObject)
);
} else {
updateObjectPositionsImpl(svgObject);
}
}

function updateObjectPositionsImpl(svgObject) {
const rect=getSpeechBubbleRectBySVG(svgObject);
const textbox=getSpeechBubbleTextBySVG(svgObject);

if (!rect||!textbox) return;
const diff={
left: svgObject.left-svgObject.lastLeft,
top: svgObject.top-svgObject.lastTop,
};
if (diff.left===0&&diff.top===0) return;
rect.set({
left: rect.left+diff.left,
top: rect.top+diff.top,
});
textbox.set({
left: textbox.left+diff.left,
top: textbox.top+diff.top,
evented: true,
selectable: true,
editable: true,
});

//  console.log("updateObjectPositionsImpl textbox", textbox.guid, textbox.left);
//  console.log("updateObjectPositionsImpl rect   ", rect.guid, rect.left);

saveInitialState(rect);
saveInitialState(textbox);

svgObject.lastLeft=svgObject.left;
svgObject.lastTop=svgObject.top;

textbox.setCoords();
canvas.setActiveObject(textbox);
canvas.renderAll();
}

function mainSpeechBubbleObjectResize(textObj) {
let newSettings=null;
if (isVerticalText(textObj)) {
const svgObj=textObj.targetObject;
const rect=getSpeechBubbleRectBySVG(svgObj);
if (rect) {
const textHeight=textObj.calcTextHeight();
const textWidth=textObj.calcTextWidth();

let scaleX=svgObj.scaleX;
let scaleY=svgObj.scaleY;

const requiredHeight=Math.max(textHeight,rect.height*0.5);
const requiredWidth=Math.max(textWidth,rect.width*0.5);
const newScaleY=svgObj.scaleY*(requiredHeight/rect.height);
const newScaleX=svgObj.scaleX*(requiredWidth/rect.width);

scaleX=Math.max(newScaleX,svgObj.baseScaleX);
scaleY=Math.max(newScaleY,svgObj.baseScaleY);

if (scaleX!==svgObj.scaleX||scaleY!==svgObj.scaleY) {
const centerX=svgObj.left+(svgObj.width*svgObj.scaleX)/2;
const centerY=svgObj.top+(svgObj.height*svgObj.scaleY)/2;

newSettings={
scaleX: scaleX,
scaleY: scaleY,
left: centerX-(svgObj.width*scaleX)/2,
top: centerY-(svgObj.height*scaleY)/2,
};
}
}
} else if (isHorizontalText(textObj)) {
const svgObj=textObj.targetObject;
const rect=canvas
.getObjects()
.find((obj)=>obj.type==="rect"&&obj.targetObject===svgObj);

if (rect) {
const chars=Math.max(textObj.text.length,1);
const fontSize=textObj.fontSize;
const charWidth=
textObj.calcTextWidth()/Math.max(textObj.text.length,1);
const singleLineHeight=
textObj.height/Math.max(textObj.textLines.length,1);
let scaleX=svgObj.scaleX;
let scaleY=svgObj.scaleY;

const requiredWidth=Math.max(
chars*charWidth+charWidth,
rect.width*0.5
);
const requiredHeight=Math.max(
textObj.height+singleLineHeight,
rect.height*0.5
);
const newScaleX=svgObj.scaleX*(requiredWidth/rect.width);
const newScaleY=svgObj.scaleY*(requiredHeight/rect.height);

scaleX=Math.max(newScaleX,svgObj.baseScaleX);
scaleY=Math.max(newScaleY,svgObj.baseScaleY);

if (scaleX!==svgObj.scaleX||scaleY!==svgObj.scaleY) {
const centerX=svgObj.left+(svgObj.width*svgObj.scaleX)/2;
const centerY=svgObj.top+(svgObj.height*svgObj.scaleY)/2;

newSettings={
scaleX: scaleX,
scaleY: scaleY,
left: centerX-(svgObj.width*scaleX)/2,
top: centerY-(svgObj.height*scaleY)/2,
};
}
}
}
return newSettings;
}


function speechBubbleTextChaged(textObj){
if (isSpeechBubbleText(textObj)) {
let newSettings=mainSpeechBubbleObjectResize(textObj);
const svgObj=textObj.targetObject;

svgObj.set(newSettings);
updateShapeMetrics(svgObj);
}
}



function customSpeechBubbleAllRelocation(){
canvas.getObjects().forEach(obj=>{
speechBubbleTextChaged(obj);
});
}

function getSpeechBubbleRectBySVG(svgObject){
return canvas.getObjects().find((obj)=>obj.type==="rect"&&obj.targetObject===svgObject);
}

function getSpeechBubbleTextBySVG(svgObject){
return canvas.getObjects().find((obj)=>isSpeechBubbleText(obj)&&obj.targetObject===svgObject);
}