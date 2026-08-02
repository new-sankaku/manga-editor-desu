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
// 画像テキストはパラメータ変更のたびにオブジェクトを作り直すため、
// 変形・重ね順・GUIDを引き継がないと毎回最前面へ飛び拡大率も失われる
var t2PendingTransform=null;

function t2BeginReplace(oldObject){
if(!oldObject){
t2PendingTransform=null;
return {left:50,top:100};
}
var objects=canvas.getObjects();
t2PendingTransform={
left:oldObject.left,
top:oldObject.top,
scaleX:oldObject.scaleX,
scaleY:oldObject.scaleY,
angle:oldObject.angle,
flipX:oldObject.flipX,
flipY:oldObject.flipY,
opacity:oldObject.opacity,
guid:oldObject.guid,
index:objects.indexOf(oldObject)
};
withoutHistory(function(){
canvas.remove(oldObject);
});
canvas.renderAll();
return {left:t2PendingTransform.left,top:t2PendingTransform.top};
}

function t2PlaceImageTextObject(img,type,left,top){
var transform=t2PendingTransform;
t2PendingTransform=null;
img.set({left:left,top:top});
if(transform){
img.set({
left:transform.left,
top:transform.top,
scaleX:transform.scaleX,
scaleY:transform.scaleY,
angle:transform.angle,
flipX:transform.flipX,
flipY:transform.flipY,
opacity:transform.opacity
});
if(transform.guid){
img.guid=transform.guid;
}
}
img.imageTextType=type;
img.imageTextParams=t2CollectParams(type);
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img);
if(transform&&transform.index>=0){
// 作り直すたびに最前面へ移動しないよう元の重ね順に戻す
img.moveTo(transform.index);
}
canvas.setActiveObject(img);
canvas.renderAll();
return img;
}

// サイドバーの入力値をオブジェクトに持たせて、あとから選び直しても編集できるようにする。
// 集める先はDOMの入力要素。sidebarValueMapは「利用者が触った項目」しか持たないため、
// そちらから集めると未変更の項目が欠け、別の画像テキストを選び直したときに
// 前のオブジェクトの値が画面に残る
function t2CollectParams(type){
var params={};
var host=$('text-area2-settings');
if(!host){
return params;
}
// setupSlider()が足す値表示のspanも同じ接頭辞のidを持つため、入力要素だけを見る
host.querySelectorAll('input[id],select[id],textarea[id]').forEach(function(element){
if(element.id.indexOf(type+'-')===0){
params[element.id]=element.value;
}
});
return params;
}
