fabric.PencilBrush=fabric.util.createClass(fabric.BaseBrush,{
decimate: 0.4,
drawStraightLine: false,
straightLineKey: "shiftKey",

initialize: function (t) {
this.canvas=t;
this._points=[];
},

needsFullRender: function () {
return this.callSuper("needsFullRender")||this._hasStraightLine;
},

_drawSegment: function (t,e,r) {
var i=e.midPointFrom(r);
t.quadraticCurveTo(e.x,e.y,i.x,i.y);
return i;
},

onMouseDown: function (t,e) {
if (this.canvas._isMainEvent(e.e)) {
this.drawStraightLine=e.e[this.straightLineKey];
this._prepareForDrawing(t);
this._captureDrawingPath(t);
this._render();
}
},

onMouseMove: function (t,e) {
if (this.canvas._isMainEvent(e.e)) {
this.drawStraightLine=e.e[this.straightLineKey];
if ((this.limitedToCanvasSize!==true||!this._isOutSideCanvas(t))&&this._captureDrawingPath(t)&&this._points.length>1) {
if (this.needsFullRender()) {
this.canvas.clearContext(this.canvas.contextTop);
this._render();
} else {
var r=this._points,
i=r.length,
n=this.canvas.contextTop;
this._saveAndTransform(n);
if (this.oldEnd) {
n.beginPath();
n.moveTo(this.oldEnd.x,this.oldEnd.y);
}
this.oldEnd=this._drawSegment(n,r[i-2],r[i-1]);
n.stroke();
n.restore();
}
}
}
},

onMouseUp: function(t) {
if (this.canvas._isMainEvent(t.e)) {
this.drawStraightLine=false;
this.oldEnd=undefined;
this._finalizeAndAddPath();
return false;
}
return true;
},

_prepareForDrawing: function(t) {
var e=new fabric.Point(t.x,t.y);
this._reset();
this._addPoint(e);
this.canvas.contextTop.moveTo(e.x,e.y);
},

_addPoint: function(t) {
if (this._points.length>1&&t.eq(this._points[this._points.length-1])) {
return false;
}
if (this.drawStraightLine&&this._points.length>1) {
this._hasStraightLine=true;
this._points.pop();
}
this._points.push(t);
return true;
},

_reset: function() {
this._points=[];
this._setBrushStyles(this.canvas.contextTop);
this._setShadow();
this._hasStraightLine=false;
},

_captureDrawingPath: function(t) {
var e=new fabric.Point(t.x,t.y);
return this._addPoint(e);
},

_render: function(t) {
var e,r,i=this._points[0],
n=this._points[1];
if (t=t||this.canvas.contextTop,this._saveAndTransform(t),t.beginPath(),2===this._points.length&&i.x===n.x&&i.y===n.y) {
var a=this.width/1e3;
i=new fabric.Point(i.x-a,i.y);
n=new fabric.Point(n.x+a,n.y);
}
for (t.moveTo(i.x,i.y),e=1,r=this._points.length;r>e;e++) {
this._drawSegment(t,i,n);
i=this._points[e];
n=this._points[e+1];
}
t.lineTo(i.x,i.y);
t.stroke();
t.restore();
}
});
