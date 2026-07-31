let svgHttp="http://www.w3.org/2000/svg";
const baseStylesDefault="";

function createSvgElement(type) {
return document.createElementNS(svgHttp,type);
}
function setAttributes(element,attrs) {
Object.entries(attrs).forEach(([key,value])=>
element.setAttribute(key,value)
);
}

function createFilterOneElement(type,attrs,child=null){
const element=createSvgElement(type);
setAttributes(element,attrs);
if(child){
const childElement=createSvgElement(child.type);
setAttributes(childElement,child.attrs);
element.appendChild(childElement);
}
return element;
}
function createFilterElement(type,attrs,children=[]) {
const element=createSvgElement(type);
setAttributes(element,attrs);
children.forEach((child)=>{
const childElement=createSvgElement(child.type);
setAttributes(childElement,child.attrs);
element.appendChild(childElement);
});
return element;
}


function createMergeNode(inValue) {
const node=createSvgElement("feMergeNode");
setAttributes(node,{in: inValue});
return node;
}

function getFirstNCharsDefault(textarea) {
return getFirstNChars(textarea,20);
}

//画像テキストの更新は削除+再追加で行われるため、途中状態を履歴に残さず最終結果のみ1エントリ保存する
function t2_removeSvgImage(obj){
removeByNotSave(obj);
canvas.renderAll();
}

function t2_addSvgImage(svgNode,left,top,onCreated){
const svgString=new XMLSerializer().serializeToString(svgNode);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
img.text=getFirstNCharsDefault(t2_text);
onCreated(img);
changeDoNotSaveHistory();
canvas.add(img).setActiveObject(img).renderAll();
changeDoSaveHistory();
saveStateByManual();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}

function getFirstNChars(textarea,maxChars) {
if (!textarea.value) return '';
return textarea.value.replace(/\n/g,' ').slice(0,maxChars);
}