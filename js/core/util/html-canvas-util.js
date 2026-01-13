// html-canvas-util.js - HTMLキャンバスに対する低レベル操作（境界検出、スケーリング、ピクセル処理）

var HtmlCanvasUtil={
findNonTransparentBounds:function(imageData){
var width=imageData.width;
var height=imageData.height;
var data=imageData.data;
var minX=width,minY=height,maxX=0,maxY=0;
for(var y=0;y<height;y++){
for(var x=0;x<width;x++){
var alpha=data[(y*width+x)*4+3];
if(alpha>0){
minX=Math.min(minX,x);
minY=Math.min(minY,y);
maxX=Math.max(maxX,x);
maxY=Math.max(maxY,y);
}
}
}
return {minX:minX,minY:minY,maxX:maxX,maxY:maxY};
},

createClippedCanvas:function(sourceCanvas,bounds){
var minX=bounds.minX;
var minY=bounds.minY;
var maxX=bounds.maxX;
var maxY=bounds.maxY;
var clipWidth=maxX-minX+1;
var clipHeight=maxY-minY+1;
var clippedCanvas=document.createElement('canvas');
clippedCanvas.width=clipWidth;
clippedCanvas.height=clipHeight;
var clippedCtx=clippedCanvas.getContext('2d');
clippedCtx.drawImage(sourceCanvas,minX,minY,clipWidth,clipHeight,0,0,clipWidth,clipHeight);
return clippedCanvas;
},

createOffscreenCanvas:function(width,height){
var canvas=document.createElement('canvas');
canvas.width=width;
canvas.height=height;
return canvas;
},

createScaledCanvas:function(sourceCanvas,maxWidth,maxHeight){
var scale=Math.min(1,maxWidth/sourceCanvas.width,maxHeight/sourceCanvas.height);
var scaledCanvas=document.createElement('canvas');
scaledCanvas.width=sourceCanvas.width*scale;
scaledCanvas.height=sourceCanvas.height*scale;
var ctx=scaledCanvas.getContext('2d');
ctx.imageSmoothingEnabled=false;
ctx.drawImage(sourceCanvas,0,0,scaledCanvas.width,scaledCanvas.height);
return scaledCanvas;
},

enhanceDarkRegionsCPU:function(imageData,intensity){
var data=imageData.data;
for(var i=0;i<data.length;i+=4){
var r=data[i];
var g=data[i+1];
var b=data[i+2];
var brightness=(r+g+b)/3;
if(brightness<200){
var darkFactor=Math.max(0,1-Math.pow(intensity*0.2,1.5));
data[i]*=darkFactor;
data[i+1]*=darkFactor;
data[i+2]*=darkFactor;
}
}
return imageData;
},

renderLayerToCanvas:function(targetCanvas,layer,scaleFactor,left,top){
var ctx=targetCanvas.getContext('2d');
var originalClipPath=layer.clipPath;
layer.clipPath=null;
ctx.fillStyle='white';
ctx.fillRect(0,0,targetCanvas.width,targetCanvas.height);
ctx.scale(scaleFactor,scaleFactor);
ctx.translate(-left,-top);
layer.render(ctx);
layer.clipPath=originalClipPath;
}
};

var findNonTransparentBounds=HtmlCanvasUtil.findNonTransparentBounds;
var createClippedCanvas=HtmlCanvasUtil.createClippedCanvas;
var createOffscreenCanvas=HtmlCanvasUtil.createOffscreenCanvas;
var createScaledCanvas=HtmlCanvasUtil.createScaledCanvas;
var enhanceDarkRegionsCPU=HtmlCanvasUtil.enhanceDarkRegionsCPU;
var renderLayerToCanvas=HtmlCanvasUtil.renderLayerToCanvas;
