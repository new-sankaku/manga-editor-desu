// 薄いカラー化は白黒版の上に元のカラーを薄く重ねる。白黒プリセットはLightと同じ
const C2C_PRESET={
brightness: 0.35,
contrast: 0.35,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
};
const C2C_COLOR_ALPHA=0.4;

// 1画像に薄いカラー化を適用する。履歴コミットと進捗表示は呼び出し側が持つ。
// 一括適用からも同じ経路を通す
async function c2cApplyToImage(object) {
// setElementで差し替えても元の要素自体は生きているので、カラー版として持っておく。
// キャンバスへ一時クローンを追加する必要がない
const colorElement=object.getElement();
const originalWidth=colorElement.naturalWidth;
const originalHeight=colorElement.naturalHeight;

await c2bwApplyToImage(object,C2C_PRESET);

const tempCanvas=document.createElement('canvas');
tempCanvas.width=originalWidth;
tempCanvas.height=originalHeight;
const ctx=tempCanvas.getContext('2d');
ctx.imageSmoothingEnabled=true;
ctx.imageSmoothingQuality='high';
ctx.drawImage(object.getElement(),0,0,originalWidth,originalHeight);
ctx.globalAlpha=C2C_COLOR_ALPHA;
ctx.drawImage(colorElement,0,0,originalWidth,originalHeight);

await replaceImageByDataURL(object,tempCanvas.toDataURL('image/webp',1.0));
object.set({objectCaching: false,imageSmoothing: true});
}

// 選択中の1画像に適用する
async function C2CStart() {
const loading=OP_showLoading({
icon: 'process',step: 'Step1',substep: 'Ink up',progress: 0
});
var activeObject=canvas.getActiveObject();
try {
glfxReset();
if (isImage(activeObject)) {
OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Brightness Contrast',progress: 40
});
await c2cApplyToImage(activeObject);
OP_updateLoadingState(loading,{
icon: 'save',step: 'Step3',substep: 'Merge images',progress: 100
});
}
} finally {
OP_hideLoading(loading);
// setElementはfabricのset()を通らず自動コミット網に検知されないため明示的に積む
saveStateByManual();
}
}
