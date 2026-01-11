/**
 * knife-geometry.js
 * ナイフツールの幾何計算ユーティリティ
 */

/**
 * 点がポリゴン内にあるかを判定
 * @param {Object} point - {x, y}
 * @param {Object} polygon - Fabric.jsポリゴンオブジェクト
 * @returns {boolean}
 */
function isInsidePolygon(point,polygon) {
var scaleX=polygon.scaleX;
var scaleY=polygon.scaleY;

var offsetX=polygon.left;
var offsetY=polygon.top;
var pointX=point.x,
pointY=point.y;

var inside=false;
var vertices=polygon.points;
vertices=pointsAdjusted(vertices);

for (var i=0,j=vertices.length-1;i<vertices.length;j=i++) {
var currentVertexX=vertices[i].x*scaleX+offsetX;
var currentVertexY=vertices[i].y*scaleY+offsetY;

var previousVertexX=vertices[j].x*scaleX+offsetX;
var previousVertexY=vertices[j].y*scaleY+offsetY;

var intersect=
currentVertexY>pointY!=previousVertexY>pointY&&
pointX<
((previousVertexX-currentVertexX)*(pointY-currentVertexY))/
(previousVertexY-currentVertexY)+
currentVertexX;

if (intersect) inside=!inside;
}
return inside;
}

/**
 * 指定した点にあるポリゴンを取得
 * @param {Object} point - {x, y}
 * @returns {Object|null} Fabric.jsポリゴンオブジェクト
 */
function getPolygonAtPoint(point) {
var foundPolygon=null;
canvas.forEachObject(function (obj) {
if (obj.type==="polygon"&&isInsidePolygon(point,obj)) {
foundPolygon=obj;
}
});
return foundPolygon;
}

/**
 * マイナス座標を補正
 * @param {Array} points - ポイント配列
 * @returns {Array} 補正されたポイント配列
 */
function pointsAdjusted(points) {
var pointsTemp=points.map((point)=>({x: point.x,y: point.y}));
var minX=Math.min(...pointsTemp.map((point)=>point.x));
var minY=Math.min(...pointsTemp.map((point)=>point.y));

pointsTemp.forEach((point)=>{
if (minX<0) {
point.x+=Math.abs(minX);
} else {
point.x-=minX;
}

if (minY<0) {
point.y+=Math.abs(minY);
} else {
point.y-=minY;
}
});

return pointsTemp;
}

/**
 * 2つの線分の交点を計算
 * @param {number} x1 - 線分1の始点X
 * @param {number} y1 - 線分1の始点Y
 * @param {number} x2 - 線分1の終点X
 * @param {number} y2 - 線分1の終点Y
 * @param {number} startKnifeX - 線分2の始点X
 * @param {number} startKnifeY - 線分2の始点Y
 * @param {number} endX - 線分2の終点X
 * @param {number} endY - 線分2の終点Y
 * @param {boolean} useFixed - 座標を丸めるかどうか
 * @returns {Object|null} 交点 {x, y} または null
 */
function calculateIntersection(x1,y1,x2,y2,startKnifeX,startKnifeY,endX,endY,useFixed) {
var a1=y2-y1;
var b1=x1-x2;
var c1=a1*x1+b1*y1;

var a2=endY-startKnifeY;
var b2=startKnifeX-endX;
var c2=a2*startKnifeX+b2*startKnifeY;

var det=a1*b2-a2*b1;

if (det===0) {
return null;
}

var x=(b2*c1-b1*c2)/det;
var y=(a1*c2-a2*c1)/det;

if (useFixed) {
x=parseFloat(x.toFixed(2));
y=parseFloat(y.toFixed(2));
x1=parseFloat(x1.toFixed(2));
x2=parseFloat(x2.toFixed(2));
y1=parseFloat(y1.toFixed(2));
y2=parseFloat(y2.toFixed(2));
}

if (
x>=Math.min(x1,x2)&&
x<=Math.max(x1,x2)&&
y>=Math.min(y1,y2)&&
y<=Math.max(y1,y2)
) {
return {x: x,y: y};
}
return null;
}

/**
 * 交点リストから最も近い/遠い交点を取得
 * @param {Array} intersections - 交点配列
 * @param {number} startKnifeX - 基準点X
 * @param {number} startKnifeY - 基準点Y
 * @param {boolean} findClosest - trueなら最も近い、falseなら最も遠い
 * @returns {Object|null} 交点 {x, y} または null
 */
function getIntersectionByDistance(intersections,startKnifeX,startKnifeY,findClosest) {
var targetDistance=findClosest ? Infinity :-Infinity;
var targetIntersection=null;

for (var i=0;i<intersections.length;i++) {
var intersection=intersections[i];
if (intersection) {
var distance=Math.sqrt(
Math.pow(intersection.x-startKnifeX,2)+
Math.pow(intersection.y-startKnifeY,2)
);

if (findClosest ? distance<targetDistance : distance>targetDistance) {
targetDistance=distance;
targetIntersection=intersection;
}
}
}

return targetIntersection;
}

/**
 * 重複座標を削除
 * @param {Array} polygon - ポリゴン座標配列
 * @returns {Array} 重複を除いたポリゴン座標配列
 */
function removeDuplicates(polygon) {
let uniqueCoords=new Set();
let filteredPolygon=polygon.filter((coord)=>{
let coordStr=`${coord.x},${coord.y}`;
if (!uniqueCoords.has(coordStr)) {
uniqueCoords.add(coordStr);
return true;
}
return false;
});

return filteredPolygon;
}

/**
 * 分割点かどうかを判定
 * @param {Object} splitLine - 分割線の端点 {x, y}
 * @param {number} tolerance - 許容誤差
 * @param {Object} point - 判定する点 {x, y}
 * @returns {boolean}
 */
function isSplitPoint(splitLine,tolerance,point) {
var splitY=splitLine.y;
var splitX=splitLine.x;

var splitYPlus=splitY+tolerance;
var splitYMinus=splitY-tolerance;
var splitXPlus=splitX+tolerance;
var splitXMinus=splitX-tolerance;

if (point.y>=splitYMinus&&point.y<=splitYPlus) {
if (point.x>=splitXMinus&&point.x<=splitXPlus) {
return true;
}
}
return false;
}

/**
 * 分割線が水平かどうかを判定
 * @param {Array} resultLine - 結果の線分配列
 * @param {Array} splitLine - 分割線の端点配列
 * @returns {number} HORIZONTAL, VERTICAL, または ERROR
 */
function isHorizontal(resultLine,splitLine) {
if (resultLine.length===2) {
let dx=splitLine[1].x-splitLine[0].x;
let dy=splitLine[1].y-splitLine[0].y;
let isHorizontalResult=Math.abs(dy)<=Math.abs(dx);

if (isHorizontalResult) {
return KNIFE_CONSTANTS.DIRECTION.HORIZONTAL;
} else {
return KNIFE_CONSTANTS.DIRECTION.VERTICAL;
}
} else {
return KNIFE_CONSTANTS.DIRECTION.ERROR;
}
}

/**
 * ポリゴンの重心を計算
 * @param {Array} polygon - ポリゴン座標配列
 * @returns {Object} 重心 {x, y}
 */
function calculatePolygonCentroid(polygon) {
let xSum=0;
let ySum=0;
let signedArea=0;
let a=0;

for (let i=0;i<polygon.length;i++) {
let x0=polygon[i].x;
let y0=polygon[i].y;
let x1=polygon[(i+1)%polygon.length].x;
let y1=polygon[(i+1)%polygon.length].y;

a=x0*y1-x1*y0;
signedArea+=a;
xSum+=(x0+x1)*a;
ySum+=(y0+y1)*a;
}

signedArea*=0.5;
xSum/=6*signedArea;
ySum/=6*signedArea;

return {x: xSum,y: ySum};
}
