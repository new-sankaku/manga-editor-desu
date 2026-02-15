Map.prototype.getOrDefault=function (key,defaultValue) {
return this.has(key) ? this.get(key) : defaultValue;
};

const sidebarValueMap=new Map();
const penValueMap=new Map();
const effectValueMap=new Map();

(function(){
try{
var s=localStorage.getItem('sidebarValues');
if(s)Object.entries(JSON.parse(s)).forEach(function(e){sidebarValueMap.set(e[0],e[1]);});
var p=localStorage.getItem('penValues');
if(p)Object.entries(JSON.parse(p)).forEach(function(e){penValueMap.set(e[0],e[1]);});
var ef=localStorage.getItem('effectValues');
if(ef)Object.entries(JSON.parse(ef)).forEach(function(e){effectValueMap.set(e[0],e[1]);});
}catch(e){}
})();

var _sidebarSaveTimer=null;
function _debouncedSidebarSave(){
if(_sidebarSaveTimer)clearTimeout(_sidebarSaveTimer);
_sidebarSaveTimer=setTimeout(function(){
var chk=document.getElementById('settingsAutoSaveCheckbox');
if(!chk||!chk.checked)return;
localStorage.setItem('sidebarValues',JSON.stringify(Object.fromEntries(sidebarValueMap)));
localStorage.setItem('penValues',JSON.stringify(Object.fromEntries(penValueMap)));
localStorage.setItem('effectValues',JSON.stringify(Object.fromEntries(effectValueMap)));
},500);
}

function savePenValueMap(element){
penValueMap.set(element.id,element.value);
_debouncedSidebarSave();
}
function saveEffectValueMap(element){
effectValueMap.set(element.id,element.value);
_debouncedSidebarSave();
}

function saveValueMap(element){
sidebarValueMap.set(element.id,element.value);
_debouncedSidebarSave();
}

function addNumber(id,label,min,max,value,step=1) {
const transLavel=getText(label);
return `
      <div class="pen-input-2group">
          <label for="${id}" data-i18n="${label}">${transLavel}</label>
          <input type="number" id="${id}" min="${min}" max="${max}" value="${value}" step="${step}">
      </div>
  `;
}

function addSimpleSubmitButton(id) {
const transLavel=getText("submit");
return `
    <div class="input-group-multi-mini">
      <a style="visibility: hidden;"></a>
      <a style="visibility: hidden;"></a>
      <button id="${id}"">
        <span>${transLavel}</span>
      </button>
    </div>
  `;
}



function addSubmitButton(id) {
const transLavel=getText("submit");
return `
    <div class="input-group-multi-mini">
      <a style="visibility: hidden;"></a>
      <a style="visibility: hidden;"></a>
      <button id="${id}-submit" onclick="text2Submit('${id}-submit')">
        <span>${transLavel}</span>
      </button>
    </div>
  `;
}


function addColor(id,label,value) {
const transLavel=getText(label);
return `
      <div class="pen-input-2group">
          <label for="${id}" data-i18n="${label}">${transLavel}</label>
          <input id="${id}" value="${value}" class="jscolor-color-picker" data-initial-color="${value}">
      </div>
  `;
}

function addSlider(id,label,min,max,value,step=1) {
const transLavel=getText(label);
return `
      <div class="input-container-leftSpace" data-label="${transLavel}">
          <input type="range" id="${id}" min="${min}" max="${max}" value="${value}" step="${step}">
      </div>
  `;
}

function addCheckBox(id,label,value) {
const transLabel=getText(label);
const checkedAttribute=value ? 'checked' : '';
return `
<div class="pen-input-2group">
<label for="${id}" data-i18n="${label}">${transLabel}</label>
<input type="checkbox" id="${id}" ${checkedAttribute}>
</div>
  `;
}


function addAlignTypeButton(prefixId) {
return `
  <div class="input-group-multi" data-group="t2Align">
    <button id="T2-align-left" data-value="start" class="selected" onclick="changeSelected(this)">
        <i class="material-icons">format_align_left</i>
    </button>
    <button id="T2-align-center" data-value="middle" onclick="changeSelected(this)">
        <i class="material-icons">format_align_center</i>
    </button>
    <button id="T2-align-right" data-value="end" onclick="changeSelected(this)">
        <i class="material-icons">format_align_right</i>
    </button>
  </div>`;
}

function addOrientationButton(prefixId) {
return `<div class="input-group-multi" data-group="orientation_group">
    <button id="T2-Orientation-horizontal" data-value="horizontal" class="selected" onclick="changeSelected(this)">
      <i class="material-icons">east</i>
    </button>
    <button id="T2-Orientation-vertical" data-value="vertical" onclick="changeSelected(this)">
      <i class="material-icons">south</i>
    </button>
  </div>`;
}

function addOneSelectBox(id) {
return `
      <div class="input-group_one">
        <select id="${id}">
        </select>
      </div>
  `;
}

function addDropDownBySpeedLine(id,label) {

var i18nHorizontal=getText("horizontal");
var i18nVertical=getText("vertical");
var i18nCross=getText("cross");
var i18nLabel=getText(label);

return `
      <div class="input-2group">
      <label for="speed-line-style" data-i18n="${label}">${i18nLabel}</label>
      <select id="${id}">
          <option data-i18n="horizontal" value="horizontal">${i18nHorizontal}</option>
          <option data-i18n="vertical"   value="vertical">${i18nVertical}</option>
          <option data-i18n="cross"      value="cross">${i18nCross}</option>
      </select>
      </div>`;
}

function addDropDownByStyle(id,label) {

var i18nSolid=getText("solid");
var i18nDashed=getText("dashed");
var i18nDotted=getText("dotted");
var i18nLineStyle=getText("line-style");

return `
      <div class="input-2group">
      <label for="line-style" data-i18n="${label}">${i18nLineStyle}</label>
      <select id="${id}">
          <option data-i18n="solid" value="solid">${i18nSolid}</option>
          <option data-i18n="dashed" value="dashed">${i18nDashed}</option>
          <option data-i18n="dotted" value="dotted">${i18nDotted}</option>
      </select>
      </div>`;
}

function addDropDownByDot(id,label) {

var i18nCircle=getText("circle");
var i18nSquare=getText("square");
var i18nTriangle=getText("triangle");
var i18nStar=getText("star");
var i18nCross=getText("cross");
var i18nHeart=getText("heart");
var i18nLabel=getText(label);

return `
        <div class="control-group">
            <label data-i18n="${label}" for="dotShape">${i18nLabel}</label>
            <select id="${id}">
                <option data-i18n="circle" value="circle">${i18nCircle}</option>
                <option data-i18n="square" value="square">${i18nSquare}</option>
                <option data-i18n="triangle" value="triangle">${i18nTriangle}</option>
                <option data-i18n="star" value="star">${i18nStar}</option>
                <option data-i18n="cross" value="cross">${i18nCross}</option>
                <option data-i18n="heart" value="heart">${i18nHeart}</option>
            </select>
        </div>`;
}



function addDropDownByGrad(id,label) {
var i18nTb=getText("top-bottom");
var i18nBt=getText("bottom-top");
var i18nLr=getText("left-right");
var i18nRl=getText("right-left");

return `
        <div class="control-group">
            <label data-i18n="${label}" for="gradientDirection"></label>
            <select id="${id}">
                <option data-i18n="top-bottom" value="top-bottom">${i18nTb}</option>
                <option data-i18n="bottom-top" value="bottom-top">${i18nBt}</option>
                <option data-i18n="left-right" value="left-right">${i18nLr}</option>
                <option data-i18n="right-left" value="right-left">${i18nRl}</option>
            </select>
        </div>`;
}



function addTextArea(id,label) {
const transLavel=getText(label);
if(transLavel){
return `
    <div class="input-group_one">
        <textarea id="${id}" rows="4">${transLavel}</textarea>
    </div>
`;
}else{
return `
    <div class="input-group_one">
        <textarea id="${id}" rows="4">New Text</textarea>
    </div>
`;
}
}
