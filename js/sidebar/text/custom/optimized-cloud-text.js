let t2_cloud_textSvg,t2_cloud_defs,t2_cloud_filter,t2_cloud_mainText,nowT2CloudStr=null;
function t2_cloud_deleteSvg(){
[t2_cloud_textSvg,t2_cloud_defs,t2_cloud_filter,t2_cloud_mainText,nowT2CloudStr]=[null,null,null,null,null];
}
function t2_cloud_createSvg(left=50,top=100){
t2_cloud_textSvg=createSvgElement("svg");
setAttributes(t2_cloud_textSvg,{
"id":"t2_cloud_textSvg","xmlns":svgHttp,
"xml:space":"preserve"
});
Object.assign(t2_cloud_textSvg.style,{position:'absolute',visibility:'visible'});
t2_cloud_defs=createSvgElement("defs");
t2_cloud_filter=createSvgElement("filter");
setAttributes(t2_cloud_filter,{
"id":"cloudFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox","primitiveUnits":"userSpaceOnUse",
"color-interpolation-filters":"linearRGB"
});
const filterElements=[
{type:"feTurbulence",attrs:{type:"turbulence",baseFrequency:"0.005",numOctaves:"2",
result:"turbulence"}},
{type:"feFlood",attrs:{"flood-color":t2_fillColor.value,"flood-opacity":t2_fillOpacity.value,result:"flood"}},
{type:"feComposite",attrs:{in:"flood",in2:"turbulence",operator:"in",result:"composite2"}},
{type:"feComposite",attrs:{in:"composite2",in2:"SourceAlpha",operator:"in",result:"composite3"}}
];
filterElements.forEach(({type,attrs})=>t2_cloud_filter.appendChild(createFilterElement(type,attrs)));
t2_cloud_defs.appendChild(t2_cloud_filter);
t2_cloud_textSvg.appendChild(t2_cloud_defs);
t2_cloud_mainText=createSvgElement("text");
setAttributes(t2_cloud_mainText,{
"id":"t2_cloud_mainText",
"filter":"url(#cloudFilter)",
"xml:space":"preserve",
"fill":t2_fillColor.value
});
t2_cloud_textSvg.appendChild(t2_cloud_mainText);
document.body.appendChild(t2_cloud_textSvg);
t2_cloud_updateText();
document.body.removeChild(t2_cloud_textSvg);
t2_cloud_addSvg(left,top);
}
function t2_cloud_updateText(){
const lines=t2_text.value.split("\n");
t2_cloud_mainText.innerHTML="";
const fontSize=parseFloat(t2_fontSize.value);
const lineHeight=parseFloat(t2_lineHeight.value);
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAlign=getSelectedValueByGroup("t2Align");
const textAttrs=isVertical?{
"writing-mode":"vertical-rl",
"dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0",
"text-orientation":"upright",
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
}:{
"dominant-baseline":"middle",
"text-anchor":textAlign,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
};
setAttributes(t2_cloud_mainText,textAttrs);
const baseStyles={
"font-family":baseStylesDefault,
"font-size":`${fontSize}px`,
"letter-spacing":`${t2_letterSpacing.value}em`
};
const verticalStyles={
"writing-mode":"vertical-rl",
"text-orientation":"upright",
"glyph-orientation-vertical":"0",
"dominant-baseline":"ideographic"
};
const styleStr=Object.entries(isVertical?{...baseStyles,...verticalStyles}:baseStyles)
.map(([k,v])=>`${k}:${v}`).join(";");
t2_cloud_mainText.setAttribute("style",styleStr);
let totalHeight=0;
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
});
t2_cloud_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_cloud_updateStyles();
}
function t2_cloud_updateStyles(){
const styles={
"font-size":`${t2_fontSize.value}px`,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`
};
Object.assign(t2_cloud_mainText.style,styles);
const floodElement=t2_cloud_filter.querySelector("feFlood");
if(floodElement){
floodElement.setAttribute("flood-color",t2_fillColor.value);
floodElement.setAttribute("flood-opacity",t2_fillOpacity.value);
}
t2_cloud_updateSvgSize();
}
function t2_cloud_updateSvgSize(){
try{
const bbox=t2_cloud_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};

setAttributes(t2_cloud_textSvg,dims);
}catch(error){}
}
function t2_cloud_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_cloud_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2CloudStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_cloud_updateAll(){
const position=nowT2CloudStr?
{left:nowT2CloudStr.left,top:nowT2CloudStr.top}:{left:50,top:100};
if(nowT2CloudStr){
canvas.remove(nowT2CloudStr).renderAll();
nowT2CloudStr=null;
}
t2_cloud_deleteSvg();
t2_cloud_createSvg(position.left,position.top);
}