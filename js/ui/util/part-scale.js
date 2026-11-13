// part-scale.js - 画像の一部分だけを範囲で選び、拡大縮小して画像へ戻す
//
// 流れ：右クリック「範囲を拡大縮小」→ 枠を合わせて Enter → 切り出した部分を拡大縮小・移動して Enter で確定
// 入り口と抜け方は ModeManager.partScale（mode-manager.js）の1か所。
// ESC・別のモードへの切り替え・選択を外す、のどれで抜けても cancel() を通り、画像は元に戻る。
//
// 切り出した場所は透明になる（画像編集ソフトで選択範囲を変形したときと同じ）。
// 画素は画像の元の解像度のまま扱う。画面の表示倍率で描き直すと、拡大縮小していない所まで粗くなる。
var PartScale={
_image:null,         // 対象の画像
_frame:null,         // 1段目：範囲の枠
_piece:null,         // 2段目：切り出した部分
_pieceCanvas:null,   // 切り出した画素（元の解像度）
_holedCanvas:null,   // 切り出した所を透明にした画像全体
_savedElement:null,  // 取り消したときに戻す元の画像
_switching:false,    // 枠→部分へ選択を移す間は、選択の変化で取り消さない
_committing:false,

isActive:function(){
return PartScale._image!==null;
},

start:function(targetImage){
if(!targetImage||!isImage(targetImage)){
createToastError("Select Image!","");
return;
}
var img=targetImage;
PartScale._image=img;
var frame=new fabric.Rect({
originX:'center',
originY:'center',
left:img.getCenterPoint().x,
top:img.getCenterPoint().y,
width:img.width*Math.abs(img.scaleX)/2,
height:img.height*Math.abs(img.scaleY)/2,
angle:img.angle,
fill:'rgba(54,253,0,0.08)',
stroke:'rgba(0,0,0,0)',
strokeWidth:0,
borderColor:'#36fd00',
cornerColor:'green',
lockRotation:true,
excludeFromLayerPanel:true,
excludeFromExport:true
});
frame.setControlsVisibility({mtr:false});
setNotSave(frame);
PartScale._frame=frame;
PartScale._switching=true;
addByNotSave(frame);
canvas.setActiveObject(frame);
PartScale._switching=false;
canvas.requestRenderAll();
showCanvasHelpText(getText('partScaleSelectHelpText'),'Enter');
},

// Enter キー。1段目なら切り出し、2段目なら画像へ戻す
next:function(){
if(!PartScale.isActive()||PartScale._committing)return;
if(PartScale._frame){
PartScale._cut();
}else if(PartScale._piece){
PartScale._commit();
}
},

// 画像の元の画素での位置へ直す（回転・反転・拡大した画像でも合う）
_toImagePixel:function(point){
var img=PartScale._image;
var inv=fabric.util.invertTransform(img.calcTransformMatrix());
var p=fabric.util.transformPoint(point,inv);
return {
x:p.x+img.width/2+(img.cropX||0),
y:p.y+img.height/2+(img.cropY||0)
};
},

_cut:function(){
var img=PartScale._image;
var frame=PartScale._frame;
var src=img._originalElement||img.getElement();
// 端数は四捨五入する。切り上げと切り捨てを混ぜると、計算の誤差で範囲が1画素ずれて絵が半画素ずれる
var corners=frame.getCoords(true,true).map(PartScale._toImagePixel);
var xs=corners.map(function(p){return p.x;});
var ys=corners.map(function(p){return p.y;});
var minX=Math.max(img.cropX||0,Math.round(Math.min.apply(null,xs)));
var minY=Math.max(img.cropY||0,Math.round(Math.min.apply(null,ys)));
var maxX=Math.min((img.cropX||0)+img.width,Math.round(Math.max.apply(null,xs)));
var maxY=Math.min((img.cropY||0)+img.height,Math.round(Math.max.apply(null,ys)));
var w=maxX-minX;
var h=maxY-minY;
if(w<2||h<2){
createToastError(getText('partScaleOutside'),"");
return;
}

var pieceCanvas=document.createElement('canvas');
pieceCanvas.width=w;
pieceCanvas.height=h;
pieceCanvas.getContext('2d').drawImage(src,minX,minY,w,h,0,0,w,h);

var srcW=src.naturalWidth||src.width;
var srcH=src.naturalHeight||src.height;
var holed=document.createElement('canvas');
holed.width=srcW;
holed.height=srcH;
var hctx=holed.getContext('2d');
hctx.drawImage(src,0,0);
hctx.clearRect(minX,minY,w,h);

PartScale._savedElement=src;
PartScale._pieceCanvas=pieceCanvas;
PartScale._holedCanvas=holed;
// 作業中だけ穴の空いた画像を見せる。履歴には積まない（確定か取り消しのどちらかで必ず差し替わる）
img.setElement(holed,{width:img.width,height:img.height});
img.dirty=true;

// 切り出した部分は、元の画像と同じ向き・倍率で同じ場所に置く
var localCenter=new fabric.Point(
minX+w/2-img.width/2-(img.cropX||0),
minY+h/2-img.height/2-(img.cropY||0)
);
var center=fabric.util.transformPoint(localCenter,img.calcTransformMatrix());
var piece=new fabric.Image(pieceCanvas,{
originX:'center',
originY:'center',
left:center.x,
top:center.y,
angle:img.angle,
scaleX:img.scaleX,
scaleY:img.scaleY,
flipX:img.flipX,
flipY:img.flipY,
skewX:img.skewX,
skewY:img.skewY,
opacity:img.opacity,
borderColor:'#36fd00',
cornerColor:'green',
// 回すと画素の並びに合わなくなり、確定のときに斜めの描き直しでぼやける。
// 裏返しも同じ理由で止める（反転は右クリックの「左右反転」「上下反転」がある）
lockRotation:true,
lockScalingFlip:true,
lockSkewingX:true,
lockSkewingY:true,
excludeFromLayerPanel:true,
excludeFromExport:true
});
piece.setControlsVisibility({mtr:false});
if(img.filters&&img.filters.length>0){
piece.filters=img.filters.slice();
piece.applyFilters();
}
setNotSave(piece);

PartScale._switching=true;
removeByNotSave(frame);
PartScale._frame=null;
addByNotSave(piece);
PartScale._piece=piece;
canvas.setActiveObject(piece);
PartScale._switching=false;
canvas.requestRenderAll();
showCanvasHelpText(getText('partScaleTransformHelpText'),'Enter');
},

_commit:function(){
var img=PartScale._image;
var piece=PartScale._piece;
var holed=PartScale._holedCanvas;
var pieceCanvas=PartScale._pieceCanvas;

// 部分の変形を画像の元の画素の座標へ写す。回転・裏返しは止めてあるので、倍率と位置だけになる
var m=fabric.util.multiplyTransformMatrices(
fabric.util.invertTransform(img.calcTransformMatrix()),
piece.calcTransformMatrix()
);
// 位置と大きさを画素の境目にそろえる。端数のまま描くと、隣どうしの画素が混ざって線がにじむ
var toW=Math.max(1,Math.round(pieceCanvas.width*m[0]));
var toH=Math.max(1,Math.round(pieceCanvas.height*m[3]));
var centerX=m[4]+img.width/2+(img.cropX||0);
var centerY=m[5]+img.height/2+(img.cropY||0);
var toLeft=Math.round(centerX-toW/2);
var toTop=Math.round(centerY-toH/2);

PartScale._committing=true;
PartScale._resize(pieceCanvas,toW,toH).then(function(resized){
var out=document.createElement('canvas');
out.width=holed.width;
out.height=holed.height;
var ctx=out.getContext('2d');
ctx.drawImage(holed,0,0);
// 等倍で整数の位置に置くので、ここでは描き直しが起きない。画像からはみ出した所は捨てる
ctx.drawImage(resized,toLeft,toTop);
return PartScale._toImageElement(out);
}).then(function(el){
var target=PartScale._image;
var width=target.width;
var height=target.height;
PartScale._removePiece();
PartScale._reset();
target.setElement(el,{width:width,height:height});
target.dirty=true;
ModeManager.clearAll();
canvas.setActiveObject(target);
canvas.requestRenderAll();
commitHistory();
updateLayerPanel();
}).catch(function(e){
uiLogger.error('PartScale commit failed',e);
createToastError(getText('partScaleFailed'),String(e));
PartScale._committing=false;
ModeManager.clearAll();
});
},

// 縮小・拡大は pica（third/pica/）の mks2013 で行う。
// ブラウザの drawImage の縮小は方式が決まっておらず（imageSmoothingQuality の中身は仕様で定めていない）、
// 細い線が薄くなる。mks2013 は pica の既定で、縮小と同時に軽く締める方式。
// Web Worker は使わない。pica は Blob の URL から Worker を起こすが、file:// で動くかは未検証
_pica:null,
_resize:function(src,toW,toH){
if(toW===src.width&&toH===src.height){
return Promise.resolve(src);
}
if(!PartScale._pica){
PartScale._pica=pica({features:['js','wasm']});
}
var dest=document.createElement('canvas');
dest.width=toW;
dest.height=toH;
return PartScale._pica.resize(src,dest,{filter:'mks2013'});
},

// 画像の要素は HTMLImageElement に揃える（_element.src を読む処理がある）
_toImageElement:function(canvasEl){
return new Promise(function(resolve,reject){
var el=new Image();
el.onload=function(){resolve(el);};
el.onerror=function(){reject(new Error('image load failed'));};
el.src=canvasEl.toDataURL('image/png');
});
},

// ModeManager.partScale.disable() からだけ呼ぶ。確定前なら画像を元に戻す
cancel:function(){
if(!PartScale.isActive())return;
var img=PartScale._image;
if(PartScale._savedElement){
img.setElement(PartScale._savedElement,{width:img.width,height:img.height});
img.dirty=true;
}
PartScale._switching=true;
if(PartScale._frame){
removeByNotSave(PartScale._frame);
}
PartScale._removePiece();
PartScale._switching=false;
PartScale._reset();
canvas.requestRenderAll();
},

_removePiece:function(){
if(PartScale._piece){
removeByNotSave(PartScale._piece);
}
},

_reset:function(){
PartScale._image=null;
PartScale._frame=null;
PartScale._piece=null;
PartScale._pieceCanvas=null;
PartScale._holedCanvas=null;
PartScale._savedElement=null;
PartScale._committing=false;
},

// 枠か部分から選択が外れたら取り消す（切り抜きと同じ扱い）
_onSelectionChanged:function(){
if(!PartScale.isActive()||PartScale._switching||PartScale._committing)return;
var active=canvas.getActiveObject();
if(active&&(active===PartScale._frame||active===PartScale._piece))return;
ModeManager.clearAll();
}
};

canvas.on('selection:cleared',PartScale._onSelectionChanged);
canvas.on('selection:updated',PartScale._onSelectionChanged);
