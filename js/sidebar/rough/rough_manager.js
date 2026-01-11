class RoughManager {
constructor() {
this.options={
roughness: 2,
bowing: 1,
seed: 1,
fillStyle: 'hachure',
fillWeight: 1,
hachureAngle:-41,
hachureGap: 4,
curveStepCount: 9,
curveFitting: 0.95,
strokeWidth: 2,
simplification: 0,
disableMultiStroke: false,
disableMultiStrokeFill: false,
fill: '#e6e6e6',
stroke: '#000000'
};
}

setOptions(options) {
this.options={...this.options,...options};
return this;
}

getOptionsFromUI() {
const options={
roughness: parseFloat($('roughness').value),
bowing: parseFloat($('bowing').value),
seed: parseInt($('seed').value),
fillStyle: $('fillStyle').value,
fillWeight: parseFloat($('fillWeight').value),
hachureAngle: parseInt($('hachureAngle').value),
hachureGap: parseFloat($('hachureGap').value),
curveStepCount: parseInt($('curveStepCount').value),
curveFitting: parseFloat($('curveFitting').value),
strokeWidth: parseFloat($('strokeWidth').value),
simplification: parseFloat($('simplification').value),
disableMultiStroke: $('disableMultiStroke').checked,
disableMultiStrokeFill: $('disableMultiStrokeFill').checked,
fill: $('fillColor').value,
stroke: $('strokeColor').value

};

this.options=options;
return this;
}

isRoughenable(fabricObj) {
const supportedTypes=['path','polygon','rect','circle','ellipse','line'];
if(supportedTypes.includes(fabricObj.type)){
return true;
}
if(fabricObj.originalSvg){
return true;
}
return false;
}

roughPath2FabrcPath(roughPath) {
let pathData='';

roughPath.sets.forEach(set=>{
set.ops.forEach(op=>{
switch (op.op) {
case 'move':
pathData+=`M ${op.data[0]} ${op.data[1]} `;
break;
case 'lineTo':
pathData+=`L ${op.data[0]} ${op.data[1]} `;
break;
case 'bcurveTo':
pathData+=`C ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]}, ${op.data[4]} ${op.data[5]} `;
break;
case 'qcurveTo':
pathData+=`Q ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]} `;
break;
case 'arcTo':
pathData+=`A ${op.data[0]} ${op.data[1]}, ${op.data[2]}, ${op.data[3]}, ${op.data[4]}, ${op.data[5]} ${op.data[6]} `;
break;
case 'close':
pathData+='Z ';
break;
}
});
});

return pathData;
}

roughenObject(fabricObj) {
this.getOptionsFromUI();

return new Promise((resolve,reject)=>{
try {
if (fabricObj.originalSvg) {
this.roughenSvgObject(fabricObj).then(roughObject=>{
resolve(roughObject);
}).catch(error=>{
createToastError(getText("rought_error"),"code:001");
resolve(null);
});
return;
}

const svgNode=document.createElementNS('http://www.w3.org/2000/svg','svg');
const rc=rough.svg(svgNode);

let roughElement;

if (fabricObj.type==='path') {
const pathData=fabricObj.path.map(p=>{
if (p[0]==='M'||p[0]==='L') {
return p[0]+' '+p[1]+' '+p[2];
} else if (p[0]==='Z') {
return 'Z';
}
return '';
}).join(' ');

roughElement=rc.path(pathData,this.options);
} else if (fabricObj.type==='polygon') {
function roughenPolygon(polygon,options) {
const roughCanvas=rough.canvas($('mangaImageCanvas'));
const points=polygon.points.map(p=>[p.x,p.y]);
const roughPolygon=roughCanvas.polygon(points,options);

let pathData='';
roughPolygon.sets.forEach(set=>{
set.ops.forEach(op=>{
switch (op.op) {
case 'move':
pathData+=`M ${op.data[0]} ${op.data[1]} `;
break;
case 'bcurveTo':
pathData+=`C ${op.data[0]}, ${op.data[1]}, ${op.data[2]}, ${op.data[3]}, ${op.data[4]}, ${op.data[5]} `;
break;
}
});
});

if (pathData.length>0) {
const newPolygon=new fabric.Path(pathData,{
left: polygon.left,
top: polygon.top,
scaleX: polygon.scaleX,
scaleY: polygon.scaleY,
angle: polygon.angle,
stroke: options.stroke||'blue',
strokeWidth: options.strokeWidth||2,
fill: options.fill
});
canvas.add(newPolygon);
canvas.remove(polygon);
canvas.renderAll();
} else {
createToastError(getText("rought_error"),"code:002");
}
}

roughenPolygon(fabricObj,this.options);
return;
} else if (fabricObj.type==='rect') {
roughElement=rc.rectangle(
fabricObj.left,
fabricObj.top,
fabricObj.width,
fabricObj.height,
this.options
);
} else if (fabricObj.type==='circle') {
roughElement=rc.circle(
fabricObj.left+fabricObj.radius,
fabricObj.top+fabricObj.radius,
fabricObj.radius*2,
this.options
);
} else if (fabricObj.type==='ellipse') {
roughElement=rc.ellipse(
fabricObj.left+fabricObj.rx,
fabricObj.top+fabricObj.ry,
fabricObj.rx*2,
fabricObj.ry*2,
this.options
);
} else if (fabricObj.type==='line') {
roughElement=rc.line(
fabricObj.x1,
fabricObj.y1,
fabricObj.x2,
fabricObj.y2,
this.options
);
} else {
createToastError(getText("rought_error"),"code:003");
resolve(null);
return;
}

svgNode.appendChild(roughElement);
const svgString=new XMLSerializer().serializeToString(svgNode);

fabric.loadSVGFromString(svgString,(objects,options)=>{
const roughObject=fabric.util.groupSVGElements(objects,options);

roughObject.set({
left: fabricObj.left,
top: fabricObj.top,
originX: fabricObj.originX,
originY: fabricObj.originY,
scaleX: fabricObj.scaleX,
scaleY: fabricObj.scaleY,
angle: fabricObj.angle,
flipX: fabricObj.flipX,
flipY: fabricObj.flipY,
opacity: fabricObj.opacity,
selectable: fabricObj.selectable,
hasControls: fabricObj.hasControls,
hasBorders: fabricObj.hasBorders,
});

resolve(roughObject);
});
} catch (error) {
createToastError(getText("rought_error"),"code:004");
resolve(null);
}
});
}

roughenSvgObject(fabricObj) {
return new Promise((resolve,reject)=>{
try {
const svgData=fabricObj.originalSvg;

if (!svgData) {
createToastError(getText("rought_error"),"code:005");
resolve(null);
return;
}

const roughOptions=this.options;
const roughCanvas=rough.canvas(document.createElement('canvas'));

const extractSvgPaths=(svgString)=>{
const parser=new DOMParser();
const doc=parser.parseFromString(svgString,'image/svg+xml');
const paths=Array.from(doc.querySelectorAll('path'));
return paths.map(path=>path.getAttribute('d')).filter(d=>d);
};

const directPaths=extractSvgPaths(svgData);

const processPaths=(roughSvgPath)=>{
if (roughSvgPath.sets.length>=2) {
const strokeSet=roughSvgPath.sets[0];
let strokePathData='';
strokeSet.ops.forEach(op=>{
switch (op.op) {
case 'move':
strokePathData+=`M ${op.data[0]} ${op.data[1]} `;
break;
case 'lineTo':
strokePathData+=`L ${op.data[0]} ${op.data[1]} `;
break;
case 'bcurveTo':
strokePathData+=`C ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]}, ${op.data[4]} ${op.data[5]} `;
break;
case 'qcurveTo':
strokePathData+=`Q ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]} `;
break;
case 'close':
strokePathData+='Z ';
break;
}
});

const fillSet=roughSvgPath.sets[1];
let fillPathData='';
fillSet.ops.forEach(op=>{
switch (op.op) {
case 'move':
fillPathData+=`M ${op.data[0]} ${op.data[1]} `;
break;
case 'lineTo':
fillPathData+=`L ${op.data[0]} ${op.data[1]} `;
break;
case 'bcurveTo':
fillPathData+=`C ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]}, ${op.data[4]} ${op.data[5]} `;
break;
case 'qcurveTo':
fillPathData+=`Q ${op.data[0]} ${op.data[1]}, ${op.data[2]} ${op.data[3]} `;
break;
case 'close':
fillPathData+='Z ';
break;
}
});

const strokePathObject=new fabric.Path(strokePathData,{
stroke: roughOptions.stroke,
strokeWidth: roughOptions.strokeWidth,
fill: 'transparent'
});

const fillPathObject=new fabric.Path(fillPathData,{
stroke: 'transparent',
fill: roughOptions.fill==='none' ? 'transparent' : roughOptions.fill
});

const group=new fabric.Group([strokePathObject,fillPathObject],{
left: fabricObj.left,
top: fabricObj.top,
scaleX: fabricObj.scaleX,
scaleY: fabricObj.scaleY,
angle: fabricObj.angle,
flipX: fabricObj.flipX,
flipY: fabricObj.flipY,
opacity: fabricObj.opacity,
selectable: fabricObj.selectable,
hasControls: fabricObj.hasControls,
hasBorders: fabricObj.hasBorders,
});

resolve(group);
} else {
const roughSvgPathData=this.roughPath2FabrcPath(roughSvgPath);

const roughPathObject=new fabric.Path(roughSvgPathData,{
left: fabricObj.left,
top: fabricObj.top,
scaleX: fabricObj.scaleX,
scaleY: fabricObj.scaleY,
angle: fabricObj.angle,
flipX: fabricObj.flipX,
flipY: fabricObj.flipY,
opacity: fabricObj.opacity,
selectable: fabricObj.selectable,
hasControls: fabricObj.hasControls,
hasBorders: fabricObj.hasBorders,
stroke: roughOptions.stroke,
strokeWidth: roughOptions.strokeWidth,
fill: roughOptions.fill==='none' ? 'transparent' : roughOptions.fill
});

resolve(roughPathObject);
}
};

if (directPaths.length>0) {
const pathData=directPaths.join(' ');

const roughSvgPath=roughCanvas.generator.path(pathData,roughOptions);
processPaths(roughSvgPath);
} else {
fabric.loadSVGFromString(svgData,(objects,options)=>{

const paths=objects.filter(obj=>{
const isTransparent=(obj.fill==='none'||obj.fill==='')&&!obj.stroke;
return!isTransparent;
});

if (paths.length===0) {
createToastError(getText("rought_error"),"code:006");
resolve(null);
return;
}

let pathData='';

for (const obj of paths) {
try {
if (obj.path&&Array.isArray(obj.path)) {
pathData+=obj.path.map(p=>{
if (Array.isArray(p)&&p.length>0) {
return p[0]+(p.slice(1).join(' '));
}
return '';
}).join(' ');
} else if (obj.d) {
pathData+=obj.d+' ';
} else if (typeof obj.getAttribute==='function'&&obj.getAttribute('d')) {
pathData+=obj.getAttribute('d')+' ';
} else if (obj.points) {
pathData+='M '+obj.points.map(p=>`${p.x} ${p.y}`).join(' L ')+' Z';
}
} catch (e) {
createToastError(getText("rought_error"),"code:007");
}
}

if (!pathData&&svgData) {
try {
const parser=new DOMParser();
const svgDoc=parser.parseFromString(svgData,'image/svg+xml');
const pathElements=svgDoc.querySelectorAll('path');

pathElements.forEach(path=>{
const d=path.getAttribute('d');
if (d) pathData+=d+' ';
});
} catch (e) {
createToastError(getText("rought_error"),"code:008");
}
}

if (!pathData) {
createToastError(getText("rought_error"),"code:009");
resolve(null);
return;
}

const roughSvgPath=roughCanvas.generator.path(pathData,roughOptions);
processPaths(roughSvgPath);
});
}
} catch (error) {
createToastError(getText("rought_error"),"code:010");
resolve(null);
}
});
}

async roughenObjects(fabricObjs) {
this.getOptionsFromUI();

const results=[];
for (const obj of fabricObjs) {
try {
if (this.isRoughenable(obj)) {
const roughObj=await this.roughenObject(obj);
if (roughObj) {
results.push(roughObj);
}
} else {
checkRoughTarget();
}
} catch (error) {
createToastError(getText("rought_error"),"code:011");
}
}
return results;
}
}

async function roughenSelectedObject() {
const activeObject=canvas.getActiveObject();
if (!activeObject) {
checkRoughTarget();
return;
}

console.log("roughenSelectedObject aaa");
if (!roughManager.isRoughenable(activeObject)) {
console.log("roughenSelectedObject bbb");
checkRoughTarget();
return;
}
console.log("roughenSelectedObject ccc");

const roughObj=await roughManager.roughenObject(activeObject);
if (roughObj) {
activeObject.visible=false;
canvas.remove(activeObject);
canvas.add(roughObj);
canvas.setActiveObject(roughObj);
} else {
createToastError(getText("rought_error"),"code:012");

}

canvas.renderAll();
}

async function refreshRoughObject() {
const activeObject=canvas.getActiveObject();
if (!activeObject||!activeObject.originalObject) return;

const originalObj=activeObject.originalObject;

syncObjectProperties(activeObject,originalObj);

canvas.remove(activeObject);
originalObj.roughObject=null;

const newRoughObj=await roughManager.roughenObject(originalObj);
if (newRoughObj) {
originalObj.roughObject=newRoughObj;
newRoughObj.originalObject=originalObj;

canvas.add(newRoughObj);
canvas.setActiveObject(newRoughObj);
}

canvas.renderAll();
}

function toggleRoughVisibility() {
const activeObject=lastCheckObject;
if (!activeObject) {
checkRoughTarget();
return;
}

if (activeObject.originalObject) {
checkRoughTarget();
}
else if (activeObject.roughObject) {
checkRoughTarget();
}
else {
roughenSelectedObject();
}

canvas.renderAll();
}

function syncObjectProperties(sourceObj,targetObj) {
const propsToSync=[
'left','top','scaleX','scaleY','angle',
'flipX','flipY','opacity','width','height'
];

propsToSync.forEach(prop=>{
if (sourceObj[prop]!==undefined) {
targetObj[prop]=sourceObj[prop];
}
});

if (sourceObj.stroke) {
targetObj.stroke=sourceObj.stroke;
}

if (sourceObj.strokeWidth) {
targetObj.strokeWidth=sourceObj.strokeWidth;
}

if (targetObj.type==='path'&&sourceObj.path) {
targetObj.path=sourceObj.path;
}

if (targetObj.type==='polygon'&&sourceObj.points) {
targetObj.points=sourceObj.points;
}

targetObj.setCoords();
}

function updateSliderValue(id) {
$(id+'-value').textContent=$(id).value;
}

function setupEventListeners() {
$('toggle-rough').addEventListener('click',toggleRoughVisibility);
}

function toggleHachureParams() {
const fillStyle=$('fillStyle').value;
const hachureParams=$('hachureParams');

if (fillStyle==='hachure'||fillStyle==='cross-hatch'||fillStyle==='zigzag'||fillStyle==='dashed'||fillStyle==='zigzag-line'||fillStyle==='nothing') {
hachureParams.style.display='block';
} else {
hachureParams.style.display='none';
}
}

function initRough() {
$('fillStyle').addEventListener('change',toggleHachureParams);

setupEventListeners();
toggleHachureParams();
}

document.addEventListener('DOMContentLoaded',function() {
initRough();
});

const roughManager=new RoughManager();