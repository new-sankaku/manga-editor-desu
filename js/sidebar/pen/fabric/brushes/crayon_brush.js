/**
 * CrayonBrush class
 * @class fabric.CrayonBrush
 * @extends fabric.BaseBrush
 */
(function(fabric){

fabric.CrayonBrush=fabric.util.createClass(fabric.BaseBrush,{

color: "#000000",
opacity: 0.6,
width: 30,

_baseWidth: 20,
_inkAmount: 10,
_latestStrokeLength: 0,
_point: null,
_sep: 5,
_size: 0,
_offscreenCanvas: null,
_offscreenCtx: null,

initialize: function(canvas,opt) {
opt=opt||{};

this.canvas=canvas;
this.width=opt.width||canvas.freeDrawingBrush.width;
this.color=opt.color||canvas.freeDrawingBrush.color;
this.opacity=opt.opacity||canvas.contextTop.globalAlpha;
this._point=new fabric.Point(0,0);
},

_initOffscreen: function(){
if(!this._offscreenCanvas){
this._offscreenCanvas=document.createElement("canvas");
this._offscreenCanvas.width=this.canvas.width;
this._offscreenCanvas.height=this.canvas.height;
this._offscreenCtx=this._offscreenCanvas.getContext("2d");
}
},

changeColor: function(color){
this.color=color;
},

changeOpacity: function(value){
this.opacity=value;
},

onMouseDown: function(pointer){
this._initOffscreen();
this._offscreenCtx.clearRect(0,0,this._offscreenCanvas.width,this._offscreenCanvas.height);
this._offscreenCtx.globalAlpha=this.opacity;
this._size=this.width/2+this._baseWidth;
this.set(pointer);
},

onMouseMove: function(pointer){
this.update(pointer);
this.draw(this._offscreenCtx);
this._copyToContextTop();
},

onMouseUp: function(pointer){
},

_copyToContextTop: function(){
var ctx=this.canvas.contextTop;
ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
ctx.drawImage(this._offscreenCanvas,0,0);
},

set: function(p) {
if(this._latest){
this._latest.setFromPoint(this._point);
}else{
this._latest=new fabric.Point(p.x,p.y);
}
fabric.Point.prototype.setFromPoint.call(this._point,p);
},

update: function(p) {
this.set(p);
this._latestStrokeLength=this._point.subtract(this._latest).distanceFrom({x: 0,y: 0});
},

draw: function(ctx) {
var i,j,p,r,c,x,y,w,h,v,s,stepNum,dotSize,dotNum,range;

v=this._point.subtract(this._latest);
s=Math.ceil(this._size/2);
stepNum=Math.floor(v.distanceFrom({x: 0,y: 0})/s)+1;
v.normalize(s);

dotSize=this._sep*fabric.util.clamp(this._inkAmount/this._latestStrokeLength*3,1,0.5);
dotNum=Math.ceil(this._size*this._sep);

range=this._size/2;

ctx.save();
ctx.fillStyle=this.color;
ctx.beginPath();
for(i=0;i<dotNum;i++){
for(j=0;j<stepNum;j++){
p=this._latest.add(v.multiply(j));
r=fabric.util.getRandom(range);
c=fabric.util.getRandom(Math.PI*2);
w=fabric.util.getRandom(dotSize,dotSize/2);
h=fabric.util.getRandom(dotSize,dotSize/2);
x=p.x+r*Math.sin(c)-w/2;
y=p.y+r*Math.cos(c)-h/2;
ctx.rect(x,y,w,h);
}
}
ctx.fill();
ctx.restore();
}
});

})(fabric);
