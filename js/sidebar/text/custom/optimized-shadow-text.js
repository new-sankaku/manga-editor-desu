let t2_shadow_textSvg,t2_shadow_defs,t2_shadow_filter,t2_shadow_primaryShadowFlood,
t2_shadow_secondaryShadowFlood,t2_shadow_mainText,nowT2ShadowStr=null;

function t2_shadow_deleteSvg(){
[t2_shadow_textSvg,t2_shadow_defs,t2_shadow_filter,t2_shadow_primaryShadowFlood,
t2_shadow_secondaryShadowFlood,t2_shadow_mainText,nowT2ShadowStr]=[null,null,null,null,null,null,null];
}
function t2_shadow_createSvg(left=50,top=100){
t2_shadow_textSvg=createSvgElement("svg");
setAttributes(t2_shadow_textSvg,{
"id":"t2_shadow_textSvg","width":"600","height":"300","xmlns":svgHttp,
"xml:space":"preserve"
});
Object.assign(t2_shadow_textSvg.style,{position:'absolute',visibility:'visible'});
t2_shadow_defs=createSvgElement("defs");
t2_shadow_filter=createSvgElement("filter");
setAttributes(t2_shadow_filter,{
"id":"t2_shadow_dualShadow","x":"-50%","y":"-50%","width":"200%","height":"200%"
});
const primaryOffsets=[1,2,3].map(i=>({
type:"feOffset",attrs:{in:"expand",dx:i,dy:i,result:`primaryShadow_${i}`}
}));
const secondaryOffsets=[1,2,3,4,5].map(i=>({
type:"feOffset",attrs:{in:"secondaryShadowBase",dx:i,dy:i,result:`secondaryShadow_${i}`}
}));
const filterElements=[
{type:"feMorphology",attrs:{in:"SourceAlpha",operator:"dilate",radius:"2",result:"expand"}},
...primaryOffsets,
{type:"feMerge",attrs:{result:"primaryShadow"},
children:[{type:"feMergeNode",attrs:{in:"expand"}},
...primaryOffsets.map((_,i)=>({type:"feMergeNode",attrs:{in:`primaryShadow_${i+1}`}}))]},
{type:"feFlood",attrs:{id:"t2_shadow_primaryShadowFlood","flood-color":"#ebe7e0"}},
{type:"feComposite",attrs:{in2:"primaryShadow",operator:"in",result:"primaryShadow"}},
{type:"feMorphology",attrs:{in:"primaryShadow",operator:"dilate",radius:"1",
result:"secondaryShadowBase"}},
...secondaryOffsets,
{type:"feMerge",attrs:{result:"secondaryShadow"},
children:[{type:"feMergeNode",attrs:{in:"secondaryShadowBase"}},
...secondaryOffsets.map((_,i)=>({type:"feMergeNode",attrs:{in:`secondaryShadow_${i+1}`}}))]},
{type:"feFlood",attrs:{id:"t2_shadow_secondaryShadowFlood","flood-color":"#35322a"}},
{type:"feComposite",attrs:{in2:"secondaryShadow",operator:"in",result:"secondaryShadow"}},
{type:"feMerge",attrs:{},children:[
{type:"feMergeNode",attrs:{in:"secondaryShadow"}},
{type:"feMergeNode",attrs:{in:"primaryShadow"}},
{type:"feMergeNode",attrs:{in:"SourceGraphic"}}
]}
].forEach(({type,attrs,children=[]})=>{
const element=createFilterElement(type,attrs,children);
if(type==="feFlood"){
if(attrs.id.includes("primary"))t2_shadow_primaryShadowFlood=element;
else t2_shadow_secondaryShadowFlood=element;
}
t2_shadow_filter.appendChild(element);
});
t2_shadow_defs.appendChild(t2_shadow_filter);
t2_shadow_textSvg.appendChild(t2_shadow_defs);
t2_shadow_mainText=createSvgElement("text");
setAttributes(t2_shadow_mainText,{
"id":"t2_shadow_mainText","filter":"url(#t2_shadow_dualShadow)","xml:space":"preserve"
});
t2_shadow_textSvg.appendChild(t2_shadow_mainText);
document.body.appendChild(t2_shadow_textSvg);
t2_shadow_updateText();
document.body.removeChild(t2_shadow_textSvg);
t2_shadow_addSvg(left,top);
}
function t2_shadow_updateText(){
const lines=t2_text.value.split("\n");
t2_shadow_mainText.innerHTML="";
const fontSize=parseFloat(t2_fontSize.value);
const lineHeight=parseFloat(t2_lineHeight.value);
let totalHeight=0;
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAttrs=isVertical?{
"writing-mode":"vertical-rl","dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0","text-orientation":"upright"
}:{
"dominant-baseline":"hanging","text-anchor":getSelectedValueByGroup("t2Align")
};
setAttributes(t2_shadow_mainText,textAttrs);
const baseStyles={
"font-family": baseStylesDefault
};

// console.log("baseStyles", JSON.stringify(baseStyles));
const verticalStyles={
"font-size":`${fontSize}px`,"fill":t2_fillColor.value,"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`,"writing-mode":"vertical-rl",
"text-orientation":"upright","glyph-orientation-vertical":"0","dominant-baseline":"ideographic"
};
t2_shadow_mainText.setAttribute("style",
isVertical?Object.entries({...baseStyles,...verticalStyles}).map(([k,v])=>`${k}:${v}`).join(";"):
Object.entries(baseStyles).map(([k,v])=>`${k}:${v}`).join(";"));
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,isVertical?
{"y":"0","x":`${-totalHeight}px`}:
{"x":"0","dy":index===0?"0":`${lineHeight}em`});
t2_shadow_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_shadow_updateStyles();
}
function t2_shadow_updateStyles(){
Object.assign(t2_shadow_mainText.style,{
fontSize:`${t2_fontSize.value}px`,fill:t2_fillColor.value,
fillOpacity:t2_fillOpacity.value,letterSpacing:`${t2_letterSpacing.value}em`
});
if(t2_shadow_primaryShadowFlood){
// console.log("t2_shadow1Opacity.value", t2_shadow1Opacity);
// console.log("t2_shadow1Color.value  ", t2_shadow1Color);

setAttributes(t2_shadow_primaryShadowFlood,{"flood-opacity":t2_shadow1Opacity.value,"flood-color":t2_shadow1Color.value});
}
if(t2_shadow_secondaryShadowFlood){
setAttributes(t2_shadow_secondaryShadowFlood,{
"flood-opacity":t2_shadow2Opacity.value,"flood-color":t2_shadow2Color.value
});
}
const filter=document.querySelector("#t2_shadow_dualShadow");
if(filter){
filter.querySelectorAll('feOffset[result^="primaryShadow_"]').forEach((offset,index)=>{
const value=Math.min(index+1,parseFloat(t2_shadow1Size.value)||1);
setAttributes(offset,{dx:value,dy:value});
});
filter.querySelectorAll('feOffset[result^="secondaryShadow_"]').forEach((offset,index)=>{
const value=Math.min(index+1,parseFloat(t2_shadow2Size.value)||1);
setAttributes(offset,{dx:value,dy:value});
});
}
t2_shadow_updateSvgSize();
}
function t2_shadow_updateSvgSize(){
try{
const bbox=t2_shadow_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};
setAttributes(t2_shadow_textSvg,dims);
}catch(error){}
}
function t2_shadow_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_shadow_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2ShadowStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_shadow_updateAll(){
const position=nowT2ShadowStr?
{left:nowT2ShadowStr.left,top:nowT2ShadowStr.top}:{left:50,top:100};
if(nowT2ShadowStr){
canvas.remove(nowT2ShadowStr).renderAll();
nowT2ShadowStr=null;
}
t2_shadow_deleteSvg();
t2_shadow_createSvg(position.left,position.top);
}