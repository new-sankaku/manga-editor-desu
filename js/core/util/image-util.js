// image-util.js - Fabric.js画像オブジェクトの処理（変換、WebP、クロップ、反転、色変換など）

var ImageUtil={
createCanvasFromFabricImage:function(fabricImage){
var tempCanvas=document.createElement('canvas');
tempCanvas.width=canvas.width;
tempCanvas.height=canvas.height;
var tempCtx=tempCanvas.getContext('2d');
tempCtx.save();
tempCtx.translate(fabricImage.left,fabricImage.top);
tempCtx.rotate(fabricImage.angle*Math.PI/180);
tempCtx.scale(fabricImage.scaleX,fabricImage.scaleY);
if(fabricImage.type==='image'){
tempCtx.drawImage(fabricImage._element,0,0,fabricImage.width,fabricImage.height);
}else if(fabricImage.type==='rect'){
if(typeof fabricImage.fill==='string'){
tempCtx.fillStyle=fabricImage.fill;
tempCtx.fillRect(0,0,fabricImage.width,fabricImage.height);
}else if(fabricImage.fill instanceof fabric.Gradient){
var grad=tempCtx.createLinearGradient(0,0,fabricImage.width,0);
fabricImage.fill.colorStops.forEach(function(stop){
grad.addColorStop(stop.offset,stop.color);
});
tempCtx.fillStyle=grad;
tempCtx.fillRect(0,0,fabricImage.width,fabricImage.height);
}
}
tempCtx.restore();
return tempCanvas;
},

fabricImage2ImageData:async function(fabricImage){
var img=fabricImage.getElement();
var tempCanvas=document.createElement('canvas');
tempCanvas.width=img.naturalWidth;
tempCanvas.height=img.naturalHeight;
var tempCtx=tempCanvas.getContext('2d',{alpha:true,willReadFrequently:true});
tempCtx.drawImage(img,0,0,img.naturalWidth,img.naturalHeight);
return tempCtx.getImageData(0,0,img.naturalWidth,img.naturalHeight);
},

imageObject2Base64Image:function(object,scale){
scale=scale||1.0;
try{
var src=object.getSrc();
if(!src){
throw new Error("Image source is not defined.");
}
var imageFormat=src.split('.').pop().toLowerCase();
var supportedFormats=['png','jpeg','jpg','webp'];
var format=supportedFormats.includes(imageFormat)?imageFormat:'png';
var base64Image=object.toDataURL({format:format,quality:scale});
return base64Image;
}catch(error){
imageLogger.error("Error converting image object to Base64:",error);
return null;
}
},

imageObject2Base64ImageEffectKeep:function(layer,scaleFactor){
scaleFactor=scaleFactor||1;
if(layer.type==='image'&&layer._element){
var imgElement=layer._element;
var originalWidth=imgElement.naturalWidth||imgElement.width;
var originalHeight=imgElement.naturalHeight||imgElement.height;
var offscreenCanvas=HtmlCanvasUtil.createOffscreenCanvas(originalWidth,originalHeight);
var ctx=offscreenCanvas.getContext('2d');
ctx.drawImage(imgElement,0,0,originalWidth,originalHeight);
return offscreenCanvas.toDataURL('image/png');
}else{
var width=layer.width;
var height=layer.height;
var scaleX=layer.scaleX;
var scaleY=layer.scaleY;
var left=layer.left;
var top=layer.top;
var pixelRatio=window.devicePixelRatio||1;
var enhancedScaleFactor=scaleFactor*2*pixelRatio;
var offscreenCanvas=HtmlCanvasUtil.createOffscreenCanvas(
Math.ceil(width*scaleX*enhancedScaleFactor),
Math.ceil(height*scaleY*enhancedScaleFactor)
);
HtmlCanvasUtil.renderLayerToCanvas(offscreenCanvas,layer,enhancedScaleFactor,left,top);
return offscreenCanvas.toDataURL('image/png');
}
},

imageObject2DataURL:function(activeObject){
if(activeObject&&activeObject.type==='image'){
var originalWidth=activeObject.width;
var originalHeight=activeObject.height;
var tempCanvas=document.createElement('canvas');
var tempContext=tempCanvas.getContext('2d');
tempCanvas.width=originalWidth;
tempCanvas.height=originalHeight;
tempContext.drawImage(activeObject.getElement(),0,0,originalWidth,originalHeight);
return tempCanvas.toDataURL('image/png');
}
return null;
},

imageObject2DataURLByCrop:function(activeObject){
imageLogger.debug("Function start: imageObject2DataURLByCrop");
imageLogger.debug("activeObject:",activeObject);
if(activeObject&&activeObject.isPanel){
var dataURL=ImageUtil.canvas2DataURL(3,"png");
return new Promise(function(resolve,reject){
var image=new Image();
image.crossOrigin="Anonymous";
image.src=dataURL;
image.onload=function(){
var tempCanvas=document.createElement('canvas');
var context=tempCanvas.getContext('2d');
tempCanvas.width=image.width;
tempCanvas.height=image.height;
context.drawImage(image,0,0);
var objectWidth=activeObject.width*activeObject.scaleX;
var objectHeight=activeObject.height*activeObject.scaleY;
var objectLeft=activeObject.left;
var objectTop=activeObject.top;
imageLogger.debug("objectWidth activeObject.strokeWidth",objectWidth,activeObject.strokeWidth);
imageLogger.debug("objectHeight activeObject.strokeWidth",objectHeight,activeObject.strokeWidth);
var scaleX=tempCanvas.width/activeObject.canvas.width;
var scaleY=tempCanvas.height/activeObject.canvas.height;
var cropX=(objectLeft)*scaleX;
var cropY=(objectTop)*scaleY;
var cropWidth=(objectWidth*scaleX)+(activeObject.strokeWidth*scaleX);
var cropHeight=(objectHeight*scaleY)+(activeObject.strokeWidth*scaleX);
var cropCanvas=document.createElement('canvas');
var cropContext=cropCanvas.getContext('2d');
cropCanvas.width=cropWidth;
cropCanvas.height=cropHeight;
cropContext.drawImage(tempCanvas,cropX,cropY,cropWidth,cropHeight,0,0,cropWidth,cropHeight);
var croppedDataURL=cropCanvas.toDataURL("image/png");
resolve(croppedDataURL);
};
image.onerror=function(err){
imageLogger.error("Image loading error:",err);
reject(err);
};
});
}
imageLogger.debug("Function end: imageObject2DataURLByCrop (no valid activeObject)");
return Promise.resolve(null);
},

img2webp:async function(i){
var blob=await fetch(i._element.src).then(function(response){return response.blob();});
var fileType=blob.type;
var fileName='image.'+fileType.split('/')[1];
var file=new File([blob],fileName,{type:fileType});
var webpFile=await ImageUtil.imgFile2webpFile(file);
var webpBlob=webpFile.slice(0,webpFile.size,'image/webp');
var reader=new FileReader();
return new Promise(function(resolve,reject){
reader.onloadend=function(){
var webpDataUrl=reader.result;
var webpImgElement=new Image();
webpImgElement.src=webpDataUrl;
webpImgElement.onload=function(){
var webpImg={};
Object.assign(webpImg,i);
webpImg._element=webpImgElement;
webpImg._originalElement=webpImgElement;
webpImg.cacheKey='webp_texture';
Object.setPrototypeOf(webpImg,Object.getPrototypeOf(i));
resolve(webpImg);
};
};
reader.onerror=reject;
reader.readAsDataURL(webpBlob);
});
},

imgFile2webpFile:async function(file){
if(file.type==='image/webp'){
return file;
}
var options={
fileType:'image/webp',
initialQuality:webpQuality
};
try{
var compressedFile=await imageCompression(file,options);
return compressedFile;
}catch(error){
imageLogger.error(error);
throw error;
}
},

cropImage:function(png,left,top,height,width){
if(top<png.top){
height=height-(png.top-top);
top=png.top;
}
if(left<png.left){
width=width-(png.left-left);
left=png.left;
}
if(top+height>png.top+png.height*png.scaleY){
height=png.top+png.height*png.scaleY-top;
}
if(left+width>png.left+png.width*png.scaleX){
width=png.left+png.width*png.scaleX-left;
}
var tempCanvas=new fabric.Canvas(document.createElement("canvas"));
tempCanvas.setWidth(png.width*png.scaleX);
tempCanvas.setHeight(png.height*png.scaleY);
var clonedObject=fabric.util.object.clone(png);
clonedObject.set({left:0,top:0});
if(clonedObject.clipPath){
clonedObject.clipPath=clonedObject.clipPath.clone();
}
tempCanvas.add(clonedObject);
tempCanvas.renderAll();
fabric.Image.fromURL(
tempCanvas.toDataURL({format:"webp",multiplier:2}),
function(img){
var scaledLeft=(left-png.left)*2;
var scaledTop=(top-png.top)*2;
var scaledWidth=width*2;
var scaledHeight=height*2;
img.set("left",-scaledLeft);
img.set("top",-scaledTop);
var canvasCrop=new fabric.Canvas("canvasCrop");
canvasCrop.setHeight(scaledHeight);
canvasCrop.setWidth(scaledWidth);
canvasCrop.add(img);
canvasCrop.renderAll();
fabric.Image.fromURL(
canvasCrop.toDataURL({format:"webp",multiplier:1}),
function(croppedImg){
croppedImg.set({left:left,top:top,scaleX:0.5,scaleY:0.5});
if(png.clipPath){
var clonedClipPath=fabric.util.object.clone(png.clipPath);
if(clonedClipPath){
croppedImg.clipPath=clonedClipPath;
}
}
replaceGuids(png.guid,croppedImg);
canvas.add(croppedImg).renderAll();
canvas.remove(cropActiveObject);
canvas.setActiveObject(croppedImg);
canvas.renderAll();
updateLayerPanel();
}
);
}
);
},

flipHorizontally:function(){
var activeObject=canvas.getActiveObject();
if(isImage(activeObject)){
activeObject.set("flipX",!activeObject.flipX);
canvas.renderAll();
}
},

flipVertically:function(){
var activeObject=canvas.getActiveObject();
if(isImage(activeObject)){
activeObject.set("flipY",!activeObject.flipY);
canvas.renderAll();
}
},

enhanceDarkImage:async function(){
var loading=OP_showLoading({icon:'process',step:'Step1',substep:'Start up',progress:0});
await new Promise(function(resolve){setTimeout(resolve,10);});
try{
var activeObject=canvas.getActiveObject();
var img=activeObject.getElement();
var originalScaleX=activeObject.scaleX||1;
var originalScaleY=activeObject.scaleY||1;
var intensity=parseFloat($('effectEnhanceDarkIntensity').value);
var originalImageData=await ImageUtil.fabricImage2ImageData(activeObject);
OP_updateLoadingState(loading,{icon:'process',step:'Step2',substep:'Dark enhance',progress:25});
await new Promise(function(resolve){setTimeout(resolve,10);});
var processedImageData=HtmlCanvasUtil.enhanceDarkRegionsCPU(originalImageData,intensity);
OP_updateLoadingState(loading,{icon:'process',step:'Step3',substep:'Image marge',progress:90});
await new Promise(function(resolve){setTimeout(resolve,10);});
var tempCanvas=document.createElement('canvas');
tempCanvas.width=img.naturalWidth;
tempCanvas.height=img.naturalHeight;
var tempCtx=tempCanvas.getContext('2d',{alpha:true,willReadFrequently:true});
tempCtx.imageSmoothingEnabled=true;
tempCtx.imageSmoothingQuality='high';
tempCtx.putImageData(processedImageData,0,0);
var webpDataUrl=tempCanvas.toDataURL('image/webp',1.0);
await new Promise(function(resolve){
fabric.Image.fromURL(webpDataUrl,function(img){
img.set({left:activeObject.left,top:activeObject.top,scaleX:originalScaleX,scaleY:originalScaleY});
copy(activeObject,img);
changeDoNotSaveHistory();
canvas.remove(activeObject);
canvas.add(img);
changeDoSaveHistory();
canvas.setActiveObject(img);
canvas.renderAll();
updateLayerPanel();
saveStateByManual();
resolve();
});
});
}catch(err){
imageLogger.error('Process error:',err);
}finally{
OP_hideLoading(loading);
}
},

sendHtmlCanvas2FabricCanvas:function(blendedCanvas,quality){
quality=quality||0.98;
var ctx=blendedCanvas.getContext('2d');
var imageData=ctx.getImageData(0,0,blendedCanvas.width,blendedCanvas.height);
var bounds=HtmlCanvasUtil.findNonTransparentBounds(imageData);
if(bounds.minX>bounds.maxX||bounds.minY>bounds.maxY){
imageLogger.warn('The image is completely transparent');
return;
}
var clippedCanvas=HtmlCanvasUtil.createClippedCanvas(blendedCanvas,bounds);
var webpDataUrl=clippedCanvas.toDataURL('image/webp',quality);
fabric.Image.fromURL(webpDataUrl,function(img){
img.scaleToWidth(canvas.width);
canvas.add(img);
canvas.setActiveObject(img);
canvas.renderAll();
},{crossOrigin:'anonymous'});
},

blobUrlToDataUrl:async function(blobUrl){
try{
var response=await fetch(blobUrl);
var blob=await response.blob();
return new Promise(function(resolve,reject){
var reader=new FileReader();
reader.onloadend=function(){resolve(reader.result);};
reader.onerror=reject;
reader.readAsDataURL(blob);
});
}catch(e){
imageLogger.error("Failed to convert blob URL:",blobUrl,e);
return null;
}
},

canvas2DataURL:function(multiplier,format){
return canvas.toDataURL({format:format,multiplier:multiplier});
},

getCropAndDownloadLinkByMultiplier:function(multiplier,format){
var cropped=canvas.toDataURL({format:format,multiplier:multiplier});
function getFormattedDateTime(){
var date=new Date();
var yyyy=date.getFullYear();
var MM=('0'+(date.getMonth()+1)).slice(-2);
var dd=('0'+date.getDate()).slice(-2);
var hh=('0'+date.getHours()).slice(-2);
var mm=('0'+date.getMinutes()).slice(-2);
var ss=('0'+date.getSeconds()).slice(-2);
var SSS=('00'+date.getMilliseconds()).slice(-3);
return yyyy+MM+dd+'_'+hh+mm+ss+'_'+SSS;
}
var link=document.createElement('a');
link.download='DESU-'+getFormattedDateTime()+'.'+format;
link.href=cropped;
return link;
},

getCropAndDownloadLink:function(){
var a5WidthInches=148/25.4;
var a5HeightInches=210/25.4;
var dpi=parseFloat($('outputDpi').value);
var canvasWidthPixels=canvas.width;
var canvasHeightPixels=canvas.height;
var targetWidthPixels=a5WidthInches*dpi;
var targetHeightPixels=a5HeightInches*dpi;
if(canvasWidthPixels>canvasHeightPixels){
targetWidthPixels=a5HeightInches*dpi;
targetHeightPixels=a5WidthInches*dpi;
}
var multiplierWidth=targetWidthPixels/canvasWidthPixels;
var multiplierHeight=targetHeightPixels/canvasHeightPixels;
var multiplier=Math.max(multiplierWidth,multiplierHeight);
return ImageUtil.getCropAndDownloadLinkByMultiplier(multiplier,'png');
},

clipCopy:function(){
removeGrid();
var link=ImageUtil.getCropAndDownloadLink();
fetch(link.href)
.then(function(res){return res.blob();})
.then(function(blob){
var item=new ClipboardItem({"image/png":blob});
navigator.clipboard.write([item]).then(function(){
createToast("Success","Image copied to clipboard successfully!");
},function(error){
createToastError("Error","Unable to write to clipboard. Error");
});
});
if(isGridVisible){
drawGrid();
isGridVisible=true;
}
},

cropAndDownload:function(){
removeGrid();
var link=ImageUtil.getCropAndDownloadLink();
link.click();
if(isGridVisible){
drawGrid();
isGridVisible=true;
}
},

getLink:function(dataURL){
var link=document.createElement('a');
link.href=dataURL;
link.download='selected-image.png';
return link;
},

getObjLeft:function(objWidth){
return canvas.getWidth()/2-objWidth/2;
},

getObjTop:function(objHeight){
return canvas.getHeight()/2-objHeight/2;
},

getWidth:function(fabricImage){
var img=fabricImage.getElement();
if(img.naturalWidth){
return img.naturalWidth;
}else{
return fabricImage.width;
}
},

getHeight:function(fabricImage){
var img=fabricImage.getElement();
if(img.naturalHeight){
return img.naturalHeight;
}else{
return fabricImage.height;
}
},

hexToRgba:function(hex,opacity){
opacity=opacity===undefined?1:opacity;
if(hex.startsWith('rgba')){
var match=hex.match(/\d+/g);
return 'rgba('+match[0]+', '+match[1]+', '+match[2]+', '+opacity+')';
}
if(hex.startsWith('rgb')){
var match=hex.match(/\d+/g);
return 'rgba('+match[0]+', '+match[1]+', '+match[2]+', '+opacity+')';
}
hex=hex.replace('#','');
var r=parseInt(hex.substring(0,2),16);
var g=parseInt(hex.substring(2,4),16);
var b=parseInt(hex.substring(4,6),16);
return 'rgba('+r+', '+g+', '+b+', '+opacity+')';
},

rgbToHex:function(color){
if(!color){
return '#000000';
}
if(color.startsWith('#')){
return color;
}
var match=color.match(/^rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)$/);
if(!match){
return color;
}
function convert(c){
var hex=parseInt(c).toString(16);
return hex.length===1?'0'+hex:hex;
}
return '#'+convert(match[1])+convert(match[2])+convert(match[3]);
},

rgbaToHex:function(color){
if(!color)return '#000000';
if(color.startsWith('#'))return color;
var match=color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d*\.?\d+))?\)/);
if(!match)return '#000000';
var r=parseInt(match[1]);
var g=parseInt(match[2]);
var b=parseInt(match[3]);
var toHex=function(n){
var hex=n.toString(16);
return hex.length===1?'0'+hex:hex;
};
return '#'+toHex(r)+toHex(g)+toHex(b);
}
};

var createCanvasFromFabricImage=ImageUtil.createCanvasFromFabricImage;
var fabricImage2ImageData=ImageUtil.fabricImage2ImageData;
var imageObject2Base64Image=ImageUtil.imageObject2Base64Image;
var imageObject2Base64ImageEffectKeep=ImageUtil.imageObject2Base64ImageEffectKeep;
var imageObject2DataURL=ImageUtil.imageObject2DataURL;
var imageObject2DataURLByCrop=ImageUtil.imageObject2DataURLByCrop;
var img2webp=ImageUtil.img2webp;
var imgFile2webpFile=ImageUtil.imgFile2webpFile;
var cropImage=ImageUtil.cropImage;
var flipHorizontally=ImageUtil.flipHorizontally;
var flipVertically=ImageUtil.flipVertically;
var enhanceDarkImage=ImageUtil.enhanceDarkImage;
var sendHtmlCanvas2FabricCanvas=ImageUtil.sendHtmlCanvas2FabricCanvas;
var blobUrlToDataUrl=ImageUtil.blobUrlToDataUrl;
var canvas2DataURL=ImageUtil.canvas2DataURL;
var getCropAndDownloadLinkByMultiplier=ImageUtil.getCropAndDownloadLinkByMultiplier;
var getCropAndDownloadLink=ImageUtil.getCropAndDownloadLink;
var clipCopy=ImageUtil.clipCopy;
var cropAndDownload=ImageUtil.cropAndDownload;
var getLink=ImageUtil.getLink;
var getObjLeft=ImageUtil.getObjLeft;
var getObjTop=ImageUtil.getObjTop;
var getWidth=ImageUtil.getWidth;
var getHeight=ImageUtil.getHeight;
var hexToRgba=ImageUtil.hexToRgba;
var rgbToHex=ImageUtil.rgbToHex;
var rgbaToHex=ImageUtil.rgbaToHex;
