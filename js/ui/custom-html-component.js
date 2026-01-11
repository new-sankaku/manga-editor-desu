document.addEventListener('DOMContentLoaded',function() {
const sliders=document.querySelectorAll('.input-container input[type="range"]');
sliders.forEach(slider=>{
setupSlider(slider,'.input-container')
});
const sliders2=document.querySelectorAll('.input-container-leftSpace input[type="range"]');
sliders2.forEach(slider=>{
setupSlider(slider,'.input-container-leftSpace')
});
});


function setupSlider(slider,classname,addButton=true){
if(slider.isSetupDone){
return;
}

const container=slider.closest(classname);
const label=container.getAttribute('data-label');
const sliderContainer=document.createElement('div');
sliderContainer.className='slider-container';

const valueButtons=document.createElement('div');
valueButtons.className='slider-value-buttons';

let upButton=null;
let downButton=null;
if(addButton){
upButton=document.createElement('button');
upButton.className='slider-value-button';
upButton.textContent='△';
downButton=document.createElement('button');
downButton.className='slider-value-button';
downButton.textContent='▽';
valueButtons.appendChild(upButton);
valueButtons.appendChild(downButton);
}


container.appendChild(sliderContainer);
sliderContainer.appendChild(slider);
sliderContainer.appendChild(valueButtons);


const originalDescriptor=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');



Object.defineProperty(slider,'value',{
get: function() {
return originalDescriptor.get.call(this);
},
set: function(newValue) {
originalDescriptor.set.call(this,newValue);
updateLabel();
}
});

function updateLabel() {
container.setAttribute('data-label',`${label}：${slider.value}`);
}

function updateSlider(newValue) {
slider.value=newValue;
slider.dispatchEvent(new Event('input'));
}

slider.addEventListener('input',updateLabel);

if(addButton){
upButton.addEventListener('click',()=>{
const step=parseFloat(slider.step)||1;

const newValue=Math.min(parseFloat(slider.value)+step,slider.max);
updateSlider(newValue);
});

downButton.addEventListener('click',()=>{
const step=parseFloat(slider.step)||1;

const newValue=Math.max(parseFloat(slider.value)-step,slider.min);
updateSlider(newValue);
});
}

updateLabel();


slider.isSetupDone=true;
}

