let t2_scratch_textSvg,t2_scratch_defs,t2_scratch_filter,t2_scratch_mainText,nowT2ScratchStr=null;
function t2_scratch_deleteSvg(){
[t2_scratch_textSvg,t2_scratch_defs,t2_scratch_filter,t2_scratch_mainText,nowT2ScratchStr]=[null,null,null,null,null];
}
function t2_scratch_createSvg(left=50,top=100){
t2_scratch_textSvg=createSvgElement("svg");
setAttributes(t2_scratch_textSvg,{
"id":"t2_scratch_textSvg","width":"10","height":"10","xmlns":svgHttp,
"xml:space":"preserve"
});
Object.assign(t2_scratch_textSvg.style,{position:'absolute',visibility:'visible'});
t2_scratch_defs=createSvgElement("defs");
t2_scratch_filter=createSvgElement("filter");
setAttributes(t2_scratch_filter,{
"id":"t2_scratch_scratchFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox","primitiveUnits":"userSpaceOnUse",
"color-interpolation-filters":"linearRGB"
});
const filterElements=[
{type:"feTurbulence",attrs:{type:"turbulence",baseFrequency:"0.001 0.065",numOctaves:"1",
seed:"1",stitchTiles:"stitch",result:"turbulence"}},
{type:"feColorMatrix",attrs:{type:"matrix",values:"1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 80 -5",
in:"turbulence",result:"colormatrix"}},
{type:"feFlood",attrs:{"flood-color":t2_fillColor.value,"flood-opacity":t2_fillOpacity.value,result:"flood"}},
{type:"feComposite",attrs:{in:"flood",in2:"colormatrix",operator:"in",result:"composite2"}},
{type:"feComposite",attrs:{in:"composite2",in2:"SourceAlpha",operator:"in",result:"composite3"}}
];
filterElements.forEach(({type,attrs})=>t2_scratch_filter.appendChild(createFilterElement(type,attrs)));
t2_scratch_defs.appendChild(t2_scratch_filter);
t2_scratch_textSvg.appendChild(t2_scratch_defs);
t2_scratch_mainText=createSvgElement("text");
setAttributes(t2_scratch_mainText,{
"id":"t2_scratch_mainText",
"filter":"url(#t2_scratch_scratchFilter)",
"xml:space":"preserve",
"fill":t2_fillColor.value
});
t2_scratch_textSvg.appendChild(t2_scratch_mainText);
document.body.appendChild(t2_scratch_textSvg);
t2_scratch_updateText();
document.body.removeChild(t2_scratch_textSvg);
t2_scratch_addSvg(left,top);
}
function t2_scratch_updateText(){
const lines=t2_text.value.split("\n");
t2_scratch_mainText.innerHTML="";
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
setAttributes(t2_scratch_mainText,textAttrs);
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
t2_scratch_mainText.setAttribute("style",styleStr);
let totalHeight=0;
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
});
t2_scratch_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_scratch_updateStyles();
}
function t2_scratch_updateStyles(){
const styles={
"font-size":`${t2_fontSize.value}px`,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`
};
Object.assign(t2_scratch_mainText.style,styles);
// フィルターの更新
const floodElement=t2_scratch_filter.querySelector("feFlood");
if(floodElement){
floodElement.setAttribute("flood-color",t2_fillColor.value);
floodElement.setAttribute("flood-opacity",t2_fillOpacity.value);
}
t2_scratch_updateSvgSize();
}
function t2_scratch_updateSvgSize(){
try{
const bbox=t2_scratch_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};

setAttributes(t2_scratch_textSvg,dims);
}catch(error){}
}
function t2_scratch_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_scratch_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2ScratchStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_scratch_updateAll(){
const position=nowT2ScratchStr?
{left:nowT2ScratchStr.left,top:nowT2ScratchStr.top}:{left:50,top:100};
if(nowT2ScratchStr){
canvas.remove(nowT2ScratchStr).renderAll();
nowT2ScratchStr=null;
}
t2_scratch_deleteSvg();
t2_scratch_createSvg(position.left,position.top);
}