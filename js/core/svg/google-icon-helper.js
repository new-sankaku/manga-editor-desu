
function getIconURL(iconName,style) {
switch (style) {
case 'outlined':
return `https://fonts.gstatic.com/s/i/materialiconsoutlined/${iconName}/v6/24px.svg`;
case 'rounded':
return `https://fonts.gstatic.com/s/i/materialiconsround/${iconName}/v6/24px.svg`;
case 'twotone':
return `https://fonts.gstatic.com/s/i/materialiconstwotone/${iconName}/v6/24px.svg`;
default:
return `https://fonts.gstatic.com/s/i/materialicons/${iconName}/v6/24px.svg`;
}
}

function searchInitialIcons() {
const resultsDiv=$('svg_icon_results');
resultsDiv.innerHTML='';
const style=$('svg_icon_iconStyle').value;

initialIcons.forEach(iconName=>{
const iconURL=getIconURL(iconName,style);
fetch(iconURL)
.then(response=>{
if (response.ok) {
return response.text();
}
return null;
})
.then(svgContent=>{
if (svgContent) {
//   console.log(`Fetched SVG content (${iconName}):`, svgContent);
displaySVG(svgContent,iconURL,iconName);
}
})
.catch(error=>uiLogger.error(`Error fetching initial icons: ${error}`));
});
}

document.addEventListener('DOMContentLoaded',()=>{
searchInitialIcons();
});


function searchIcon() {
const query=$('svg_icon_searchInput').value.toLowerCase();
const resultsDiv=$('svg_icon_results');
resultsDiv.innerHTML='';
const style=$('svg_icon_iconStyle').value;

if (!query) {
searchInitialIcons();
return;
}

const matchedIcons=iconList.filter(iconName=>iconName.includes(query));

if (matchedIcons.length>0) {
matchedIcons.forEach(iconName=>{
const iconURL=getIconURL(iconName,style);
fetch(iconURL)
.then(response=>{
if (response.ok) {
return response.text();
}
return null;
})
.then(svgContent=>{
if (svgContent) {
//   console.log(`Fetched SVG content (${iconName}):`, svgContent);
displaySVG(svgContent,iconURL,iconName);
}
})
.catch(error=>uiLogger.error(`Error fetching icons: ${error}`));
});
} else {
const noResultsDiv=document.createElement('div');
noResultsDiv.textContent='No icons found!';
resultsDiv.appendChild(noResultsDiv);
}
}


function displaySVG(svgContent,iconURL,iconName) {

const resultsDiv=$('svg_icon_results');
const svgElement=document.createElement('div');
svgElement.innerHTML=svgContent;
svgElement.className='icon-result';
svgElement.addEventListener('click',()=>addToCanvas(iconURL,iconName));
resultsDiv.appendChild(svgElement);

const svg=svgElement.querySelector('svg');
removeUnnecessaryElements(svg);
updateSVGElementStyles(svg);
}

function updateSVGElementStyles(svgElement) {
const lineColor=$('svg_icon_lineColor').value;
const fillColor=$('svg_icon_fillColor').value;
const fillOpacity=parseFloat($('svg_icon_fillOpacity').value);
const lineWidth=parseInt($('svg_icon_lineWidth').value,10);

svgElement.setAttribute('stroke',lineColor);
svgElement.setAttribute('fill',fillColor);
svgElement.setAttribute('fill-opacity',fillOpacity);
svgElement.setAttribute('stroke-width',lineWidth);
}

function updateSVGStyles() {
const iconResults=document.querySelectorAll('.icon-result svg');
iconResults.forEach(svgElement=>{
updateSVGElementStyles(svgElement);
});
}

function removeUnnecessaryElements(svgElement) {
const unnecessaryPaths=svgElement.querySelectorAll('path[d="M0 0h24v24H0z"], path[d="M0,0h24v24H0V0z"], path[d="M0 0h24v24H0V0z"], path[d="M0 0h24v24H0V0zm0 0h24v24H0V0z"]');
unnecessaryPaths.forEach(path=>path.remove());
const unnecessaryRects=svgElement.querySelectorAll('rect[fill="none"][height="24"][width="24"]');
unnecessaryRects.forEach(rect=>rect.remove());
}

function addToCanvas(iconURL,iconName) {
const lineColor=$('svg_icon_lineColor').value;
const fillColor=$('svg_icon_fillColor').value;
const fillOpacity=parseFloat($('svg_icon_fillOpacity').value);
const lineWidth=parseInt($('svg_icon_lineWidth').value,10);
const shadowColor=$('svg_icon_shadowColor').value;
const shadowBlur=parseInt($('svg_icon_shadowBlur').value,10);
const shadowOffsetX=parseInt($('svg_icon_shadowOffsetX').value,10);
const shadowOffsetY=parseInt($('svg_icon_shadowOffsetY').value,10);

fetch(iconURL)
.then(response=>response.text())
.then(svgContent=>{
const parser=new DOMParser();
const svgDoc=parser.parseFromString(svgContent,'image/svg+xml');
const svgElement=svgDoc.documentElement;

// Remove unnecessary <path> and <rect> elements
removeUnnecessaryElements(svgElement);

svgElement.setAttribute('stroke',lineColor);
svgElement.setAttribute('fill',fillColor);
svgElement.setAttribute('fill-opacity',fillOpacity);
svgElement.setAttribute('stroke-width',lineWidth);

const serializer=new XMLSerializer();
const newSvgContent=serializer.serializeToString(svgElement);
uiLogger.debug("newSvgContent",newSvgContent);

// Add to Fabric.js canvas
fabric.loadSVGFromString(newSvgContent,function (objects,options) {
const obj=fabric.util.groupSVGElements(objects,options);
obj.set({
left: 50,
top: 50,
shadow: new fabric.Shadow({
color: shadowColor,
blur: shadowBlur,
offsetX: shadowOffsetX,
offsetY: shadowOffsetY
}),
isIcon: true,
name: iconName,
originalSvg: newSvgContent
});
obj.scaleToWidth(50);
canvas.setActiveObject(obj);
canvas.add(obj).renderAll();
});
})
.catch(error=>uiLogger.error(`Error fetching SVG: ${error}`));
}
