var tmpCanvasFL=null;
var tmpCtxFL=null;
var isDrawingFL=false;
var nowFocusLine=null;
var nowFCActiveObject=null;
var conf=null;
var lines=null;

function focusLineStart() {
effectLogger.debug("focusLineStart");
var activeObject=getLastObject();
tmpCanvasFL=document.createElement("canvas");

if (isPanel(activeObject)) {
var canvasX=(activeObject.width*activeObject.scaleX);
var canvasY=(activeObject.height*activeObject.scaleY);
tmpCanvasFL.width=canvasX*3;
tmpCanvasFL.height=canvasY*3;
}else{
tmpCanvasFL.width=canvas.width*3;
tmpCanvasFL.height=canvas.height*3;
}

tmpCtxFL=tmpCanvasFL.getContext("2d");
tmpCtxFL.scale(3,3);
conf={
cx: tmpCanvasFL.width/2,
cy: tmpCanvasFL.height/2,
lineWidth: 30,
lineNum: 200,
crMax: 40,
crMin: 30,
color: "#000000",
};

effectLogger.debug("focusLineStart updateFocusLine");
updateFocusLine();
}

function focusLineEnd() {
nowFocusLine=null;
if(tmpCanvasFL){
if (tmpCanvasFL.parentNode) {
tmpCanvasFL.parentNode.removeChild(tmpCanvasFL);
}
}
tmpCanvasFL=null;
tmpCtxFL=null;
lines=null;
isDrawingFL=false;
}

var focusLine=function (
tmpCanvasFL,
centralX,
centralY,
lineWidth,
lineNum,
circleRadiusMax,
circleRadiusMin,
lineColor
) {
var lines=[];

var getRandomInt=function (max,min) {
return Math.floor(Math.random()*(max-min))+min;
};

var getCircumPos={
x: function (d,r,cx) {
return Math.cos((Math.PI/180)*d)*r+cx;
},
y: function (d,r,cy) {
return Math.sin((Math.PI/180)*d)*r+cy;
},
};

var Liner=function () {
this.initialize();
};

Liner.prototype={
initialize: function () {
this.deg=getRandomInt(360,0);
},
setPos: function () {
this.moveDeg=this.deg+getRandomInt(lineWidth,1)/10;
var sizeMultiplier=
1+
Math.max(
Math.abs(centralX-tmpCanvasFL.width/2)/(tmpCanvasFL.width/2),
Math.abs(centralY-tmpCanvasFL.height/2)/(tmpCanvasFL.height/2)
);
this.endRadius=
getRandomInt(circleRadiusMax,circleRadiusMin)*sizeMultiplier;
var canvasRadius=
Math.max(tmpCanvasFL.width,tmpCanvasFL.height)*sizeMultiplier;
this.startPos={
x: getCircumPos.x(this.deg,canvasRadius,centralX),
y: getCircumPos.y(this.deg,canvasRadius,centralY),
};
this.movePos={
x: getCircumPos.x(this.moveDeg,canvasRadius,centralX),
y: getCircumPos.y(this.moveDeg,canvasRadius,centralY),
};
this.endPos={
x: getCircumPos.x(this.moveDeg,this.endRadius,centralX),
y: getCircumPos.y(this.moveDeg,this.endRadius,centralY),
};
},
update: function () {
this.setPos();
},
draw: function () {
tmpCtxFL.beginPath();
tmpCtxFL.lineWidth=1;
tmpCtxFL.fillStyle=lineColor;
tmpCtxFL.moveTo(this.startPos.x,this.startPos.y);
tmpCtxFL.lineTo(this.movePos.x,this.movePos.y);
tmpCtxFL.lineTo(this.endPos.x,this.endPos.y);
tmpCtxFL.fill();
tmpCtxFL.closePath();
},
render: function () {
this.update();
this.draw();
},
};

function createLines(num) {
lines=[];
var i=0;
for (;i<num;i++) {
lines[lines.length]=new Liner();
}
}

function render() {
var i=0;
var l=lines.length;
tmpCtxFL.clearRect(0,0,tmpCanvasFL.width,tmpCanvasFL.height);
for (;i<l;i++) {
lines[i].render();
}
}

createLines(lineNum);
render();

return lines;
};




function updateFocusLine() {
conf.lineNum=parseInt($(MODE_FOCUSING_LINE+'-lineNum').value);
conf.crMax=((parseInt($(MODE_FOCUSING_LINE+"-max-radius").value)/100)*Math.min(tmpCanvasFL.width,tmpCanvasFL.height))/2;
conf.crMin=((parseInt($(MODE_FOCUSING_LINE+"-min-radius").value)/100)*Math.min(tmpCanvasFL.width,tmpCanvasFL.height))/2;
conf.cx=(parseInt($(MODE_FOCUSING_LINE+"-center-x").value)/100)*tmpCanvasFL.width;
conf.cy=(parseInt($(MODE_FOCUSING_LINE+"-center-y").value)/100)*tmpCanvasFL.height;
conf.lineWidth=parseInt($(MODE_FOCUSING_LINE+"-line-size").value);
conf.color=$(MODE_FOCUSING_LINE+"-color").value;
lines=focusLine(
tmpCanvasFL,
conf.cx,
conf.cy,
conf.lineWidth,
conf.lineNum,
conf.crMax,
conf.crMin,
conf.color
);

effectLogger.debug("updateFCFabricCanvas start");
updateFCFabricCanvas();
}

function addFCEventListener() {
[
MODE_FOCUSING_LINE+'-lineNum',
MODE_FOCUSING_LINE+"-color",
MODE_FOCUSING_LINE+"-line-size",
MODE_FOCUSING_LINE+"-max-radius",
MODE_FOCUSING_LINE+"-min-radius",
MODE_FOCUSING_LINE+"-center-x",
MODE_FOCUSING_LINE+"-center-y",
MODE_FOCUSING_LINE+"-line-width-expand",
].forEach((id)=>{
$(id).addEventListener("input",()=>{
effectLogger.debug("addFCEventListener updateFocusLine");

updateFocusLine();
});
});
}

function updateFCFabricCanvas() {
if (isDrawingFL) {
return;
}

isDrawingFL=true;
if (nowFocusLine) {
canvas.remove(nowFocusLine);
}

var svgString=convertToSVG(tmpCanvasFL);
var activeObject=getLastObject();
if (isPanel(activeObject)) {
var canvasX=activeObject.left+(activeObject.width*activeObject.scaleX)/2;
var canvasY=activeObject.top+(activeObject.height*activeObject.scaleY)/2;
var obj=putImageInFrame(svgString,canvasX,canvasY,true,false,true,activeObject);
obj.name='Focus Line';
canvas.add(obj);
nowFocusLine=obj;
updateLayerPanel();
} else {
fabric.loadSVGFromString(svgString,function (objects,options) {
var svgGroup=fabric.util.groupSVGElements(objects,options);
svgGroup.scaleToWidth(canvas.width);
svgGroup.scaleToHeight(canvas.height);
svgGroup.name='Focus Line';
canvas.add(svgGroup);
canvas.renderAll();
nowFocusLine=svgGroup;
});
}
isDrawingFL=false;
}
