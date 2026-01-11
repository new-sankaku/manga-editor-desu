var fpsCheckbox=$("InfomationFPS");
var coordCheckbox=$("InfomationCoordinate");

var frameCount=0;
var lastTime=performance.now();
var fps=0;
var animFrameId;

function updateFPS() {
if (fpsCheckbox.checked) {
frameCount++;
var now=performance.now();
var elapsedTime=now-lastTime;

if (elapsedTime>=1000) {
fps=(frameCount/elapsedTime)*1000;
fpsCheckbox.nextSibling.nodeValue=" FPS : "+fps.toFixed(2);
frameCount=0;
lastTime=now;
}
animFrameId=requestAnimationFrame(updateFPS);
} else {
cancelAnimationFrame(animFrameId);
fpsCheckbox.nextSibling.nodeValue=" FPS : 0";
}
}

function updateCoordinates(options) {
if (coordCheckbox.checked) {
var pointer=canvas.getPointer(options.e);
coordCheckbox.nextSibling.nodeValue=
" X:"+pointer.x.toFixed(1)+" Y:"+pointer.y.toFixed(1);
} else {
coordCheckbox.nextSibling.nodeValue=" X:0.0 Y:0.0";
}
}

document.addEventListener('DOMContentLoaded',function() {
fpsCheckbox.addEventListener("change",function () {
if (fpsCheckbox.checked) {
lastTime=performance.now();
frameCount=0;
updateFPS();
} else {
cancelAnimationFrame(animFrameId);
fpsCheckbox.nextSibling.nodeValue=" FPS : 0";
}
});

coordCheckbox.addEventListener("change",function () {
if (!coordCheckbox.checked) {
coordCheckbox.nextSibling.nodeValue=" X:0.0 Y:0.0";
}
});




updateFPS();
});
