/**
 * knife-line-renderer.js
 * ナイフツールの線描画とアニメーション
 */

/**
 * 現在のオブジェクトのスケールXを取得
 * @returns {number}
 */
function getScaleX() {
if (currentKnifeObject&&currentKnifeObject.scaleX!==undefined) {
return currentKnifeObject.scaleX;
}
return 1;
}

/**
 * 現在のオブジェクトのスケールYを取得
 * @returns {number}
 */
function getScaleY() {
if (currentKnifeObject&&currentKnifeObject.scaleY!==undefined) {
return currentKnifeObject.scaleY;
}
return 0;
}

/**
 * 現在のオブジェクトのleftを取得
 * @returns {number}
 */
function getCurrentLeft() {
if (currentKnifeObject&&currentKnifeObject.left!==undefined) {
return currentKnifeObject.left;
}
return 0;
}

/**
 * 現在のオブジェクトのtopを取得
 * @returns {number}
 */
function getCurrentTop() {
if (currentKnifeObject&&currentKnifeObject.top!==undefined) {
return currentKnifeObject.top;
}
return 0;
}

/**
 * 分割線を描画
 * @param {number} startKnifeX - 開始X座標
 * @param {number} startKnifeY - 開始Y座標
 * @param {number} endX - 終了X座標
 * @param {number} endY - 終了Y座標
 * @param {Object} panel - 対象パネル（省略可）
 * @returns {Object|null} Fabric.js線オブジェクト
 */
function drawLine(startKnifeX,startKnifeY,endX,endY,panel=null) {
if (panel!==null) {
currentKnifeObject=panel;
}

if (!currentKnifeObject) {
return null;
}

var points=currentKnifeObject.points;
points=pointsAdjusted(points);

var offsetX=getCurrentLeft();
var offsetY=getCurrentTop();

var scaleX=getScaleX();
var scaleY=getScaleY();

var intersections=[];

for (var i=0;i<points.length;i++) {
var p1=points[i];
var p2=points[(i+1)%points.length];

var p1x=p1.x*scaleX+offsetX;
var p1y=p1.y*scaleY+offsetY;
var p2x=p2.x*scaleX+offsetX;
var p2y=p2.y*scaleY+offsetY;

var intersection;

intersection=calculateIntersection(p1x,p1y,p2x,p2y,startKnifeX,startKnifeY,endX,endY,panel!==null);

if (intersection!==null) {
intersections.push(intersection);
}
}

if (intersections.length===2) {
var intersection1=getIntersectionByDistance(intersections,startKnifeX,startKnifeY,true);
var intersection2=getIntersectionByDistance(intersections,startKnifeX,startKnifeY,false);

if (intersection1&&intersection2) {
var style=KNIFE_CONSTANTS.LINE_STYLE;
var nextLine=new fabric.Line(
[intersection1.x,intersection1.y,intersection2.x,intersection2.y],
{
stroke: style.STROKE_COLOR,
strokeWidth: style.STROKE_WIDTH,
strokeDashArray: style.DASH_ARRAY,
selectable: false,
shadow: new fabric.Shadow({
color: style.SHADOW.color,
blur: style.SHADOW.blur,
offsetX: style.SHADOW.offsetX,
offsetY: style.SHADOW.offsetY
})
}
);
setNotSave(nextLine);

if (currentKnifeLine) {
stopKnifeLineAnimation();
setNotSave(currentKnifeLine);
canvas.remove(currentKnifeLine);
currentKnifeLine=null;
}

canvas.add(nextLine);
currentKnifeLine=nextLine;
startKnifeLineAnimation();
return currentKnifeLine;
}
}

return null;
}

/**
 * 分割線のアニメーションを開始
 */
function startKnifeLineAnimation() {
if (knifeLineAnimationId) {
cancelAnimationFrame(knifeLineAnimationId);
}
knifeLineDashOffset=0;
animateKnifeLine();
}

/**
 * 分割線のアニメーションを停止
 */
function stopKnifeLineAnimation() {
if (knifeLineAnimationId) {
cancelAnimationFrame(knifeLineAnimationId);
knifeLineAnimationId=null;
}
knifeLineDashOffset=0;
}

/**
 * 分割線のアニメーションフレーム
 */
function animateKnifeLine() {
if (!currentKnifeLine) {
stopKnifeLineAnimation();
return;
}
knifeLineDashOffset+=KNIFE_CONSTANTS.ANIMATION.DASH_SPEED;
if (knifeLineDashOffset>KNIFE_CONSTANTS.ANIMATION.DASH_OFFSET_MAX) {
knifeLineDashOffset=0;
}
currentKnifeLine.set("strokeDashOffset",knifeLineDashOffset);
canvas.renderAll();
knifeLineAnimationId=requestAnimationFrame(animateKnifeLine);
}
