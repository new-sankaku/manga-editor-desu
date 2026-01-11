var glfxOriginalImage=null;
var glfxCopiedImage=null;

function glfxResetFilterValues() {
$("glfxBrightness").value=0;
$("glfxContrast").value=0;
$("glfxHue").value=0;
$("glfxSaturation").value=0;
$("glfxSepiaAmount").value=0;
$("glfxUnsharpRadius").value=0;
$("glfxUnsharpStrength").value=0;
$("glfxVibranceAmount").value=0;
$("glfxVignetteSize").value=0;
$("glfxVignetteAmount").value=0;
$("glfxBlurRadius").value=0;
$("glfxBlurBrightness").value=0;
$("glfxBlurAngle").value=0;
$("glfxStartX").value=0.5;
$("glfxStartY").value=0.5;
$("glfxEndX").value=0.5;
$("glfxEndY").value=0.5;
$("glfxTiltBlurRadius").value=0;
$("glfxGradientRadius").value=0.5;
$("glfxTriangleRadius").value=0;
$("glfxZoomCenterX").value=0.5;
$("glfxZoomCenterY").value=0.5;
$("glfxZoomStrength").value=0;
$("glfxHalftoneAngle").value=0;
$("glfxHalftoneSize").value=2;
$("glfxDotAngle").value=0;
$("glfxDotSize").value=2;
$("glfxEdgeRadius").value=0;
$("glfxHexScale").value=2;
$("glfxInkStrength").value=0.2;
$("glfxBulgeCenterX").value=500;
$("glfxBulgeCenterY").value=500;
$("glfxBulgeRadius").value=0;
$("glfxBulgeStrength").value=0;
$("glfxSwirlCenterX").value=256;
$("glfxSwirlCenterY").value=256;
$("glfxSwirlRadius").value=0;
$("glfxSwirlAngle").value=0;
}

var fxCanvas,texture;

function glfxApplyFilter(filter=null) {
// console.log("glfxApplyFilter: Start");
if (!canvas) {
// console.log("glfxApplyFilter: Canvas is null");
return;
}

var activeObject=canvas.getActiveObject();

if (activeObject&&activeObject.type==="image") {
// console.log("glfxApplyFilter: Applying filter to object", activeObject);
glfxApplyFilterToObject(activeObject,filter).then(()=>{
// console.log("glfxApplyFilter: Filter applied to object successfully");
});
} else {
// console.log("glfxApplyFilter: No active image object, applying filter to canvas");
glfxApplyFilterToCanvas(filter);
}
}

function glfxApplyFilterToCanvas(filter=null) {
var fabricCanvas=canvas.upperCanvasEl;
var img=new Image();
img.onload=function () {
fxCanvas=fx.canvas();
texture=fxCanvas.texture(img);
fxCanvas.draw(texture);
applySelectedFilter(fxCanvas,filter);
fxCanvas.update();
canvas
.getContext("2d")
.drawImage(fxCanvas,0,0,canvas.width,canvas.height);
};
img.src=fabricCanvas.toDataURL();
}

function glfxApplyFilterToObject(object,filter=null,filterValues=null) {
return new Promise((resolve)=>{
if (!glfxOriginalImage) {
// console.log("glfxApplyFilterToObject: glfxOriginalImage is null");
return resolve();
}

var img=new Image();
img.onload=function () {
// console.log("glfxApplyFilterToObject: Image loaded for filtering");
fxCanvas=fx.canvas();
texture=fxCanvas.texture(img);
fxCanvas.draw(texture);
applySelectedFilter(fxCanvas,filter,filterValues);
fxCanvas.update();

var filteredImage=new Image();
filteredImage.src=fxCanvas.toDataURL();
filteredImage.onload=function () {
// console.log("glfxApplyFilterToObject: Filtered image loaded");

// Log the object state before applying the filter
// console.log("Before applying filter:", object);

var top=object.top;
var left=object.left;
var scaleX=object.scaleX;
var scaleY=object.scaleY;
var width=object.width;
var height=object.height;

object.setElement(filteredImage);
object.top=top;
object.left=left;
object.scaleX=scaleX;
object.scaleY=scaleY;
object.width=width;
object.height=height;

// Log the object state after applying the filter
// console.log("After applying filter:", object);

object.set({
left: left,
top: top,
scaleX: scaleX,
scaleY: scaleY,
width: width,
height: height,
});

canvas.requestRenderAll();

// Log to confirm the canvas is rendered
// console.log("Canvas rendered with filtered image");

resolve();
};
};

img.src=glfxOriginalImage.src;
});
}


function applySelectedFilter(fxCanvas,filter=null,filterValues=null) {
// console.log("applySelectedFilter start");
var isNotAuto=true;
if(filter){
isNotAuto=false;
}else{
filter=$("glfxFilter").value;
}
// console.log("applySelectedFilter: Selected filter is", filter);


switch (filter) {
case "glfxBrightnessContrast":
var brightness=0.29;
var contrast=0.29;

if(isNotAuto){
brightness=parseFloat($("glfxBrightness").value);
contrast=parseFloat($("glfxContrast").value);
}else{
brightness=filterValues.brightness;
contrast=filterValues.contrast;

}
// console.log( "glfxBrightnessContrast brightness", brightness );
// console.log( "glfxBrightnessContrast contrast", contrast );
fxCanvas.brightnessContrast(brightness,contrast);
break;
case "glfxHueSaturation":
var hue=parseFloat($("glfxHue").value);
var saturation=parseFloat($("glfxSaturation").value);

// console.log("glfxHueSaturation hue", hue);
// console.log("glfxHueSaturation saturation", saturation);

fxCanvas.hueSaturation(hue,saturation);
break;
case "glfxSepia":
var amount=parseFloat($("glfxSepiaAmount").value);
fxCanvas.sepia(amount);
break;
case "glfxUnsharpMask":
var radius=parseFloat(
$("glfxUnsharpRadius").value
);
var strength=parseFloat(
$("glfxUnsharpStrength").value
);
fxCanvas.unsharpMask(radius,strength);
break;
case "glfxVibrance":
var vibranceAmount=parseFloat(
$("glfxVibranceAmount").value
);
fxCanvas.vibrance(vibranceAmount);
break;
case "glfxVignette":
var vignetteSize=parseFloat(
$("glfxVignetteSize").value
);
var vignetteAmount=parseFloat(
$("glfxVignetteAmount").value
);
fxCanvas.vignette(vignetteSize,vignetteAmount);
break;
case "glfxLensBlur":
var blurRadius=parseFloat(
$("glfxBlurRadius").value
);
var blurBrightness=parseFloat(
$("glfxBlurBrightness").value
);
var blurAngle=parseFloat(
$("glfxBlurAngle").value
);
fxCanvas.lensBlur(blurRadius,blurBrightness,blurAngle);
break;
case "glfxTiltShift":
var startX=parseFloat($("glfxStartX").value);
var startY=parseFloat($("glfxStartY").value);
var endX=parseFloat($("glfxEndX").value);
var endY=parseFloat($("glfxEndY").value);

var tiltBlurRadius=parseFloat(
$("glfxTiltBlurRadius").value
);
var gradientRadius=parseFloat(
$("glfxGradientRadius").value
);
fxCanvas.tiltShift(
startX,
startY,
endX,
endY,
tiltBlurRadius,
gradientRadius
);
break;
case "glfxTriangleBlur":
var triangleRadius=parseFloat(
$("glfxTriangleRadius").value
);
fxCanvas.triangleBlur(triangleRadius);
break;
case "glfxZoomBlur":
var zoomCenterX=parseFloat(
$("glfxZoomCenterX").value
);
var zoomCenterY=parseFloat(
$("glfxZoomCenterY").value
);
var zoomStrength=parseFloat(
$("glfxZoomStrength").value
);
fxCanvas.zoomBlur(zoomCenterX,zoomCenterY,zoomStrength);
break;
case "glfxColorHalftone":
var halftoneCenterX=100;
var halftoneCenterY=100;
var halftoneAngle=parseFloat(
$("glfxHalftoneAngle").value
);
var halftoneSize=parseFloat(
$("glfxHalftoneSize").value
);

fxCanvas.colorHalftone(
halftoneCenterX,
halftoneCenterY,
halftoneAngle,
halftoneSize
);
break;
case "glfxDotScreen":
var dotCenterX=1;
var dotCenterY=1;
var dotAngle=1.1;
var dotSize=1.6;

if(isNotAuto){
dotAngle=parseFloat($("glfxDotAngle").value);
dotSize=parseFloat($("glfxDotSize").value);
}else{
dotAngle=filterValues.dotAngle;
dotSize=filterValues.dotSize;
}
// console.log("dotAngle", dotAngle)
// console.log("dotSize", dotSize)

fxCanvas.dotScreen(dotCenterX,dotCenterY,dotAngle,dotSize);
break;
case "glfxEdgeWork":
var edgeRadius=parseFloat(
$("glfxEdgeRadius").value
);
fxCanvas.edgeWork(edgeRadius);
break;
case "glfxHexagonalPixelate":
var hexCenterX=1;
var hexCenterY=1;
var hexScale=parseFloat($("glfxHexScale").value);
fxCanvas.hexagonalPixelate(hexCenterX,hexCenterY,hexScale);
break;
case "glfxInk":
var inkStrength=0.26;

if(isNotAuto){
inkStrength=parseFloat($("glfxInkStrength").value);
}else{
inkStrength=filterValues.inkStrength;
}
// console.log("applySelectedFilter: Ink strength is", inkStrength);

fxCanvas.ink(inkStrength);
break;
case "glfxBulgePinch":
var bulgeCenterX=parseFloat(
$("glfxBulgeCenterX").value
);
var bulgeCenterY=parseFloat(
$("glfxBulgeCenterY").value
);
var bulgeRadius=parseFloat(
$("glfxBulgeRadius").value
);
var bulgeStrength=parseFloat(
$("glfxBulgeStrength").value
);
fxCanvas.bulgePinch(
bulgeCenterX,
bulgeCenterY,
bulgeRadius,
bulgeStrength
);
break;
case "glfxSwirl":
var swirlCenterX=parseFloat(
$("glfxSwirlCenterX").value
);
var swirlCenterY=parseFloat(
$("glfxSwirlCenterY").value
);
var swirlRadius=parseFloat(
$("glfxSwirlRadius").value
);
var swirlAngle=parseFloat(
$("glfxSwirlAngle").value
);
fxCanvas.swirl(swirlCenterX,swirlCenterY,swirlRadius,swirlAngle);
break;
}
// console.log("applySelectedFilter: Filter applied and canvas updated");

}

function debounceGlfx(func,wait) {
let timeout;
return function () {
const context=this,
args=arguments;
clearTimeout(timeout);
timeout=setTimeout(()=>func.apply(context,args),wait);
};
}


function glfxAddEvent(){
$("glfxFilter").addEventListener("change",function () {
var value=this.value;
document.querySelectorAll(".glfxCcontrol-group").forEach(function (group) {
group.style.display="none";
});
if (value) {
$(value).style.display="block";
}
});
document.querySelectorAll(".glfxControls input").forEach(function (input) {
input.addEventListener("input",debounceGlfx(function () {
var activeObject=canvas.getActiveObject();
if (!glfxOriginalImage&&activeObject&&activeObject.type==="image") {
glfxOriginalImage=activeObject.getElement();
}

if (!activeObject) {
createToast("Select Image!");
return;
}

changeDoNotSaveHistory();
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyFilter();
}
changeDoSaveHistory();
},100)
);
});

$("glfxApplyButton").addEventListener("click",function () {
glfxApply();
});

$("glfxResetButton").addEventListener("click",function () {
glfxReset();
});
}

function glfxApply() {
if (glfxCopiedImage) {
glfxOriginalImage=glfxCopiedImage.cloneNode();
glfxCopiedImage=null;
glfxOriginalImage=null;
glfxResetFilterValues();
saveStateByManual();
}
}
function glfxApplyNoReset() {
if (glfxCopiedImage) {
glfxOriginalImage=glfxCopiedImage.cloneNode();
glfxCopiedImage=null;
glfxOriginalImage=null;
// saveStateByManual();
}
}

function glfxReset() {
if (glfxOriginalImage) {
var imgObj=new Image();
imgObj.onload=function () {
var img=new fabric.Image(imgObj);
var activeObject=lastActiveObjectState;
if (activeObject&&activeObject.type==="image") {
var copyObject={};
copy(activeObject,copyObject);
copy(copyObject,img);
}
canvas.remove(activeObject);
canvas.add(img);
canvas.setActiveObject(img);
canvas.requestRenderAll();
lastActiveObjectState=null;
glfxCopiedImage=null;
glfxOriginalImage=null;
glfxResetFilterValues();
lastActiveObjectState=canvas.getActiveObject();
};
imgObj.src=glfxOriginalImage.src;
}
}