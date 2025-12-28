document.addEventListener("DOMContentLoaded", function () {
$("knifeModeButton").addEventListener("click", function () {
changeKnifeMode();
});
});

function changeKnifeMode() {
isKnifeMode = !isKnifeMode;
updateKnifeMode();
}

function updateKnifeMode() {
var knifeModeButton = $("knifeModeButton");
knifeModeButton.textContent = isKnifeMode
? getText("knifeOff")
: getText("knifeOn");

if (isKnifeMode) {
activeClearButton();
knifeModeButton.classList.add("selected");
changeCursor("knife");
knifeModeButton.textContent = getText("knifeOff");
} else {
nonActiveClearButton();
knifeModeButton.classList.remove("selected");
changeDefaultCursor();
knifeModeButton.textContent = getText("knifeOn");
}
changeMovement();
}

function changeMovement() {
canvas.discardActiveObject();
canvas.selection = !isKnifeMode;

canvas.forEachObject(function (obj) {
if (isKnifeMode) {
obj.set({
selectable: false,
});
} else {
obj.set({
selectable: true,
});
}
});
canvas.renderAll();
}

function blindSplitPanel(panel, isVertical) {
const canvasArea = canvas.width * canvas.height;

var centerX = getCenterXByFabricObject(panel);
var centerY = getCenterYByFabricObject(panel);

var angle;
var tiltRandom = $("tiltRandam").value;
tiltRandom = generateRandomInt(tiltRandom);
var halfTilt = tiltRandom == 0 ? 0 : tiltRandom / 2;
var cutChangeRate = $("cutChangeRate").value;

var changeRate = 10;
if (isVertical) {
var widthPanel = panel.width;
changeRate = widthPanel * (cutChangeRate / 100);
} else {
var heightPanel = panel.height;
changeRate = heightPanel * (cutChangeRate / 100);
}
// -changeRateからchangeRateまでの整数がランダムに取得できます
const randomInt =
Math.floor(Math.random() * (changeRate * 2 + 1)) - changeRate;

if (isVertical) {
centerX = centerX + randomInt;
angle = (Math.random() * tiltRandom - halfTilt + 90) * (Math.PI / 180);
} else {
centerY = centerY + randomInt;
angle = (Math.random() * tiltRandom - halfTilt) * (Math.PI / 180);
}

const pointAtpx = getPointAtDistance(centerX, centerY, angle, 50);

var blindLine = drawLine(centerX, centerY, pointAtpx.x, pointAtpx.y, panel);

if (blindLine !== null) {
const { isSplit, polygon1, polygon2 } = splitPolygon(panel);
if (isSplit) {
const area1AspectRatio = polygon1.width / polygon1.height;
const area2AspectRatio = polygon2.width / polygon2.height;
if (area1AspectRatio <= 0.27 || area1AspectRatio >= 3.45) {
//比率が不自然
canvas.add(setNotSave(panel));
canvas.remove(setNotSave(polygon1));
canvas.remove(setNotSave(polygon2));
return false;
}
if (area2AspectRatio <= 0.27 || area2AspectRatio >= 3.45) {
//比率が不自然
canvas.add(setNotSave(panel));
canvas.remove(setNotSave(polygon1));
canvas.remove(setNotSave(polygon2));
return false;
}
return true;
} else {
}
} else {
}
return false;
}

var knifeAssistAngle = 3;
var currentKnifeObject = null;
var currentKnifeLine = null;
var startKnifeX, startKnifeY;
var isHorizontalInt = 1;
var isVerticalInt = 2;
var isErrorInt = -1;

function getScaleX() {
if (currentKnifeObject && currentKnifeObject.scaleX !== undefined) {
return currentKnifeObject.scaleX;
}
return 1;
}

function getScaleY() {
if (currentKnifeObject && currentKnifeObject.scaleY !== undefined) {
return currentKnifeObject.scaleY;
}
return 0;
}

function getCurrentLeft() {
if (currentKnifeObject && currentKnifeObject.left !== undefined) {
return currentKnifeObject.left;
}
return 0;
}

function getCurrentTop() {
if (currentKnifeObject && currentKnifeObject.top !== undefined) {
return currentKnifeObject.top;
}
return 0;
}

function isInsidePolygon(point, polygon) {
var scaleX = polygon.scaleX;
var scaleY = polygon.scaleY;

var offsetX = polygon.left;
var offsetY = polygon.top;
var pointX = point.x,
pointY = point.y;

var inside = false;
var vertices = polygon.points;
vertices = pointsAdjusted(vertices);

for (var i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
// スケールとオフセットを適用した頂点座標
var currentVertexX = vertices[i].x * scaleX + offsetX;
var currentVertexY = vertices[i].y * scaleY + offsetY;

var previousVertexX = vertices[j].x * scaleX + offsetX;
var previousVertexY = vertices[j].y * scaleY + offsetY;

var intersect =
currentVertexY > pointY != previousVertexY > pointY &&
pointX <
((previousVertexX - currentVertexX) * (pointY - currentVertexY)) /
(previousVertexY - currentVertexY) +
currentVertexX;

if (intersect) inside = !inside;
}
return inside;
}

function getPolygonAtPoint(point) {
var foundPolygon = null;
canvas.forEachObject(function (obj) {
if (obj.type === "polygon" && isInsidePolygon(point, obj)) {
foundPolygon = obj;
}
});
return foundPolygon;
}

//マイナス座標を補正
function pointsAdjusted(points) {
var pointsTemp = points.map((point) => ({ x: point.x, y: point.y }));
var minX = Math.min(...pointsTemp.map((point) => point.x));
var minY = Math.min(...pointsTemp.map((point) => point.y));

pointsTemp.forEach((point) => {
if (minX < 0) {
point.x += Math.abs(minX);
} else {
point.x -= minX;
}

if (minY < 0) {
point.y += Math.abs(minY);
} else {
point.y -= minY;
}
});

return pointsTemp;
}

function drawLine(startKnifeX, startKnifeY, endX, endY, panel = null) {
	if (panel !== null) {
		currentKnifeObject = panel;
	}

	if (!currentKnifeObject) {
		return null;
	}

	var points = currentKnifeObject.points;
	points = pointsAdjusted(points);

	var offsetX = getCurrentLeft();
	var offsetY = getCurrentTop();

	var scaleX = getScaleX();
	var scaleY = getScaleY();

	var intersections = [];

	for (var i = 0; i < points.length; i++) {
		var p1 = points[i];
		var p2 = points[(i + 1) % points.length];

		var p1x = p1.x * scaleX + offsetX;
		var p1y = p1.y * scaleY + offsetY;
		var p2x = p2.x * scaleX + offsetX;
		var p2y = p2.y * scaleY + offsetY;

		var intersection;

		intersection = calculateIntersection(p1x, p1y, p2x, p2y, startKnifeX, startKnifeY, endX, endY, panel !== null);

		if (intersection !== null) {
			intersections.push(intersection);
		}
	}
	if (intersections.length === 2) {
		var intersection1 = getIntersectionByDistance(intersections, startKnifeX, startKnifeY, true);
		var intersection2 = getIntersectionByDistance(intersections, startKnifeX, startKnifeY, false);

		if (intersection1 && intersection2) {
			var nextLine = new fabric.Line(
				[intersection1.x, intersection1.y, intersection2.x, intersection2.y],
				{
					stroke: "#ff6b6b",
					strokeWidth: 3,
					strokeDashArray: [12, 6],
					selectable: false,
					shadow: new fabric.Shadow({
						color: "rgba(255,107,107,0.6)",
						blur: 8,
						offsetX: 0,
						offsetY: 0
					})
				}
			);
			setNotSave(nextLine);

			if (currentKnifeLine) {
				stopKnifeLineAnimation();
				setNotSave(currentKnifeLine);
				canvas.remove(currentKnifeLine);
				currentKnifeLine = null;
			}

			canvas.add(nextLine);
			currentKnifeLine = nextLine;
			startKnifeLineAnimation();
			return currentKnifeLine;
		}
	}

	return null;
}

var knifeLineAnimationId = null;
var knifeLineDashOffset = 0;

function startKnifeLineAnimation() {
	if (knifeLineAnimationId) {
		cancelAnimationFrame(knifeLineAnimationId);
	}
	knifeLineDashOffset = 0;
	animateKnifeLine();
}

function stopKnifeLineAnimation() {
	if (knifeLineAnimationId) {
		cancelAnimationFrame(knifeLineAnimationId);
		knifeLineAnimationId = null;
	}
	knifeLineDashOffset = 0;
}

function animateKnifeLine() {
	if (!currentKnifeLine) {
		stopKnifeLineAnimation();
		return;
	}
	knifeLineDashOffset += 0.5;
	if (knifeLineDashOffset > 18) {
		knifeLineDashOffset = 0;
	}
	currentKnifeLine.set("strokeDashOffset", knifeLineDashOffset);
	canvas.renderAll();
	knifeLineAnimationId = requestAnimationFrame(animateKnifeLine);
}


function calculateIntersection(x1, y1, x2, y2, startKnifeX, startKnifeY, endX, endY, useFixed) {
var a1 = y2 - y1;
var b1 = x1 - x2;
var c1 = a1 * x1 + b1 * y1;

var a2 = endY - startKnifeY;
var b2 = startKnifeX - endX;
var c2 = a2 * startKnifeX + b2 * startKnifeY;

var det = a1 * b2 - a2 * b1;

if (det === 0) {
return null;
}

var x = (b2 * c1 - b1 * c2) / det;
var y = (a1 * c2 - a2 * c1) / det;

if (useFixed) {
x = parseFloat(x.toFixed(2));
y = parseFloat(y.toFixed(2));
x1 = parseFloat(x1.toFixed(2));
x2 = parseFloat(x2.toFixed(2));
y1 = parseFloat(y1.toFixed(2));
y2 = parseFloat(y2.toFixed(2));
}

if (
x >= Math.min(x1, x2) &&
x <= Math.max(x1, x2) &&
y >= Math.min(y1, y2) &&
y <= Math.max(y1, y2)
) {
return { x: x, y: y };
}
return null;
}

function getIntersectionByDistance(intersections, startKnifeX, startKnifeY, findClosest) {
var targetDistance = findClosest ? Infinity : -Infinity;
var targetIntersection = null;

for (var i = 0; i < intersections.length; i++) {
var intersection = intersections[i];
if (intersection) {
var distance = Math.sqrt(
Math.pow(intersection.x - startKnifeX, 2) +
Math.pow(intersection.y - startKnifeY, 2)
);

if (findClosest ? distance < targetDistance : distance > targetDistance) {
targetDistance = distance;
targetIntersection = intersection;
}
}
}

return targetIntersection;
}


// 重複を削除する関数
function removeDuplicates(polygon) {
let uniqueCoords = new Set();
let filteredPolygon = polygon.filter((coord) => {
let coordStr = `${coord.x},${coord.y}`;
if (!uniqueCoords.has(coordStr)) {
uniqueCoords.add(coordStr);
return true;
}
return false;
});

return filteredPolygon;
}

function isSplitPoint(splitLine, tolerance, point) {
splitY = splitLine.y;
splitX = splitLine.x;

splitYPlus = splitY + tolerance;
splitYMinus = splitY - tolerance;
splitXPlus = splitX + tolerance;
splitXMinus = splitX - tolerance;

if (point.y >= splitYMinus && point.y <= splitYPlus) {
if (point.x >= splitXMinus && point.x <= splitXPlus) {
return true;
}
}
return false;
}

function isHorizontal(resultLine, splitLine) {
if (resultLine.length === 2) {
let dx = splitLine[1].x - splitLine[0].x;
let dy = splitLine[1].y - splitLine[0].y;
// let angle = Math.atan2(dy, dx);
let isHorizontal = Math.abs(dy) <= Math.abs(dx);

if (isHorizontal) {
return isHorizontalInt;
} else {
return isVerticalInt;
}
} else {
return isErrorInt;
}
}


function calculatePolygonCentroid(polygon) {
let xSum = 0;
let ySum = 0;
let signedArea = 0;
let a = 0; // Partial signed area

for (let i = 0; i < polygon.length; i++) {
let x0 = polygon[i].x;
let y0 = polygon[i].y;
let x1 = polygon[(i + 1) % polygon.length].x;
let y1 = polygon[(i + 1) % polygon.length].y;

a = x0 * y1 - x1 * y0;
signedArea += a;
xSum += (x0 + x1) * a;
ySum += (y0 + y1) * a;
}

signedArea *= 0.5;
xSum /= 6 * signedArea;
ySum /= 6 * signedArea;

return { x: xSum, y: ySum };
}

function splitPolygon(polygon) {
	if (!polygon || !polygon.points) {
		return { isSplit: false, polygon1: null, polygon2: null };
	}
	var points = pointsAdjusted(polygon.points);

	var newPolygon1Points = [];
	var newPolygon2Points = [];

	if (currentKnifeLine) {
		var offsetX = getCurrentLeft();
		var offsetY = getCurrentTop();

		var scaleX = getScaleX();
		var scaleY = getScaleY();

		var pointsStr = points.map(function (point) {
			return point.x * scaleX + offsetX + " " + (point.y * scaleY + offsetY);
		});
		pointsStr.push(pointsStr[0]);

		var splitPoint1 = [currentKnifeLine.x1, currentKnifeLine.y1];
		var splitPoint2 = [currentKnifeLine.x2, currentKnifeLine.y2];

		// JSTSライブラリを使用して多角形と分割線を読み込む
		var reader = new jsts.io.WKTReader();
		var poly = reader.read("POLYGON((" + pointsStr.join(", ") + "))");
		var line = reader.read(
			"LINESTRING(" + splitPoint1.join(" ") + ", " + splitPoint2.join(" ") + ")"
		);

		// 分割を試みる
		var union = poly.getExteriorRing().union(line);
		var polygonizer = new jsts.operation.polygonize.Polygonizer();
		polygonizer.add(union);

		var polygons = polygonizer.getPolygons();
		var resultLine = [];

		for (var i = polygons.iterator(); i.hasNext();) {
			var polygonTemp = i.next();
			var coords = polygonTemp
				.getCoordinates()
				.map((coord) => ({ x: coord.x, y: coord.y }));
			resultLine.push(coords);
		}

		// 分割線が交点を持たない場合、分割線を延長して再試行
		if (resultLine.length !== 2) {
			var extendLength = 10; // 延長するピクセル数
			var dx = currentKnifeLine.x2 - currentKnifeLine.x1;
			var dy = currentKnifeLine.y2 - currentKnifeLine.y1;
			var length = Math.sqrt(dx * dx + dy * dy);
			var extendX = (dx / length) * extendLength;
			var extendY = (dy / length) * extendLength;
			if ([...splitPoint1, ...splitPoint2, extendX, extendY].some(isNaN)) {
				return { isSplit: false, polygon1: null, polygon2: null };
			}

			var y2 = Number(splitPoint2[1]) + Number(extendY);
			var extendedLine = reader.read(
				"LINESTRING(" +
				(Number(splitPoint1[0]) - Number(extendX)) +
				" " +
				(Number(splitPoint1[1]) - Number(extendY)) +
				", " +
				(Number(splitPoint2[0]) + Number(extendX)) +
				" " +
				y2.toFixed(2) +
				")"
			);

			union = poly.getExteriorRing().union(extendedLine);
			polygonizer = new jsts.operation.polygonize.Polygonizer();
			polygonizer.add(union);

			polygons = polygonizer.getPolygons();
			resultLine = [];
			for (var i = polygons.iterator(); i.hasNext();) {
				var polygonTemp = i.next();
				var coords = polygonTemp
					.getCoordinates()
					.map((coord) => ({ x: coord.x, y: coord.y }));
				resultLine.push(coords);
			}
		}

		var isSplit = -1;

		if (resultLine.length === 2) {
			resultLine[0] = removeDuplicates(resultLine[0]);
			resultLine[1] = removeDuplicates(resultLine[1]);

			// 分割線の座標を配列に格納します。
			var splitLine = [
				{ x: currentKnifeLine.x1, y: currentKnifeLine.y1 },
				{ x: currentKnifeLine.x2, y: currentKnifeLine.y2 },
			];

			isSplit = isHorizontal(resultLine, splitLine);
			adjustShapesBySplitLineDirection(resultLine, splitLine);
		} else {
			stopKnifeLineAnimation();
			setNotSave(currentKnifeLine);
			canvas.remove(currentKnifeLine);
			return { isSplit: false, polygon1: null, polygon2: null };
		}

		newPolygon1Points = resultLine[0];
		newPolygon2Points = resultLine[1];

		var minX = 0;
		var minY = 0;

		var adjustedPolygon1Points = newPolygon1Points.map(function (point) {
			return {
				x: point.x - offsetX - minX,
				y: point.y - offsetY - minY,
			};
		});

		var adjustedPolygon2Points = newPolygon2Points.map(function (point) {
			return {
				x: point.x - offsetX - minX,
				y: point.y - offsetY - minY,
			};
		});

		var minX = Math.min(...adjustedPolygon2Points.map((v) => v.x));
		var minY = Math.min(...adjustedPolygon2Points.map((v) => v.y));

		var adjustedPolygon2Points2 = adjustedPolygon2Points.map(function (point) {
			return {
				x: point.x - minX,
				y: point.y - minY,
			};
		});

		var polygon1MinX = Math.min(...newPolygon1Points.map((point) => point.x));
		var polygon1MinY = Math.min(...newPolygon1Points.map((point) => point.y));

		var polygon2MinX = Math.min(...newPolygon2Points.map((point) => point.x));
		var polygon2MinY = Math.min(...newPolygon2Points.map((point) => point.y));

		var left = 0;
		var top = 0;

		var scaleX = getScaleX();
		var scaleY = getScaleY();
		var scaleX2 = getScaleX();
		var scaleY2 = getScaleY();

		if (isSplit == isHorizontalInt) {
			top = polygon2MinY;
			left = polygon2MinX;
			scaleY = 1;
			scaleY2 = 1;
		} else if (isSplit == isVerticalInt) {
			top = polygon2MinY;
			left = polygon2MinX;
			scaleX = 1;
			scaleX2 = 1;
		} else {
			stopKnifeLineAnimation();
			setNotSave(currentKnifeLine);
			canvas.remove(currentKnifeLine);
			return { isSplit: false, polygon1: null, polygon2: null };
		}

		var strokeWidthScale = canvas.width / 700;

		var tempLockMovementX = polygon.lockMovementX;
		var tempLockMovementY = polygon.lockMovementY;

		var polygon1 = new fabric.Polygon(adjustedPolygon1Points, {
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

		var polygon2 = new fabric.Polygon(adjustedPolygon2Points2, {
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

		currentKnifeObject = null;
		currentKnifeLine = null;

		return { isSplit: true, polygon1: polygon1, polygon2: polygon2 };
	}
}


function updateKnifeMode() {
	var knifeModeButton = $("knifeModeButton");
	knifeModeButton.textContent = isKnifeMode
		? getText("knifeOff")
		: getText("knifeOn");

	if (isKnifeMode) {
		activeClearButton();
		knifeModeButton.classList.add("selected");
		changeCursor("knife");
		knifeModeButton.textContent = getText("knifeOff");
	} else {
		nonActiveClearButton();
		knifeModeButton.classList.remove("selected");
		changeDefaultCursor();
		knifeModeButton.textContent = getText("knifeOn");
		// ナイフモード解除時にアニメーションを停止し線を削除
		if (currentKnifeLine) {
			stopKnifeLineAnimation();
			setNotSave(currentKnifeLine);
			canvas.remove(currentKnifeLine);
			currentKnifeLine = null;
		}
	}
	changeMovement();
}


function adjustShapesBySplitLineDirection(resultLine, splitLine) {
var tolerance = 5;
var adjustment = $("knifePanelSpaceSize").value;
adjustment = adjustment / 2;

function getBoundingBox(polygon) {
var minX = Math.min(...polygon.map((p) => p.x));
var maxX = Math.max(...polygon.map((p) => p.x));
var minY = Math.min(...polygon.map((p) => p.y));
var maxY = Math.max(...polygon.map((p) => p.y));
return {
min: { x: minX, y: minY },
max: { x: maxX, y: maxY },
width: maxX - minX,
height: maxY - minY,
center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 }
};
}

function findEdgeForPoint(polygon, point, tol) {
for (var i = 0; i < polygon.length; i++) {
var p1 = polygon[i];
var p2 = polygon[(i + 1) % polygon.length];
if (isPointOnSegment(point, p1, p2, tol)) {
return { p1: p1, p2: p2 };
}
}
return null;
}

function isPointOnSegment(point, p1, p2, tol) {
var minX = Math.min(p1.x, p2.x) - tol;
var maxX = Math.max(p1.x, p2.x) + tol;
var minY = Math.min(p1.y, p2.y) - tol;
var maxY = Math.max(p1.y, p2.y) + tol;
if (point.x < minX || point.x > maxX || point.y < minY || point.y > maxY) {
return false;
}
var dx = p2.x - p1.x;
var dy = p2.y - p1.y;
var len = Math.sqrt(dx * dx + dy * dy);
if (len < 0.001) return false;
var t = ((point.x - p1.x) * dx + (point.y - p1.y) * dy) / (len * len);
if (t < -0.1 || t > 1.1) return false;
var closestX = p1.x + t * dx;
var closestY = p1.y + t * dy;
var dist = Math.sqrt((point.x - closestX) * (point.x - closestX) + (point.y - closestY) * (point.y - closestY));
return dist <= tol;
}

function calculateAdjustment(edge, isUpperOrLeft, isHorizontalSplit) {
if (!edge) {
if (isHorizontalSplit) {
return { dx: 0, dy: isUpperOrLeft ? -adjustment : adjustment };
} else {
return { dx: isUpperOrLeft ? -adjustment : adjustment, dy: 0 };
}
}
var edgeDx = edge.p2.x - edge.p1.x;
var edgeDy = edge.p2.y - edge.p1.y;
var edgeLen = Math.sqrt(edgeDx * edgeDx + edgeDy * edgeDy);
if (edgeLen < 0.001) {
if (isHorizontalSplit) {
return { dx: 0, dy: isUpperOrLeft ? -adjustment : adjustment };
} else {
return { dx: isUpperOrLeft ? -adjustment : adjustment, dy: 0 };
}
}
var unitX = edgeDx / edgeLen;
var unitY = edgeDy / edgeLen;
var moveDistance = isUpperOrLeft ? -adjustment : adjustment;
if (isHorizontalSplit) {
if (Math.abs(unitY) < 0.001) {
return { dx: 0, dy: moveDistance };
}
var ratio = moveDistance / unitY;
return { dx: unitX * ratio, dy: moveDistance };
} else {
if (Math.abs(unitX) < 0.001) {
return { dx: moveDistance, dy: 0 };
}
var ratio = moveDistance / unitX;
return { dx: moveDistance, dy: unitY * ratio };
}
}

function adjustPolygonPoints(polygon, scaledOriginalPoints, isUpperOrLeft, isHorizontalSplit) {
return polygon.map(function (point) {
if (isSplitPoint(splitLine[0], tolerance, point) || isSplitPoint(splitLine[1], tolerance, point)) {
var edge = scaledOriginalPoints ? findEdgeForPoint(scaledOriginalPoints, point, tolerance * 2) : null;
var adj = calculateAdjustment(edge, isUpperOrLeft, isHorizontalSplit);
return { x: point.x + adj.dx, y: point.y + adj.dy };
}
return { x: point.x, y: point.y };
});
}

if (resultLine.length !== 2) return;

var poly1 = resultLine[0];
var poly2 = resultLine[1];
var originalBox = getBoundingBox([...poly1, ...poly2]);
var THRESHOLD_DISTANCE_X = originalBox.width * 0.1;
var THRESHOLD_DISTANCE_Y = originalBox.height * 0.1;
var center1 = calculatePolygonCentroid(poly1);
var center2 = calculatePolygonCentroid(poly2);
var centerDiffY = Math.abs(center1.y - center2.y);
var centerDiffX = Math.abs(center1.x - center2.x);
var isHorizontalSplit;

if (centerDiffY > THRESHOLD_DISTANCE_Y || centerDiffX > THRESHOLD_DISTANCE_X) {
isHorizontalSplit = centerDiffY / THRESHOLD_DISTANCE_Y > centerDiffX / THRESHOLD_DISTANCE_X;
} else {
var dx = splitLine[1].x - splitLine[0].x;
var dy = splitLine[1].y - splitLine[0].y;
var angle = (Math.atan2(dy, dx) * 180) / Math.PI;
var isLineMoreHorizontal = Math.abs(angle) < 45 || Math.abs(angle) > 135;
var box1 = getBoundingBox(poly1);
var box2 = getBoundingBox(poly2);
var boxDiffY = Math.abs(box1.center.y - box2.center.y);
var boxDiffX = Math.abs(box1.center.x - box2.center.x);
isHorizontalSplit = isLineMoreHorizontal && centerDiffY > centerDiffX && boxDiffY > boxDiffX;
}

var originalPoints = currentKnifeObject ? pointsAdjusted(currentKnifeObject.points) : null;
var scaleX = getScaleX();
var scaleY = getScaleY();
var objOffsetX = getCurrentLeft();
var objOffsetY = getCurrentTop();
var scaledOriginalPoints = null;
if (originalPoints) {
scaledOriginalPoints = originalPoints.map(function (p) {
return { x: p.x * scaleX + objOffsetX, y: p.y * scaleY + objOffsetY };
});
}

if (isHorizontalSplit) {
var isFirstPolygonTop = center1.y < center2.y;
resultLine[0] = adjustPolygonPoints(poly1, scaledOriginalPoints, isFirstPolygonTop, true);
resultLine[1] = adjustPolygonPoints(poly2, scaledOriginalPoints, !isFirstPolygonTop, true);
} else {
var isFirstPolygonLeft = center1.x < center2.x;
resultLine[0] = adjustPolygonPoints(poly1, scaledOriginalPoints, isFirstPolygonLeft, false);
resultLine[1] = adjustPolygonPoints(poly2, scaledOriginalPoints, !isFirstPolygonLeft, false);
}
}