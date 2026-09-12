// ホワイトボード(8190)との往復、プレビュー、本採用、破棄を担当
var whiteboardPreview=null;

function whiteboardPageNumber(){
var index=btmGetGuidIndex(getCanvasGUID());
return index>=0?index+1:1;
}

function whiteboardPanelFor(layer){
if(isPanel(layer))return layer;
if(isImage(layer)&&layer.relatedPoly&&isPanel(layer.relatedPoly))return layer.relatedPoly;
return layer;
}

function whiteboardTextContext(panel){
var texts=[];
canvas.getObjects().forEach(function(obj){
if(!isText(obj)||!obj.text)return;
var linked=Array.isArray(obj.guids)&&obj.guids.indexOf(getGUID(panel))>=0;
var inside=false;
try{inside=obj.intersectsWithObject(panel)||panel.containsPoint(obj.getCenterPoint());}catch(e){inside=false;}
if(linked||inside)texts.push(String(obj.text));
});
return texts;
}

function whiteboardNeighborContext(panel){
var panels=canvas.getObjects().filter(isPanel);var index=panels.indexOf(panel);
return {previous:index>0?(panels[index-1].name||""):"",next:index>=0&&index<panels.length-1?(panels[index+1].name||""):""};
}

function whiteboardBaseImage(layer){
if(isPanel(layer))return imageObject2DataURLByCrop(layer);
return Promise.resolve(imageObject2DataURL(layer));
}

function whiteboardStageBase(base){
if(!base||base.indexOf("data:image/")!==0)return Promise.resolve(base||"");
var comma=base.indexOf(",");
return fetch("http://127.0.0.1:8190/api/board/base",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({png:base.slice(comma+1)})})
.then(function(response){if(!response.ok)throw new Error("背景画像の一時保存に失敗しました");return response.json();})
.then(function(data){return "http://127.0.0.1:8190"+data.url;});
}

function whiteboardOpen(layer){
var panel=whiteboardPanelFor(layer);
var width=Math.max(8,Math.round(panel.getScaledWidth?panel.getScaledWidth():panel.width||1216));
var height=Math.max(8,Math.round(panel.getScaledHeight?panel.getScaledHeight():panel.height||832));
var pageId=getCanvasGUID();
var layerId=getGUID(layer);
var neighbors=whiteboardNeighborContext(panel);
var ctx={pageNumber:"p"+String(whiteboardPageNumber()).padStart(2,"0"),panelName:panel.name||layer.name||"コマ",purpose:panel.text2img_prompt||panel.name||"",mustInclude:panel.mustInclude||panel.requiredElements||"",texts:whiteboardTextContext(panel),previousPurpose:neighbors.previous,nextPurpose:neighbors.next,prompt:panel.text2img_prompt||""};
whiteboardBaseImage(layer).then(whiteboardStageBase).then(function(base){
var params=new URLSearchParams();
params.set("panel",pageId+"/"+layerId);params.set("w",width);params.set("h",height);
if(base)params.set("base",base);if(layer.wbBoardId)params.set("board",layer.wbBoardId);
params.set("ctx",btoa(unescape(encodeURIComponent(JSON.stringify(ctx)))));
window.open("http://127.0.0.1:8190/?"+params.toString(),"_blank");
}).catch(function(error){createToastError("Whiteboard",error.message||String(error));});
}

function whiteboardFindLayer(pageId,layerId){
if(pageId!==getCanvasGUID())return null;
return canvas.getObjects().find(function(obj){return String(getGUID(obj))===String(layerId);})||null;
}

function whiteboardBar(){
var bar=document.getElementById("whiteboard-preview-bar");
if(bar)return bar;
bar=document.createElement("div");bar.id="whiteboard-preview-bar";
bar.style.cssText="position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2200;background:#222;color:#fff;border:2px solid #4a9eff;border-radius:8px;padding:10px;display:none";
bar.innerHTML='<span data-i18n="wbPreviewReady">ホワイトボード結果をプレビュー中</span> <button id="whiteboard-preview-apply" data-i18n="wbApply">本採用</button> <button id="whiteboard-preview-discard" data-i18n="wbDiscard">破棄</button>';
document.body.appendChild(bar);
document.getElementById("whiteboard-preview-apply").onclick=whiteboardApply;
document.getElementById("whiteboard-preview-discard").onclick=whiteboardDiscard;
return bar;
}

function whiteboardReceive(event){
if(event.origin!=="http://127.0.0.1:8190"||!event.data||event.data.type!=="wb.apply")return;
var target=whiteboardFindLayer(event.data.pageId,event.data.layerId);
if(!target){createToastError("Whiteboard","対象コマが現在のページにありません");return;}
if(whiteboardPreview)whiteboardDiscard();
var panel=whiteboardPanelFor(target);var hidden=[];
canvas.getObjects().forEach(function(obj){if(isImage(obj)&&obj!==target&&obj.relatedPoly===panel&&obj.visible){obj.visible=false;hidden.push(obj);}});
changeDoNotSaveHistory();
fabric.Image.fromURL(event.data.imageUrl,function(img){
var center=panel.getCenterPoint();putImageInFrame(img,center.x,center.y,false,false,true,panel);
var preview=canvas.getActiveObject();preview.wbBoardId=event.data.boardId;preview.wbAssetId="asset_g"+event.data.assetId;preview.wbImageUrl=event.data.imageUrl;
whiteboardPreview={image:preview,target:target,panel:panel,hidden:hidden,data:event.data};
changeDoSaveHistory();whiteboardBar().style.display="block";updateLayerPanel();
},{crossOrigin:"anonymous"});
}

function whiteboardApply(){
if(!whiteboardPreview)return;
whiteboardPreview.hidden.forEach(function(obj){canvas.remove(obj);});
whiteboardPreview.panel.wbBoardId=whiteboardPreview.data.boardId;
saveStateByManual();whiteboardBar().style.display="none";whiteboardPreview=null;updateLayerPanel();
}

function whiteboardDiscard(){
if(!whiteboardPreview)return;
changeDoNotSaveHistory();canvas.remove(whiteboardPreview.image);whiteboardPreview.hidden.forEach(function(obj){obj.visible=true;});changeDoSaveHistory();
canvas.renderAll();whiteboardBar().style.display="none";whiteboardPreview=null;updateLayerPanel();
}

window.addEventListener("message",whiteboardReceive);
document.addEventListener("DOMContentLoaded",whiteboardBar);
