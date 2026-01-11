let t2_layered_textSvg,nowT2LayeredStr=null;
function t2_layered_deleteSvg(){
[t2_layered_textSvg,nowT2LayeredStr]=[null,null];
}
function t2_layered_createSvg(left=50,top=100){
t2_layered_textSvg=createSvgElement("svg");
setAttributes(t2_layered_textSvg,{
"id":"t2_layered_textSvg","xmlns":svgHttp,
"xml:space":"preserve"
});
Object.assign(t2_layered_textSvg.style,{position:'absolute',visibility:'visible'});
const layers=[
{fill:"hsl(40,100%,50%)",translate:[0,0]},
{fill:"hsl(5,100%,50%)",translate:[10,0]},
{fill:"hsl(165,100%,50%)",translate:[-10,0]},
{fill:"hsl(220,100%,50%)",translate:[0,5]}
];
const lines=t2_text.value.split("\n");
const fontSize=parseFloat(t2_fontSize.value);
const lineHeight=parseFloat(t2_lineHeight.value);
const isVertical=getSelectedValueByGroup("orientation_group")==="vertical";
const textAlign=getSelectedValueByGroup("t2Align");
const baseTextAttrs=isVertical?{
"writing-mode":"vertical-rl",
"dominant-baseline":"ideographic",
"glyph-orientation-vertical":"0",
"text-orientation":"upright",
"fill-opacity":t2_fillOpacity.value
}:{
"dominant-baseline":"middle",
"text-anchor":textAlign,
"fill-opacity":t2_fillOpacity.value
};
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
layers.forEach(({fill,translate:[x,y]})=>{
const textGroup=createSvgElement("g");
if(x||y)textGroup.setAttribute("transform",`translate(${x}, ${y})`);
let totalHeight=0;
lines.forEach((line,index)=>{
const text=createSvgElement("text");
setAttributes(text,baseTextAttrs);
const styleStr=Object.entries(isVertical?{...baseStyles,...verticalStyles}:baseStyles)
.map(([k,v])=>`${k}:${v}`).join(";");
text.setAttribute("style",styleStr);
const tspan=createSvgElement("tspan");
tspan.textContent=line;
setAttributes(tspan,{
...(isVertical?{"y":"0","x":`${-totalHeight}px`}:{"x":"0","dy":index===0?"0":`${lineHeight}em`}),
"fill":fill,
"fill-opacity":t2_fillOpacity.value
});
text.appendChild(tspan);
textGroup.appendChild(text);
if(isVertical)totalHeight+=fontSize*lineHeight;
});
t2_layered_textSvg.appendChild(textGroup);
});
document.body.appendChild(t2_layered_textSvg);
const{x,y,width,height}=t2_layered_textSvg.getBBox();
const dims={
viewBox:`${x} ${y} ${width} ${height}`,
width:width,
height:height
};
setAttributes(t2_layered_textSvg,dims);
document.body.removeChild(t2_layered_textSvg);
t2_layered_addSvg(left,top);
}
function t2_layered_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_layered_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2LayeredStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_layered_updateAll(){
const position=nowT2LayeredStr?
{left:nowT2LayeredStr.left,top:nowT2LayeredStr.top}:{left:50,top:100};
if(nowT2LayeredStr){
canvas.remove(nowT2LayeredStr).renderAll();
nowT2LayeredStr=null;
}
t2_layered_deleteSvg();
t2_layered_createSvg(position.left,position.top);
}