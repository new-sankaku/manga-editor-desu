document.addEventListener("DOMContentLoaded",function () {
toggleVisibility("svg-container-vertical");
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
$("svg-container-vertical").style.display="none";
$("svg-container-landscape").style.display="none";
$("panel-manager-area").style.display="none";
$("custom-panel-manager-area").style.display="none";
$("auto-generate-area").style.display="none";
$("prompt-manager-area").style.display="none";
$("speech-bubble-area1").style.display="none";
$("speech-bubble-area2").style.display="none";
$("text-area").style.display="none";
$("text-area2").style.display="none";
$("tool-area").style.display="none";
$("manga-tone-area").style.display="none";
$("rough-manager-area").style.display="none";
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
