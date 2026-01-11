fabric.DoubleOutlineBrush=fabric.util.createClass(fabric.BaseBrush,{
type: "DoubleOutlineBrush",
initialize: function(canvas){
this.canvas=canvas;
this.color="#FFFFFF";
this.width=10;
this.outline1Color="#000000";
this.outline1Width=2;
this.outline1Opacity=1;
this.outline2Color="#FF0000";
this.outline2Width=1;
this.outline2Opacity=1;
this.isDrawing=false;
this.currentPathData=null;
this.points=[];
this.pathDataArray=[];
this.outlineImage=null;
this.offscreenCanvas=null;
this.offscreenCtx=null;
},
_initOffscreen: function(){
if(!this.offscreenCanvas){
this.offscreenCanvas=document.createElement("canvas");
this.offscreenCanvas.width=this.canvas.width;
this.offscreenCanvas.height=this.canvas.height;
this.offscreenCtx=this.offscreenCanvas.getContext("2d");
}
},
onMouseDown: function(pointer){
this._initOffscreen();
this.isDrawing=true;
this.points=[pointer];
this.currentPathData={
path:[["M",pointer.x,pointer.y],["L",pointer.x,pointer.y]],
stroke: this.color,
strokeWidth: this.width,
outline1Color: this.outline1Color,
outline1Width: this.outline1Width,
outline1Opacity: this.outline1Opacity,
outline2Color: this.outline2Color,
outline2Width: this.outline2Width,
outline2Opacity: this.outline2Opacity,
};
this._render();
},
onMouseMove: function(pointer){
if(this.isDrawing&&this.currentPathData){
this.points.push(pointer);
if(this.points.length>3){
var lastIndex=this.points.length-1;
var controlX=(this.points[lastIndex].x+this.points[lastIndex-1].x)/2;
var controlY=(this.points[lastIndex].y+this.points[lastIndex-1].y)/2;
this.currentPathData.path.push(["Q",this.points[lastIndex-1].x,this.points[lastIndex-1].y,controlX,controlY]);
this.points.shift();
}else{
this.currentPathData.path[1]=["L",pointer.x,pointer.y];
}
this._render();
}
},
onMouseUp: function(){
if(this.isDrawing){
this.isDrawing=false;
this.pathDataArray.push(this.currentPathData);
this.currentPathData=null;
this.points=[];
this._processOutlines();
}
},
_render: function(){
this.offscreenCtx.clearRect(0,0,this.offscreenCanvas.width,this.offscreenCanvas.height);
var allPaths=this.pathDataArray.slice();
if(this.currentPathData){
allPaths.push(this.currentPathData);
}
var self=this;
allPaths.forEach(function(pathData){
if(pathData.outline2Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width+2*pathData.outline2Width,pathData.outline2Color,pathData.outline2Opacity);
}
});
allPaths.forEach(function(pathData){
if(pathData.outline1Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width,pathData.outline1Color,pathData.outline1Opacity);
}
});
allPaths.forEach(function(pathData){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth,pathData.stroke,1);
});
var ctx=this.canvas.contextTop;
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
ctx.drawImage(this.offscreenCanvas,0,0);
},
_drawStroke: function(pathData,ctx,width,color,opacity){
ctx.save();
ctx.beginPath();
ctx.strokeStyle=color;
ctx.globalAlpha=opacity;
ctx.lineWidth=width;
ctx.lineCap="round";
ctx.lineJoin="round";
pathData.path.forEach(function(segment){
if(segment[0]==="M"){
ctx.moveTo(segment[1],segment[2]);
}else if(segment[0]==="L"){
ctx.lineTo(segment[1],segment[2]);
}else if(segment[0]==="Q"){
ctx.quadraticCurveTo(segment[1],segment[2],segment[3],segment[4]);
}
});
if(pathData.path.length===1){
ctx.lineTo(pathData.path[0][1],pathData.path[0][2]);
}
ctx.stroke();
ctx.restore();
},
_processOutlines: function(){
this.offscreenCtx.clearRect(0,0,this.offscreenCanvas.width,this.offscreenCanvas.height);
var self=this;
this.pathDataArray.forEach(function(pathData){
if(pathData.outline2Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width+2*pathData.outline2Width,pathData.outline2Color,pathData.outline2Opacity);
}
});
this.pathDataArray.forEach(function(pathData){
if(pathData.outline1Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width,pathData.outline1Color,pathData.outline1Opacity);
}
});
this.pathDataArray.forEach(function(pathData){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth,pathData.stroke,1);
});
if(this.outlineImage){
this.canvas.remove(this.outlineImage);
}
var tempCanvas=document.createElement("canvas");
tempCanvas.width=this.offscreenCanvas.width;
tempCanvas.height=this.offscreenCanvas.height;
tempCanvas.getContext("2d").drawImage(this.offscreenCanvas,0,0);
this.outlineImage=new fabric.Image(tempCanvas,{
left: 0,
top: 0,
selectable: false,
evented: false,
});
this.canvas.add(this.outlineImage);
this.canvas.contextTop.clearRect(0,0,this.canvas.width,this.canvas.height);
this.canvas.renderAll();
},
mergeDrawings: function(){
if(this.pathDataArray.length===0){
if(this.outlineImage){
this.canvas.remove(this.outlineImage);
this.outlineImage=null;
}
return;
}
this._initOffscreen();
this.offscreenCtx.clearRect(0,0,this.offscreenCanvas.width,this.offscreenCanvas.height);
var self=this;
this.pathDataArray.forEach(function(pathData){
if(pathData.outline2Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width+2*pathData.outline2Width,pathData.outline2Color,pathData.outline2Opacity);
}
});
this.pathDataArray.forEach(function(pathData){
if(pathData.outline1Width>0){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth+2*pathData.outline1Width,pathData.outline1Color,pathData.outline1Opacity);
}
});
this.pathDataArray.forEach(function(pathData){
self._drawStroke(pathData,self.offscreenCtx,pathData.strokeWidth,pathData.stroke,1);
});
var imageData=this.offscreenCtx.getImageData(0,0,this.offscreenCanvas.width,this.offscreenCanvas.height);
var data=imageData.data;
var minX=this.offscreenCanvas.width;
var minY=this.offscreenCanvas.height;
var maxX=0;
var maxY=0;
for(var y=0;y<this.offscreenCanvas.height;y++){
for(var x=0;x<this.offscreenCanvas.width;x++){
var alpha=data[(y*this.offscreenCanvas.width+x)*4+3];
if(alpha>0){
minX=Math.min(minX,x);
minY=Math.min(minY,y);
maxX=Math.max(maxX,x);
maxY=Math.max(maxY,y);
}
}
}
if(maxX<minX||maxY<minY){
changeDoNotSaveHistory();
if(this.outlineImage){
this.canvas.remove(this.outlineImage);
this.outlineImage=null;
}
this.pathDataArray=[];
changeDoSaveHistory();
return;
}
var width=maxX-minX+1;
var height=maxY-minY+1;
var croppedCanvas=document.createElement("canvas");
croppedCanvas.width=width;
croppedCanvas.height=height;
var croppedCtx=croppedCanvas.getContext("2d");
croppedCtx.drawImage(this.offscreenCanvas,minX,minY,width,height,0,0,width,height);
var mergedImage=croppedCanvas.toDataURL();
fabric.Image.fromURL(mergedImage,function(img){
img.set({
left: minX,
top: minY,
selectable: false,
scaleX: 1,
scaleY: 1
});
changeDoNotSaveHistory();
if(self.outlineImage){
self.canvas.remove(self.outlineImage);
self.outlineImage=null;
}
self.pathDataArray=[];
changeDoSaveHistory();
self.canvas.add(img);
self.canvas.renderAll();
});
}
});

fabric.MosaicBrush=fabric.util.createClass(fabric.BaseBrush,{
initialize: function (canvas) {
this.canvas=canvas;
this.mosaicSize=10;
this.circleSize=40;
this.isDrawing=false;
this.lastPointer={x: this.canvas.width/2,y: this.canvas.height/2};
this.images=[];
},

onMouseDown: function (pointer) {
this.isDrawing=true;
this.lastPointer=pointer;
this.canvas.contextTop.clearRect(0,0,this.canvas.width,this.canvas.height);
this.drawMosaic(pointer);
},

onMouseMove: function (pointer) {
this.lastPointer=pointer;
if (this.isDrawing) {
this.drawMosaic(pointer);
} else {
this.drawPreviewCircle(pointer);
}
},

onMouseUp: function () {
this.isDrawing=false;
this.commitDrawing();
this.drawPreviewCircle(this.lastPointer);
},

drawMosaic: function (pointer) {
var ctx=this.canvas.contextTop;
var mainCtx=this.canvas.getContext('2d');

var mosaicSize=this.mosaicSize;
var circleRadius=this.circleSize/2;

var startGridX=Math.floor(Math.max(0,pointer.x-circleRadius)/mosaicSize);
var startGridY=Math.floor(Math.max(0,pointer.y-circleRadius)/mosaicSize);
var endGridX=Math.ceil(Math.min(this.canvas.width,pointer.x+circleRadius)/mosaicSize);
var endGridY=Math.ceil(Math.min(this.canvas.height,pointer.y+circleRadius)/mosaicSize);

var scaleX=mainCtx.getTransform().a;
var scaleY=mainCtx.getTransform().d;

for (var gridX=startGridX;gridX<endGridX;gridX++) {
for (var gridY=startGridY;gridY<endGridY;gridY++) {
var cellCenterX=(gridX+0.5)*mosaicSize;
var cellCenterY=(gridY+0.5)*mosaicSize;

if (this.isInsideCircle(pointer.x,pointer.y,cellCenterX,cellCenterY,circleRadius)) {
var x=gridX*mosaicSize;
var y=gridY*mosaicSize;
var imageData=mainCtx.getImageData(x*scaleX,y*scaleY,mosaicSize*scaleX,mosaicSize*scaleY);

var data=imageData.data;
var r=0,g=0,b=0,a=0,count=0;

for (var i=0;i<data.length;i+=4) {
r+=data[i];
g+=data[i+1];
b+=data[i+2];
a+=data[i+3];
count++;
}
r=Math.floor(r/count);
g=Math.floor(g/count);
b=Math.floor(b/count);
a=Math.floor(a/count);

ctx.fillStyle=`rgba(${r},${g},${b},${a / 255})`;
ctx.fillRect(x,y,mosaicSize,mosaicSize);
}
}
}
},

isInsideCircle: function (cx,cy,x,y,radius) {
var dx=cx-x;
var dy=cy-y;
return (dx*dx+dy*dy<=radius*radius);
},

drawPreviewCircle: function (pointer) {
var ctx=this.canvas.contextTop;
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);

ctx.beginPath();
ctx.arc(pointer.x,pointer.y,this.circleSize/2,0,2*Math.PI);
ctx.strokeStyle='rgba(0, 255, 0, 0.5)';
ctx.lineWidth=2;
ctx.stroke();

ctx.strokeStyle='rgba(255, 0, 0, 0.3)';
ctx.lineWidth=1;
var startX=Math.floor(pointer.x-this.circleSize/2);
var startY=Math.floor(pointer.y-this.circleSize/2);
var endX=startX+this.circleSize;
var endY=startY+this.circleSize;

for (var x=startX;x<=endX;x+=this.mosaicSize) {
ctx.beginPath();
ctx.moveTo(x,startY);
ctx.lineTo(x,endY);
ctx.stroke();
}

for (var y=startY;y<=endY;y+=this.mosaicSize) {
ctx.beginPath();
ctx.moveTo(startX,y);
ctx.lineTo(endX,y);
ctx.stroke();
}
},

_render: function(){}

});



function enhanceBrush(brush,keepOriginalMethod) {
brush.images=[];

brush.commitDrawing=function () {
var ctx=this.canvas.contextTop;
var scaleX=1/ctx.getTransform().a;
var scaleY=1/ctx.getTransform().d;
var dataURL=ctx.canvas.toDataURL();
fabric.Image.fromURL(dataURL,(img)=>{
img.set({
left: 0,
top: 0,
selectable: false,
evented: false,
scaleX: scaleX,
scaleY: scaleY,
});
this.canvas.add(img);
this.canvas.renderAll();
this.images.push(img);
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
});
};


brush.commitDrawing=function () {
var ctx=this.canvas.contextTop;
var scaleX=1/ctx.getTransform().a;
var scaleY=1/ctx.getTransform().d;
var dataURL=ctx.canvas.toDataURL();
fabric.Image.fromURL(dataURL,(img)=>{
img.set({
left: 0,
top: 0,
selectable: false,
evented: false,
scaleX: scaleX,
scaleY: scaleY,
});
this.canvas.add(img);
this.canvas.renderAll();
this.images.push(img);
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
});
};


brush.mergeDrawings=function () {
var existingImages=this.images.filter((img)=>this.canvas.contains(img));

if (existingImages.length==0) {
this.images=[];
return;
}

var tempCanvas=document.createElement('canvas');
var tempCtx=tempCanvas.getContext('2d');

tempCanvas.width=this.canvas.width;
tempCanvas.height=this.canvas.height;

existingImages.forEach((img)=>{
tempCtx.drawImage(
img.getElement(),
img.left,
img.top,
img.width*img.scaleX,
img.height*img.scaleY
);
});

var imageData=tempCtx.getImageData(0,0,tempCanvas.width,tempCanvas.height);
var data=imageData.data;
var minX=tempCanvas.width;
var minY=tempCanvas.height;
var maxX=0;
var maxY=0;

for (var y=0;y<tempCanvas.height;y++) {
for (var x=0;x<tempCanvas.width;x++) {
var alpha=data[(y*tempCanvas.width+x)*4+3];
if (alpha>0) {
minX=Math.min(minX,x);
minY=Math.min(minY,y);
maxX=Math.max(maxX,x);
maxY=Math.max(maxY,y);
}
}
}

var width=maxX-minX+1;
var height=maxY-minY+1;

var croppedCanvas=document.createElement('canvas');
croppedCanvas.width=width;
croppedCanvas.height=height;

var croppedCtx=croppedCanvas.getContext('2d');
croppedCtx.drawImage(tempCanvas,
minX,minY,width,height,
0,0,width,height
);

var mergedImage=croppedCanvas.toDataURL();
fabric.Image.fromURL(mergedImage,(img)=>{
img.set({
left: minX,
top: minY,
selectable: false,
scaleX: 1,
scaleY: 1
});
this.canvas.add(img);
existingImages.forEach((image)=>{
this.canvas.remove(image);
});
this.images=[];

this.canvas.renderAll();
});
};
if(keepOriginalMethod){
var originalOnMouseUp=brush.onMouseUp;
brush.onMouseUp=function() {
if (originalOnMouseUp) {
originalOnMouseUp.call(this);
}
this.commitDrawing();
};
}

return brush;
}