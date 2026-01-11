function attachControlEvents() {
["angle-control",'scale-control','top-control','left-control','skewX-control','skewY-control','opacity-control'].forEach(function(id) {
$(id).oninput=function() {
var activeObject=canvas.getActiveObject();
if (!activeObject) return;
switch (id) {
case 'angle-control':
activeObject.set('angle',parseInt(this.value,10));
break;
case 'scale-control':
activeObject.scale(parseFloat(this.value));
break;
case 'top-control':
activeObject.set('top',parseInt(this.value,10));
break;
case 'left-control':
activeObject.set('left',parseInt(this.value,10));
break;
case 'skewX-control':
activeObject.set('skewX',parseInt(this.value,10));
break;
case 'skewY-control':
activeObject.set('skewY',parseInt(this.value,10));
break;
case 'opacity-control':
var opacity=this.value/100
activeObject.set('opacity',opacity);
break;
}
activeObject.setCoords();
canvas.requestRenderAll();
};
});
}
document.addEventListener('DOMContentLoaded',function() {
attachControlEvents();
});


function updateControls(activeObject) {
if (!activeObject) {
$("angle-control").value=0;
$("scale-control").value=1;
$("top-control").value=0;
$("left-control").value=0;
$("skewX-control").value=0;
$("skewY-control").value=0;
$("opacity-control").value=1;

return;
}

$("angle-control").value=activeObject.angle||0;
$("scale-control").value=activeObject.scaleX||1;
$("top-control").value=activeObject.top||0;
$("left-control").value=activeObject.left||0;
$("skewX-control").value=activeObject.skewX||0;
$("skewY-control").value=activeObject.skewY||0;
$("opacity-control").value=activeObject.opacity*100||100;
}
