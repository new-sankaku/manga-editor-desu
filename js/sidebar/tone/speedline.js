var tempCanvasSpeedLine=null;
var tempCtxSpeedLine=null;
var isDrawingSpeedLine=false;
var nowSpeedLine=null;

function speedLineStart(){
tempCanvasSpeedLine=document.createElement("canvas");

var activeObject=getLastObject();
if (isPanel(activeObject)) {
var canvasX=(activeObject.width*activeObject.scaleX);
var canvasY=(activeObject.height*activeObject.scaleY);
tempCanvasSpeedLine.width=canvasX*3;
tempCanvasSpeedLine.height=canvasY*3;
}else{
tempCanvasSpeedLine.width=canvas.width*3;
tempCanvasSpeedLine.height=canvas.height*3;
}
tempCtxSpeedLine=tempCanvasSpeedLine.getContext("2d");
tempCtxSpeedLine.scale(3,3);

}

function speedLineEnd(){
nowSpeedLine=null;
if(tempCanvasSpeedLine){
if (tempCanvasSpeedLine.parentNode) {
tempCanvasSpeedLine.parentNode.removeChild(tempCanvasSpeedLine);
}
}
tempCanvasSpeedLine=null;
tempCtxSpeedLine=null;
}



function updateSpeedLineValue(id) {
const input=$(id);
const display=$(id+"Value");
if (display) {
display.textContent=input.value;
}
}

function drawTempCanvasSpeedLine(start,end,options) {
const gradientToggle=$(MODE_SPEED_LINE+'-grad-check').checked;
const lineColor=$(MODE_SPEED_LINE+'-color').value;
const gradientStart=parseInt($(MODE_SPEED_LINE+'-grad-start').value)/100;
const gradientEnd=parseInt($(MODE_SPEED_LINE+'-grad-end').value)/100;

if (gradientToggle) {
const gradient=tempCtxSpeedLine.createLinearGradient(
start.x,
start.y,
end.x,
end.y
);
gradient.addColorStop(
0,
`${lineColor}${Math.round(gradientStart * 255)
        .toString(16)
        .padStart(2, "0")}`
);
gradient.addColorStop(
1,
`${lineColor}${Math.round(gradientEnd * 255)
        .toString(16)
        .padStart(2, "0")}`
);
tempCtxSpeedLine.strokeStyle=gradient;
} else {
tempCtxSpeedLine.strokeStyle=lineColor;
tempCtxSpeedLine.globalAlpha=options.opacity||1;
}

tempCtxSpeedLine.lineWidth=options.strokeWidth||1;
tempCtxSpeedLine.beginPath();
tempCtxSpeedLine.moveTo(start.x,start.y);
tempCtxSpeedLine.lineTo(end.x,end.y);
tempCtxSpeedLine.stroke();
}
function drawTempCanvasSpeedlines() {
tempCtxSpeedLine.clearRect(0,0,tempCanvasSpeedLine.width,tempCanvasSpeedLine.height);
const density=parseInt($(MODE_SPEED_LINE+'-density').value);
const angle=(parseInt(0)*Math.PI)/180;
const width=tempCanvasSpeedLine.width;
const height=tempCanvasSpeedLine.height;

const speedLineStyle=$('speed-line-style').value;



for (let i=0;i<density;i++) {
let start,end;
switch (speedLineStyle) {
case "horizontal":
start={x: 0,y: (i*height)/density};
end={x: width,y: (i*height)/density};
break;
case "vertical":
start={x: (i*width)/density,y: 0};
end={x: (i*width)/density,y: height};
break;
case "diagonal":
start={x: 0,y: (i*height)/(density-1)};
end={x: width,y: (i*height)/(density-1)};
break;
case "cross":
if (i<density/2) {
start={x: 0,y: (i*height)/(density/2)};
end={x: width,y: (i*height)/(density/2)};
} else {
start={x: ((i-density/2)*width)/(density/2),y: 0};
end={x: ((i-density/2)*width)/(density/2),y: height};
}
break;
}

const dx=end.x-start.x;
const dy=end.y-start.y;
const rotatedEnd={
x: start.x+dx*Math.cos(angle)-dy*Math.sin(angle),
y: start.y+dx*Math.sin(angle)+dy*Math.cos(angle),
};

drawTempCanvasSpeedLine(start,rotatedEnd,{opacity: 1,strokeWidth: 1});
}
updateSpeedLineCanvas();
}
function updateDrawingSpeedlines() {
if (!isDrawingSpeedLine) {
drawTempCanvasSpeedlines();
}
}


function addSppedLineEventListener(){
[MODE_SPEED_LINE+'-density',MODE_SPEED_LINE+'-grad-start',MODE_SPEED_LINE+'-grad-end',MODE_SPEED_LINE+'-color'].forEach(
(id)=>{
$(id).addEventListener("input",()=>{
updateSpeedLineValue(id);
updateDrawingSpeedlines();
});
}
);
$(MODE_SPEED_LINE+'-grad-check').addEventListener("input",updateDrawingSpeedlines);
}

function removeSppedLineEventListener() {
const updateSpeedLineValueAndDrawing=(id)=>{
updateSpeedLineValue(id);
updateDrawingSpeedlines();
};

[MODE_SPEED_LINE+'-density',MODE_SPEED_LINE+'-grad-start',MODE_SPEED_LINE+'-grad-end',MODE_SPEED_LINE+'-color'].forEach(
(id)=>{
const inputElement=$(id);
const listener=updateSpeedLineValueAndDrawing.bind(null,id);
inputElement.removeEventListener("input",listener);
}
);

$(MODE_SPEED_LINE+'-grad-check').removeEventListener("input",updateDrawingSpeedlines);
}

function updateSpeedLineCanvas() {
if (isDrawingSpeedLine) {
return;
}

isDrawingSpeedLine=true;
if (nowSpeedLine) {
canvas.remove(nowSpeedLine);
}

fabric.Image.fromURL(tempCanvasSpeedLine.toDataURL(),function (img) {
var activeObject=getLastObject();
if(isPanel(activeObject)){
var canvasX=(activeObject.left+(activeObject.width*activeObject.scaleX/2))  ;
var canvasY=(activeObject.top+(activeObject.height*activeObject.scaleY/2)) ;
putImageInFrame(img,canvasX,canvasY,true,false,true,activeObject);
img.name='Speed Line';
}else{
img.name='Speed Line';
img.scaleToWidth(canvas.width);
canvas.add(img);
canvas.renderAll();
}
nowSpeedLine=img;
isDrawingSpeedLine=false;
});
}
