let t2_zebra_textSvg,t2_zebra_defs,t2_zebra_filter,t2_zebra_mainText,nowT2ZebraStr=null;
function t2_zebra_deleteSvg(){
[t2_zebra_textSvg,t2_zebra_defs,t2_zebra_filter,t2_zebra_mainText,nowT2ZebraStr]=[null,null,null,null,null];
}
function t2_zebra_createSvg(left=50,top=100){
t2_zebra_textSvg=createSvgElement("svg");
setAttributes(t2_zebra_textSvg,{
"id":"t2_zebra_textSvg","xmlns":svgHttp,"xml:space":"preserve"
});
Object.assign(t2_zebra_textSvg.style,{position:'absolute',visibility:'visible'});
t2_zebra_defs=createSvgElement("defs");
t2_zebra_filter=createSvgElement("filter");
setAttributes(t2_zebra_filter,{
"id":"zebraFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox","primitiveUnits":"userSpaceOnUse",
"color-interpolation-filters":"linearRGB"
});
const filterElements=[
{type:"feTurbulence",attrs:{type:"turbulence",baseFrequency:"0.03 0.01",numOctaves:"2",
seed:"4",stitchTiles:"stitch",result:"turbulence"}},
{type:"feColorMatrix",attrs:{type:"matrix",values:"1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 500 -100",
in:"turbulence",result:"colormatrix"}},
{type:"feFlood",attrs:{"flood-color":t2_fillColor.value,"flood-opacity":t2_fillOpacity.value,result:"flood"}},
{type:"feComposite",attrs:{in:"flood",in2:"colormatrix",operator:"in",result:"composite"}},
{type:"feComposite",attrs:{in:"composite",in2:"SourceAlpha",operator:"in",result:"composite1"}}
];
filterElements.forEach(({type,attrs})=>t2_zebra_filter.appendChild(createFilterElement(type,attrs)));
t2_zebra_defs.appendChild(t2_zebra_filter);
t2_zebra_textSvg.appendChild(t2_zebra_defs);
t2_zebra_mainText=createSvgElement("text");
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAlign=getSelectedValueByGroup("t2Align");
const textAttrs=isVertical?{
"writing-mode":"vertical-rl",
"dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0",
"text-orientation":"upright",
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"filter":"url(#zebraFilter)",
"xml:space":"preserve"
}:{
"dominant-baseline":"middle",
"text-anchor":textAlign,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"filter":"url(#zebraFilter)",
"xml:space":"preserve"
};
setAttributes(t2_zebra_mainText,textAttrs);
t2_zebra_textSvg.appendChild(t2_zebra_mainText);
document.body.appendChild(t2_zebra_textSvg);
t2_zebra_updateText();
document.body.removeChild(t2_zebra_textSvg);
t2_zebra_addSvg(left,top);
}
function t2_zebra_updateText(){
const lines=t2_text.value.split("\n");
t2_zebra_mainText.innerHTML="";
const fontSize=parseFloat(t2_fontSize.value);
const lineHeight=parseFloat(t2_lineHeight.value);
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
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
t2_zebra_mainText.setAttribute("style",styleStr);
let totalHeight=0;
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
});
t2_zebra_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_zebra_updateStyles();
}
function t2_zebra_updateStyles(){
const styles={
"font-size":`${t2_fontSize.value}px`,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`
};
Object.assign(t2_zebra_mainText.style,styles);
const floodElement=t2_zebra_filter.querySelector("feFlood");
if(floodElement){
floodElement.setAttribute("flood-color",t2_fillColor.value);
floodElement.setAttribute("flood-opacity",t2_fillOpacity.value);
}
t2_zebra_updateSvgSize();
}
function t2_zebra_updateSvgSize(){
try{
const bbox=t2_zebra_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};

setAttributes(t2_zebra_textSvg,dims);
}catch(error){}
}
function t2_zebra_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_zebra_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2ZebraStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_zebra_updateAll(){
const position=nowT2ZebraStr?
{left:nowT2ZebraStr.left,top:nowT2ZebraStr.top}:{left:50,top:100};
if(nowT2ZebraStr){
canvas.remove(nowT2ZebraStr).renderAll();
nowT2ZebraStr=null;
}
t2_zebra_deleteSvg();
t2_zebra_createSvg(position.left,position.top);
}