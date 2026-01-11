
async function loadBookSize(width,height,addPanel,newPage=false) {
const loading=OP_showLoading({
icon: 'process',step: 'Step1',substep: 'Next Project',progress: 0
});
try{
if (stateStack.length>2||newPage) {
OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Zip Start',progress: 40
});

await btmSaveProjectFile().then(()=>{
setCanvasGUID();
});
OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Next Project End',progress: 90
});

changeDoNotSaveHistory();
resizeCanvasToObject(width,height);
if (addPanel) {
addSquareBySize(width,height);
} else {
initImageHistory();
saveState();
}
changeDoSaveHistory();
} else {
changeDoNotSaveHistory();
resizeCanvasToObject(width,height);
if (addPanel) {
addSquareBySize(width,height);
} else {
initImageHistory();
saveState();
}
changeDoSaveHistory();
setCanvasGUID();
}
}finally{
OP_hideLoading(loading);
}

}

function addSquareBySize(width,height) {
initImageHistory();
saveState();

var strokeWidthScale=canvas.width/700;
var strokeWidth=2*strokeWidthScale;

var widthScale=canvas.width/width;
var heightScale=canvas.height/height;

var svgPaggingWidth=svgPagging*widthScale;
var svgPaggingHeight=svgPagging*heightScale;

var svgPaggingHalfWidth=svgPaggingWidth/2;
var svgPaggingHalfHeight=svgPaggingHeight/2;

var newWidth=width*widthScale-svgPaggingWidth-strokeWidth;
var newHeight=height*heightScale-svgPaggingHeight-strokeWidth;

// console.log("addSquareBySize height", height);
// console.log("addSquareBySize svgPaggingWidth", svgPaggingWidth);
// console.log("addSquareBySize svgPaggingHeight", svgPaggingHeight);
// console.log("addSquareBySize heightScale", heightScale);
// console.log("addSquareBySize newHeight", newHeight);

var square=new fabric.Polygon(
[
{x: 0,y: 0},
{x: newWidth,y: 0},
{x: newWidth,y: newHeight},
{x: 0,y: newHeight},
],
{
left: svgPaggingHalfWidth,
top: svgPaggingHalfHeight,
scaleX: 1,
scaleY: 1,
strokeWidth: strokeWidth,
strokeUniform: true,
stroke: "black",
objectCaching: false,
transparentCorners: false,
cornerColor: "Blue",
isPanel: true
}
);

setText2ImageInitPrompt(square);
setPanelValue(square);
canvas.add(square);

square.selectable=false;
updateLayerPanel();
}

document.addEventListener('DOMContentLoaded',function () {

$("CustomPanelButton").addEventListener("click",function () {
var x=$("customPanelSizeX").value;
var y=$("customPanelSizeY").value;
loadBookSize(x,y,false);
canvas.renderAll();
adjustCanvasSize();
});
$on($("A4-H"),"click",()=>loadBookSize(210,297,true));
$on($("A4-V"),"click",()=>loadBookSize(297,210,true));
$on($("B4-H"),"click",()=>loadBookSize(257,364,true));
$on($("B4-V"),"click",()=>loadBookSize(364,257,true));
$on($("insta"),"click",()=>loadBookSize(1080,1080,true));
$on($("insta-story"),"click",()=>loadBookSize(1080,1920,true));
$on($("insta-portrait"),"click",()=>loadBookSize(1080,1350,true));
$on($("fb-page-cover"),"click",()=>loadBookSize(1640,664,true));
$on($("fb-event"),"click",()=>loadBookSize(1920,1080,true));
$on($("fb-group-header"),"click",()=>loadBookSize(1640,856,true));
$on($("youtube-thumbnail"),"click",()=>loadBookSize(1280,720,true));
$on($("youtube-profile"),"click",()=>loadBookSize(800,800,true));
$on($("youtube-cover"),"click",()=>loadBookSize(2560,1440,true));
$on($("twitter-profile"),"click",()=>loadBookSize(400,400,true));
$on($("twitter-header"),"click",()=>loadBookSize(1500,500,true));
});



function addArRect() {
var width=parseFloat($("ar_width").value);
var height=parseFloat($("ar_height").value);

if (isNaN(width)||isNaN(height)||width<=0||height<=0) {
return;
}
var canvasWidth=canvas.getWidth();
var canvasHeight=canvas.getHeight();
var canvasSize=Math.min(canvasWidth,canvasHeight)*0.25;
var aspectRatio=width/height;
if (width>height) {
width=canvasSize;
height=canvasSize/aspectRatio;
} else {
height=canvasSize;
width=canvasSize*aspectRatio;
}
var points=[
{x: 0,y: 0},
{x: width,y: 0},
{x: width,y: height},
{x: 0,y: height},
];
addShape(points);
}

function addShape(points,options={}) {
var canvasWidth=canvas.width;
var canvasHeight=canvas.height;

var minX=Math.min(...points.map((p)=>p.x));
var maxX=Math.max(...points.map((p)=>p.x));
var minY=Math.min(...points.map((p)=>p.y));
var maxY=Math.max(...points.map((p)=>p.y));

var shapeWidth=maxX-minX;
var shapeHeight=maxY-minY;

var scaleX=canvasWidth/3/shapeWidth;
var scaleY=canvasHeight/3/shapeHeight;
var scale=Math.min(scaleX,scaleY);

options.strokeWidth=2*(canvas.width/700);
options.strokeUniform=true;
options.stroke="black";
options.objectCaching=false;
options.transparentCorners=false;
options.isPanel=true;
options.left=options.left||50;
options.top=options.top||50;
options.scaleX=scale;
options.scaleY=scale;

var shape=new fabric.Polygon(points,options);
setText2ImageInitPrompt(shape);
canvas.add(shape);
canvas.setActiveObject(shape);
setPanelValue(shape);
updateLayerPanel();
}

function addSquare() {
var points=[
{x: 0,y: 0},
{x: 200,y: 0},
{x: 200,y: 200},
{x: 0,y: 200},
];
addShape(points);
}

function addPentagon() {
var side=150;
var angle=54;
var points=[];
for (var i=0;i<5;i++) {
var x=side*Math.cos((Math.PI/180)*(angle+i*72));
var y=side*Math.sin((Math.PI/180)*(angle+i*72));
points.push({x: x,y: y});
}
addShape(points);
}

function addTallRect() {
var points=[
{x: 0,y: 0},
{x: 100,y: 0},
{x: 100,y: 400},
{x: 0,y: 400},
];
addShape(points);
}

function addTallTrap() {
var points=[
{x: 50,y: 0},
{x: 150,y: 0},
{x: 100,y: 400},
{x: 0,y: 400},
];
addShape(points);
}

function addWideRect() {
var points=[
{x: 0,y: 0},
{x: 400,y: 0},
{x: 400,y: 100},
{x: 0,y: 100},
];
addShape(points);
}

function addWideTrap() {
var points=[
{x: 0,y: 0},
{x: 400,y: 0},
{x: 350,y: 100},
{x: 50,y: 100},
];
addShape(points);
}

function addTrapezoid() {
var points=[
{x: 50,y: 0},
{x: 200,y: 0},
{x: 150,y: 100},
{x: 0,y: 100},
];
addShape(points);
}

function addTriangle() {
var points=[
{x: 100,y: 0},
{x: 200,y: 200},
{x: 0,y: 200},
];
addShape(points);
}

function addCircle() {
var circle=new fabric.Circle({
radius: 100,
left: 50,
top: 50,
strokeWidth: (canvas.width/700)*2,
strokeUniform: true,
stroke: "black",
objectCaching: false,
transparentCorners: false,
cornerColor: "Blue",
isPanel: true,
});
setText2ImageInitPrompt(circle);
setPanelValue(circle);
canvas.add(circle);
updateLayerPanel();
}

function addHexagon() {
var side=100;
var points=[];
for (var i=0;i<6;i++) {
var x=side*Math.cos((Math.PI/180)*(60*i));
var y=side*Math.sin((Math.PI/180)*(60*i));
points.push({x: x,y: y});
}
addShape(points);
}

function addEllipse() {
var ellipse=new fabric.Ellipse({
rx: 100,
ry: 50,
left: 50,
top: 50,
strokeWidth: (canvas.width/700)*2,
strokeUniform: true,
stroke: "black",
objectCaching: false,
transparentCorners: false,
cornerColor: "Blue",
isPanel: true,
});
setText2ImageInitPrompt(ellipse);
setPanelValue(ellipse);
canvas.add(ellipse);
updateLayerPanel();
}

function addRhombus() {
var points=[
{x: 0,y: 100},
{x: 100,y: 0},
{x: 200,y: 100},
{x: 100,y: 200},
];
addShape(points);
}

function addStar() {
var points=[];
var outerRadius=100;
var innerRadius=50;
for (var i=0;i<10;i++) {
var radius=i%2===0 ? outerRadius : innerRadius;
var angle=(Math.PI/5)*i;
points.push({
x: radius*Math.sin(angle),
y:-radius*Math.cos(angle),
});
}
addShape(points);
}


function addTv() {
const canvasWidth=canvas.width;
const canvasHeight=canvas.height;

const originalWidth=780;
const originalHeight=580;

const scale=canvasInScale(originalWidth,originalHeight);

const frame=new fabric.Rect({
width: originalWidth,
height: originalHeight,
rx: 20,
ry: 20,
fill: '#333333',
stroke: '#222222',
strokeWidth: 2
});

const screenBorder=new fabric.Rect({
width: 730,
height: 490,
fill: 'transparent',
stroke: '#444444',
strokeWidth: 5,
left: 25,
top: 25
});

const screen=new fabric.Rect({
width: 720,
height: 480,
fill: '#000000',
left: 30,
top: 30
});

const logo=new fabric.Text('SANKAKU',{
fontSize: 24,
fill: '#FFFFFF',
left: 35,
top: 540
});

const controlPanel=new fabric.Rect({
width: 200,
height: 40,
fill: '#444444',
left: 550,
top: 530
});

const dial1=new fabric.Circle({
radius: 10,
fill: '#666666',
left: 570,
top: 540
});

const dial2=new fabric.Circle({
radius: 10,
fill: '#666666',
left: 620,
top: 540
});

const dial3=new fabric.Circle({
radius: 10,
fill: '#666666',
left: 670,
top: 540
});

const tv=new fabric.Group([
frame,screenBorder,screen,logo,controlPanel,
dial1,dial2,dial3
],{
left: (canvasWidth-originalWidth*scale)/2,
top: (canvasHeight-originalHeight*scale)/2,
scaleX: scale,
scaleY: scale
});

canvas.add(tv);
}


function addSmartphone() {
const canvasWidth=canvas.width;
const canvasHeight=canvas.height;

const originalWidth=300;
const originalHeight=600;

const scale=canvasInScale(originalWidth,originalHeight);

const frame=new fabric.Rect({
width: originalWidth,
height: originalHeight,
rx: 30,
ry: 30,
fill: '#333333',
stroke: '#222222',
strokeWidth: 2
});

const screen=new fabric.Rect({
width: originalWidth-20,
height: originalHeight-100,// 画面の高さを調整
fill: '#000000',
left: 10,
top: 40
});

const homeButtonOuter=new fabric.Circle({
radius: 25,
fill: 'transparent',
stroke: '#FFFFFF',
strokeWidth: 2,
left: originalWidth/2-25,
top: originalHeight-55  // 位置を調整
});

const homeButtonInner=new fabric.Circle({
radius: 23,
fill: 'rgba(100, 100, 100, 0.5)',
left: originalWidth/2-23,
top: originalHeight-53  // 外側の円に合わせて調整
});

const camera=new fabric.Circle({
radius: 5,
fill: '#666666',
left: originalWidth/2-5,
top: 20
});

const speaker=new fabric.Rect({
width: 50,
height: 5,
rx: 2,
ry: 2,
fill: '#666666',
left: originalWidth/2-25,
top: 10
});

const smartphone=new fabric.Group([
frame,screen,homeButtonOuter,homeButtonInner,camera,speaker
],{
left: (canvasWidth-originalWidth*scale)/2,
top: (canvasHeight-originalHeight*scale)/2,
scaleX: scale,
scaleY: scale
});

canvas.add(smartphone);
}


function createButton(centerX,centerY,size,color,label='',name='') {
const button=new fabric.Circle({
radius: size/2,
fill: color,
stroke: '#000000',
strokeWidth: 2,
shadow: new fabric.Shadow({color: 'rgba(0,0,0,0.6)',blur: 5,offsetX: 2,offsetY: 2}),
originX: 'center',
originY: 'center',
left: 0,
top: 0
});

const group=new fabric.Group([button],{
left: centerX,
top: centerY,
originX: 'center',
originY: 'center',
name: name
});
return group;
}

function addRedDot(x,y,name) {
const redDot=new fabric.Circle({
radius: 3,
fill: 'red',
left: x,
top: y,
originX: 'center',
originY: 'center'
});

const text=new fabric.Text(name,{
fontSize: 12,
fill: 'red',
left: x+5,
top: y-10,
originX: 'left',
originY: 'bottom'
});

canvas.add(redDot);
canvas.add(text);
}

function addRefinedRazerKishiController() {
const canvasWidth=canvas.width;
const canvasHeight=canvas.height;

const originalWidth=200;
const originalHeight=350;

const scale=canvasInScale(originalWidth+600,originalHeight);
// 左右のコントローラー
const leftController=new fabric.Rect({
width: originalWidth,
height: originalHeight,
rx: 20,
ry: 20,
fill: '#2b2b2b',
stroke: '#000000',
strokeWidth: 2,
left: 0,
top: 25,
name: 'Left Controller'
});
const rightController=new fabric.Rect({
width: originalWidth,
height: originalHeight,
rx: 20,
ry: 20,
fill: '#2b2b2b',
stroke: '#000000',
strokeWidth: 2,
left: 800,
top: 25,
name: 'Right Controller'
});
//addRedDot(rightController.left, rightController.top, rightController.name);

// スマートフォン
const smartphone=new fabric.Rect({
width: 600,
height: 300,
rx: 20,
ry: 20,
fill: '#000000',
stroke: '#333333',
strokeWidth: 2,
left: 200,
top: 50,
name: 'Smartphone'
});
//addRedDot(smartphone.left, smartphone.top, smartphone.name);

// スマートフォン画面
const screen=new fabric.Rect({
width: 580,
height: 280,
rx: 15,
ry: 15,
fill: '#000000',
left: 210,
top: 60,
name: 'Screen'
});
//addRedDot(screen.left, screen.top, screen.name);

// 左側十字キー
function createDPadButton(left,top,angle=0,name='') {
const button=new fabric.Rect({
width: 35,
height: 35,
fill: '#4a4a4a',
stroke: '#000000',
strokeWidth: 2,
rx: 5,
ry: 5,
shadow: new fabric.Shadow({color: 'rgba(0,0,0,0.6)',blur: 5,offsetX: 2,offsetY: 2}),
angle: angle
});
//addRedDot(left, top, name);
return new fabric.Group([button],{left: left,top: top,name: name});
}

const dpadUp=createDPadButton(82,195,0,'D-Pad Up');
const dpadDown=createDPadButton(82,265,0,'D-Pad Down');
const dpadLeft=createDPadButton(47,230,0,'D-Pad Left');
const dpadRight=createDPadButton(117,230,0,'D-Pad Right');
const dpadCenter=new fabric.Rect({
width: 25,
height: 25,
fill: '#4a4a4a',
stroke: '#000000',
strokeWidth: 2,
left: 87,
top: 235,
name: 'D-Pad Center'
});
//addRedDot(dpadCenter.left, dpadCenter.top, dpadCenter.name);

// 左ジョイスティック
const leftStick=createButton(100,130,60,'#333333','','Left Stick');
//addRedDot(leftStick.left, leftStick.top, leftStick.name);

// 右ジョイスティック
const rightStick=createButton(900,130,60,'#333333','','Right Stick');
//addRedDot(rightStick.left, rightStick.top, rightStick.name);

// 右側4つのボタン
const buttonSize=40;
const buttonCenterX=900;
const buttonCenterY=250;
const buttonOffset=45;

const buttonA=createButton(buttonCenterX,buttonCenterY+buttonOffset,buttonSize,'#90EE90','A','Button A');
//addRedDot(buttonA.left, buttonA.top, buttonA.name);
const buttonB=createButton(buttonCenterX+buttonOffset,buttonCenterY,buttonSize,'#FFA07A','B','Button B');
//addRedDot(buttonB.left, buttonB.top, buttonB.name);
const buttonX=createButton(buttonCenterX-buttonOffset,buttonCenterY,buttonSize,'#ADD8E6','X','Button X');
//addRedDot(buttonX.left, buttonX.top, buttonX.name);
const buttonY=createButton(buttonCenterX,buttonCenterY-buttonOffset,buttonSize,'#FFFFE0','Y','Button Y');
//addRedDot(buttonY.left, buttonY.top, buttonY.name);

// LRボタン（シャドウ付き）
function createTriggerButton(left,top,name) {
const path=new fabric.Path('M 10 5 Q 60 0, 110 5 L 110 25 Q 60 30, 10 25 Z',{
fill: '#333333',
stroke: '#000000',
strokeWidth: 2,
left: left,
top: top,
name: name
});
//addRedDot(left, top, name);
return path;
}

const leftTrigger=createTriggerButton(45,0,'Left Trigger');
const rightTrigger=createTriggerButton(845,0,'Right Trigger');

// すべての要素をグループ化
const controller=new fabric.Group([
leftController,rightController,smartphone,screen,
dpadUp,dpadDown,dpadLeft,dpadRight,dpadCenter,
leftStick,rightStick,
buttonA,buttonB,buttonX,buttonY,
leftTrigger,rightTrigger
],{
left: (canvasWidth-originalWidth*scale)/2,
top: (canvasHeight-originalHeight*scale)/2,
scaleX: scale,
scaleY: scale
});

canvas.add(controller);
}

function addPentagon() {
var side=150;
var angle=54;
var points=[];
for (var i=0;i<5;i++) {
var x=side*Math.cos((Math.PI/180)*(angle+i*72));
var y=side*Math.sin((Math.PI/180)*(angle+i*72));
points.push({x: x,y: y});
}
addShape(points);
}

function addOctagon() {
var side=100;
var points=[];
for (var i=0;i<8;i++) {
var x=side*Math.cos((Math.PI/180)*(45*i));
var y=side*Math.sin((Math.PI/180)*(45*i));
points.push({x: x,y: y});
}
addShape(points);
}

function addTallRightLeaningTrapezoid() {
var points=[
{x: 0,y: 0},
{x: 100,y: 50},
{x: 100,y: 300},
{x: 0,y: 300},
];
addShape(points);
}

function addRightSlantingTrapezoid() {
var points=[
{x: 0,y: 0},
{x: 300,y: 0},
{x: 350,y: 100},
{x: 0,y: 100},
];
addShape(points);
}
