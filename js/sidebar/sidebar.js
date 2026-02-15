document.addEventListener("DOMContentLoaded",function () {
toggleVisibility("svg-container-template");
});

function toggleVisibility(id) {
var element=$(id);
var icons=document.querySelectorAll("#sidebar i");
icons.forEach((icon)=>{
if (icon.getAttribute("onclick").includes(`toggleVisibility('${id}')`)) {
icon.classList.toggle("active",element.style.display==="none");
} else {
icon.classList.remove("active");
}
});

if (element.style.display==="none") {
$("svg-container-template").style.display="none";
$("panel-manager-area").style.display="none";
$("auto-generate-area").style.display="none";
$("prompt-manager-area").style.display="none";
$("speech-bubble-area1").style.display="none";
$("speech-bubble-area2").style.display="none";
$("text-area").style.display="none";
$("text-area2").style.display="none";
$("tool-area").style.display="none";
$("manga-tone-area").style.display="none";
$("manga-effect-area").style.display="none";
$("shape-area").style.display="none";
$("controle-area").style.display="none";
element.style.display="block";
lazyLoadSvgData(id);
} else {
element.style.display="none";
}
adjustCanvasSize();
}

function switchTemplateOrientation(){
var checkbox=$("template-orientation-toggle");
var vertical=$("svg-preview-area-vertical");
var landscape=$("svg-preview-area-landscape");
var toggleLabel=document.querySelector(".template-toggle-label");
if(checkbox.checked){
vertical.style.display="none";
landscape.style.display="block";
toggleLabel.classList.add("landscape");
lazyLoadSvgData("svg-container-landscape");
}else{
vertical.style.display="block";
landscape.style.display="none";
toggleLabel.classList.remove("landscape");
lazyLoadSvgData("svg-container-vertical");
}
}
