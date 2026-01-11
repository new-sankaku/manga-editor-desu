/**
 * knife-split-engine.js
 * パネル分割ロジック
 */

/**
 * パネルを自動分割（ランダム分割用）
 * @param {Object} panel - 分割対象パネル
 * @param {boolean} isVertical - 垂直分割かどうか
 * @returns {boolean} 分割成功かどうか
 */
function blindSplitPanel(panel,isVertical) {
const canvasArea=canvas.width*canvas.height;

var centerX=getCenterXByFabricObject(panel);
var centerY=getCenterYByFabricObject(panel);

var angle;
var tiltRandom=$("tiltRandam").value;
tiltRandom=generateRandomInt(tiltRandom);
var halfTilt=tiltRandom==0 ? 0 : tiltRandom/2;
var cutChangeRate=$("cutChangeRate").value;

var changeRate=10;
if (isVertical) {
var widthPanel=panel.width;
changeRate=widthPanel*(cutChangeRate/100);
} else {
var heightPanel=panel.height;
changeRate=heightPanel*(cutChangeRate/100);
}

const randomInt=
Math.floor(Math.random()*(changeRate*2+1))-changeRate;

if (isVertical) {
centerX=centerX+randomInt;
angle=(Math.random()*tiltRandom-halfTilt+90)*(Math.PI/180);
} else {
centerY=centerY+randomInt;
angle=(Math.random()*tiltRandom-halfTilt)*(Math.PI/180);
}

const pointAtpx=getPointAtDistance(centerX,centerY,angle,KNIFE_CONSTANTS.SPLIT_LINE.POINT_DISTANCE);

var blindLine=drawLine(centerX,centerY,pointAtpx.x,pointAtpx.y,panel);

if (blindLine!==null) {
const {isSplit,polygon1,polygon2}=splitPolygon(panel);
if (isSplit) {
const area1AspectRatio=polygon1.width/polygon1.height;
const area2AspectRatio=polygon2.width/polygon2.height;

if (area1AspectRatio<=KNIFE_CONSTANTS.ASPECT_RATIO.MIN||
area1AspectRatio>=KNIFE_CONSTANTS.ASPECT_RATIO.MAX) {
canvas.add(setNotSave(panel));
canvas.remove(setNotSave(polygon1));
canvas.remove(setNotSave(polygon2));
return false;
}
if (area2AspectRatio<=KNIFE_CONSTANTS.ASPECT_RATIO.MIN||
area2AspectRatio>=KNIFE_CONSTANTS.ASPECT_RATIO.MAX) {
canvas.add(setNotSave(panel));
canvas.remove(setNotSave(polygon1));
canvas.remove(setNotSave(polygon2));
return false;
}
return true;
}
}
return false;
}

/**
 * ポリゴンを分割
 * @param {Object} polygon - 分割対象ポリゴン
 * @returns {Object} {isSplit, polygon1, polygon2}
 */
function splitPolygon(polygon) {
if (!polygon||!polygon.points) {
return {isSplit: false,polygon1: null,polygon2: null};
}
var points=pointsAdjusted(polygon.points);

var newPolygon1Points=[];
var newPolygon2Points=[];

if (currentKnifeLine) {
var offsetX=getCurrentLeft();
var offsetY=getCurrentTop();

var scaleX=getScaleX();
var scaleY=getScaleY();

var pointsStr=points.map(function (point) {
return point.x*scaleX+offsetX+" "+(point.y*scaleY+offsetY);
});
pointsStr.push(pointsStr[0]);

var splitPoint1=[currentKnifeLine.x1,currentKnifeLine.y1];
var splitPoint2=[currentKnifeLine.x2,currentKnifeLine.y2];

var reader=new jsts.io.WKTReader();
var poly=reader.read("POLYGON(("+pointsStr.join(", ")+"))");
var line=reader.read(
"LINESTRING("+splitPoint1.join(" ")+", "+splitPoint2.join(" ")+")"
);

var union=poly.getExteriorRing().union(line);
var polygonizer=new jsts.operation.polygonize.Polygonizer();
polygonizer.add(union);

var polygons=polygonizer.getPolygons();
var resultLine=[];

for (var i=polygons.iterator();i.hasNext();) {
var polygonTemp=i.next();
var coords=polygonTemp
.getCoordinates()
.map((coord)=>({x: coord.x,y: coord.y}));
resultLine.push(coords);
}

if (resultLine.length!==2) {
var extendLength=KNIFE_CONSTANTS.SPLIT_LINE.EXTEND_LENGTH;
var dx=currentKnifeLine.x2-currentKnifeLine.x1;
var dy=currentKnifeLine.y2-currentKnifeLine.y1;
var length=Math.sqrt(dx*dx+dy*dy);
var extendX=(dx/length)*extendLength;
var extendY=(dy/length)*extendLength;
if ([...splitPoint1,...splitPoint2,extendX,extendY].some(isNaN)) {
return {isSplit: false,polygon1: null,polygon2: null};
}

var y2=Number(splitPoint2[1])+Number(extendY);
var extendedLine=reader.read(
"LINESTRING("+
(Number(splitPoint1[0])-Number(extendX))+
" "+
(Number(splitPoint1[1])-Number(extendY))+
", "+
(Number(splitPoint2[0])+Number(extendX))+
" "+
y2.toFixed(2)+
")"
);

union=poly.getExteriorRing().union(extendedLine);
polygonizer=new jsts.operation.polygonize.Polygonizer();
polygonizer.add(union);

polygons=polygonizer.getPolygons();
resultLine=[];
for (var i=polygons.iterator();i.hasNext();) {
var polygonTemp=i.next();
var coords=polygonTemp
.getCoordinates()
.map((coord)=>({x: coord.x,y: coord.y}));
resultLine.push(coords);
}
}

var isSplit=-1;

if (resultLine.length===2) {
resultLine[0]=removeDuplicates(resultLine[0]);
resultLine[1]=removeDuplicates(resultLine[1]);

var splitLine=[
{x: currentKnifeLine.x1,y: currentKnifeLine.y1},
{x: currentKnifeLine.x2,y: currentKnifeLine.y2},
];

isSplit=isHorizontal(resultLine,splitLine);
adjustShapesBySplitLineDirection(resultLine,splitLine);
} else {
stopKnifeLineAnimation();
setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
return {isSplit: false,polygon1: null,polygon2: null};
}

newPolygon1Points=resultLine[0];
newPolygon2Points=resultLine[1];

var minX=0;
var minY=0;

var adjustedPolygon1Points=newPolygon1Points.map(function (point) {
return {
x: point.x-offsetX-minX,
y: point.y-offsetY-minY,
};
});

var adjustedPolygon2Points=newPolygon2Points.map(function (point) {
return {
x: point.x-offsetX-minX,
y: point.y-offsetY-minY,
};
});

var minX=Math.min(...adjustedPolygon2Points.map((v)=>v.x));
var minY=Math.min(...adjustedPolygon2Points.map((v)=>v.y));

var adjustedPolygon2Points2=adjustedPolygon2Points.map(function (point) {
return {
x: point.x-minX,
y: point.y-minY,
};
});

var polygon1MinX=Math.min(...newPolygon1Points.map((point)=>point.x));
var polygon1MinY=Math.min(...newPolygon1Points.map((point)=>point.y));

var polygon2MinX=Math.min(...newPolygon2Points.map((point)=>point.x));
var polygon2MinY=Math.min(...newPolygon2Points.map((point)=>point.y));

var left=0;
var top=0;

var scaleX=getScaleX();
var scaleY=getScaleY();
var scaleX2=getScaleX();
var scaleY2=getScaleY();

if (isSplit==KNIFE_CONSTANTS.DIRECTION.HORIZONTAL) {
top=polygon2MinY;
left=polygon2MinX;
scaleY=1;
scaleY2=1;
} else if (isSplit==KNIFE_CONSTANTS.DIRECTION.VERTICAL) {
top=polygon2MinY;
left=polygon2MinX;
scaleX=1;
scaleX2=1;
} else {
stopKnifeLineAnimation();
setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
return {isSplit: false,polygon1: null,polygon2: null};
}

var strokeWidthScale=canvas.width/700;

var tempLockMovementX=polygon.lockMovementX;
var tempLockMovementY=polygon.lockMovementY;

var polygon1=new fabric.Polygon(adjustedPolygon1Points,{
left: polygon1MinX,
top: polygon1MinY,
fill: polygon.fill,
opacity: polygon.opacity,
stroke: polygon.stroke,
strokeWidth: polygon.strokeWidth,
isPanel: true,
scaleX: 1,
scaleY: 1,
lockMovementX: tempLockMovementX,
lockMovementY: tempLockMovementY,
selectable: true,
});

var polygon2=new fabric.Polygon(adjustedPolygon2Points2,{
left: left,
top: top,
fill: polygon.fill,
opacity: polygon.opacity,
stroke: polygon.stroke,
strokeWidth: polygon.strokeWidth,
isPanel: true,
scaleX: 1,
scaleY: 1,
lockMovementX: tempLockMovementX,
lockMovementY: tempLockMovementY,
selectable: true,
});

setText2ImageInitPrompt(polygon1);
setText2ImageInitPrompt(polygon2);

stopKnifeLineAnimation();
canvas.remove(setNotSave(currentKnifeLine));
canvas.remove(setNotSave(polygon));
canvas.add(setNotSave(polygon1));
canvas.add(setNotSave(polygon2));
saveStateByManual();

currentKnifeObject=null;
currentKnifeLine=null;

return {isSplit: true,polygon1: polygon1,polygon2: polygon2};
}
}

/**
 * 分割線の方向に応じて形状を調整
 * @param {Array} resultLine - 結果のポリゴン配列
 * @param {Array} splitLine - 分割線の端点配列
 */
function adjustShapesBySplitLineDirection(resultLine,splitLine) {
var tolerance=KNIFE_CONSTANTS.SPLIT_LINE.TOLERANCE;
var adjustment=$("knifePanelSpaceSize").value;
adjustment=adjustment/2;

function getBoundingBox(polygon) {
var minX=Math.min(...polygon.map((p)=>p.x));
var maxX=Math.max(...polygon.map((p)=>p.x));
var minY=Math.min(...polygon.map((p)=>p.y));
var maxY=Math.max(...polygon.map((p)=>p.y));
return {
min: {x: minX,y: minY},
max: {x: maxX,y: maxY},
width: maxX-minX,
height: maxY-minY,
center: {x: (minX+maxX)/2,y: (minY+maxY)/2}
};
}

function findEdgeForPoint(polygon,point,tol) {
for (var i=0;i<polygon.length;i++) {
var p1=polygon[i];
var p2=polygon[(i+1)%polygon.length];
if (isPointOnSegment(point,p1,p2,tol)) {
return {p1: p1,p2: p2};
}
}
return null;
}

function isPointOnSegment(point,p1,p2,tol) {
var minX=Math.min(p1.x,p2.x)-tol;
var maxX=Math.max(p1.x,p2.x)+tol;
var minY=Math.min(p1.y,p2.y)-tol;
var maxY=Math.max(p1.y,p2.y)+tol;
if (point.x<minX||point.x>maxX||point.y<minY||point.y>maxY) {
return false;
}
var dx=p2.x-p1.x;
var dy=p2.y-p1.y;
var len=Math.sqrt(dx*dx+dy*dy);
if (len<KNIFE_CONSTANTS.GEOMETRY.MIN_LENGTH) return false;
var t=((point.x-p1.x)*dx+(point.y-p1.y)*dy)/(len*len);
if (t<-KNIFE_CONSTANTS.GEOMETRY.SEGMENT_TOLERANCE||t>1+KNIFE_CONSTANTS.GEOMETRY.SEGMENT_TOLERANCE) return false;
var closestX=p1.x+t*dx;
var closestY=p1.y+t*dy;
var dist=Math.sqrt((point.x-closestX)*(point.x-closestX)+(point.y-closestY)*(point.y-closestY));
return dist<=tol;
}

function calculateAdjustment(edge,isUpperOrLeft,isHorizontalSplit) {
if (!edge) {
if (isHorizontalSplit) {
return {dx: 0,dy: isUpperOrLeft ?-adjustment : adjustment};
} else {
return {dx: isUpperOrLeft ?-adjustment : adjustment,dy: 0};
}
}
var edgeDx=edge.p2.x-edge.p1.x;
var edgeDy=edge.p2.y-edge.p1.y;
var edgeLen=Math.sqrt(edgeDx*edgeDx+edgeDy*edgeDy);
if (edgeLen<KNIFE_CONSTANTS.GEOMETRY.MIN_LENGTH) {
if (isHorizontalSplit) {
return {dx: 0,dy: isUpperOrLeft ?-adjustment : adjustment};
} else {
return {dx: isUpperOrLeft ?-adjustment : adjustment,dy: 0};
}
}
var unitX=edgeDx/edgeLen;
var unitY=edgeDy/edgeLen;
var moveDistance=isUpperOrLeft ?-adjustment : adjustment;
if (isHorizontalSplit) {
if (Math.abs(unitY)<KNIFE_CONSTANTS.GEOMETRY.MIN_LENGTH) {
return {dx: 0,dy: moveDistance};
}
var ratio=moveDistance/unitY;
return {dx: unitX*ratio,dy: moveDistance};
} else {
if (Math.abs(unitX)<KNIFE_CONSTANTS.GEOMETRY.MIN_LENGTH) {
return {dx: moveDistance,dy: 0};
}
var ratio=moveDistance/unitX;
return {dx: moveDistance,dy: unitY*ratio};
}
}

function adjustPolygonPoints(polygon,scaledOriginalPoints,isUpperOrLeft,isHorizontalSplit) {
return polygon.map(function (point) {
if (isSplitPoint(splitLine[0],tolerance,point)||isSplitPoint(splitLine[1],tolerance,point)) {
var edge=scaledOriginalPoints ? findEdgeForPoint(scaledOriginalPoints,point,tolerance*2) : null;
var adj=calculateAdjustment(edge,isUpperOrLeft,isHorizontalSplit);
return {x: point.x+adj.dx,y: point.y+adj.dy};
}
return {x: point.x,y: point.y};
});
}

if (resultLine.length!==2) return;

var poly1=resultLine[0];
var poly2=resultLine[1];
var originalBox=getBoundingBox([...poly1,...poly2]);
var THRESHOLD_DISTANCE_X=originalBox.width*KNIFE_CONSTANTS.GEOMETRY.THRESHOLD_RATIO;
var THRESHOLD_DISTANCE_Y=originalBox.height*KNIFE_CONSTANTS.GEOMETRY.THRESHOLD_RATIO;
var center1=calculatePolygonCentroid(poly1);
var center2=calculatePolygonCentroid(poly2);
var centerDiffY=Math.abs(center1.y-center2.y);
var centerDiffX=Math.abs(center1.x-center2.x);
var isHorizontalSplit;

if (centerDiffY>THRESHOLD_DISTANCE_Y||centerDiffX>THRESHOLD_DISTANCE_X) {
isHorizontalSplit=centerDiffY/THRESHOLD_DISTANCE_Y>centerDiffX/THRESHOLD_DISTANCE_X;
} else {
var dx=splitLine[1].x-splitLine[0].x;
var dy=splitLine[1].y-splitLine[0].y;
var angle=(Math.atan2(dy,dx)*180)/Math.PI;
var isLineMoreHorizontal=Math.abs(angle)<45||Math.abs(angle)>135;
var box1=getBoundingBox(poly1);
var box2=getBoundingBox(poly2);
var boxDiffY=Math.abs(box1.center.y-box2.center.y);
var boxDiffX=Math.abs(box1.center.x-box2.center.x);
isHorizontalSplit=isLineMoreHorizontal&&centerDiffY>centerDiffX&&boxDiffY>boxDiffX;
}

var originalPoints=currentKnifeObject ? pointsAdjusted(currentKnifeObject.points) : null;
var scaleX=getScaleX();
var scaleY=getScaleY();
var objOffsetX=getCurrentLeft();
var objOffsetY=getCurrentTop();
var scaledOriginalPoints=null;
if (originalPoints) {
scaledOriginalPoints=originalPoints.map(function (p) {
return {x: p.x*scaleX+objOffsetX,y: p.y*scaleY+objOffsetY};
});
}

if (isHorizontalSplit) {
var isFirstPolygonTop=center1.y<center2.y;
resultLine[0]=adjustPolygonPoints(poly1,scaledOriginalPoints,isFirstPolygonTop,true);
resultLine[1]=adjustPolygonPoints(poly2,scaledOriginalPoints,!isFirstPolygonTop,true);
} else {
var isFirstPolygonLeft=center1.x<center2.x;
resultLine[0]=adjustPolygonPoints(poly1,scaledOriginalPoints,isFirstPolygonLeft,false);
resultLine[1]=adjustPolygonPoints(poly2,scaledOriginalPoints,!isFirstPolygonLeft,false);
}
}
