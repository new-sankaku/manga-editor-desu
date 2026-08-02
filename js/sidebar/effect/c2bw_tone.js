// 白黒プリセット。値の違いだけで工程は共通
const C2BW_PRESET_MAP={
[MODE_EFFECT_C2BW_LIGHT]: {
brightness: 0.35,
contrast: 0.35,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
},
[MODE_EFFECT_C2BW_DARK]: {
brightness: 0.22,
contrast: 0.22,
dotSize: 1.5,
dotAngle: 0,
inkStrength: 0.25
},
[MODE_EFFECT_C2BW_ROUGHT]: {
brightness: 0.41,
contrast: 0.41,
dotSize: 1.5,
dotAngle: 0.1,
inkStrength: 0.42
},
[MODE_EFFECT_C2BW_SIMPLE]: {
brightness: 0.15,
contrast: 0.15,
dotSize: 1.5,
dotAngle: 0
}
};

function c2bwGetPreset(type) {
const preset=C2BW_PRESET_MAP[type];
if (!preset) {
effectLogger.error("unknown c2bw preset",type);
return null;
}
return preset;
}

function c2bwFilterSteps(filterValues) {
const steps=[];
if (filterValues.inkStrength) {
steps.push("glfxInk");
}
steps.push("glfxBrightnessContrast");
steps.push("glfxDotScreen");
return steps;
}

// 1画像に白黒プリセットを適用する。履歴コミットと進捗表示は呼び出し側が持つ。
// 一括適用からも同じ経路を通す
async function c2bwApplyToImage(object,filterValues) {
await glfxApplyPresetToImage(object,c2bwFilterSteps(filterValues),filterValues);
}

async function C2BWStartLight() {
await C2BWStart(c2bwGetPreset(MODE_EFFECT_C2BW_LIGHT));
}
async function C2BWStartDark() {
await C2BWStart(c2bwGetPreset(MODE_EFFECT_C2BW_DARK));
}
async function C2BWStartRough() {
await C2BWStart(c2bwGetPreset(MODE_EFFECT_C2BW_ROUGHT));
}
async function C2BWStartSimple() {
await C2BWStart(c2bwGetPreset(MODE_EFFECT_C2BW_SIMPLE));
}

// 選択中の1画像に適用する
async function C2BWStart(filterValues) {
const loading=OP_showLoading({
icon: 'process',step: 'Step1',substep: 'Ink up',progress: 0
});
var activeObject=canvas.getActiveObject();
try {
glfxReset();
if (isImage(activeObject)) {
OP_updateLoadingState(loading,{
icon: 'process',step: 'Step2',substep: 'Brightness Contrast',progress: 50
});
await c2bwApplyToImage(activeObject,filterValues);
OP_updateLoadingState(loading,{
icon: 'save',step: 'Step3',substep: 'Dot',progress: 100
});
}
} finally {
OP_hideLoading(loading);
saveStateByManual();
}
}
