const effectMap=new Map();

const MODE_EFFECT_C2BW_LIGHT="Color2BlackWhiteLight";
const MODE_EFFECT_C2BW_DARK="Color2BlackWhiteDark";
const MODE_EFFECT_C2BW_ROUGHT="Color2BlackWhiteRough";
const MODE_EFFECT_C2BW_SIMPLE="Color2BlackWhiteSimple";
const MODE_EFFECT_C2BC_LIGHT="Color2BlackLightColor";
const MODE_EFFECT_ENHANCE_DARK="EnhanceDark";

const MODE_EFFECT_GLOW="EffectGlow";
const MODE_EFFECT_BLEND="EffectBlend";
const MODE_EFFECT_GLFX="EffectGLFX";

var effectCheck=null;
var effectSize1=null;
var effectColor=null;
var effectEnhanceDarkIntensity=null;
var effectEnhanceDarkSubmit=null;

let nowEffect=null;
function switchMangaEffect(type) {

switch (type) {
case MODE_EFFECT_ENHANCE_DARK:
case MODE_EFFECT_C2BW_LIGHT:
case MODE_EFFECT_C2BW_DARK:
case MODE_EFFECT_C2BW_ROUGHT:
case MODE_EFFECT_C2BW_SIMPLE:
case MODE_EFFECT_C2BC_LIGHT:
case MODE_EFFECT_GLOW:
case MODE_EFFECT_GLFX:
if (!checkActiveImage()) {
return;
}
break;
case MODE_EFFECT_BLEND:
break;
default:
break;
}


switchMangaEffectUi(type);

if (nowEffect) {
if (type==nowEffect) {
clearActiveEffectButton();
nowEffect=null;
return;
} else {
clearActiveEffectButton();
nowEffect=null;
}
}

nowEffect=type;


if (type===MODE_EFFECT_ENHANCE_DARK) {
//skip
} else if (type===MODE_EFFECT_C2BW_LIGHT) {
C2BWStartLight();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_C2BW_DARK) {
C2BWStartDark();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_C2BW_ROUGHT) {
C2BWStartRough();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_C2BW_SIMPLE) {
C2BWStartSimple();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_C2BC_LIGHT) {
C2CStart();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_BLEND) {
handleBlend();
clearActiveEffectButton();
nowEffect=null;
return;
} else if (type===MODE_EFFECT_GLOW) {
//skip
} else if (type===MODE_EFFECT_GLFX) {
setGlfxI18NextLabel();
glfxAddEvent();
} else {
console.error("unknown type",type);
}

addEffectEventListener();
clearActiveEffectButton();
$(type+'Button').classList.add('active-button');
}

function switchMangaEffectUi(type) {
clearEffectSettings();
let settingsHTML='';

switch (type) {
case MODE_EFFECT_GLOW:
settingsHTML+=addCheckBox("addGlowEffectCheckBox","outloneGlow",false)
settingsHTML+=addSlider("glowOutLineSlider","glowOutLineSize",0,250,effectMap.getOrDefault("glowOutLineSlider",20));
settingsHTML+=addColor("glowOutLineColorPicker","glowOutLineColor",effectMap.getOrDefault("glowOutLineColorPicker",'#FFFFFF'));
settingsHTML+=addTextArea("glowInfomation","glowInfomation");
$('manga-effect-settings').innerHTML=settingsHTML;
effectCheck=$("addGlowEffectCheckBox");
effectSize1=$("glowOutLineSlider");
effectColor=$("glowOutLineColorPicker");
break;
case MODE_EFFECT_GLFX:
$('manga-effect-settings').innerHTML=gpifHTML;
break;
case MODE_EFFECT_ENHANCE_DARK:
settingsHTML+=addSlider("effectEnhanceDarkIntensity","effectEnhanceDarkIntensity",0.1,20.0,effectMap.getOrDefault("effectEnhanceDarkIntensity",2.0),0.1);
settingsHTML+=addSimpleSubmitButton("effectEnhanceDarkSubmit");
$('manga-effect-settings').innerHTML=settingsHTML;
effectEnhanceDarkIntensity=$("effectEnhanceDarkIntensity");
effectEnhanceDarkSubmit=$("effectEnhanceDarkSubmit");
break;
default:
$('manga-effect-settings').innerHTML=settingsHTML;
return;
}

jsColorSet();

const sliders2=document.querySelectorAll('.input-container-leftSpace input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container-leftSpace')
});
}

function clearEffectSettings() {
const elements=[
effectCheck,
effectSize1,
effectEnhanceDarkIntensity,
effectColor
];
elements.forEach(element=>{
if (element) {
element.removeEventListener("change",saveEffectValueMap);
}
});

effectCheck=null;
effectSize1=null;
effectColor=null;
effectEnhanceDarkIntensity=null;
}


function addEffectEventListener() {
const elements=[
effectCheck,
effectSize1,
effectEnhanceDarkIntensity,
effectColor
];

if(effectEnhanceDarkSubmit){
effectEnhanceDarkSubmit.addEventListener('click',()=>{
if (nowEffect==MODE_EFFECT_ENHANCE_DARK) {
const selectedObject=canvas.getActiveObject();
if (selectedObject) {
console.log("enhanceDarkImage","start");
enhanceDarkImage();
} else {
createToast("Check image!")
}
}
});
}

elements.forEach(element=>{
if (element) {
element.addEventListener('change',()=>{saveEffectValueMap(element);});
element.addEventListener('change',()=>{
if (nowEffect==MODE_EFFECT_GLOW) {
const selectedObject=canvas.getActiveObject();
if (selectedObject) {
if (effectCheck.checked) {
const color=effectColor.value;
const blurValue=parseInt(effectSize1.value,20);
selectedObject.set({
shadow: {
color: color,
blur: blurValue,
offsetX: 0,
offsetY: 0
}
});
} else {
selectedObject.set({shadow: null});
}
canvas.renderAll();
} else {
createToast("Check image!")
}
}
});
} else {
console.log("element is null");
}
});
}



function clearActiveEffectButton() {
$(MODE_EFFECT_GLOW+'Button').classList.remove('active-button');
$(MODE_EFFECT_GLFX+'Button').classList.remove('active-button');
$(MODE_EFFECT_ENHANCE_DARK+'Button').classList.remove('active-button');
}


