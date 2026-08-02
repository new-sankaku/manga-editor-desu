var glfxOriginalImage=null;
var glfxCopiedImage=null;
// フィルタ結果は画像1枚分の容量を持つため、履歴化はスライダー停止後に1回だけ行う
const GLFX_HISTORY_DEBOUNCE=700;

function glfxResetFilterValues() {
$("glfxBrightness").value=0;
$("glfxContrast").value=0;
$("glfxHue").value=0;
$("glfxSaturation").value=0;
$("glfxSepiaAmount").value=0;
$("glfxUnsharpRadius").value=0;
$("glfxUnsharpStrength").value=0;
$("glfxVibranceAmount").value=0;
$("glfxVignetteSize").value=0;
$("glfxVignetteAmount").value=0;
$("glfxBlurRadius").value=0;
$("glfxBlurBrightness").value=0;
$("glfxBlurAngle").value=0;
$("glfxStartX").value=0.5;
$("glfxStartY").value=0.5;
$("glfxEndX").value=0.5;
$("glfxEndY").value=0.5;
$("glfxTiltBlurRadius").value=0;
$("glfxGradientRadius").value=0.5;
$("glfxTriangleRadius").value=0;
$("glfxZoomCenterX").value=0.5;
$("glfxZoomCenterY").value=0.5;
$("glfxZoomStrength").value=0;
$("glfxHalftoneAngle").value=0;
$("glfxHalftoneSize").value=2;
$("glfxDotAngle").value=0;
$("glfxDotSize").value=2;
$("glfxEdgeRadius").value=0;
$("glfxHexScale").value=2;
$("glfxInkStrength").value=0.2;
$("glfxBulgeCenterX").value=500;
$("glfxBulgeCenterY").value=500;
$("glfxBulgeRadius").value=0;
$("glfxBulgeStrength").value=0;
$("glfxSwirlCenterX").value=256;
$("glfxSwirlCenterY").value=256;
$("glfxSwirlRadius").value=0;
$("glfxSwirlAngle").value=0;
}

var fxCanvas,texture;

// fx.canvas()はWebGLコンテキストを1つ消費する。呼ぶたびに生成するとブラウザの
// コンテキスト上限（16程度）に達し、古いコンテキストがロストして結果が壊れる。
// 一括適用で必ず踏むため1個だけ生成して使い回す
var glfxSharedCanvas=null;
// fxCanvas.texture()も呼ぶたびにGPU上へ新規テクスチャを確保して解放されない。
// 1個をloadContentsOfで詰め替える
var glfxSharedTexture=null;

function glfxGetSharedCanvas() {
if (!glfxSharedCanvas) {
glfxSharedCanvas=fx.canvas();
}
return glfxSharedCanvas;
}

function glfxLoadSharedTexture(fxCanvasObject,element) {
if (glfxSharedTexture) {
glfxSharedTexture.loadContentsOf(element);
} else {
glfxSharedTexture=fxCanvasObject.texture(element);
}
return glfxSharedTexture;
}

// デコード済みの要素はそのままGPUへ渡せる。canvas要素もloadContentsOfが受け付ける
function glfxIsDecodedElement(element) {
if (!element) {
return false;
}
if (element.tagName==="CANVAS") {
return true;
}
return!!(element.complete&&element.naturalWidth>0);
}

function glfxApplyFilter(filter=null) {
// console.log("glfxApplyFilter: Start");
if (!canvas) {
// console.log("glfxApplyFilter: Canvas is null");
return Promise.resolve();
}

var activeObject=canvas.getActiveObject();

if (activeObject&&activeObject.type==="image") {
// console.log("glfxApplyFilter: Applying filter to object", activeObject);
return glfxApplyFilterToObject(activeObject,filter);
} else {
// console.log("glfxApplyFilter: No active image object, applying filter to canvas");
glfxApplyFilterToCanvas(filter);
return Promise.resolve();
}
}

function glfxApplyFilterToCanvas(filter=null) {
var fabricCanvas=canvas.upperCanvasEl;
var img=new Image();
img.onload=function () {
fxCanvas=glfxGetSharedCanvas();
texture=glfxLoadSharedTexture(fxCanvas,img);
fxCanvas.draw(texture);
applySelectedFilter(fxCanvas,filter);
fxCanvas.update();
canvas
.getContext("2d")
.drawImage(fxCanvas,0,0,canvas.width,canvas.height);
};
img.src=fabricCanvas.toDataURL();
}

function glfxApplyFilterToObject(object,filter=null,filterValues=null) {
return glfxApplyFilterChainToObject(object,[filter],filterValues);
}

// filterListのフィルタをGPU上で連続適用し、最後に1回だけ画像化する。
// 1フィルタごとにtoDataURL→再デコードすると1画像あたりの往復が増えるため、
// 複数フィルタのプリセット（白黒・薄いカラー化）ではまとめて掛ける。
// テクスチャは8bit RGBAなので、途中で画像化した場合と精度は変わらない
function glfxApplyFilterChainToObject(object,filterList,filterValues=null) {
return new Promise((resolve)=>{
if (!glfxOriginalImage) {
return resolve();
}

const applyToElement=function (sourceElement) {
fxCanvas=glfxGetSharedCanvas();
texture=glfxLoadSharedTexture(fxCanvas,sourceElement);
fxCanvas.draw(texture);
filterList.forEach(function (filter) {
applySelectedFilter(fxCanvas,filter,filterValues);
});
fxCanvas.update();

var filteredImage=new Image();
filteredImage.onload=function () {
var top=object.top;
var left=object.left;
var scaleX=object.scaleX;
var scaleY=object.scaleY;
var width=object.width;
var height=object.height;

object.setElement(filteredImage);
object.top=top;
object.left=left;
object.scaleX=scaleX;
object.scaleY=scaleY;
object.width=width;
object.height=height;

object.set({
left: left,
top: top,
scaleX: scaleX,
scaleY: scaleY,
width: width,
height: height,
});

canvas.requestRenderAll();

resolve();
};
filteredImage.src=fxCanvas.toDataURL();
};

if (glfxIsDecodedElement(glfxOriginalImage)) {
applyToElement(glfxOriginalImage);
} else {
var img=new Image();
img.onload=function () {
applyToElement(img);
};
img.src=glfxOriginalImage.src;
}
});
}

// 一括適用用。グローバルのglfxOriginalImageを対象オブジェクトで上書きしてから
// 適用し、必ず後始末する。GLFXパネルの編集途中の状態を持ち越さない
async function glfxApplyPresetToImage(object,filterList,filterValues) {
try {
glfxOriginalImage=object.getElement();
await glfxApplyFilterChainToObject(object,filterList,filterValues);
} finally {
glfxCopiedImage=null;
glfxOriginalImage=null;
}
}


function applySelectedFilter(fxCanvas,filter=null,filterValues=null) {
// console.log("applySelectedFilter start");
var isNotAuto=true;
if(filter){
isNotAuto=false;
}else{
filter=$("glfxFilter").value;
}
// console.log("applySelectedFilter: Selected filter is", filter);


switch (filter) {
case "glfxBrightnessContrast":
var brightness=0.29;
var contrast=0.29;

if(isNotAuto){
brightness=parseFloat($("glfxBrightness").value);
contrast=parseFloat($("glfxContrast").value);
}else{
brightness=filterValues.brightness;
contrast=filterValues.contrast;

}
// console.log( "glfxBrightnessContrast brightness", brightness );
// console.log( "glfxBrightnessContrast contrast", contrast );
fxCanvas.brightnessContrast(brightness,contrast);
break;
case "glfxHueSaturation":
var hue=parseFloat($("glfxHue").value);
var saturation=parseFloat($("glfxSaturation").value);

// console.log("glfxHueSaturation hue", hue);
// console.log("glfxHueSaturation saturation", saturation);

fxCanvas.hueSaturation(hue,saturation);
break;
case "glfxSepia":
var amount=parseFloat($("glfxSepiaAmount").value);
fxCanvas.sepia(amount);
break;
case "glfxUnsharpMask":
var radius=parseFloat(
$("glfxUnsharpRadius").value
);
var strength=parseFloat(
$("glfxUnsharpStrength").value
);
fxCanvas.unsharpMask(radius,strength);
break;
case "glfxVibrance":
var vibranceAmount=parseFloat(
$("glfxVibranceAmount").value
);
fxCanvas.vibrance(vibranceAmount);
break;
case "glfxVignette":
var vignetteSize=parseFloat(
$("glfxVignetteSize").value
);
var vignetteAmount=parseFloat(
$("glfxVignetteAmount").value
);
fxCanvas.vignette(vignetteSize,vignetteAmount);
break;
case "glfxLensBlur":
var blurRadius=parseFloat(
$("glfxBlurRadius").value
);
var blurBrightness=parseFloat(
$("glfxBlurBrightness").value
);
var blurAngle=parseFloat(
$("glfxBlurAngle").value
);
fxCanvas.lensBlur(blurRadius,blurBrightness,blurAngle);
break;
case "glfxTiltShift":
var startX=parseFloat($("glfxStartX").value);
var startY=parseFloat($("glfxStartY").value);
var endX=parseFloat($("glfxEndX").value);
var endY=parseFloat($("glfxEndY").value);

var tiltBlurRadius=parseFloat(
$("glfxTiltBlurRadius").value
);
var gradientRadius=parseFloat(
$("glfxGradientRadius").value
);
fxCanvas.tiltShift(
startX,
startY,
endX,
endY,
tiltBlurRadius,
gradientRadius
);
break;
case "glfxTriangleBlur":
var triangleRadius=parseFloat(
$("glfxTriangleRadius").value
);
fxCanvas.triangleBlur(triangleRadius);
break;
case "glfxZoomBlur":
var zoomCenterX=parseFloat(
$("glfxZoomCenterX").value
);
var zoomCenterY=parseFloat(
$("glfxZoomCenterY").value
);
var zoomStrength=parseFloat(
$("glfxZoomStrength").value
);
fxCanvas.zoomBlur(zoomCenterX,zoomCenterY,zoomStrength);
break;
case "glfxColorHalftone":
var halftoneCenterX=100;
var halftoneCenterY=100;
var halftoneAngle=parseFloat(
$("glfxHalftoneAngle").value
);
var halftoneSize=parseFloat(
$("glfxHalftoneSize").value
);

fxCanvas.colorHalftone(
halftoneCenterX,
halftoneCenterY,
halftoneAngle,
halftoneSize
);
break;
case "glfxDotScreen":
var dotCenterX=1;
var dotCenterY=1;
var dotAngle=1.1;
var dotSize=1.6;

if(isNotAuto){
dotAngle=parseFloat($("glfxDotAngle").value);
dotSize=parseFloat($("glfxDotSize").value);
}else{
dotAngle=filterValues.dotAngle;
dotSize=filterValues.dotSize;
}
// console.log("dotAngle", dotAngle)
// console.log("dotSize", dotSize)

fxCanvas.dotScreen(dotCenterX,dotCenterY,dotAngle,dotSize);
break;
case "glfxEdgeWork":
var edgeRadius=parseFloat(
$("glfxEdgeRadius").value
);
fxCanvas.edgeWork(edgeRadius);
break;
case "glfxHexagonalPixelate":
var hexCenterX=1;
var hexCenterY=1;
var hexScale=parseFloat($("glfxHexScale").value);
fxCanvas.hexagonalPixelate(hexCenterX,hexCenterY,hexScale);
break;
case "glfxInk":
var inkStrength=0.26;

if(isNotAuto){
inkStrength=parseFloat($("glfxInkStrength").value);
}else{
inkStrength=filterValues.inkStrength;
}
// console.log("applySelectedFilter: Ink strength is", inkStrength);

fxCanvas.ink(inkStrength);
break;
case "glfxBulgePinch":
var bulgeCenterX=parseFloat(
$("glfxBulgeCenterX").value
);
var bulgeCenterY=parseFloat(
$("glfxBulgeCenterY").value
);
var bulgeRadius=parseFloat(
$("glfxBulgeRadius").value
);
var bulgeStrength=parseFloat(
$("glfxBulgeStrength").value
);
fxCanvas.bulgePinch(
bulgeCenterX,
bulgeCenterY,
bulgeRadius,
bulgeStrength
);
break;
case "glfxSwirl":
var swirlCenterX=parseFloat(
$("glfxSwirlCenterX").value
);
var swirlCenterY=parseFloat(
$("glfxSwirlCenterY").value
);
var swirlRadius=parseFloat(
$("glfxSwirlRadius").value
);
var swirlAngle=parseFloat(
$("glfxSwirlAngle").value
);
fxCanvas.swirl(swirlCenterX,swirlCenterY,swirlRadius,swirlAngle);
break;
}
// console.log("applySelectedFilter: Filter applied and canvas updated");

}

function debounceGlfx(func,wait) {
let timeout;
return function () {
const context=this,
args=arguments;
clearTimeout(timeout);
timeout=setTimeout(()=>func.apply(context,args),wait);
};
}


// 見出しの表示名は<select>の選択中optionから取る。名前を別に持つと
// フィルタ追加時の修正漏れになる
function glfxSyncFilterName(){
var select=$("glfxFilter");
var name=$("glfxFilterName");
if (!select||!name) {
return;
}
var option=select.options[select.selectedIndex];
name.textContent=option ? option.textContent : "";
}

function glfxAddEvent(){
// gpifHTMLごと差し替わるため、ここで張り直しても多重登録にはならない
$("glfxFilter").addEventListener("change",function () {
var value=this.value;
document.querySelectorAll(".glfxCcontrol-group").forEach(function (group) {
group.style.display="none";
});
if (value) {
$(value).style.display="block";
}
glfxSyncFilterName();
});

glfxSyncFilterName();

// GLFXは15種から選ぶのが前提なので、押した時点でピッカーまで開く。
// glfxAddEvent()はGLFXボタンのクリック経由でしか呼ばれない
PresetPicker.openFromSelect($("glfxFilter"),getText("glfxFilterPickerTitle"),glfxBuildFilterPickerMeta());
document.querySelectorAll(".glfxControls input").forEach(function (input) {
input.addEventListener("input",debounceGlfx(function () {
var activeObject=canvas.getActiveObject();
if (!glfxOriginalImage&&activeObject&&activeObject.type==="image") {
glfxOriginalImage=activeObject.getElement();
}

if (!activeObject) {
createToastError("Select Image!");
return;
}

if (glfxOriginalImage) {
glfxCopiedImage=glfxOriginalImage.cloneNode();
glfxApplyFilter().then(function(){
commitHistoryDebounced(GLFX_HISTORY_DEBOUNCE);
});
}
},100)
);
});

// フィルタはスライダー操作で即時反映される。Applyは「現在の結果を確定して
// スライダーを0に戻す（重ねがけに進む）」、Resetは「元画像に戻す」
addTooltipByElement($("glfxApplyButton"),"glfxApplyHelp");
addTooltipByElement($("glfxResetButton"),"glfxResetHelp");

$("glfxApplyButton").addEventListener("click",function () {
glfxApply();
});

$("glfxResetButton").addEventListener("click",function () {
glfxReset();
});
}

function glfxApply() {
if (glfxCopiedImage) {
glfxOriginalImage=glfxCopiedImage.cloneNode();
glfxCopiedImage=null;
glfxOriginalImage=null;
glfxResetFilterValues();
saveStateByManual();
}
}
function glfxApplyNoReset() {
if (glfxCopiedImage) {
glfxOriginalImage=glfxCopiedImage.cloneNode();
glfxCopiedImage=null;
glfxOriginalImage=null;
// saveStateByManual();
}
}

function glfxReset() {
if (glfxOriginalImage) {
var imgObj=new Image();
imgObj.onload=function () {
var img=new fabric.Image(imgObj);
var activeObject=lastActiveObjectState;
if (activeObject&&activeObject.type==="image") {
var copyObject={};
copy(activeObject,copyObject);
copy(copyObject,img);
}
canvas.remove(activeObject);
canvas.add(img);
canvas.setActiveObject(img);
canvas.requestRenderAll();
lastActiveObjectState=null;
glfxCopiedImage=null;
glfxOriginalImage=null;
glfxResetFilterValues();
lastActiveObjectState=canvas.getActiveObject();
};
imgObj.src=glfxOriginalImage.src;
}
}