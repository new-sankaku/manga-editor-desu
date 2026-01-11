
async function processQueue(layer,spinnerId,fetchFunction,imageName) {
console.log(`Processing queue for ${imageName}`);
try {
const {img,responseData}=await sdQueue.add(()=>sdwebuiGenerateImage(layer,fetchFunction));
if (img) {
await handleSuccessfulGeneration(img,responseData,layer,imageName);
} else {
createToastError("Generation error","");
}
} catch (error) {
console.error("processQueue",error);
} finally {
removeSpinner(spinnerId);
}
}

async function handleSuccessfulGeneration(img,responseData,layer,imageName) {
const webpImg=await img2webp(img);
webpImg.name=imageName;
setImage2ImageInitPrompt(webpImg);
const {centerX,centerY}=calculateCenter(layer);
putImageInFrame(webpImg,centerX,centerY);

const infoObject=JSON.parse(responseData.info);
layer.tempSeed=infoObject.seed;
webpImg.tempPrompt=infoObject.prompt;
webpImg.tempNegative=infoObject.negative_prompt;
}

const sdwebuiT2IProcessQueue=(layer,spinnerId)=>processQueue(layer,spinnerId,sdwebuiFetchText2Image,"t2i");
const sdwebuiI2IProcessQueue=(layer,spinnerId)=>processQueue(layer,spinnerId,sdwebuiFetchImage2Image,"i2i");

async function sdwebuiFetchText2Image(layer) {
return post(sdWebUIUrls.t2i,baseRequestData(layer));
}

async function sdwebuiFetchImage2Image(layer) {
const base64Image=imageObject2Base64ImageEffectKeep(layer);
const requestData={
...baseRequestData(layer),
init_images: [base64Image.split(',')[1]],
denoising_strength: layer.img2img_denoise
};
console.log("sdwebuiFetchImage2Image requestData",requestData);
return post(sdWebUIUrls.i2i,requestData);
}

async function post(url,requestData) {
try {
console.log("requestData:",requestData);
const response=await fetch(url,{
method: 'POST',
headers: {
'Content-Type': 'application/json',
'accept': 'application/json'
},
body: JSON.stringify(requestData)
});
return await response.json();
} catch (error) {
var checkSD=getText("checkSD_webUI_Text");
createToastError("Fetch Error",checkSD);
return null;
}
}

async function sdwebuiGenerateImage(layer,fetchFunction) {
const responseData=await fetchFunction(layer);
if (!responseData) return null;

const base64ImageData=responseData.images[0];
const imageSrc='data:image/png;base64,'+base64ImageData;

return new Promise((resolve,reject)=>{
fabric.Image.fromURL(imageSrc,(img)=>{
img ? resolve({img,responseData}) : reject(new Error('Failed to create a fabric.Image object'));
});
});
}

async function sdwebuiRembgProcessQueue(layer,spinnerId) {
console.log("Processing queue for rembg");
try {
const responseData=await sdQueue.add(()=>sdwebuiRemoveBackground(layer));
if (responseData&&typeof responseData==='string') {
await handleSuccessfulRembg(responseData,layer);
} else {
createToastError("Invalid background removal response","");
}
} catch (error) {
console.error("sdwebuiRembgProcessQueue",error);
} finally {
removeSpinner(spinnerId);
}
}

async function sdwebuiRemoveBackground(layer) {
const base64Image=imageObject2Base64ImageEffectKeep(layer);

const requestData=rembgRequestData(layer);
requestData.input_image=base64Image.split(',')[1];
const response=await post(sdWebUIUrls.rembg,requestData);

if (typeof response==='object'&&response.hasOwnProperty('image')) {
return response.image;
} else if (typeof response==='string') {
return response;
} else {
throw new Error('Unexpected response format from rembg API');
}
}

async function handleSuccessfulRembg(responseData,layer) {
if (!responseData.startsWith('data:image')) {
responseData='data:image/png;base64,'+responseData;
}

return new Promise((resolve,reject)=>{
fabric.Image.fromURL(responseData,(img)=>{
if (img) {
const {centerX,centerY}=calculateCenter(layer);
putImageInFrame(img,centerX,centerY);
resolve(img);
visibleChange(layer);
} else {
reject(new Error('Failed to create a fabric.Image object from rembg result'));
}
},{crossOrigin: 'anonymous'});
});
}
