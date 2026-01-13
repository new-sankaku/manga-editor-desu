const allBlendModes=['normal','add','screen','darken','lighten','color-dodge','color-burn','linear-burn','linear-dodge','linear-light','hard-light','soft-light','pin-light','difference','exclusion','overlay','saturation','color','luminosity','add-npm','subtract','divide','vivid-light','hard-mix','negation'];

const layerDisplaySize=300;
const blendDisplaySize=450;


function createFloatingWindow() {
const floatingWindow=document.createElement("div");
floatingWindow.id="blendFloatingWindow";

const header=document.createElement("div");
header.id="blendFloatingWindowHeader";
header.textContent=getText("blendResult");


const controls=document.createElement("div");
controls.id="blendControls";

const reblendButton=document.createElement("button");
reblendButton.id="reblendButton";
reblendButton.textContent=getText("reblend");
reblendButton.onclick=handleReblend;

const closeButton=document.createElement("button");
closeButton.id="closeButton";
closeButton.textContent="Close";
closeButton.onclick=handleClose;

const addFillButton=document.createElement("button");
addFillButton.textContent=getText("addFillLayer");
addFillButton.onclick=showFillLayerEditor;

const addGradientButton=document.createElement("button");
addGradientButton.textContent=getText("addGradientLayer");
addGradientButton.onclick=showGradientLayerEditor;

controls.appendChild(reblendButton);
controls.appendChild(closeButton);
controls.appendChild(addFillButton);
controls.appendChild(addGradientButton);

const sourceImages=document.createElement("div");
sourceImages.id="sourceImages";

const blendModes=document.createElement("div");
blendModes.id="blendModes";

floatingWindow.appendChild(header);
floatingWindow.appendChild(controls);
floatingWindow.appendChild(sourceImages);
floatingWindow.appendChild(blendModes);

document.body.appendChild(floatingWindow);

setupInteractJS(floatingWindow);
}

function recreateFloatingWindow() {
const existingWindow=$("blendFloatingWindow");
if (existingWindow) {
existingWindow.remove();
}
createFloatingWindow();
}


function setupInteractJS(element) {
interact(element)
.draggable({
listeners: {
move(event) {
const target=event.target;
const x=(parseFloat(target.getAttribute("data-x"))||0)+event.dx;
const y=(parseFloat(target.getAttribute("data-y"))||0)+event.dy;

target.style.transform=`translate(${x}px, ${y}px)`;

target.setAttribute("data-x",x);
target.setAttribute("data-y",y);
},
},
inertia: true,
modifiers: [
interact.modifiers.restrictRect({
restriction: "parent",
endOnly: true,
}),
],
})
.resizable({
edges: {left: true,right: true,bottom: true,top: true},
listeners: {
move(event) {
let {x,y}=event.target.dataset;

x=(parseFloat(x)||0)+event.deltaRect.left;
y=(parseFloat(y)||0)+event.deltaRect.top;

Object.assign(event.target.style,{
width: `${event.rect.width}px`,
height: `${event.rect.height}px`,
transform: `translate(${x}px, ${y}px)`,
});

Object.assign(event.target.dataset,{x,y});
},
},
modifiers: [
interact.modifiers.restrictEdges({
outer: "parent",
endOnly: true,
}),
interact.modifiers.restrictSize({
min: {width: 100,height: 100},
}),
],
inertia: true,
});
}

async function blendCanvasesWithPixi(canvases,blendMode) {
const maxWidth=Math.max(...canvases.map((c)=>c.width));
const maxHeight=Math.max(...canvases.map((c)=>c.height));
const app=new PIXI.Application();
await app.init({
width: maxWidth,
height: maxHeight,
antialias: false,
backgroundColor: "transparent",
backgroundAlpha: 0,
useBackBuffer: true,
clearBeforeRender: false,
preserveDrawingBuffer: true,
});
canvases.forEach((canvas,index)=>{
const texture=PIXI.Texture.from(canvas);
const sprite=new PIXI.Sprite({
texture,
blendMode: index===0 ? "normal" : blendMode,
});
app.stage.addChild(sprite);
});
app.render();
const blendedCanvas=document.createElement("canvas");
blendedCanvas.width=maxWidth;
blendedCanvas.height=maxHeight;
blendedCanvas.getContext("2d").drawImage(app.canvas,0,0);
app.destroy();
return blendedCanvas;
}

async function updateBlendModes(imageLayerList) {
const blendModesContainer=$("blendModes");
blendModesContainer.innerHTML="";
const checkedLayers=imageLayerList.filter((layer)=>layer.layerCheck);
if (checkedLayers.length<2) return;
const canvases=checkedLayers.map((layer)=>
createCanvasFromFabricImage(layer)
);

for (let i=0;i<allBlendModes.length;i++) {
const blendedCanvas=await blendCanvasesWithPixi(
canvases,
allBlendModes[i]
);
const container=document.createElement("div");
container.className="blend-mode-container";
const displayCanvas=createScaledCanvas(
blendedCanvas,
blendDisplaySize,
blendDisplaySize
);
displayCanvas.onclick=()=>showEnlargedImage(blendedCanvas.toDataURL());
container.appendChild(displayCanvas);
const label=document.createElement("div");

label.textContent=getText(allBlendModes[i]);

container.appendChild(label);
const submitButton=document.createElement("button");
submitButton.textContent=getText("submit");
submitButton.className="submit-blend";
submitButton.onclick=()=>handleSubmit(blendedCanvas);
container.appendChild(submitButton);
blendModesContainer.appendChild(container);
await new Promise((resolve)=>setTimeout(resolve,0));
}
}

function createScaledCanvas(sourceCanvas,maxWidth,maxHeight){
return HtmlCanvasUtil.createScaledCanvas(sourceCanvas,maxWidth,maxHeight);
}

function updateLayerPreviewStyle(layer,previewCanvas) {
if (layer.layerCheck) {
previewCanvas.classList.remove("unchecked");
} else {
previewCanvas.classList.add("unchecked");
}
}

function addImagePreviewsToFloatingWindow(imageLayerList) {
const sourceImagesContainer=$("sourceImages");
sourceImagesContainer.innerHTML="";

var first=true;
imageLayerList.forEach((layer,index)=>{
const previewContainer=document.createElement("div");
previewContainer.className="layer-preview-blend";
const previewCanvas=createCanvasFromFabricImage(layer);
const scaledPreviewCanvas=createScaledCanvas(
previewCanvas,
layerDisplaySize,
layerDisplaySize
);
scaledPreviewCanvas.onclick=()=>toggleFloatingLayerCheck(layer,index,scaledPreviewCanvas);
previewContainer.appendChild(scaledPreviewCanvas);
const label=document.createElement("div");
if (first) {
label.textContent=`Lower Layer ${index + 1}`;
first=false;
} else {
label.textContent=`Layer ${index + 1}`;
}

previewContainer.appendChild(label);
sourceImagesContainer.appendChild(previewContainer);
updateLayerPreviewStyle(layer,scaledPreviewCanvas);
});
}

function toggleFloatingLayerCheck(layer,index,previewCanvas) {
layer.layerCheck=!layer.layerCheck;
updateLayerPreviewStyle(layer,previewCanvas);
updateLayerPreviewStyle(
layer,
$("layerPreviewsBlend").children[index].querySelector("canvas")
);
layer.visible=layer.layerCheck;
canvas.renderAll();
}

var imageLayerListTemp=null;

async function handleBlend() {
var imageLayerList=getImageObjectListByLayerChecked();
if(imageLayerList.length<1){
var blendLowImages=getText("blendLowImages");
createToastError("Blend error",blendLowImages);
return;
}

imageLayerListTemp=imageLayerList;

layerLogger.debug("handleBlend start",imageLayerList.length);
addImagePreviewsToFloatingWindow(imageLayerList);
$("blendFloatingWindow").style.display="block";

await updateBlendModes(imageLayerList);
}

async function handleReblend() {
await updateBlendModes(imageLayerListTemp);
}


function handleSubmit(blendedCanvas,quality=0.98) {
sendHtmlCanvas2FabricCanvas(blendedCanvas);
removeAdditionalLayers();
$("blendFloatingWindow").style.display="none";
}



function handleClose() {
removeAdditionalLayers();
$("blendFloatingWindow").style.display="none";
}

createFloatingWindow();



let brendContainer,brendImg;

function initializeBrendImageViewer() {
brendContainer=document.createElement('div');
brendContainer.id='enlargedImageContainer';
brendContainer.style.display='none';

brendImg=document.createElement('img');
brendImg.id='enlargedImage';

brendContainer.appendChild(brendImg);
document.body.appendChild(brendContainer);

brendContainer.addEventListener('click',hideEnlargedImage);
}

function showEnlargedImage(src) {
brendImg.src=src;
brendContainer.style.display="block";
}

function hideEnlargedImage() {
brendContainer.style.display='none';
}

function showFillLayerEditor() {
const editor=createLayerEditor('fill');
editor.innerHTML=`
    <h3>${getText("fillLayer")}</h3>
    <input id="blendFillColor" class="jscolor-color-picker" data-initial-color="rgba(0,0,0,1)">
    <button onclick="addFillLayer()">${getText("addLayer")}</button>
    <button onclick="closeLayerEditor('fill')">${getText("cancel")}</button>
  `;
document.body.appendChild(editor);
jsColorSetById("gradientStart");
}

function showGradientLayerEditor() {
const editor=createLayerEditor('gradient');
editor.innerHTML=`
    <h3>${getText("gradientLayer")}</h3>
    <input id="gradientStart" class="jscolor-color-picker" data-initial-color="rgba(0,0,0,1)" >
    <input id="gradientEnd" class="jscolor-color-picker" data-initial-color="rgba(255,255,255,1)" >
    <canvas id="gradientDirection" width="200" height="200" style="border: 1px solid black;">
      ${getText("dragToSetDirection")}
    </canvas>
    <button onclick="addGradientLayer()">${getText("addLayer")}</button>
    <button onclick="closeLayerEditor('gradient')">${getText("cancel")}</button>
  `;
document.body.appendChild(editor);

jsColorSetById("gradientStart");
jsColorSetById("gradientEnd");
setupGradientDirectionDrag();
}


function createLayerEditor(type) {
const editor=document.createElement('div');
editor.id=`${type}LayerEditor`;
editor.style.position='fixed';
editor.style.top='50%';
editor.style.left='50%';
editor.style.transform='translate(-50%, -50%)';
editor.style.background='white';
editor.style.padding='20px';
editor.style.border='1px solid black';
editor.style.zIndex='1000';
return editor;
}

let startX,startY,endX,endY;

function setupGradientDirectionDrag() {
const directionElement=$('gradientDirection');

directionElement.onmousedown=(e)=>{
startX=e.offsetX;
startY=e.offsetY;

document.onmousemove=(e)=>{
const rect=directionElement.getBoundingClientRect();
endX=e.clientX-rect.left;
endY=e.clientY-rect.top;
drawGradientPreview();
};

document.onmouseup=()=>{
document.onmousemove=null;
document.onmouseup=null;
};
};

endX=directionElement.width;
endY=directionElement.height;
// drawGradientPreview();
}

function drawGradientPreview() {
const directionElement=$('gradientDirection');
const ctx=directionElement.getContext('2d');
const gradient=ctx.createLinearGradient(startX,startY,endX,endY);

layerLogger.debug("$('gradientStart').value:",$('gradientStart').value);
gradient.addColorStop(0,$('gradientStart').value);
gradient.addColorStop(1,$('gradientEnd').value);
ctx.fillStyle=gradient;
ctx.fillRect(0,0,directionElement.width,directionElement.height);
}




let additionalLayers=[];
function addFillLayer() {
const color=$('blendFillColor').value;
const fillLayer=new fabric.Rect({
width: canvas.width,
height: canvas.height,
fill: color,
layerCheck: true,
selectable: false
});
canvas.add(fillLayer);
additionalLayers.push(fillLayer);
canvas.renderAll();
updateLayerList();
closeLayerEditor('fill');
}

function addGradientLayer() {
const startColor=$('gradientStart').value;
const endColor=$('gradientEnd').value;
const angle=Math.atan2(endY-startY,endX-startX);

const gradientLayer=new fabric.Rect({
width: canvas.width,
height: canvas.height,
angle: angle*(180/Math.PI),
fill: new fabric.Gradient({
type: 'linear',
coords: {
x1: 0,
y1: 0,
x2: canvas.width,
y2: 0
},
colorStops: [
{offset: 0,color: startColor},
{offset: 1,color: endColor}
]
}),
layerCheck: true,
selectable: false
});
canvas.add(gradientLayer);
additionalLayers.push(gradientLayer);
canvas.renderAll();
updateLayerList();
closeLayerEditor('gradient');
}



function closeLayerEditor(type) {
const editor=$(`${type}LayerEditor`);
editor.remove();
}

function updateLayerList() {
let imageLayers=getImageObjectListByLayerChecked();
let allLayers=[...imageLayers,...additionalLayers.filter(layer=>layer.layerCheck)];
imageLayerListTemp=allLayers;
addImagePreviewsToFloatingWindow(allLayers);
handleReblend();
}

function removeAdditionalLayers() {
additionalLayers.forEach(layer=>{
canvas.remove(layer);
});
additionalLayers=[];
canvas.renderAll();
}