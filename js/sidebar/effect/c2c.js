

async function C2CStart() {
const loading=OP_showLoading({
icon: 'process',step: 'Step1',substep: 'Clone',progress: 0
});

try {
const filterValues={
brightness: 0.35,
contrast: 0.35,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
};
glfxReset();

var activeObject=canvas.getActiveObject();
let tempObject=null;

if (isImage(activeObject)) {
activeObject.saveHistory=false;
activeObject.clone(function(cloned) {
cloned.set({
left: cloned.left,
top: cloned.top,
evented: true
});
cloned.saveHistory=false;
canvas.add(cloned);
tempObject=cloned;
});
}

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Ink up',progress: 15
});
if (activeObject&&activeObject.type==="image") {
if(filterValues.inkStrength){
glfxOriginalImage=activeObject.getElement();
await glfxApplyFilterToObject(activeObject,"glfxInk",filterValues);
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyNoReset();
}
}

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step3',substep: 'Brightness Contrast',progress: 30
});


glfxOriginalImage=activeObject.getElement();
await glfxApplyFilterToObject(activeObject,"glfxBrightnessContrast",filterValues);
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyNoReset();
}

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step4',substep: 'Dot',progress: 60
});
glfxOriginalImage=activeObject.getElement();
await glfxApplyFilterToObject(activeObject,"glfxDotScreen",filterValues);
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyNoReset();
}
}

OP_updateLoadingState(loading,{
icon: 'process',step: 'Step5',substep: 'Merge images',progress: 80
});

if (activeObject&&tempObject) {
const tempCanvas=document.createElement('canvas');
const ctx=tempCanvas.getContext('2d');

const originalWidth=activeObject.getElement().naturalWidth;
const originalHeight=activeObject.getElement().naturalHeight;

tempCanvas.width=originalWidth;
tempCanvas.height=originalHeight;

ctx.imageSmoothingEnabled=true;
ctx.imageSmoothingQuality='high';
ctx.drawImage(activeObject.getElement(),0,0,originalWidth,originalHeight);
ctx.globalAlpha=0.4;
ctx.drawImage(tempObject.getElement(),0,0,originalWidth,originalHeight);
const dataURL=tempCanvas.toDataURL('image/webp',1.0);

fabric.Image.fromURL(dataURL,function(newImage) {
newImage.set({
left: activeObject.left,
top: activeObject.top,
scaleX: activeObject.scaleX,
scaleY: activeObject.scaleY
});

copy(activeObject,newImage);

newImage.set({
objectCaching: false,
imageSmoothing: true
});


activeObject.saveHistory=false;
activeObject.saveHistory=false;

canvas.remove(activeObject);
canvas.remove(tempObject);
canvas.add(newImage);
canvas.setActiveObject(newImage);
canvas.renderAll();
});
}
} finally {
OP_hideLoading(loading);
}
}

