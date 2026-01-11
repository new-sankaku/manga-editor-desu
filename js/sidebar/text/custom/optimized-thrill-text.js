let t2_thrill_textSvg,t2_thrill_defs,t2_thrill_filter,t2_thrill_mainText,nowT2ThrillStr=null;
function t2_thrill_deleteSvg(){
[t2_thrill_textSvg,t2_thrill_defs,t2_thrill_filter,t2_thrill_mainText,nowT2ThrillStr]=[null,null,null,null,null];
}
function t2_thrill_createSvg(left=50,top=100){
t2_thrill_textSvg=createSvgElement("svg");
setAttributes(t2_thrill_textSvg,{
"id":"t2_thrill_textSvg","xmlns":svgHttp,"xml:space":"preserve"
});
Object.assign(t2_thrill_textSvg.style,{position:'absolute',visibility:'visible'});
t2_thrill_defs=createSvgElement("defs");
t2_thrill_filter=createSvgElement("filter");
setAttributes(t2_thrill_filter,{
"id":"thrillFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox","primitiveUnits":"userSpaceOnUse",
"color-interpolation-filters":"linearRGB"
});
const filterElements=[
{type:"feTurbulence",attrs:{type:"fractalNoise",baseFrequency:"0 0.075",numOctaves:"1",
seed:"2",stitchTiles:"stitch",result:"turbulence1"}},
{type:"feColorMatrix",attrs:{type:"saturate",values:"5",in:"turbulence1",result:"colormatrix4"}},
{type:"feDisplacementMap",attrs:{in:"SourceGraphic",in2:"colormatrix4",scale:"10",
xChannelSelector:"R",yChannelSelector:"A",result:"displacementMap2"}}
];
filterElements.forEach(({type,attrs})=>t2_thrill_filter.appendChild(createFilterElement(type,attrs)));
t2_thrill_defs.appendChild(t2_thrill_filter);
t2_thrill_textSvg.appendChild(t2_thrill_defs);
t2_thrill_mainText=createSvgElement("text");
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAlign=getSelectedValueByGroup("t2Align");
const textAttrs=isVertical?{
"writing-mode":"vertical-rl",
"dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0",
"text-orientation":"upright",
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"filter":"url(#thrillFilter)",
"xml:space":"preserve"
}:{
"dominant-baseline":"middle",
"text-anchor":textAlign,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"filter":"url(#thrillFilter)",
"xml:space":"preserve"
};
setAttributes(t2_thrill_mainText,textAttrs);
t2_thrill_textSvg.appendChild(t2_thrill_mainText);
document.body.appendChild(t2_thrill_textSvg);
t2_thrill_updateText();
document.body.removeChild(t2_thrill_textSvg);
t2_thrill_addSvg(left,top);
}
function t2_thrill_updateText(){
const lines=t2_text.value.split("\n");
t2_thrill_mainText.innerHTML="";
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
t2_thrill_mainText.setAttribute("style",styleStr);
let totalHeight=0;
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
});
t2_thrill_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_thrill_updateStyles();
}
function t2_thrill_updateStyles(){
const styles={
"font-size":`${t2_fontSize.value}px`,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`
};
Object.assign(t2_thrill_mainText.style,styles);
t2_thrill_updateSvgSize();
}
function t2_thrill_updateSvgSize(){
try{
const bbox=t2_thrill_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};

setAttributes(t2_thrill_textSvg,dims);
}catch(error){}
}
function t2_thrill_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_thrill_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2ThrillStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_thrill_updateAll(){
const position=nowT2ThrillStr?
{left:nowT2ThrillStr.left,top:nowT2ThrillStr.top}:{left:50,top:100};
if(nowT2ThrillStr){
canvas.remove(nowT2ThrillStr).renderAll();
nowT2ThrillStr=null;
}
t2_thrill_deleteSvg();
t2_thrill_createSvg(position.left,position.top);
}