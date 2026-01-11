/**
 * Drip class
 * @class fabric.Drip
 * @extends fabric.Object
 */
(function(fabric) {

fabric.Drip=fabric.util.createClass(fabric.Object,{
rate: 0,
color: "#000000",
amount: 10,
life: 10,
_point: null,
_lastPoint: null,
_strokeId: 0,
_interval: 20,

initialize: function(ctx,pointer,amount,color,_strokeId) {
this.ctx=ctx;
this._point=pointer;
this._strokeId=_strokeId;
this.amount=fabric.util.getRandom(amount,amount*0.5);
this.color=color;
this.life=this.amount*1.5;
ctx.lineCap=ctx.lineJoin="round";

this._render();
},

_update: function(brush) {
this._lastPoint=fabric.util.object.clone(this._point);
this._point.addEquals({
x: this.life*this.rate,
y: fabric.util.getRandom(this.life*this.amount/30)
});

this.life-=0.05;

if (fabric.util.getRandom()<0.03) {
this.rate+=fabric.util.getRandom(0.03,-0.03);
} else if (fabric.util.getRandom()<0.05) {
this.rate*=0.01;
}
},

_draw: function() {
this.ctx.save();
this.line(this.ctx,this._lastPoint,this._point,this.color,this.amount*0.8+this.life*0.2);
this.ctx.restore();
},

_render: function() {
var context=this;

setTimeout(draw,this._interval);

function draw() {
context._update();
context._draw();
if(context.life>0) {
setTimeout(draw,context._interval);
}
}
},

line: function(ctx,point1,point2,color,lineWidth) {
ctx.strokeStyle=color;
ctx.lineWidth=lineWidth;
ctx.beginPath();
ctx.moveTo(point1.x,point1.y);
ctx.lineTo(point2.x,point2.y);

ctx.stroke();
}
});

})(fabric);
