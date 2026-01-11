let t2_broken_textSvg,t2_broken_defs,t2_broken_filter,t2_broken_mainText,nowT2BrokenStr=null;
function t2_broken_deleteSvg(){
[t2_broken_textSvg,t2_broken_defs,t2_broken_filter,t2_broken_mainText,nowT2BrokenStr]=[null,null,null,null,null];
}
function t2_broken_createSvg(left=50,top=100){
t2_broken_textSvg=createSvgElement("svg");
setAttributes(t2_broken_textSvg,{
"id":"t2_broken_textSvg","width":"10","height":"10","xmlns":svgHttp,
"xml:space":"preserve"
});
Object.assign(t2_broken_textSvg.style,{position:'absolute',visibility:'visible'});
t2_broken_defs=createSvgElement("defs");
t2_broken_filter=createSvgElement("filter");
setAttributes(t2_broken_filter,{
"id":"brokenFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox"
});
const filterElements=[
{type:"feTurbulence",attrs:{type:"turbulence",baseFrequency:"0.002 0.008",numOctaves:"2",
seed:"2",stitchTiles:"stitch",result:"turbulence"}},
{type:"feColorMatrix",attrs:{type:"saturate",values:"30",in:"turbulence",result:"colormatrix"}},
{type:"feColorMatrix",attrs:{type:"matrix",values:"1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 150 -15",
in:"colormatrix",result:"colormatrix1"}},
{type:"feComposite",attrs:{in:"SourceGraphic",in2:"colormatrix1",operator:"in",result:"composite"}},
{type:"feDisplacementMap",attrs:{in:"SourceGraphic",in2:"colormatrix1",scale:"15",
xChannelSelector:"R",yChannelSelector:"A",result:"displacementMap"}}
];
filterElements.forEach(({type,attrs})=>t2_broken_filter.appendChild(createFilterElement(type,attrs)));
t2_broken_defs.appendChild(t2_broken_filter);
t2_broken_textSvg.appendChild(t2_broken_defs);
t2_broken_mainText=createSvgElement("text");
setAttributes(t2_broken_mainText,{
"id":"t2_broken_mainText",
"filter":"url(#brokenFilter)",
"xml:space":"preserve",
"fill":t2_fillColor.value
});
t2_broken_textSvg.appendChild(t2_broken_mainText);
document.body.appendChild(t2_broken_textSvg);
t2_broken_updateText();
document.body.removeChild(t2_broken_textSvg);
t2_broken_addSvg(left,top);
}
function t2_broken_updateText(){
const lines=t2_text.value.split("\n");
t2_broken_mainText.innerHTML="";
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
setAttributes(t2_broken_mainText,textAttrs);
const baseStyles={
"font-family": baseStylesDefault,
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
t2_broken_mainText.setAttribute("style",styleStr);
let totalHeight=0;
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value
});
t2_broken_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_broken_updateStyles();
}
function t2_broken_updateStyles(){
const styles={
"font-size":`${t2_fontSize.value}px`,
"fill":t2_fillColor.value,
"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`
};
Object.assign(t2_broken_mainText.style,styles);
t2_broken_updateSvgSize();
}
function t2_broken_updateSvgSize(){
try{
const bbox=t2_broken_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};
setAttributes(t2_broken_textSvg,dims);
}catch(error){}
}
function t2_broken_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_broken_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2BrokenStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_broken_updateAll(){
const position=nowT2BrokenStr?
{left:nowT2BrokenStr.left,top:nowT2BrokenStr.top}:{left:50,top:100};
if(nowT2BrokenStr){
canvas.remove(nowT2BrokenStr).renderAll();
nowT2BrokenStr=null;
}
t2_broken_deleteSvg();
t2_broken_createSvg(position.left,position.top);
}