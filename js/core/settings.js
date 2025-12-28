//FabricCanvas2HtmlCanvas Scale
const blendScale = 3;
var webpQuality = 0.98;

fabric.Object.NUM_FRACTION_DIGITS = 100;

const minCanvasSizeWidth = 600;
const minCanvasSizeHeight = 400;

var canvas = new fabric.Canvas("mangaImageCanvas", {
  enableRetinaScaling: true,
  renderOnAddRemove: false,
  imageSmoothingEnabled: true,
  skipOffscreen: true,
  renderer: fabric.isWebglSupported ? "webgl" : "canvas",
});
document.addEventListener("DOMContentLoaded", function() {
  loadBookSize(210, 297, false);
  canvas.renderAll();
});

  canvas.backgroundColor = "gray";

var svgPagging = 20;
document.addEventListener('DOMContentLoaded', function() {
  svgPagging = $('marginFromPanel').value;
  $('marginFromPanel').addEventListener('input', function() {
    svgPagging = $('marginFromPanel').value;
  });
});



var sdWebUIPort = 7860;
var sdWebUIHost = "127.0.0.1";

var comfyuiPort = 8188;
var comfyuiHost = "127.0.0.1";

const basePrompt = {
  text2img_prompt         :"masterpiece, best quality, 1girl, simple background, ",
  text2img_negative       :"low quality, worst quality, jpeg, normal quality, ",
  text2img_seed           :-1,
  text2img_cfg_scale      :7,
  text2img_width          :1024,
  text2img_height         :1024,
  text2img_samplingMethod :"Euler a",
  text2img_samplingSteps  :20,
  text2img_scheduler      :"Automatic",
  text2img_model          :"",
  text2img_hr_upscaler    :"None",
  text2img_hr_scale       :"1.3",
  text2img_hr_step        :20,
  text2img_hr_denoise     :"0.7",
};

const t2i_init = {
  isPanel            : true,
  t2i_prompt         : "",
  t2i_negativePrompt : "",
  t2i_seed           : -2,
  t2i_width          : -1,
  t2i_height         : -1,
};

const i2i_init = {
  i2i_prompt         : "",
  i2i_negativePrompt : "",
  i2i_seed           : -2,
  i2i_width          : -1,
  i2i_height         : -1,
  i2i_samplingSteps : 20,
  i2i_denoise : 0.7,
  i2i_scale : 1.05,
};

const commonProperties = [
'excludeFromLayerPanel', 
'isPanel', 
'isIcon',
'text2img_prompt', 
'text2img_negative', 
'text2img_seed', 
'text2img_width', 
'text2img_height', 
'text2img_samplingMethod', 
'text2img_samplingSteps',
'initial', 
'clipPath.initial',
'name',
"guids", "guid", "tempPrompt", "tempNegative", "tempSeed", "img2imgScale", "img2img_denoise", "canvasGuid", "isSpeechBubble","jstsGeom","text","selectable","customType"
,"speechBubbleGrid","speechBubbleScale","speechBubbleViewBoxWidth","speechBubbleViewBoxHeight","speechBubbleRectX","speechBubbleRectY","speechBubbleRectWidth","speechBubbleRectHeight"
,"baseScaleX","baseScaleY","lastLeft", "lastTop", "targetObject", "originalSvg"
];

let jscolorOptions = {
  value: 'rgba(0,0,0,1)',
  position: 'bottom',
  height: 80,
  backgroundColor: '#333',
  palette: 'rgba(0,0,0,0) #fff #808080 #000 #996e36 #f55525 #ffe438 #88dd20 #22e0cd #269aff #bb1cd4',
  paletteCols: 11,
  hideOnPaletteClick: true
 };

document.addEventListener('DOMContentLoaded', function() {
  jsColorSet();
});

function jsColorSet(){
  const colorPickers = document.querySelectorAll('.jscolor-color-picker');
  colorPickers.forEach(picker => {
    if (picker.hasAttribute('data-jscolor')) return;

    const initialValue = picker.getAttribute('data-initial-color') || 'rgba(0,0,0,1)';
    jscolorOptions.value = initialValue;
    picker.setAttribute('data-jscolor', JSON.stringify(jscolorOptions));
  });
  jscolor.install();
}

function jsColorSetById(id){
  const picker = document.getElementById(id);
  if (!picker) return;

  const initialValue = picker.getAttribute('data-initial-color') || 'rgba(0,0,0,1)';
  jscolorOptions.value = initialValue;
  picker.setAttribute('data-jscolor', JSON.stringify(jscolorOptions));
  jscolor.install();
}
