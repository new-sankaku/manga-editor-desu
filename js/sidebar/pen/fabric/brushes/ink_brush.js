/**
* InkBrush class
* @class fabric.InkBrush
* @extends fabric.BaseBrush
*/
(function(fabric){

fabric.InkBrush=fabric.util.createClass(fabric.BaseBrush,{

color: "#000000",
opacity: 1,
width: 30,

_baseWidth: 20,
_dripCount: 0,
_drips: [],
_inkAmount: 7,
_lastPoint: null,
_point: null,
_range: 10,
_strokeCount: 0,
_strokeId: null,
_strokeNum: 40,
_strokes: null,

initialize: function(canvas,opt) {
opt=opt||{};

this.canvas=canvas;
this.width=opt.width||canvas.freeDrawingBrush.width;
this.color=opt.color||canvas.freeDrawingBrush.color;
this.opacity=opt.opacity||canvas.contextTop.globalAlpha;

this._point=new fabric.Point();
},

changeColor: function(color){
this.color=color;
},

changeOpacity: function(value){
this.opacity=value;
this.canvas.contextTop.globalAlpha=value;
},

_render: function(pointer){
var subtractPoint,distance,point,i,len,strokes,stroke;
this._strokeCount++;
if (this._strokeCount%120===0&&this._dripCount<10) {
this._dripCount++;
}

point=this.setPointer(pointer);
subtractPoint=point.subtract(this._lastPoint);
distance=point.distanceFrom(this._lastPoint);
strokes=this._strokes;

for (i=0,len=strokes.length;i<len;i++) {
stroke=strokes[i];
stroke.update(point,subtractPoint,distance);
stroke.draw();
}

if (distance>30) {
this.drawSplash(point,this._inkAmount);
} else if (distance<10&&fabric.util.getRandom()<0.085&&this._dripCount) {
this._drips.push(new fabric.Drip(this.canvas.contextTop,point,fabric.util.getRandom(this.size*0.25,this.size*0.1),this.color,this._strokeId));
this._dripCount--;
}
},

onMouseDown: function(pointer){
this._resetTip(pointer);
this._strokeId=+new Date();
this._dripCount=fabric.util.getRandom(6,3)|0;
},

onMouseMove: function(pointer){
if(this.canvas._isCurrentlyDrawing){
this._render(pointer);
}
},

onMouseUp: function(){
this._strokeCount=0;
this._dripCount=0;
this._strokeId=null;
},

drawSplash: function(pointer,maxSize) {
var c,r,i,point,
ctx=this.canvas.contextTop,
num=fabric.util.getRandom(12),
range=maxSize*10,
color=this.color;

ctx.save();
for (i=0;i<num;i++) {
r=fabric.util.getRandom(range,1);
c=fabric.util.getRandom(Math.PI*2);
point=new fabric.Point(pointer.x+r*Math.sin(c),pointer.y+r*Math.cos(c));

ctx.fillStyle=color;
ctx.beginPath();
ctx.arc(point.x,point.y,fabric.util.getRandom(maxSize)/2,0,Math.PI*2,false);
ctx.fill();
}
ctx.restore();
},

setPointer: function(pointer) {
var point=new fabric.Point(pointer.x,pointer.y);

this._lastPoint=fabric.util.object.clone(this._point);
this._point=point;

return point;
},

_resetTip: function(pointer){
var strokes,point,len,i;

point=this.setPointer(pointer);
strokes=this._strokes=[];
this.size=this.width/5+this._baseWidth;
this._strokeNum=this.size;
this._range=this.size/2;

for (i=0,len=this._strokeNum;i<len;i++) {
strokes[i]=new fabric.Stroke(this.canvas.contextTop,point,this._range,this.color,this.width,this._inkAmount);
}
}
});

})(fabric);
