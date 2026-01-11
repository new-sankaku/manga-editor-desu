(function(fabric) {

fabric.Point.prototype.angleBetween=function(that){
return Math.atan2(this.x-that.x,this.y-that.y);
};

fabric.Point.prototype.normalize=function(thickness) {
if (null===thickness||undefined===thickness) {
thickness=1;
}

var length=this.distanceFrom({x: 0,y: 0});

if (length>0) {
this.x=this.x/length*thickness;
this.y=this.y/length*thickness;
}

return this;
};

})(fabric);