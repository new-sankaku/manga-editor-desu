const t2Map=new Map();
const MODE_T2_SHADOW="shadow";
const MODE_T2_aurora="aurora";
const MODE_T2_broken="broken";
const MODE_T2_cloud="cloud";
const MODE_T2_layered="layered";
const MODE_T2_mesh="mesh";
const MODE_T2_night="night";
const MODE_T2_scratch="scratch";
const MODE_T2_thrill="thrill";
const MODE_T2_water="water";
const MODE_T2_wild="wild";
const MODE_T2_zebra="zebra";

var t2_text=null;
var t2_fontSize=null;
var t2_lineHeight=null;
var t2_letterSpacing=null;
var t2_shadow1Size=null;
var t2_shadow1Opacity=null;
var t2_shadow1Color=null;
var t2_shadow2Size=null;
var t2_shadow2Opacity=null;
var t2_shadow2Color=null;
var t2_fillColor=null;
var t2_fillOpacity=null;
var t2_align_l=null;
var t2_align_c=null;
var t2_align_r=null;
var t2_orientation_v=null;
var t2_orientation_l=null;

let elementsT2=[];
let buttonElementsT2=[];

let nowText2=null;

function switchText2(type) {
switchText2Ui(type);

if (nowText2) {
deleteText2();
clearT2Settings();
nowText2=null;
}

createText2(type);

if(type){
addT2EventListener();
nowText2=type;
}
}


function switchText2Ui(type) {
let settingsHTML='';

elementsT2.forEach(element=>{
if (element) {
element=null;
}
});

//Common settings.
var cName="";
// cName = "fontT2Selector";
// settingsHTML += "<div id='fontT2Selector'></div>"
cName="Text";
settingsHTML+=addTextArea(type+'-'+cName,cName,t2Map.getOrDefault(type+'-'+cName,'New Text'));
cName="FontSize";
settingsHTML+=addSlider(type+'-'+cName,cName,1,300,t2Map.getOrDefault(type+'-'+cName,40));
cName="LineHeight";
settingsHTML+=addSlider(type+'-'+cName,cName,0.1,5,t2Map.getOrDefault(type+'-'+cName,1.2),0.1);
cName="LetterSpacing";
settingsHTML+=addSlider(type+'-'+cName,cName,-0.5,2,t2Map.getOrDefault(type+'-'+cName,0.4),0.1);
settingsHTML+=addAlignTypeButton(type);
settingsHTML+=addOrientationButton(type);
cName="TextColor";
settingsHTML+=addColor(type+'-'+cName,cName,t2Map.getOrDefault(type+'-'+cName,'#35322a'));
cName="FillOpacity";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,t2Map.getOrDefault(type+'-'+cName,1),0.1);



switch (type) {
case MODE_T2_aurora:
break;
case MODE_T2_broken:
break;
case MODE_T2_cloud :
break;
case MODE_T2_layered:
break;
case MODE_T2_mesh  :
break;
case MODE_T2_night :
break;
case MODE_T2_scratch:
break;
case MODE_T2_thrill:
break;
case MODE_T2_water :
break;
case MODE_T2_wild  :
break;
case MODE_T2_zebra :
break;

case MODE_T2_SHADOW:
cName="ShadowSize1";
settingsHTML+=addSlider(type+'-'+cName,cName,0,3,t2Map.getOrDefault(type+'-'+cName,1));
cName="ShadowOpacity1";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,t2Map.getOrDefault(type+'-'+cName,1),0.1);
cName="ShadowColor1";
settingsHTML+=addColor(type+'-'+cName,cName,t2Map.getOrDefault(type+'-'+cName,'#ebe7e0'));

cName="ShadowSize2";
settingsHTML+=addSlider(type+'-'+cName,cName,0,5,t2Map.getOrDefault(type+'-'+cName,5));
cName="ShadowOpacity2";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,t2Map.getOrDefault(type+'-'+cName,1),0.1);
cName="ShadowColor2";
settingsHTML+=addColor(type+'-'+cName,cName,t2Map.getOrDefault(type+'-'+cName,'#35322a'));
break;
}

$('text-area2-settings').innerHTML=settingsHTML;
jsColorSet();

t2_text=$(type+'-'+"Text");
t2_fontSize=$(type+'-'+"FontSize");
t2_fillColor=$(type+'-'+"TextColor");
t2_fillOpacity=$(type+'-'+"FillOpacity");
t2_lineHeight=$(type+'-'+"LineHeight");
t2_letterSpacing=$(type+'-'+"LetterSpacing");
t2_align_l=$("T2-align-left");
t2_align_c=$("T2-align-center");
t2_align_r=$("T2-align-right");
t2_orientation_v=$("T2-Orientation-vertical");
t2_orientation_l=$("T2-Orientation-horizontal");


switch (type) {
case MODE_T2_aurora:
break;
case MODE_T2_broken:
break;
case MODE_T2_cloud :
break;
case MODE_T2_layered:
break;
case MODE_T2_mesh  :
break;
case MODE_T2_night :
break;
case MODE_T2_scratch:
break;
case MODE_T2_thrill:
break;
case MODE_T2_water :
break;
case MODE_T2_wild  :
break;
case MODE_T2_zebra :
break;
case MODE_T2_SHADOW:
t2_shadow1Size=$(type+'-'+"ShadowSize1");
t2_shadow1Opacity=$(type+'-'+"ShadowOpacity1");
t2_shadow1Color=$(type+'-'+"ShadowColor1");
t2_shadow2Size=$(type+'-'+"ShadowSize2");
t2_shadow2Opacity=$(type+'-'+"ShadowOpacity2");
t2_shadow2Color=$(type+'-'+"ShadowColor2");
break;
}

// new FontSelector("fontT2Selector", "Font");

elementsT2=[
t2_text,
t2_fontSize,
t2_lineHeight,
t2_letterSpacing,
t2_fillColor,
t2_fillOpacity,

t2_shadow1Size,
t2_shadow1Opacity,
t2_shadow1Color,
t2_shadow2Size,
t2_shadow2Opacity,
t2_shadow2Color
];

buttonElementsT2=[
t2_align_l,
t2_align_c,
t2_align_r,
t2_orientation_v,
t2_orientation_l
];

const sliders2=document.querySelectorAll('.input-container-leftSpace input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container-leftSpace')
});
}

function clearT2Settings() {
// document.removeEventListener("fontT2Selector", handleFont);

elementsT2.forEach(element=>{
if (element) {
element.removeEventListener("input",saveValueMap);
element=null;
}
});
buttonElementsT2.forEach(element=>{
if (element) {
element.removeEventListener("click",saveValueMap);
element=null;
}
});
}

function debounceCustomText(func,delay) {
let timeoutId;
return function (...args) {
clearTimeout(timeoutId);
timeoutId=setTimeout(()=>func.apply(this,args),delay);
};
}

const debouncedUpdate=debounceCustomText(()=>{
updateText2();
},50);

const handleFont=(e)=>{
updateText2();
};

function addT2EventListener(){
// document.addEventListener("fontT2Selector", handleFont);



elementsT2.forEach(element=>{
if (element) {
element.addEventListener('input',()=>{
saveValueMap(element);
debouncedUpdate();
});
}
});
buttonElementsT2.forEach(element=>{
if (element) {
element.addEventListener('click',()=>{
saveValueMap(element);
updateText2();

});
}
});
}



function updateText2(){
switch (nowText2) {
case MODE_T2_aurora:
t2_aurora_updateAll();
break;
case MODE_T2_broken:
t2_broken_updateAll();
break;
case MODE_T2_cloud :
t2_cloud_updateAll();
break;
case MODE_T2_layered:
t2_layered_updateAll();
break;
case MODE_T2_mesh  :
t2_mesh_updateAll();
break;
case MODE_T2_night :
t2_nightlights_updateAll();
break;
case MODE_T2_scratch:
t2_scratch_updateAll();
break;
case MODE_T2_thrill:
t2_thrill_updateAll();
break;
case MODE_T2_water :
t2_water_updateAll();
break;
case MODE_T2_wild  :
t2_wild_updateAll();
break;
case MODE_T2_zebra :
t2_zebra_updateAll();
break;
case MODE_T2_SHADOW:
t2_shadow_updateAll();
break;
default:
console.error("unknown type",type);
break;
}
}


function createText2(type){
let nowImageTextObject=null;
switch (type) {
case MODE_T2_aurora:
t2_aurora_createSvg();
break;
case MODE_T2_broken:
t2_broken_createSvg();
break;
case MODE_T2_cloud :
t2_cloud_createSvg();
break;
case MODE_T2_layered:
t2_layered_createSvg();
break;
case MODE_T2_mesh  :
t2_mesh_createSvg();
break;
case MODE_T2_night :
t2_nightlights_createSvg();
break;
case MODE_T2_scratch:
t2_scratch_createSvg();
break;
case MODE_T2_thrill:
t2_thrill_createSvg();
break;
case MODE_T2_water :
t2_water_createSvg();
break;
case MODE_T2_wild  :
t2_wild_createSvg();
break;
case MODE_T2_zebra :
t2_zebra_createSvg();
break;
case MODE_T2_SHADOW:
t2_shadow_createSvg();
nowImageTextObject=nowT2ShadowStr;
break;
default:
console.error("unknown type",type);
break;
}
}

function deleteText2(){
switch (nowText2) {
case MODE_T2_aurora:
t2_aurora_deleteSvg();
break;
case MODE_T2_broken:
t2_broken_deleteSvg();
break;
case MODE_T2_cloud :
t2_cloud_deleteSvg();
break;
case MODE_T2_layered:
t2_layered_deleteSvg();
break;
case MODE_T2_mesh  :
t2_mesh_deleteSvg();
break;
case MODE_T2_night :
t2_nightlights_deleteSvg();
break;
case MODE_T2_scratch:
t2_scratch_deleteSvg();
break;
case MODE_T2_thrill:
t2_thrill_deleteSvg();
break;
case MODE_T2_water :
t2_water_deleteSvg();
break;
case MODE_T2_wild  :
t2_wild_deleteSvg();
break;
case MODE_T2_zebra :
t2_zebra_deleteSvg();
break;
case MODE_T2_SHADOW:
t2_shadow_deleteSvg();
break;
default:
console.error("unknown type",type);
break;
}
}


function clearActiveT2Button() {
// $(MODE_T2_SHADOW + 'Button').classList.remove('active-button');
}
