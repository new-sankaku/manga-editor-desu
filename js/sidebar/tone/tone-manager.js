function parseColor(color) {
var m=color.match(/rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)/);
if(m)return{r:parseInt(m[1]),g:parseInt(m[2]),b:parseInt(m[3]),a:parseFloat(m[4])};
m=color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
if(m)return{r:parseInt(m[1]),g:parseInt(m[2]),b:parseInt(m[3]),a:1};
var result=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(color);
if(result)return{r:parseInt(result[1],16),g:parseInt(result[2],16),b:parseInt(result[3],16),a:1};
return{r:0,g:0,b:0,a:1};
}

const MODE_TONE="Tone";
const MODE_TONE_NOISE="ToneNoise";
const MODE_TONE_SNOW="ToneSnow";
const MODE_FOCUSING_LINE="FocusingLine";
const MODE_SPEED_LINE="SpeedLine";

var mangaToneAngle=null;
var mangaToneBackBlurSize=null;
var mangaToneBackColor=null;
var mangaToneBackSize=null;
var mangaToneCenterX=null;
var mangaToneCenterY=null;
var mangaToneColor=null;
var mangaToneDensity=null;
var mangaToneDotSize=null;
var mangaToneDotSpacing=null;
var mangaToneDotStyle=null;
var mangaToneFrontBlurSize=null;
var mangaToneFrontSize=null;
var mangaToneGradEnd=null;
var mangaToneGradEndX=null;
var mangaToneGradEndY=null;
var mangaToneGradStart=null;
var mangaToneGradStartX=null;
var mangaToneGradStartY=null;
var mangaToneGradStyle=null;
var mangaToneLineSize=null;
var mangaToneLineWidthExpand=null;
var mangaToneMaxNoise=null;
var mangaToneMaxRadius=null;
var mangaToneMinNoise=null;
var mangaToneMinRadius=null;

let nowTone=null;

function switchMangaTone(type) {
switchMangaToneUi(type);

if (nowTone) {
if (type==nowTone) {
clearActiveToneButton();
speedLineEnd();
focusLineEnd();
toneNoiseEnd();
toneEnd();
nowTone=null;
return;
} else {
clearActiveToneButton();
speedLineEnd();
focusLineEnd();
toneNoiseEnd();
toneEnd();
nowTone=null;
}
}

if (type===MODE_TONE) {
toneStart();
addToneEventListener();
debouncedGenerateTone();
} else if (type===MODE_TONE_NOISE) {
toneNoiseStart();
addToneNoiseEventListener();
updateToneNoise();
} else if (type===MODE_TONE_SNOW) {
snowToneStart();
addSnowToneEventListener();
generateSnowTone();
} else if (type===MODE_FOCUSING_LINE) {
focusLineStart();
addFCEventListener();
// updateFocusLine();
} else if (type===MODE_SPEED_LINE) {
speedLineStart();
addSppedLineEventListener();
updateDrawingSpeedlines();
} else {
effectLogger.error("unknown type",type);
}

clearActiveToneButton();
$(type+'Button').classList.add('active-button');
nowTone=type;
}

function switchMangaToneUi(type) {

// console.log("switchMangaToneUi type ", type);

clearToneSettings();
let settingsHTML='';
switch (type) {
case MODE_TONE:
settingsHTML+=addDropDownByDot(MODE_TONE+'-dot-style','dotStyle');
settingsHTML+=addColor(MODE_TONE+'-color','color',sidebarValueMap.getOrDefault(MODE_TONE+'-color','#000000'));
settingsHTML+=addCheckBox(MODE_TONE+'-grad-check','grad-check',sidebarValueMap.getOrDefault(MODE_TONE+'-grad-check','true'));//density
settingsHTML+=addDropDownByGrad(MODE_TONE+'-grad-style','gradStyle');
settingsHTML+=addSlider(MODE_TONE+'-dot-size','dot-size',1,100,sidebarValueMap.getOrDefault(MODE_TONE+'-dot-size',5));//density
settingsHTML+=addSlider(MODE_TONE+'-dot-spacing','dot-spacing',1,100,sidebarValueMap.getOrDefault(MODE_TONE+'-dot-spacing',5));//density
settingsHTML+=addSlider(MODE_TONE+'-grad-start','grad-start',0,100,sidebarValueMap.getOrDefault(MODE_TONE+'-grad-start',0));//grad-start-y
settingsHTML+=addSlider(MODE_TONE+'-grad-end','grad-end',0,100,sidebarValueMap.getOrDefault(MODE_TONE+'-grad-end',100));//grad-end-y
$('manga-tone-settings').innerHTML=settingsHTML;
jsColorSet();

mangaToneColor=$(MODE_TONE+'-color');
mangaToneDotStyle=$(MODE_TONE+'-dot-style');
mangaToneDotSize=$(MODE_TONE+'-dot-size');
mangaToneDotSpacing=$(MODE_TONE+'-dot-spacing');
mangaToneGradStyle=$(MODE_TONE+'-grad-style');
mangaToneGradStart=$(MODE_TONE+'-grad-start');
mangaToneGradEnd=$(MODE_TONE+'-grad-end');
break;
case MODE_TONE_NOISE:
settingsHTML+=addColor(MODE_TONE_NOISE+'-color','color',sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-color','#000000'));
settingsHTML+=addSlider(MODE_TONE_NOISE+'-max-noise','max-noise',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-max-radius',95));//max-noise
settingsHTML+=addSlider(MODE_TONE_NOISE+'-min-noise','min-noise',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-min-radius',100));//min-noise
settingsHTML+=addSlider(MODE_TONE_NOISE+'-grad-start-x','grad-start-x',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-grad-start-x',0));//grad-start-y
settingsHTML+=addSlider(MODE_TONE_NOISE+'-grad-start-y','grad-start-y',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-grad-start-y',0));//grad-start-y
settingsHTML+=addSlider(MODE_TONE_NOISE+'-grad-end-x','grad-end-x',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-grad-end-x',100));//grad-end-y
settingsHTML+=addSlider(MODE_TONE_NOISE+'-grad-end-y','grad-end-y',0,100,sidebarValueMap.getOrDefault(MODE_TONE_NOISE+'-grad-end-y',100));//grad-end-y
$('manga-tone-settings').innerHTML=settingsHTML;
jsColorSet();

mangaToneColor=$(MODE_TONE_NOISE+'-color');
mangaToneMaxNoise=$(MODE_TONE_NOISE+'-max-noise');
mangaToneMinNoise=$(MODE_TONE_NOISE+'-min-noise');
mangaToneGradStartX=$(MODE_TONE_NOISE+'-grad-start-x');
mangaToneGradEndX=$(MODE_TONE_NOISE+'-grad-end-x');
mangaToneGradStartY=$(MODE_TONE_NOISE+'-grad-start-y');
mangaToneGradEndY=$(MODE_TONE_NOISE+'-grad-end-y');
break;
case MODE_TONE_SNOW:
settingsHTML+=addColor(MODE_TONE_SNOW+'-frontColor','frontColor',sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-frontColor','#FFFFFF'));
settingsHTML+=addColor(MODE_TONE_SNOW+'-backColor','backColor',sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-backColor','#CCCCCC'));
settingsHTML+=addSlider(MODE_TONE_SNOW+'-density','density',1,3000,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-density',1000));//density
settingsHTML+=addSlider(MODE_TONE_SNOW+'-frontSize','frontSize',1,50,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-frontSize',10));//density
settingsHTML+=addSlider(MODE_TONE_SNOW+'-backSize','backSize',1,50,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-backSize',3));//density
settingsHTML+=addSlider(MODE_TONE_SNOW+'-frontBlurSize','frontBlurSize',1,50,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-frontBlurSize',10));//density
settingsHTML+=addSlider(MODE_TONE_SNOW+'-backBlurSize','backBlurSize',1,50,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-backBlurSize',3));//density
settingsHTML+=addSlider(MODE_TONE_SNOW+'-angle','angle',0,180,sidebarValueMap.getOrDefault(MODE_TONE_SNOW+'-angle',140));//density
$('manga-tone-settings').innerHTML=settingsHTML;
jsColorSet();

mangaToneColor=$(MODE_TONE_NOISE+'-frontColor');
mangaToneBackColor=$(MODE_TONE_NOISE+'-backColor');
mangaToneDensity=$(MODE_TONE_NOISE+'-density');
mangaToneFrontSize=$(MODE_TONE_NOISE+'-frontSize');
mangaToneBackSize=$(MODE_TONE_NOISE+'-backSize');
mangaToneFrontBlurSize=$(MODE_TONE_NOISE+'-frontBlurSize');
mangaToneBackBlurSize=$(MODE_TONE_NOISE+'-backBlurSize');
mangaToneAngle=$(MODE_TONE_NOISE+'-angle');

break;
case MODE_FOCUSING_LINE:
settingsHTML+=addColor(MODE_FOCUSING_LINE+'-color','color',sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-color','#000000'));
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-lineNum','lineNum',1,500,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-lineNum',200));//line-size
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-line-size','line-size',1,500,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-line-width',50));//line-size
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-min-radius','min-radius',1,200,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-min-radius',20));//min-radius
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-max-radius','max-radius',1,200,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-max-radius',60));//max-radius
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-center-x','centerX',0,100,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-center-x',0));
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-center-y','centerY',0,100,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-center-y',0));
settingsHTML+=addSlider(MODE_FOCUSING_LINE+'-line-width-expand','line-width-expand',1,300,sidebarValueMap.getOrDefault(MODE_FOCUSING_LINE+'-line-width-expand',100));// line-width-expand
$('manga-tone-settings').innerHTML=settingsHTML;
jsColorSet();

mangaToneColor=$(MODE_FOCUSING_LINE+'-color');
mangaToneLineSize=$(MODE_FOCUSING_LINE+'-line-size');
mangaToneMaxRadius=$(MODE_FOCUSING_LINE+'-max-radius');
mangaToneMinRadius=$(MODE_FOCUSING_LINE+'-min-radius');
mangaToneCenterX=$(MODE_FOCUSING_LINE+'-center-x');
mangaToneCenterY=$(MODE_FOCUSING_LINE+'-center-y');
mangaToneLineWidthExpand=$(MODE_FOCUSING_LINE+'-line-width-expand');
break;

case MODE_SPEED_LINE:
settingsHTML+=addColor(MODE_SPEED_LINE+'-color','color',sidebarValueMap.getOrDefault(MODE_SPEED_LINE+'-color','#000000'));
settingsHTML+=addDropDownBySpeedLine("speed-line-style","speedLineStyle");
settingsHTML+=addCheckBox(MODE_SPEED_LINE+'-grad-check','grad-check',sidebarValueMap.getOrDefault(MODE_SPEED_LINE+'-grad-check','true'));//density
settingsHTML+=addSlider(MODE_SPEED_LINE+'-density','density',1,1500,sidebarValueMap.getOrDefault(MODE_SPEED_LINE+'-density',150));//density
settingsHTML+=addSlider(MODE_SPEED_LINE+'-grad-start','grad-start',0,100,sidebarValueMap.getOrDefault(MODE_SPEED_LINE+'-grad-start',0));//grad-start-y
settingsHTML+=addSlider(MODE_SPEED_LINE+'-grad-end','grad-end',0,100,sidebarValueMap.getOrDefault(MODE_SPEED_LINE+'-grad-end',100));//grad-end-y
$('manga-tone-settings').innerHTML=settingsHTML;
jsColorSet();

mangaToneColor=$(MODE_TONE_NOISE+'-color');
mangaToneDensity=$(MODE_TONE_NOISE+'-density');
mangaToneGradStart=$(MODE_TONE_NOISE+'-grad-start');
mangaToneGradEnd=$(MODE_TONE_NOISE+'-grad-end');
break;
}

const sliders2=document.querySelectorAll('.input-container-leftSpace input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container-leftSpace')
});
}

function clearToneSettings() {

const elements=[
mangaToneAngle,
mangaToneBackBlurSize,
mangaToneBackColor,
mangaToneBackSize,
mangaToneCenterX,
mangaToneCenterY,
mangaToneColor,
mangaToneDensity,
mangaToneDotSize,
mangaToneDotSpacing,
mangaToneDotStyle,
mangaToneFrontBlurSize,
mangaToneFrontSize,
mangaToneGradEnd,
mangaToneGradEndX,
mangaToneGradEndY,
mangaToneGradStart,
mangaToneGradStartX,
mangaToneGradStartY,
mangaToneGradStyle,
mangaToneLineSize,
mangaToneLineWidthExpand,
mangaToneMaxNoise,
mangaToneMaxRadius,
mangaToneMinNoise,
mangaToneMinRadius
];

elements.forEach(element=>{
if (element) {
element.removeEventListener("change",saveValueMap);
}
});
mangaToneAngle=null;
mangaToneBackBlurSize=null;
mangaToneBackColor=null;
mangaToneBackSize=null;
mangaToneCenterX=null;
mangaToneCenterY=null;
mangaToneColor=null;
mangaToneDensity=null;
mangaToneDotSize=null;
mangaToneDotSpacing=null;
mangaToneDotStyle=null;
mangaToneFrontBlurSize=null;
mangaToneFrontSize=null;
mangaToneGradEnd=null;
mangaToneGradEndX=null;
mangaToneGradEndY=null;
mangaToneGradStart=null;
mangaToneGradStartX=null;
mangaToneGradStartY=null;
mangaToneGradStyle=null;
mangaToneLineSize=null;
mangaToneLineWidthExpand=null;
mangaToneMaxNoise=null;
mangaToneMaxRadius=null;
mangaToneMinNoise=null;
mangaToneMinRadius=null;
}


function addToneEventListener(){

const elements=[
mangaToneAngle,
mangaToneBackBlurSize,
mangaToneBackColor,
mangaToneBackSize,
mangaToneCenterX,
mangaToneCenterY,
mangaToneColor,
mangaToneDensity,
mangaToneDotSize,
mangaToneDotSpacing,
mangaToneDotStyle,
mangaToneFrontBlurSize,
mangaToneFrontSize,
mangaToneGradEnd,
mangaToneGradEndX,
mangaToneGradEndY,
mangaToneGradStart,
mangaToneGradStartX,
mangaToneGradStartY,
mangaToneGradStyle,
mangaToneLineSize,
mangaToneLineWidthExpand,
mangaToneMaxNoise,
mangaToneMaxRadius,
mangaToneMinNoise,
mangaToneMinRadius
];

elements.forEach(element=>{
if (element) {
element.addEventListener('change',()=>{
saveValueMap(element);
});
}
});
}



function clearActiveToneButton() {
$(MODE_TONE+'Button').classList.remove('active-button');
$(MODE_TONE_NOISE+'Button').classList.remove('active-button');
$(MODE_TONE_SNOW+'Button').classList.remove('active-button');
$(MODE_FOCUSING_LINE+'Button').classList.remove('active-button');
$(MODE_SPEED_LINE+'Button').classList.remove('active-button');
}



function convertToSVG(tempCanvas) {
var width=tempCanvas.width;
var height=tempCanvas.height;
var svgString=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">`;

lines.forEach(function (line) {
svgString+=`<path d="M${line.startPos.x},${line.startPos.y} L${line.movePos.x},${line.movePos.y} L${line.endPos.x},${line.endPos.y} Z" fill="${conf.color}" />`;
});

svgString+="</svg>";
return svgString;
}


