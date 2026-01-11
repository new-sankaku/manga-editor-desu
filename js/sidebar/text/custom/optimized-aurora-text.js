let t2_aurora_textSvg,t2_aurora_defs,t2_aurora_mainText,t2_aurora_symbol,t2_aurora_mask,nowT2AuroraStr=null;
function t2_aurora_deleteSvg(){
[t2_aurora_textSvg,t2_aurora_defs,t2_aurora_mainText,t2_aurora_symbol,t2_aurora_mask,nowT2AuroraStr]=
[null,null,null,null,null,null];
}
function createGradient({id,color}){
const radialGradient=createSvgElement("radialGradient");
setAttributes(radialGradient,{
id,gradientUnits:"objectBoundingBox",cx:"50%",cy:"50%",r:"50%"
});
const stops=[
{offset:"0","stop-color":color},
{offset:"90%","stop-color":"black","stop-opacity":"0"}
].forEach(attrs=>{
const stop=createSvgElement("stop");
setAttributes(stop,attrs);
radialGradient.appendChild(stop);
});
return radialGradient;
}
function t2_aurora_createSvg(left=50,top=100){
t2_aurora_textSvg=createSvgElement("svg");
setAttributes(t2_aurora_textSvg,{
"id":"t2_aurora_textSvg","xmlns":svgHttp,"xml:space":"preserve"
});
Object.assign(t2_aurora_textSvg.style,{position:'absolute',visibility:'visible'});
t2_aurora_defs=createSvgElement("defs");
const staticBlur=createFilterElement("filter",{id:"staticBlur"});
staticBlur.appendChild(createFilterElement("feGaussianBlur",{stdDeviation:"3 1"}));
t2_aurora_defs.appendChild(staticBlur);
const gradients=[
{id:"gr-aurora-1",color:"hsl(180,100%,30%)"},{id:"gr-aurora-2",color:"hsl(70,60%,60%)"},
{id:"gr-aurora-3",color:"hsl(300,80%,40%)"},{id:"gr-aurora-4",color:"hsl(20,100%,60%)"},
{id:"gr-aurora-5",color:"hsl(220,80%,40%)"}
].forEach(grad=>t2_aurora_defs.appendChild(createGradient(grad)));
t2_aurora_symbol=createSvgElement("symbol");
setAttributes(t2_aurora_symbol,{id:"text"});
t2_aurora_mainText=createSvgElement("text");
setAttributes(t2_aurora_mainText,{
"x":"50%","y":"50%","dy":".3em","text-anchor":"middle",
"font-family":"'Russo One', Impact","font-size":"160","filter":"url(#staticBlur)"
});
t2_aurora_symbol.appendChild(t2_aurora_mainText);
t2_aurora_defs.appendChild(t2_aurora_symbol);
t2_aurora_mask=createSvgElement("mask");
setAttributes(t2_aurora_mask,{
id:"mask",maskUnits:"userSpaceOnUse",maskContentUnits:"userSpaceOnUse"
});
const maskUse=createSvgElement("use");
setAttributes(maskUse,{href:"#text",fill:"white"});
t2_aurora_mask.appendChild(maskUse);
t2_aurora_defs.appendChild(t2_aurora_mask);
t2_aurora_textSvg.appendChild(t2_aurora_defs);
const shadowUse=createSvgElement("use");
setAttributes(shadowUse,{
href:"#text",fill:"#000","fill-opacity":"0.5",transform:"translate(0, 30)"
});
t2_aurora_textSvg.appendChild(shadowUse);
const maskGroup=createSvgElement("g");
setAttributes(maskGroup,{mask:"url(#mask)"});
const rects=[
{x:"-100",y:"50",fill:"url(#gr-aurora-1)"},{x:"-100",y:"50",fill:"url(#gr-aurora-2)"},
{x:"-200",y:"100",fill:"url(#gr-aurora-3)"},{x:"80",y:"50",fill:"url(#gr-aurora-4)"},
{x:"300",y:"50",fill:"url(#gr-aurora-5)"},{x:"500",y:"50",fill:"url(#gr-aurora-4)"},
{x:"600",y:"50",fill:"url(#gr-aurora-3)"},{x:"720",y:"50",fill:"url(#gr-aurora-2)"},
{x:"550",y:"100",fill:"url(#gr-aurora-1)"},{x:"400",y:"100",fill:"url(#gr-aurora-2)"},
{x:"300",y:"100",fill:"url(#gr-aurora-3)"},{x:"250",y:"100",fill:"url(#gr-aurora-4)"},
{x:"100",y:"100",fill:"url(#gr-aurora-5)"}
].forEach(rect=>{
const rectElement=createSvgElement("rect");
setAttributes(rectElement,{...rect});
maskGroup.appendChild(rectElement);
});
t2_aurora_textSvg.appendChild(maskGroup);
const outlineUse=createSvgElement("use");
setAttributes(outlineUse,{
href:"#text",fill:"transparent",stroke:"#000","stroke-width":"8","stroke-opacity":"0.4"
});
t2_aurora_textSvg.appendChild(outlineUse);
document.body.appendChild(t2_aurora_textSvg);
t2_aurora_updateText();
document.body.removeChild(t2_aurora_textSvg);
t2_aurora_addSvg(left,top);
}
function t2_aurora_updateText(){
t2_aurora_mainText.textContent=t2_text.value;
Object.assign(t2_aurora_mainText.style,{
fontSize:`${t2_fontSize.value}px`,
fill:t2_fillColor.value
});
t2_aurora_updateSvgSize();
}
function t2_aurora_updateSvgSize(){
try{
const bbox=t2_aurora_mainText.getBBox();
const padding=Math.max(20,bbox.width*0.1);
const dims={
viewBox: `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding*2} ${bbox.height + padding*2}`,
width: bbox.width+padding*2,
height: bbox.height+padding*2
};
setAttributes(t2_aurora_textSvg,dims);
}catch(error){}
}
function t2_aurora_addSvg(left,top){
const svgString=new XMLSerializer().serializeToString(t2_aurora_textSvg);
const reader=new FileReader();
reader.onload=({target})=>{
fabric.Image.fromURL(target.result,img=>{
Object.assign(img,{left,top});
nowT2AuroraStr=img;
img.text=getFirstNCharsDefault(t2_text);
canvas.add(img).setActiveObject(img).renderAll();
},{crossOrigin:'anonymous'});
};
reader.readAsDataURL(new Blob([svgString],{type:"image/svg+xml;charset=utf-8"}));
}
function t2_aurora_updateAll(){
const position=nowT2AuroraStr?
{left:nowT2AuroraStr.left,top:nowT2AuroraStr.top}:{left:50,top:100};
if(nowT2AuroraStr){
canvas.remove(nowT2AuroraStr).renderAll();
nowT2AuroraStr=null;
}
t2_aurora_deleteSvg();
t2_aurora_createSvg(position.left,position.top);
}