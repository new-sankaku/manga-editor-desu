class SDWebUIEndpoints {
#getUrlParts() {
let apiUrl=$('sdWebUIPageUrl').value;
const url=new URL(apiUrl);
return {
protocol: url.protocol.replace(':',''),
host: url.hostname,
port: url.port
};
}

constructor() {
this.urls=this.setupUrlProxy();
}

setupUrlProxy() {
return new Proxy({},{
get: (target,prop)=>{
const urlParts=this.#getUrlParts();
const endpoint=this.getEndpoint(prop);
return `${urlParts.protocol}://${urlParts.host}${urlParts.port ? ':' + urlParts.port : ''}${endpoint}`;
}
});
}

getEndpoint(key) {
const endpoints={
ping: '/internal/ping',
sampler: '/sdapi/v1/samplers',
scheduler: '/sdapi/v1/schedulers',
upscaler: '/sdapi/v1/upscalers',
sdModel: '/sdapi/v1/sd-models',
t2i: '/sdapi/v1/txt2img',
i2i: '/sdapi/v1/img2img',
options: '/sdapi/v1/options',
samplers: '/sdapi/v1/samplers',
interrogate: '/sdapi/v1/interrogate',
sdModules: '/sdapi/v1/sd-modules',
rembg: '/rembg',
adetilerModel: '/adetailer/v1/ad_model'
};
return endpoints[key]||'';
}
}




function rembgRequestData(layer) {
const requestData={
"input_image": "",
"model": "u2net",
"return_mask": false,
"alpha_matting": false,
"alpha_matting_foreground_threshold": 240,
"alpha_matting_background_threshold": 10,
"alpha_matting_erode_size": 10
};
return requestData;
}

function baseRequestData(layer) {
var seed=-1;
var width=-1;
var height=-1;

if (layer.text2img_seed==-2) {
seed=basePrompt.text2img_seed;
} else if (layer.text2img_seed>-1) {
seed=layer.text2img_seed;
}

if(isImage(layer)){
width=layer.width*layer.scaleX*layer.img2imgScale;
height=layer.height*layer.scaleY*layer.img2imgScale;
console.log("widthLayer",layer.width);
console.log("scaleX",layer.scaleX);
console.log("heightLayer",layer.height);
console.log("scaleY",layer.caleY);
console.log("layer.img2imgScale",layer.img2imgScale);
console.log("width",width);
console.log("height",height);

}else{
if (layer.text2img_width<=0) {
width=basePrompt.text2img_width;
} else {
width=layer.text2img_width;
}
if (layer.text2img_height<=0) {
height=basePrompt.text2img_height;
} else {
height=layer.text2img_height;
}
}


const requestData={
"prompt": basePrompt.text2img_prompt+", "+layer.text2img_prompt,
"negative_prompt": basePrompt.text2img_negative+", "+layer.text2img_negative,
"seed": seed,
"width": width,
"height": height,
"sampler_name": basePrompt.text2img_samplingMethod,
"steps": basePrompt.text2img_samplingSteps,
"cfg_scale": basePrompt.text2img_cfg_scale,
"scheduler": basePrompt.text2img_scheduler,
"do_not_save_grid": true,
"scheduler": "simple",
"save_images": true,
};

if($("AdetailerCheck").checked){
const adModels=getAdetailerList();
console.log("adModels",JSON.stringify(adModels));
if (adModels.length>0) {
const adPromptElement=document.getElementById('AdetilerModelsPrompt');
const adNegativePromptElement=document.getElementById('AdetilerModelsNegative');

const adPrompt=adPromptElement&&adPromptElement.value ? adPromptElement.value.trim() : "";
const adNegativePrompt=adNegativePromptElement&&adNegativePromptElement.value ? adNegativePromptElement.value.trim() : "";

requestData.alwayson_scripts={
"ADetailer": {
"args": adModels.map(model=>({
"ad_model": model,
"ad_prompt": adPrompt,
"ad_negative_prompt": adNegativePrompt
}))
}
};
}
}else{
}

if (basePrompt.text2img_hr_upscaler&&basePrompt.text2img_hr_upscaler!='None') {
Object.assign(requestData,{
enable_hr: true,
hr_upscaler: basePrompt.text2img_hr_upscaler,
hr_scale: basePrompt.text2img_hr_scale,
hr_second_pass_steps: basePrompt.text2img_hr_step,
denoising_strength: basePrompt.text2img_hr_denoise,
});
}

// console.log("requestData", JSON.stringify(requestData));
return requestData;
}