
let t2_wild_textSvg,t2_wild_defs,t2_wild_filter,t2_wild_mainText,nowT2WildStr=null;
function t2_wild_deleteSvg(){
[t2_wild_textSvg,t2_wild_defs,t2_wild_filter,t2_wild_mainText,nowT2WildStr]=[null,null,null,null,null];
}
function t2_wild_createSvg(left=50,top=100){
t2_wild_textSvg=createSvgElement("svg");
setAttributes(t2_wild_textSvg,{
"id":"t2_wild_textSvg","xmlns":svgHttp,"xml:space":"preserve"
});
Object.assign(t2_wild_textSvg.style,{position:'absolute',visibility:'visible'});
t2_wild_defs=createSvgElement("defs");
t2_wild_filter=createSvgElement("filter");
setAttributes(t2_wild_filter,{
"id":"t2_wild_wildFilter","x":"-20%","y":"-20%","width":"140%","height":"140%",
"filterUnits":"objectBoundingBox"
});
const filterElements=[
{type:"feMorphology",attrs:{operator:"dilate",radius:"4",in:"SourceAlpha",result:"morphology"}},
{type:"feFlood",attrs:{"flood-color":"black","flood-opacity":"1",result:"flood"}},
{type:"feComposite",attrs:{in:"flood",in2:"morphology",operator:"in",result:"composite"}},
{type:"feComposite",attrs:{in:"composite",in2:"SourceAlpha",operator:"out",result:"composite1"}},
{type:"feTurbulence",attrs:{type:"fractalNoise",baseFrequency:"0.01 0.02",numOctaves:"1",
seed:"0",stitchTiles:"stitch",result:"turbulence"}},
{type:"feDisplacementMap",attrs:{in:"composite1",in2:"turbulence",scale:"17",
xChannelSelector:"A",yChannelSelector:"A",result:"displacementMap"}},
{type:"feMerge",attrs:{result:"merge"},children:[
{type:"feMergeNode",attrs:{in:"SourceGraphic",result:"mergeNode"}},
{type:"feMergeNode",attrs:{in:"displacementMap",result:"mergeNode1"}}
]}
];
filterElements.forEach(({type,attrs,children=[]})=>
t2_wild_filter.appendChild(createFilterElement(type,attrs,children)));
t2_wild_defs.appendChild(t2_wild_filter);
t2_wild_textSvg.appendChild(t2_wild_defs);
t2_wild_mainText=createSvgElement("text");
setAttributes(t2_wild_mainText,{
"id":"t2_wild_mainText","filter":"url(#t2_wild_wildFilter)","xml:space":"preserve"
});
t2_wild_textSvg.appendChild(t2_wild_mainText);
document.body.appendChild(t2_wild_textSvg);
t2_wild_updateText();
document.body.removeChild(t2_wild_textSvg);
t2_wild_addSvg(left,top);
}
function t2_wild_updateText(){
const lines=t2_text.value.split("\n");
t2_wild_mainText.innerHTML="";
const fontSize=parseFloat(t2_fontSize.value);
const lineHeight=parseFloat(t2_lineHeight.value);
let totalHeight=0;
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAttrs=isVertical?{
"writing-mode":"vertical-rl","dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0","text-orientation":"upright"
}:{
"dominant-baseline":"middle","text-anchor":getSelectedValueByGroup("t2Align")
};
setAttributes(t2_wild_mainText,textAttrs);
const baseStyles={
"font-family":baseStylesDefault
};
const verticalStyles={
"font-size":`${fontSize}px`,"fill":t2_fillColor.value,"fill-opacity":t2_fillOpacity.value,
"letter-spacing":`${t2_letterSpacing.value}em`,"writing-mode":"vertical-rl",
"text-orientation":"upright","glyph-orientation-vertical":"0","dominant-baseline":"ideographic"
};
t2_wild_mainText.setAttribute("style",
isVertical?Object.entries({...baseStyles,...verticalStyles}).map(([k,v])=>`${k}:${v}`).join(";"):
Object.entries(baseStyles).map(([k,v])=>`${k}:${v}`).join(";"));
lines.forEach((line,index)=>{
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,isVertical?
{"y":"0","x":`${-totalHeight}px`}:
{"x":"0","dy":index===0?"0":`${lineHeight}em`});
t2_wild_mainText.appendChild(tspan);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_wild_updateStyles();
}
function t2_wild_updateStyles(){
Object.assign(t2_wild_mainText.style,{
fontSize:`${t2_fontSize.value}px`,fill:t2_fillColor.value,
fillOpacity:t2_fillOpacity.value,letterSpacing:`${t2_letterSpacing.value}em`
});
t2_wild_updateSvgSize();
}
function t2_wild_updateSvgSize(){
try{
const bbox=t2_wild_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};
setAttributes(t2_wild_textSvg,dims);
}catch(error){}
}
function t2_wild_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_wild_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2WildStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_wild_updateAll(){
const position=nowT2WildStr?
{left:nowT2WildStr.left,top:nowT2WildStr.top}:{left:50,top:100};
if(nowT2WildStr){
canvas.remove(nowT2WildStr).renderAll();
nowT2WildStr=null;
}
t2_wild_deleteSvg();
t2_wild_createSvg(position.left,position.top);
}