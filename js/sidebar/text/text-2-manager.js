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

// 種類を跨いでも同じ意味を持つ設定。種類を変えたときはこれだけ引き継ぐ。
// 引き継がないと入力中の文字が新しい種類の記憶値に戻り、
// 「同じ文字のまま見た目だけ変える」ができない
const T2_COMMON_SETTINGS=["Text","FontSize","LineHeight","LetterSpacing","TextColor","FillOpacity"];

// 挿入位置。同じ座標に重ねると増えたことが見た目で分からないため押すたびにずらす
const T2_INSERT_LEFT=50;
const T2_INSERT_TOP=100;
const T2_INSERT_STEP=20;
const T2_INSERT_WRAP=8;
let t2InsertCount=0;

function t2CaptureCommonValues(type) {
var values={};
T2_COMMON_SETTINGS.forEach(function (name) {
var element=$(type+'-'+name);
if (element) {
values[name]=element.value;
}
});
return values;
}

function t2RestoreCommonValues(type,values) {
Object.keys(values).forEach(function (name) {
var element=$(type+'-'+name);
if (!element) {
return;
}
// jscolorのピッカーはvalue代入では見た目が変わらない
if (element.jscolor) {
element.jscolor.fromString(values[name]);
} else {
element.value=values[name];
}
sidebarValueMap.set(type+'-'+name,values[name]);
});
}

// キャンバスで選んでいる画像テキスト。種類を変えたときの差し替え対象になる
function t2GetSelectedImageText() {
var activeObject=canvas.getActiveObject();
if (activeObject&&activeObject.imageTextType) {
return activeObject;
}
return null;
}

// 種類を選ぶ。選択中の画像テキストがあればその現物を新しい種類へ差し替え、
// 無ければ設定を切り替えるだけ。キャンバスに増やすのはtext2Insert()だけが行う
function switchText2(type) {
if (type===nowText2) {
return;
}

var editing=t2GetSelectedImageText();
var carried=nowText2 ? t2CaptureCommonValues(nowText2) : null;

if (editing) {
// 変形・重ね順・GUIDを退避してキャンバスから外す。
// 下のcreateText2()がこれを引き継いで同じ場所に作り直す
t2BeginReplace(editing);
}
if (nowText2) {
deleteText2();
clearT2Settings();
}

switchText2Ui(type);
nowText2=type;
if (carried) {
t2RestoreCommonValues(type,carried);
}
addT2EventListener();

if (editing) {
createText2(type);
}
}

// 「キャンバスに挿入」。今の種類・今の設定で1つ追加する
function text2Insert() {
if (!nowText2) {
createToastError(getText("imageTextSelectStyleFirst"),"",2000);
return;
}
var offset=(t2InsertCount%T2_INSERT_WRAP)*T2_INSERT_STEP;
t2InsertCount++;
createText2(nowText2,T2_INSERT_LEFT+offset,T2_INSERT_TOP+offset);
}

EventDelegator.register('insertImageText',function () {
text2Insert();
});


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
settingsHTML+=addTextArea(type+'-'+cName,cName,sidebarValueMap.getOrDefault(type+'-'+cName,'New Text'));
cName="FontSize";
settingsHTML+=addSlider(type+'-'+cName,cName,1,300,sidebarValueMap.getOrDefault(type+'-'+cName,40));
cName="LineHeight";
settingsHTML+=addSlider(type+'-'+cName,cName,0.1,5,sidebarValueMap.getOrDefault(type+'-'+cName,1.2),0.1);
cName="LetterSpacing";
settingsHTML+=addSlider(type+'-'+cName,cName,-0.5,2,sidebarValueMap.getOrDefault(type+'-'+cName,0.4),0.1);
settingsHTML+=addAlignTypeButton(type);
settingsHTML+=addOrientationButton(type);
cName="TextColor";
settingsHTML+=addColor(type+'-'+cName,cName,sidebarValueMap.getOrDefault(type+'-'+cName,'#35322a'));
cName="FillOpacity";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,sidebarValueMap.getOrDefault(type+'-'+cName,1),0.1);



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
settingsHTML+=addSlider(type+'-'+cName,cName,0,3,sidebarValueMap.getOrDefault(type+'-'+cName,1));
cName="ShadowOpacity1";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,sidebarValueMap.getOrDefault(type+'-'+cName,1),0.1);
cName="ShadowColor1";
settingsHTML+=addColor(type+'-'+cName,cName,sidebarValueMap.getOrDefault(type+'-'+cName,'#ebe7e0'));

cName="ShadowSize2";
settingsHTML+=addSlider(type+'-'+cName,cName,0,5,sidebarValueMap.getOrDefault(type+'-'+cName,5));
cName="ShadowOpacity2";
settingsHTML+=addSlider(type+'-'+cName,cName,0,1,sidebarValueMap.getOrDefault(type+'-'+cName,1),0.1);
cName="ShadowColor2";
settingsHTML+=addColor(type+'-'+cName,cName,sidebarValueMap.getOrDefault(type+'-'+cName,'#35322a'));
break;
}

$('text-area2-settings').innerHTML=settingsHTML;
jsColorSet();

t2_text=$(type+'-'+"Text");
// addTextArea()は翻訳された既定文しか埋め込めない（利用者の入力をHTMLに
// 埋めると</textarea>を含む文字でDOMが壊れる）。記憶した文字はここで代入する
var savedText=sidebarValueMap.get(type+'-'+"Text");
if (savedText!==undefined&&t2_text) {
t2_text.value=savedText;
}
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

// キャンバス上の画像テキストを選び直したときもここを通るため、
// カードは常に「今編集している種類」を指す
presetPanelSetActive('text2',type);
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
// 編集対象が無いときは何もしない。ここで作り直すと、挿入していないのに
// スライダーを触っただけでキャンバスに現れる
if(!t2GetCurrentObject()){
return;
}
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
textLogger.error("unknown type",type);
break;
}
}


// left/topを渡さないと各createSvgの既定位置になる。差し替え時は
// t2BeginReplace()が退避した変形が優先されるため位置は引き継がれる
function createText2(type,left,top){
let nowImageTextObject=null;
switch (type) {
case MODE_T2_aurora:
t2_aurora_createSvg(left,top);
break;
case MODE_T2_broken:
t2_broken_createSvg(left,top);
break;
case MODE_T2_cloud :
t2_cloud_createSvg(left,top);
break;
case MODE_T2_layered:
t2_layered_createSvg(left,top);
break;
case MODE_T2_mesh  :
t2_mesh_createSvg(left,top);
break;
case MODE_T2_night :
t2_nightlights_createSvg(left,top);
break;
case MODE_T2_scratch:
t2_scratch_createSvg(left,top);
break;
case MODE_T2_thrill:
t2_thrill_createSvg(left,top);
break;
case MODE_T2_water :
t2_water_createSvg(left,top);
break;
case MODE_T2_wild  :
t2_wild_createSvg(left,top);
break;
case MODE_T2_zebra :
t2_zebra_createSvg(left,top);
break;
case MODE_T2_SHADOW:
t2_shadow_createSvg(left,top);
nowImageTextObject=nowT2ShadowStr;
break;
default:
textLogger.error("unknown type",type);
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
textLogger.error("unknown type",type);
break;
}
}


function clearActiveT2Button() {
// $(MODE_T2_SHADOW + 'Button').classList.remove('active-button');
}

const t2SetCurrentMap={
aurora:function(obj){t2_aurora_setCurrent(obj);},
broken:function(obj){t2_broken_setCurrent(obj);},
cloud:function(obj){t2_cloud_setCurrent(obj);},
layered:function(obj){t2_layered_setCurrent(obj);},
mesh:function(obj){t2_mesh_setCurrent(obj);},
scratch:function(obj){t2_scratch_setCurrent(obj);},
shadow:function(obj){t2_shadow_setCurrent(obj);},
thrill:function(obj){t2_thrill_setCurrent(obj);},
water:function(obj){t2_water_setCurrent(obj);},
wild:function(obj){t2_wild_setCurrent(obj);},
zebra:function(obj){t2_zebra_setCurrent(obj);}
};

// t2SetCurrentMapの取得側。今どのオブジェクトを編集しているかの判定に使う
const t2GetCurrentMap={
aurora:function(){return nowT2AuroraStr;},
broken:function(){return nowT2BrokenStr;},
cloud:function(){return nowT2CloudStr;},
layered:function(){return nowT2LayeredStr;},
mesh:function(){return nowT2MeshStr;},
scratch:function(){return nowT2ScratchStr;},
shadow:function(){return nowT2ShadowStr;},
thrill:function(){return nowT2ThrillStr;},
water:function(){return nowT2WaterStr;},
wild:function(){return nowT2WildStr;},
zebra:function(){return nowT2ZebraStr;}
};

function t2GetCurrentObject(){
if(!nowText2||!t2GetCurrentMap[nowText2]){
return null;
}
return t2GetCurrentMap[nowText2]();
}

// キャンバス上の画像テキストを選び直したとき、サイドバーをその種類・値に戻し、
// 以降の編集がそのオブジェクトに向くようにする。
// これをしないと直前に作った1つしか編集できない
function syncImageTextControls(activeObject){
if(!activeObject||!activeObject.imageTextType){
return;
}
var type=activeObject.imageTextType;
if(!t2SetCurrentMap[type]){
textLogger.error("unknown imageTextType: "+type);
return;
}
var params=activeObject.imageTextParams||{};
Object.keys(params).forEach(function(key){
sidebarValueMap.set(key,params[key]);
});
if(nowText2!==type){
clearT2Settings();
switchText2Ui(type);
nowText2=type;
addT2EventListener();
}
// 種類が同じでも必ず選び直した相手の値へ入れ替える。
// 入れ替えないと、アアアを選んだあとイイイを選んでもアアアの値が残る
restoreT2SettingValues(params);
t2SetCurrentMap[type](activeObject);
}

function restoreT2SettingValues(params){
if(!params){
return;
}
Object.keys(params).forEach(function(key){
var element=$(key);
if(!element){
return;
}
// jscolorのピッカーはvalue代入では見た目が変わらない
if(element.jscolor){
element.jscolor.fromString(params[key]);
}else{
element.value=params[key];
}
});
}
