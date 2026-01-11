async function C2BWStartLight(){
const filterValues={
brightness: 0.35,
contrast: 0.35,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
};
C2BWStart(filterValues);
}
async function C2BWStartDark(){
const filterValues={
brightness: 0.22,
contrast: 0.22,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
};
C2BWStart(filterValues);
}
async function C2BWStartRough(){
const filterValues={
brightness: 0.41,
contrast: 0.41,
dotSize: 1.5,
dotAngle: 0.1,
inkStrength: 0.42
};
C2BWStart(filterValues);
}
async function C2BWStartSimple(){
const filterValues={
brightness: 0.15,
contrast: 0.15,
dotSize: 1.5,
dotAngle: 0
};
C2BWStart(filterValues);
}



async function C2BWStart(filterValues) {

const loading=OP_showLoading({
icon: 'process',step: 'Step1',substep: 'Ink up',progress: 0
});
var activeObject=canvas.getActiveObject();
try {
// console.log(filterValues);
glfxReset();
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
icon: 'process',step: 'Step2',substep: 'Brightness Contrast',progress: 50
});

glfxOriginalImage=activeObject.getElement();
await glfxApplyFilterToObject(activeObject,"glfxBrightnessContrast",filterValues);
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyNoReset();
}


OP_updateLoadingState(loading,{
icon: 'save',step: 'Step3',substep: 'Dot',progress: 100
});

glfxOriginalImage=activeObject.getElement();
await glfxApplyFilterToObject(activeObject,"glfxDotScreen",filterValues);
if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyNoReset();
}
}
} finally {
OP_hideLoading(loading);
saveStateByManual();
}
}

