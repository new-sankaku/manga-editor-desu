document.getElementById('knifeModeButton').addEventListener('click', function () {
  isKnifeMode = !isKnifeMode;
  this.textContent = isKnifeMode ? 'Knife Mode(β): ON' : 'Knife Mode(β): OFF';
  changeMovement();
});

function changeMovement() {

  canvas.discardActiveObject();

  canvas.forEachObject(function (obj) {
    //console.log("obj");
    if (isKnifeMode) {
      //console.log("is ナイフ");
      obj.set({
        selectable: false
      });
    } else {
      //console.log("not ナイフ");
      obj.set({
        selectable: true
      });
    }
  });
  canvas.renderAll();
}


canvas.on('mouse:down', function (options) {
  if (!isKnifeMode) return;

  var pointer = canvas.getPointer(options.e);
  var selectedPolygon = getPolygonAtPoint(pointer);

  if (selectedPolygon) {
    //console.log("selectedPolygon");
    isKnifeDrawing = true;
    currentKnifeObject = selectedPolygon;
    startKnifeX = pointer.x;
    startKnifeY = pointer.y;
    //console.log( "startKnifeX, startKnifeY, startKnifeX, startKnifeY", startKnifeX, startKnifeY, startKnifeX, startKnifeY );
    drawLine(startKnifeX, startKnifeY, startKnifeX, startKnifeY);
  } else {
    //console.log("not selectedPolygon");
    isKnifeDrawing = false;
    canvas.discardActiveObject().renderAll();
  }
});

canvas.on('mouse:up', function (options) {
  if (!isKnifeMode || !isKnifeDrawing) return;

  isKnifeDrawing = false;

  if (currentKnifeLine) {
    currentKnifeLine.bringToFront();
    splitPolygon(currentKnifeObject);
  }
  currentKnifeObject = null;
  currentKnifeLine = null;
});
canvas.on('mouse:move', function (options) {
  if (!isKnifeMode || !isKnifeDrawing) return;

  var pointer = canvas.getPointer(options.e);
  var endX = pointer.x;
  var endY = pointer.y;

  var dx = endX - startKnifeX;
  var dy = endY - startKnifeY;
  var angle = Math.atan2(dy, dx) * 180 / Math.PI;

  if ((angle >= (0 - knifeAssistAngle) && angle <= knifeAssistAngle) || angle <= (-180 + knifeAssistAngle) || angle >= (180 - knifeAssistAngle)) {
    endY = startKnifeY;
  } else if ((angle >= (90 - knifeAssistAngle) && angle <= (90 + knifeAssistAngle)) || (angle >= (-90 - knifeAssistAngle) && angle <= (-90 + knifeAssistAngle))) {
    endX = startKnifeX;
  }

  drawLine(startKnifeX, startKnifeY, endX, endY);
});




var panelSpacing = 5;
var knifeAssistAngle = 3;
var currentKnifeObject = null;
var currentKnifeLine = null;
var isKnifeDrawing = false;
var isKnifeMode = false;
var startKnifeX, startKnifeY;
var isHorizontalInt = 1;
var isVerticalInt = 2;
var isErrorInt = -1;


var strokeWidth = 2;


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

  for (var i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
    // スケールとオフセットを適用した頂点座標
    var currentVertexX = (vertices[i].x * scaleX) + offsetX;
    var currentVertexY = (vertices[i].y * scaleY) + offsetY;

    var previousVertexX = (vertices[j].x * scaleX) + offsetX;
    var previousVertexY = (vertices[j].y * scaleY) + offsetY;

    var intersect = ((currentVertexY > pointY) != (previousVertexY > pointY)) &&
                     (pointX < (previousVertexX - currentVertexX) * 
                     (pointY - currentVertexY) / (previousVertexY - currentVertexY) + currentVertexX);

    if (intersect) inside = !inside;
  }
  return inside;
}

function getPolygonAtPoint(point) {
  var foundPolygon = null;
  canvas.forEachObject(function (obj) {

    if (obj.type === 'polygon' && isInsidePolygon(point, obj)) {
      foundPolygon = obj;
    }
  });
  return foundPolygon;
}

function drawLine(startKnifeX, startKnifeY, endX, endY) {
  if (!currentKnifeObject) {
    return;
  }

  var points = currentKnifeObject.points;
  var offsetX = getCurrentLeft();
  var offsetY = getCurrentTop();

  var scaleX = getScaleX();
  var scaleY = getScaleY();

  var intersections = [];

  for (var i = 0; i < points.length; i++) {
    var p1 = points[i];
    var p2 = points[(i + 1) % points.length];

    // スケールとオフセットを適用した座標を計算
    var p1x = (p1.x * scaleX) + offsetX;
    var p1y = (p1.y * scaleY) + offsetY;
    var p2x = (p2.x * scaleX) + offsetX;
    var p2y = (p2.y * scaleY) + offsetY;

    var intersection = calculateIntersection(
      p1x, p1y, p2x, p2y,
      startKnifeX, startKnifeY, endX, endY
    );

    if (intersection) {
      intersections.push(intersection);
    }
  }

  if (intersections.length === 2) {
    var intersection1 = getClosestIntersection(intersections, startKnifeX, startKnifeY);
    var intersection2 = getFurthestIntersection(intersections, startKnifeX, startKnifeY);

    if (intersection1 && intersection2) {
      
      //console.log("intersection1.x, intersection1.y, intersection2.x, intersection2.y", intersection1.x, intersection1.y, intersection2.x, intersection2.y);

      var nextLine = new fabric.Line([intersection1.x, intersection1.y, intersection2.x, intersection2.y], {
        stroke: 'red',
        strokeWidth: 2,
        selectable: false
      });

      isUndoRedoOperation = true;
      canvas.add(nextLine);
      isUndoRedoOperation = false;
 
      if (currentKnifeLine) {
        isUndoRedoOperation = true;
        canvas.remove(currentKnifeLine);
        isUndoRedoOperation = false;
      }
      currentKnifeLine = nextLine;
    }
  }
}

function calculateIntersection(x1, y1, x2, y2, startKnifeX, startKnifeY, endX, endY) {
  var a1 = y2 - y1;
  var b1 = x1 - x2;
  var c1 = a1 * x1 + b1 * y1;

  var a2 = endY - startKnifeY;
  var b2 = startKnifeX - endX;
  var c2 = a2 * startKnifeX + b2 * startKnifeY;

  var det = a1 * b2 - a2 * b1;

  if (det === 0) {
    return null; // Parallel lines
  } else {
    var x = (b2 * c1 - b1 * c2) / det;
    var y = (a1 * c2 - a2 * c1) / det;

    if (x >= Math.min(x1, x2) && x <= Math.max(x1, x2) && y >= Math.min(y1, y2) && y <= Math.max(y1, y2)) {
      return { x: x, y: y };
    } else {
      return null;
    }
  }
}

function getClosestIntersection(intersections, startKnifeX, startKnifeY) {
  var minDistance = Infinity;
  var closestIntersection = null;

  for (var i = 0; i < intersections.length; i++) {
    var intersection = intersections[i];
    if (intersection) {
      var distance = Math.sqrt(Math.pow(intersection.x - startKnifeX, 2) + Math.pow(intersection.y - startKnifeY, 2));

      if (distance < minDistance) {
        minDistance = distance;
        closestIntersection = intersection;
      }
    }
  }

  return closestIntersection;
}

function getFurthestIntersection(intersections, startKnifeX, startKnifeY) {
  var maxDistance = -Infinity;
  var furthestIntersection = null;

  for (var i = 0; i < intersections.length; i++) {
    var intersection = intersections[i];
    if (intersection) {
      var distance = Math.sqrt(Math.pow(intersection.x - startKnifeX, 2) + Math.pow(intersection.y - startKnifeY, 2));

      if (distance > maxDistance) {
        maxDistance = distance;
        furthestIntersection = intersection;
      }
    }
  }
  return furthestIntersection;
}

// 重複を削除する関数
function removeDuplicates(polygon) {
  let uniqueCoords = new Set();
  let filteredPolygon = polygon.filter(coord => {
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
    let angle = Math.atan2(dy, dx);
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



function adjustShapesBySplitLineDirection(resultLine, splitLine) {
  const tolerance = 5;
  const adjustment = 5;

  var scaleX = getScaleX();
  var scaleY = getScaleY();

  var offsetX = getCurrentLeft();
  var offsetY = getCurrentTop();

  if (resultLine.length === 2) {
    let poly1 = resultLine[0];
    let poly2 = resultLine[1];

    let dx = splitLine[1].x - splitLine[0].x;
    let dy = splitLine[1].y - splitLine[0].y;
    let angle = Math.atan2(dy, dx);
    let isHorizontal = Math.abs(dy) <= Math.abs(dx);
    //console.log("分割線の向き:", isHorizontal ? "水平なので上下に分割" : "垂直なので左右に分割");

    if (isHorizontal) {
      // 水平の場合、Y軸のみ調整（X座標も範囲内かチェック）
      resultLine[0] = poly1.map(point => {

        if (isSplitPoint(splitLine[0], tolerance, point)) {
          // console.log("水平：poly1 splitLine[0]：isSplitPoint");
          point.y -= adjustment;
          return { x: point.x, y: point.y };
        }else{
          // console.log( "水平：poly1 splitLine[0]：splitLine, tolerance, point", JSON.stringify(splitLine[0]), JSON.stringify(tolerance), JSON.stringify(point) );
        }

        if (isSplitPoint(splitLine[1], tolerance, point)) {
          // console.log("水平：poly1 splitLine[1]：isSplitPoint");
          point.y -= adjustment;
          return { x: point.x, y: point.y };
        }else{
          // console.log( "水平：poly1 splitLine[1]：splitLine, tolerance, point", JSON.stringify(splitLine[1]), JSON.stringify(tolerance), JSON.stringify(point) );
        }
        return { x: point.x, y: point.y };
      });

      //console.log( "poly2", JSON.stringify(poly2) );
      resultLine[1] = poly2.map(point => {
        if (isSplitPoint(splitLine[0], tolerance, point)) {
          //console.log( "isSplitPoint 水平：poly2 splitLine[0]：splitLine, tolerance, point", JSON.stringify(splitLine[0]), JSON.stringify(tolerance), JSON.stringify(point) );
          point.y += adjustment;
          return { x: point.x, y: point.y };
        }else{
          //console.log( "notSplitPoint 水平：poly2 splitLine[0]：splitLine, tolerance, point", JSON.stringify(splitLine[0]), JSON.stringify(tolerance), JSON.stringify(point) );
        }

        // var tempPoint = {
        //   x: (point.x - offsetX) > 0 ? (point.x - offsetX) * scaleX: (point.x - offsetX),
        //   y: (point.y - offsetY) > 0 ? (point.y - offsetY) * scaleY: (point.y - offsetY)
        // };
        if (isSplitPoint(splitLine[1], tolerance, point)) {
          //console.log("isSplitPoint 水平：poly2 splitLine[1]：isSplitPoint");
          point.y += adjustment;
          return { x: point.x, y: point.y };
        }else{
          //console.log( "notSplitPoint 水平：poly2 splitLine[1]：splitLine, tolerance, point", JSON.stringify(splitLine[1]), JSON.stringify(tolerance), JSON.stringify(point) );
        }

        // console.log("point.x, point.y__, offsetX, offsetY, scaleX, scaleY", point.x, ((point.y - offsetY) * scaleY) + offsetY, offsetX, offsetY, scaleX, scaleY);
        return { x: point.x, y: ((point.y - offsetY)) + offsetY };
      });
    } else {
      // 垂直の場合、X軸のみ調整（Y座標も範囲内かチェック）
      resultLine[0] = poly1.map(point => {

        if (isSplitPoint(splitLine[0], tolerance, point)) {
          point.x -= adjustment;
          return { x: point.x, y: point.y };
        }

        if (isSplitPoint(splitLine[1], tolerance, point)) {
          point.x -= adjustment;
          return { x: point.x, y: point.y };
        }

        return { x: point.x, y: point.y };
      });
      resultLine[1] = poly2.map(point => {

        if (isSplitPoint(splitLine[0], tolerance, point)) {
          point.x += adjustment;
          return { x: point.x, y: point.y };
        }

        if (isSplitPoint(splitLine[1], tolerance, point)) {
          point.x += adjustment;
          return { x: point.x, y: point.y };
        }

        return { x: ((point.x - offsetX)) + offsetX, y: point.y };
      });
    }

    //console.log("調整後の図形1の座標:", resultLine[0]);
    //console.log("調整後の図形2の座標:", resultLine[1]);
  } else {
    //console.log("図形が適切に分割されていません。図形数:", resultLine.length);
  }
}



function splitPolygon(polygon) {
  if (!polygon || !polygon.points) {
    return;
  }

  var points = polygon.points.map(function (point, index) {
    return { x: point.x, y: point.y };
  });

  var newPolygon1Points = [];
  var newPolygon2Points = [];

  if (currentKnifeLine) {
    var offsetX = getCurrentLeft();
    var offsetY = getCurrentTop();

    var scaleX = getScaleX();
    var scaleY = getScaleY();

    var pointsStr = polygon.points.map(function (point) {
      return ((point.x *scaleX) + offsetX) + " " + ((point.y*scaleY) + offsetY);
    });
    pointsStr.push(pointsStr[0]);

    var splitPoint1 = [currentKnifeLine.x1, currentKnifeLine.y1];
    var splitPoint2 = [currentKnifeLine.x2, currentKnifeLine.y2];


    //console.log("pointsStr", JSON.stringify(pointsStr));
    //console.log("pointsStr", pointsStr);

    //console.log("splitPoint1", JSON.stringify(splitPoint1));
    //console.log("splitPoint2", JSON.stringify(splitPoint2));

    // JSTSライブラリを使用して多角形と分割線を読み込む
    var reader = new jsts.io.WKTReader();
    var poly = reader.read('POLYGON((' + pointsStr.join(', ') + '))');
    var line = reader.read('LINESTRING(' + splitPoint1.join(' ') + ', ' + splitPoint2.join(' ') + ')');

    // 分割を試みる
    var union = poly.getExteriorRing().union(line);
    var polygonizer = new jsts.operation.polygonize.Polygonizer();
    polygonizer.add(union);

    var polygons = polygonizer.getPolygons();
    var resultLine = [];
    //console.log("coords first", JSON.stringify(resultLine));


    for (var i = polygons.iterator(); i.hasNext();) {
      var polygonTemp = i.next();
      var coords = polygonTemp.getCoordinates().map(coord => ({ x: coord.x, y: coord.y }));

      //console.log("coords", coords);
      resultLine.push(coords);
      //console.log("coords resultLine", JSON.stringify(resultLine));

    }

    // 分割線が交点を持たない場合、分割線を延長して再試行
    if (resultLine.length !== 2) {
      //console.log("分割線が無いので再試行", resultLine.length);

      var extendLength = 10; // 延長するピクセル数
      var dx = currentKnifeLine.x2 - currentKnifeLine.x1;
      var dy = currentKnifeLine.y2 - currentKnifeLine.y1;
      var length = Math.sqrt(dx * dx + dy * dy);
      var extendX = (dx / length) * extendLength;
      var extendY = (dy / length) * extendLength;

      var extendedLine = reader.read('LINESTRING(' + (splitPoint1[0] - extendX) + ' ' + (splitPoint1[1] - extendY) + ', ' + (splitPoint2[0] + extendX) + ' ' + (splitPoint2[1] + extendY) + ')');
      union = poly.getExteriorRing().union(extendedLine);
      polygonizer = new jsts.operation.polygonize.Polygonizer();
      polygonizer.add(union);

      polygons = polygonizer.getPolygons();
      resultLine = [];
      for (var i = polygons.iterator(); i.hasNext();) {
        var polygonTemp = i.next();
        var coords = polygonTemp.getCoordinates().map(coord => ({ x: coord.x, y: coord.y }));
        resultLine.push(coords);
      }
    }

    var isSplit = -1;


    //console.log("if (resultLine.length === 2) { resultLine1", JSON.stringify(resultLine));
    if (resultLine.length === 2) {
      resultLine[0] = removeDuplicates(resultLine[0]);
      resultLine[1] = removeDuplicates(resultLine[1]);

      // 分割線の座標を配列に格納します。
      var splitLine = [
        { x: currentKnifeLine.x1, y: currentKnifeLine.y1 },
        { x: currentKnifeLine.x2, y: currentKnifeLine.y2 }
      ];

      //console.log("resultLine1", JSON.stringify(resultLine));

      isSplit = isHorizontal(resultLine, splitLine);

      //console.log("resultLine2", JSON.stringify(resultLine));
      adjustShapesBySplitLineDirection(resultLine, splitLine);
    } else {
      //console.log("not found splitLine", resultLine.length);
      isUndoRedoOperation = true;
      canvas.remove(currentKnifeLine);
      isUndoRedoOperation = false;
      return;
    }

    //console.log("resultLine[1]", resultLine[1]);

    newPolygon1Points = resultLine[0];
    newPolygon2Points = resultLine[1];

    var minX = 0;
    var minY = 0;

    var adjustedPolygon1Points = newPolygon1Points.map(function (point) {
      return {
        x: point.x - offsetX - minX,
        y: point.y - offsetY - minY
      };
    });

    var adjustedPolygon2Points = newPolygon2Points.map(function (point) {
      //console.log( "newPolygon2Points Y", point.y - offsetY - minY);
      return {
        x: point.x - offsetX - minX,
        y: point.y - offsetY - minY
      };
    });

    var minX = Math.min(...adjustedPolygon2Points.map(v => v.x));
    var minY = Math.min(...adjustedPolygon2Points.map(v => v.y));

    //console.log("adjustedPolygon2Points", adjustedPolygon2Points);


    var adjustedPolygon2Points2 = adjustedPolygon2Points.map(function (point) {
      //console.log( "adjustedPolygon2Points2 Y", point.y - minY);
      return {
        x: point.x - minX,
        y: point.y - minY
      };
    });

    var polygon1MinX = Math.min(...newPolygon1Points.map(point => point.x));
    var polygon1MinY = Math.min(...newPolygon1Points.map(point => point.y));

    var polygon2MinX = Math.min(...newPolygon2Points.map(point => point.x));
    var polygon2MinY = Math.min(...newPolygon2Points.map(point => point.y));

    var left = 0;
    var top = 0;

    var scaleX = getScaleX();
    var scaleY = getScaleY();
    var scaleX2 = getScaleX();
    var scaleY2 = getScaleY();

    if (isSplit == isHorizontalInt) {
      // console.log("isHorizontalInt");
      top = polygon2MinY;
      left = polygon2MinX;
      scaleY = 1;
      scaleY2 = 1;
    } else if (isSplit == isVerticalInt) {
      // console.log("isVerticalInt");
      top = polygon2MinY;
      left = polygon2MinX;
      scaleX = 1;
      scaleX2 = 1;
    } else {
      // console.log("is else");
      //console.log("分割線がありません?", resultLine.length);
      console.log("not found splitLine", resultLine.length);
      isUndoRedoOperation = true;
      canvas.remove(currentKnifeLine);
      isUndoRedoOperation = false;
      return;
    }

    // console.log( "adjustedPolygon1Points  top, left, scaleX, scaleY",  adjustedPolygon1Points, top, left, scaleX, scaleY);
    // console.log( "adjustedPolygon2Points2 top, left, scaleX, scaleY", adjustedPolygon2Points2, top, left, scaleX, scaleY);

    var polygon1 = new fabric.Polygon(adjustedPolygon1Points, {
      left: polygon1MinX,
      top: polygon1MinY,
      fill: 'white',
      stroke: 'black',
      strokeWidth: strokeWidth,
      scaleX: 1,
      scaleY: 1,
      selectable: false
    });

    //console.log("scaleX", scaleX);
    //console.log("adjustedPolygon2Points2", adjustedPolygon2Points2);

    var polygon2 = new fabric.Polygon(adjustedPolygon2Points2, {
      left: left,
      top: top,
      fill: 'white',
      stroke: 'black',
      strokeWidth: strokeWidth,
      scaleX: 1,
      scaleY: 1,
      selectable: false
    });

    isUndoRedoOperation = true;
    canvas.remove(currentKnifeLine);
    canvas.remove(polygon);
    canvas.add(polygon1);
    canvas.add(polygon2);
    isUndoRedoOperation = false;
    saveStateByManual();

    currentKnifeObject = null;
    currentKnifeLine = null;
  }
}