/**
* MarkerBrush class
* @class fabric.MarkerBrush
* @extends fabric.BaseBrush
*/
(function(fabric) {

fabric.MarkerBrush=fabric.util.createClass(fabric.BaseBrush,{

color: "#000000",
opacity: 1,
width: 30,

_baseWidth: 10,
_lastPoint: null,
_lineWidth: 3,
_point: null,
_size: 0,
_offscreenCanvas: null,
_offscreenCtx: null,

initialize: function(canvas,opt) {
opt=opt||{};

this.canvas=canvas;
this.width=opt.width||canvas.freeDrawingBrush.width;
this.color=opt.color||canvas.freeDrawingBrush.color;
this.opacity=opt.opacity||canvas.contextTop.globalAlpha;
this._point=new fabric.Point();
},

_initOffscreen: function(){
if(!this._offscreenCanvas){
this._offscreenCanvas=document.createElement("canvas");
this._offscreenCanvas.width=this.canvas.width;
this._offscreenCanvas.height=this.canvas.height;
this._offscreenCtx=this._offscreenCanvas.getContext("2d");
this._offscreenCtx.lineJoin='round';
this._offscreenCtx.lineCap='round';
}
},

changeColor: function(color) {
this.color=color;
},

changeOpacity: function(value) {
this.opacity=value;
},

_render: function(pointer) {
var ctx,lineWidthDiff,i;

ctx=this._offscreenCtx;

ctx.beginPath();

for(i=0,len=(this._size/this._lineWidth)/2;i<len;i++){
lineWidthDiff=(this._lineWidth-1)*i;

ctx.globalAlpha=0.8*this.opacity;
ctx.moveTo(this._lastPoint.x+lineWidthDiff,this._lastPoint.y+lineWidthDiff);
ctx.lineTo(pointer.x+lineWidthDiff,pointer.y+lineWidthDiff);
ctx.stroke();
}

this._lastPoint=new fabric.Point(pointer.x,pointer.y);
this._copyToContextTop();
},

_copyToContextTop: function(){
var ctx=this.canvas.contextTop;
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
ctx.drawImage(this._offscreenCanvas,0,0);
},

onMouseDown: function(pointer) {
this._initOffscreen();
this._offscreenCtx.clearRect(0,0,this._offscreenCanvas.width,this._offscreenCanvas.height);
this._lastPoint=pointer;
this._offscreenCtx.strokeStyle=this.color;
this._offscreenCtx.lineWidth=this._lineWidth;
this._size=this.width+this._baseWidth;
},

onMouseMove: function(pointer) {
if(this.canvas._isCurrentlyDrawing){
this._render(pointer);
}
},

onMouseUp: function() {
}
});

})(fabric);
