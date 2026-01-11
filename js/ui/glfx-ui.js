let gpifHTML=`
<div class="control-content glfxControls">
    <select id="glfxFilter">
        <option value="" data-i18n="select">Select</option>
        <option value="glfxBrightnessContrast" data-i18n="brightnessContrast">Brightness / Contrast</option>
        <option value="glfxHueSaturation" data-i18n="hueSaturation">Hue / Saturation</option>
        <option value="glfxSepia" data-i18n="sepia">Sepia</option>
        <option value="glfxUnsharpMask" data-i18n="unsharpMask">Unsharp Mask</option>
        <option value="glfxVibrance" data-i18n="vibrance">Vibrance</option>
        <option value="glfxVignette" data-i18n="vignette">Vignette</option>
        <option value="glfxLensBlur" data-i18n="lensBlur">Lens Blur</option>
        <!-- <option value="glfxTiltShift" data-i18n="tiltShift">Tilt Shift</option> -->
        <option value="glfxTriangleBlur" data-i18n="triangleBlur">Triangle Blur</option>
        <option value="glfxZoomBlur" data-i18n="zoomBlur">Zoom Blur</option>
        <option value="glfxColorHalftone" data-i18n="colorHalftone">Color Halftone</option>
        <option value="glfxDotScreen" data-i18n="dotScreen">Dot Screen</option>
        <option value="glfxEdgeWork" data-i18n="edgeWork">Edge Work</option>
        <option value="glfxHexagonalPixelate" data-i18n="hexagonalPixelate">Hexagonal Pixelate</option>
        <option value="glfxInk" data-i18n="ink">Ink</option>
        <!-- <option value="glfxBulgePinch" data-i18n="bulgePinch">Bulge / Pinch</option> -->
        <option value="glfxSwirl" data-i18n="swirl">Swirl</option>
    </select>

    <div id="glfxBrightnessContrast" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="brightness">
            <input type="range" id="glfxBrightness" min="-1" max="1" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="contrast">
            <input type="range" id="glfxContrast" min="-1" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxHueSaturation" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="hue">
            <input type="range" id="glfxHue" min="-1" max="1" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="saturation">
            <input type="range" id="glfxSaturation" min="-1" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxSepia" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="sepia">
            <input type="range" id="glfxSepiaAmount" min="0" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxUnsharpMask" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxUnsharpRadius" min="0" max="200" step="0.1" value="0">
        </div>
        <div class="input-container" data-i18n-label="strength">
            <input type="range" id="glfxUnsharpStrength" min="0" max="5" step="0.1" value="0">
        </div>
    </div>

    <div id="glfxVibrance" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="vibrance">
            <input type="range" id="glfxVibranceAmount" min="-1" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxVignette" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="size">
            <input type="range" id="glfxVignetteSize" min="0" max="1" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="amount">
            <input type="range" id="glfxVignetteAmount" min="0" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxLensBlur" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxBlurRadius" min="0" max="50" step="1" value="0">
        </div>
        <div class="input-container" data-i18n-label="brightness">
            <input type="range" id="glfxBlurBrightness" min="-1" max="1" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="angle">
            <input type="range" id="glfxBlurAngle" min="-3.14" max="3.14" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxTiltShift" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="startX">
            <input type="range" id="glfxStartX" min="0" max="1" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="startY">
            <input type="range" id="glfxStartY" min="0" max="1" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="endX">
            <input type="range" id="glfxEndX" min="0" max="1" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="endY">
            <input type="range" id="glfxEndY" min="0" max="1" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="blurRadius">
            <input type="range" id="glfxTiltBlurRadius" min="0" max="50" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="gradientRadius">
            <input type="range" id="glfxGradientRadius" min="0" max="1" step="0.01" value="0.5">
        </div>
    </div>

    <div id="glfxTriangleBlur" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxTriangleRadius" min="0" max="200" step="1" value="0">
        </div>
    </div>

    <div id="glfxZoomBlur" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="centerX">
            <input type="range" id="glfxZoomCenterX" min="0" max="1024" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="centerY">
            <input type="range" id="glfxZoomCenterY" min="0" max="1024" step="0.01" value="0.5">
        </div>
        <div class="input-container" data-i18n-label="strength">
            <input type="range" id="glfxZoomStrength" min="0" max="1" step="0.01" value="0">
        </div>
    </div>

    <div id="glfxColorHalftone" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="angle">
            <input type="range" id="glfxHalftoneAngle" min="0" max="6.28" step="0.1" value="0">
        </div>
        <div class="input-container" data-i18n-label="size">
            <input type="range" id="glfxHalftoneSize" min="1" max="100" step="0.1" value="2">
        </div>
    </div>

    <div id="glfxDotScreen" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="angle">
            <input type="range" id="glfxDotAngle" min="0" max="6.28" step="0.1" value="0">
        </div>
        <div class="input-container" data-i18n-label="size">
            <input type="range" id="glfxDotSize" min="1" max="100" step="0.1" value="2">
        </div>
    </div>

    <div id="glfxEdgeWork" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxEdgeRadius" min="0" max="10" step="0.1" value="0">
        </div>
    </div>

    <div id="glfxHexagonalPixelate" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="scale">
            <input type="range" id="glfxHexScale" min="1" max="100" step="0.1" value="2">
        </div>
    </div>

    <div id="glfxInk" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="strength">
            <input type="range" id="glfxInkStrength" min="0" max="1" step="0.01" value="0.3">
        </div>
    </div>

    <div id="glfxBulgePinch" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="centerX">
            <input type="range" id="glfxBulgeCenterX" min="0" max="1024" step="1" value="500">
        </div>
        <div class="input-container" data-i18n-label="centerY">
            <input type="range" id="glfxBulgeCenterY" min="0" max="1024" step="1" value="500">
        </div>
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxBulgeRadius" min="-1" max="1" step="0.01" value="0">
        </div>
        <div class="input-container" data-i18n-label="strength">
            <input type="range" id="glfxBulgeStrength" min="0" max="600" step="1" value="0">
        </div>
    </div>

    <div id="glfxSwirl" class="glfxCcontrol-group">
        <div class="input-container" data-i18n-label="centerX">
            <input type="range" id="glfxSwirlCenterX" min="0" max="1024" step="1" value="256">
        </div>
        <div class="input-container" data-i18n-label="centerY">
            <input type="range" id="glfxSwirlCenterY" min="0" max="1024" step="1" value="256">
        </div>
        <div class="input-container" data-i18n-label="radius">
            <input type="range" id="glfxSwirlRadius" min="0" max="600" step="1" value="0">
        </div>
        <div class="input-container" data-i18n-label="angle">
            <input type="range" id="glfxSwirlAngle" min="-25" max="25" step="10" value="0">
        </div>
    </div>
    <div style="margin-top: 5px;">
        <button id="glfxApplyButton" data-i18n="apply">Apply</button>
        <button id="glfxResetButton" data-i18n="reset">Reset</button>
    </div>
</div>
`;


function setGlfxI18NextLabel() {
const parentElement=document.getElementById('manga-effect-settings');
const controlsDiv=parentElement.querySelector('.control-content.glfxControls');

if (controlsDiv) {
applyLabelTranslations(controlsDiv);
}

const sliders2=document.querySelectorAll('.input-container input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container');
});
}




function applyLabelTranslations(container) {
const labelElements=container.querySelectorAll('[data-i18n-label]');
labelElements.forEach(element=>{
const key=element.getAttribute('data-i18n-label');
const translatedText=getText(key);
if (translatedText) {
element.setAttribute('data-label',translatedText);
}
});

const i18nElements=container.querySelectorAll('[data-i18n]');
i18nElements.forEach(element=>{
const key=element.getAttribute('data-i18n');
const translatedText=getText(key);
if (translatedText) {
if (element.tagName.toLowerCase()==='option') {
element.textContent=translatedText;
} else {
element.setAttribute('data-label',translatedText);
}
}
});
}

