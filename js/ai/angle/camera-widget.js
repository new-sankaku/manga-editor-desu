// 3Dカメラウィジェット（アングル選択用）
var cameraWidgetLogger=new SimpleLogger('cameraWidget',LogLevel.DEBUG);

class CameraWidget{
constructor(canvasContainer,options){
options=options||{};
this.canvasContainer=canvasContainer;
this.promptEl=options.promptEl;
this.resetBtn=options.resetBtn;
this.onChange=options.onChange||null;
this.state={azimuth:0,elevation:0,distance:5};
this.liveAzimuth=0;
this.liveElevation=0;
this.liveDistance=5;
this.CENTER=new THREE.Vector3(0,0.5,0);
this.AZIMUTH_RADIUS=1.8;
this.ELEVATION_RADIUS=1.4;
this.ELEV_ARC_X=-0.8;
this.isDragging=false;
this.dragTarget=null;
this.hoveredHandle=null;
this.raycaster=new THREE.Raycaster();
this.mouse=new THREE.Vector2();
this.time=0;
this.dragStartDistance=0;
this.dragStartMouseY=0;
this._animating=false;
this._boundOnMove=null;
this._boundOnUp=null;
this._boundOnResize=null;
this.initThreeJS();
this.bindEvents();
this.updateDisplay();
this.startAnimate();
}
initThreeJS(){
var width=this.canvasContainer.clientWidth||300;
var height=this.canvasContainer.clientHeight||300;
this.scene=new THREE.Scene();
this.scene.background=new THREE.Color(0x0a0a0f);
this.camera=new THREE.PerspectiveCamera(45,width/height,0.1,1000);
this.camera.position.set(4,3.5,4);
this.camera.lookAt(0,0.3,0);
this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
this.renderer.setSize(width,height);
this.renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
this.canvasContainer.appendChild(this.renderer.domElement);
var ambientLight=new THREE.AmbientLight(0xffffff,0.4);
this.scene.add(ambientLight);
var mainLight=new THREE.DirectionalLight(0xffffff,0.8);
mainLight.position.set(5,10,5);
this.scene.add(mainLight);
var fillLight=new THREE.DirectionalLight(0xe93d82,0.3);
fillLight.position.set(-5,5,-5);
this.scene.add(fillLight);
this.gridHelper=new THREE.GridHelper(5,20,0x1a1a2e,0x12121a);
this.gridHelper.position.y=-0.01;
this.scene.add(this.gridHelper);
this.createSubject();
this.createCameraIndicator();
this.createAzimuthRing();
this.createElevationArc();
this.createDistanceHandle();
this.updateVisuals();
}
createGridTexture(){
var canvas=document.createElement('canvas');
var size=256;
canvas.width=size;
canvas.height=size;
var ctx=canvas.getContext('2d');
ctx.fillStyle='#1a1a2a';
ctx.fillRect(0,0,size,size);
ctx.strokeStyle='#2a2a3a';
ctx.lineWidth=1;
var gridSize=16;
for(var i=0;i<=size;i+=gridSize){
ctx.beginPath();
ctx.moveTo(i,0);
ctx.lineTo(i,size);
ctx.stroke();
ctx.beginPath();
ctx.moveTo(0,i);
ctx.lineTo(size,i);
ctx.stroke();
}
var texture=new THREE.CanvasTexture(canvas);
texture.wrapS=THREE.RepeatWrapping;
texture.wrapT=THREE.RepeatWrapping;
texture.repeat.set(4,4);
return texture;
}
createSubject(){
var cardThickness=0.02;
var cardGeo=new THREE.BoxGeometry(1.2,1.2,cardThickness);
var frontMat=new THREE.MeshBasicMaterial({color:0x3a3a4a});
var backMat=new THREE.MeshBasicMaterial({map:this.createGridTexture()});
var edgeMat=new THREE.MeshBasicMaterial({color:0x1a1a2a});
var cardMaterials=[edgeMat,edgeMat,edgeMat,edgeMat,frontMat,backMat];
this.imagePlane=new THREE.Mesh(cardGeo,cardMaterials);
this.imagePlane.position.copy(this.CENTER);
this.scene.add(this.imagePlane);
this.planeMat=frontMat;
var frameGeo=new THREE.EdgesGeometry(cardGeo);
var frameMat=new THREE.LineBasicMaterial({color:0xe93d82});
this.imageFrame=new THREE.LineSegments(frameGeo,frameMat);
this.imageFrame.position.copy(this.CENTER);
this.scene.add(this.imageFrame);
var glowRingGeo=new THREE.RingGeometry(0.55,0.58,64);
var glowRingMat=new THREE.MeshBasicMaterial({
color:0xe93d82,
transparent:true,
opacity:0.4,
side:THREE.DoubleSide
});
this.glowRing=new THREE.Mesh(glowRingGeo,glowRingMat);
this.glowRing.position.set(0,0.01,0);
this.glowRing.rotation.x=-Math.PI/2;
this.scene.add(this.glowRing);
}
createCameraIndicator(){
var camGeo=new THREE.ConeGeometry(0.15,0.4,4);
var camMat=new THREE.MeshStandardMaterial({
color:0xe93d82,
emissive:0xe93d82,
emissiveIntensity:0.5,
metalness:0.8,
roughness:0.2
});
this.cameraIndicator=new THREE.Mesh(camGeo,camMat);
this.scene.add(this.cameraIndicator);
var camGlowGeo=new THREE.SphereGeometry(0.08,16,16);
var camGlowMat=new THREE.MeshBasicMaterial({color:0xff6ba8,transparent:true,opacity:0.8});
this.camGlow=new THREE.Mesh(camGlowGeo,camGlowMat);
this.scene.add(this.camGlow);
}
createAzimuthRing(){
var azRingGeo=new THREE.TorusGeometry(this.AZIMUTH_RADIUS,0.04,16,100);
var azRingMat=new THREE.MeshBasicMaterial({color:0xe93d82,transparent:true,opacity:0.7});
this.azimuthRing=new THREE.Mesh(azRingGeo,azRingMat);
this.azimuthRing.rotation.x=Math.PI/2;
this.azimuthRing.position.y=0.02;
this.scene.add(this.azimuthRing);
var azHandleGeo=new THREE.SphereGeometry(0.16,32,32);
var azHandleMat=new THREE.MeshStandardMaterial({
color:0xe93d82,
emissive:0xe93d82,
emissiveIntensity:0.6,
metalness:0.3,
roughness:0.4
});
this.azimuthHandle=new THREE.Mesh(azHandleGeo,azHandleMat);
this.scene.add(this.azimuthHandle);
var azGlowGeo=new THREE.SphereGeometry(0.22,16,16);
var azGlowMat=new THREE.MeshBasicMaterial({color:0xe93d82,transparent:true,opacity:0.2});
this.azGlow=new THREE.Mesh(azGlowGeo,azGlowMat);
this.scene.add(this.azGlow);
}
createElevationArc(){
var arcPoints=[];
for(var i=0;i<=32;i++){
var angle=((-30+(90*i)/32)*Math.PI)/180;
arcPoints.push(
new THREE.Vector3(
this.ELEV_ARC_X,
this.ELEVATION_RADIUS*Math.sin(angle)+this.CENTER.y,
this.ELEVATION_RADIUS*Math.cos(angle)
)
);
}
var arcCurve=new THREE.CatmullRomCurve3(arcPoints);
var elArcGeo=new THREE.TubeGeometry(arcCurve,32,0.04,8,false);
var elArcMat=new THREE.MeshBasicMaterial({color:0x00ffd0,transparent:true,opacity:0.8});
this.elevationArc=new THREE.Mesh(elArcGeo,elArcMat);
this.scene.add(this.elevationArc);
var elHandleGeo=new THREE.SphereGeometry(0.16,32,32);
var elHandleMat=new THREE.MeshStandardMaterial({
color:0x00ffd0,
emissive:0x00ffd0,
emissiveIntensity:0.6,
metalness:0.3,
roughness:0.4
});
this.elevationHandle=new THREE.Mesh(elHandleGeo,elHandleMat);
this.scene.add(this.elevationHandle);
var elGlowGeo=new THREE.SphereGeometry(0.22,16,16);
var elGlowMat=new THREE.MeshBasicMaterial({color:0x00ffd0,transparent:true,opacity:0.2});
this.elGlow=new THREE.Mesh(elGlowGeo,elGlowMat);
this.scene.add(this.elGlow);
}
createDistanceHandle(){
var distHandleGeo=new THREE.SphereGeometry(0.15,32,32);
var distHandleMat=new THREE.MeshStandardMaterial({
color:0xffb800,
emissive:0xffb800,
emissiveIntensity:0.7,
metalness:0.5,
roughness:0.3
});
this.distanceHandle=new THREE.Mesh(distHandleGeo,distHandleMat);
this.scene.add(this.distanceHandle);
var distGlowGeo=new THREE.SphereGeometry(0.22,16,16);
var distGlowMat=new THREE.MeshBasicMaterial({color:0xffb800,transparent:true,opacity:0.25});
this.distGlow=new THREE.Mesh(distGlowGeo,distGlowMat);
this.scene.add(this.distGlow);
}
updateDistanceLine(start,end){
if(this.distanceTube){
this.scene.remove(this.distanceTube);
this.distanceTube.geometry.dispose();
this.distanceTube.material.dispose();
}
var path=new THREE.LineCurve3(start,end);
var tubeGeo=new THREE.TubeGeometry(path,1,0.025,8,false);
var tubeMat=new THREE.MeshBasicMaterial({color:0xffb800,transparent:true,opacity:0.8});
this.distanceTube=new THREE.Mesh(tubeGeo,tubeMat);
this.scene.add(this.distanceTube);
}
updateVisuals(){
var azRad=(this.liveAzimuth*Math.PI)/180;
var elRad=(this.liveElevation*Math.PI)/180;
var visualDist=2.6-(this.liveDistance/10)*2.0;
var camX=visualDist*Math.sin(azRad)*Math.cos(elRad);
var camY=this.CENTER.y+visualDist*Math.sin(elRad);
var camZ=visualDist*Math.cos(azRad)*Math.cos(elRad);
this.cameraIndicator.position.set(camX,camY,camZ);
this.cameraIndicator.lookAt(this.CENTER);
this.cameraIndicator.rotateX(Math.PI/2);
this.camGlow.position.copy(this.cameraIndicator.position);
var azX=this.AZIMUTH_RADIUS*Math.sin(azRad);
var azZ=this.AZIMUTH_RADIUS*Math.cos(azRad);
this.azimuthHandle.position.set(azX,0.16,azZ);
this.azGlow.position.copy(this.azimuthHandle.position);
var elY=this.CENTER.y+this.ELEVATION_RADIUS*Math.sin(elRad);
var elZ=this.ELEVATION_RADIUS*Math.cos(elRad);
this.elevationHandle.position.set(this.ELEV_ARC_X,elY,elZ);
this.elGlow.position.copy(this.elevationHandle.position);
var distT=0.15+((10-this.liveDistance)/10)*0.7;
this.distanceHandle.position.lerpVectors(this.CENTER,this.cameraIndicator.position,distT);
this.distGlow.position.copy(this.distanceHandle.position);
this.updateDistanceLine(this.CENTER.clone(),this.cameraIndicator.position.clone());
this.glowRing.rotation.z+=0.005;
}
bindEvents(){
var canvas=this.renderer.domElement;
var self=this;
canvas.addEventListener('mousedown',function(e){self.onPointerDown(e);});
this._boundOnMove=function(e){self.onPointerMove(e);};
this._boundOnUp=function(){self.onPointerUp();};
this._boundOnResize=function(){self.onResize();};
window.addEventListener('mousemove',this._boundOnMove);
window.addEventListener('mouseup',this._boundOnUp);
canvas.addEventListener('touchstart',function(e){
e.preventDefault();
self.onPointerDown({clientX:e.touches[0].clientX,clientY:e.touches[0].clientY});
},{passive:false});
window.addEventListener('touchmove',function(e){
if(self.isDragging){
e.preventDefault();
self.onPointerMove({clientX:e.touches[0].clientX,clientY:e.touches[0].clientY});
}
},{passive:false});
window.addEventListener('touchend',this._boundOnUp);
window.addEventListener('resize',this._boundOnResize);
if(this.resetBtn){
this.resetBtn.addEventListener('click',function(){self.resetToDefaults();});
}
}
getMousePos(event){
var rect=this.renderer.domElement.getBoundingClientRect();
this.mouse.x=((event.clientX-rect.left)/rect.width)*2-1;
this.mouse.y=-((event.clientY-rect.top)/rect.height)*2+1;
}
setHandleScale(handle,glow,scale){
handle.scale.setScalar(scale);
if(glow) glow.scale.setScalar(scale);
}
onPointerDown(event){
this.getMousePos(event);
this.raycaster.setFromCamera(this.mouse,this.camera);
var handles=[
{mesh:this.azimuthHandle,glow:this.azGlow,name:'azimuth'},
{mesh:this.elevationHandle,glow:this.elGlow,name:'elevation'},
{mesh:this.distanceHandle,glow:this.distGlow,name:'distance'}
];
for(var i=0;i<handles.length;i++){
var h=handles[i];
if(this.raycaster.intersectObject(h.mesh).length>0){
this.isDragging=true;
this.dragTarget=h.name;
this.setHandleScale(h.mesh,h.glow,1.3);
this.renderer.domElement.style.cursor='grabbing';
if(h.name==='distance'){
this.dragStartDistance=this.liveDistance;
this.dragStartMouseY=this.mouse.y;
}
return;
}
}
}
onPointerMove(event){
this.getMousePos(event);
this.raycaster.setFromCamera(this.mouse,this.camera);
if(!this.isDragging){
var handles=[
{mesh:this.azimuthHandle,glow:this.azGlow,name:'azimuth'},
{mesh:this.elevationHandle,glow:this.elGlow,name:'elevation'},
{mesh:this.distanceHandle,glow:this.distGlow,name:'distance'}
];
var foundHover=null;
for(var i=0;i<handles.length;i++){
var h=handles[i];
if(this.raycaster.intersectObject(h.mesh).length>0){
foundHover=h;
break;
}
}
if(this.hoveredHandle&&this.hoveredHandle!==foundHover){
this.setHandleScale(this.hoveredHandle.mesh,this.hoveredHandle.glow,1.0);
}
if(foundHover){
this.setHandleScale(foundHover.mesh,foundHover.glow,1.15);
this.renderer.domElement.style.cursor='grab';
this.hoveredHandle=foundHover;
}else{
this.renderer.domElement.style.cursor='default';
this.hoveredHandle=null;
}
return;
}
var plane=new THREE.Plane();
var intersect=new THREE.Vector3();
if(this.dragTarget==='azimuth'){
plane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0,1,0),new THREE.Vector3(0,0,0));
if(this.raycaster.ray.intersectPlane(plane,intersect)){
var angle=Math.atan2(intersect.x,intersect.z)*(180/Math.PI);
if(angle<0) angle+=360;
this.liveAzimuth=Math.max(0,Math.min(360,angle));
this.state.azimuth=Math.round(this.liveAzimuth);
this.updateDisplay();
this.updateVisuals();
}
}else if(this.dragTarget==='elevation'){
var elevPlane=new THREE.Plane(new THREE.Vector3(1,0,0),-this.ELEV_ARC_X);
if(this.raycaster.ray.intersectPlane(elevPlane,intersect)){
var relY=intersect.y-this.CENTER.y;
var relZ=intersect.z;
var angle2=Math.atan2(relY,relZ)*(180/Math.PI);
angle2=Math.max(-30,Math.min(60,angle2));
this.liveElevation=angle2;
this.state.elevation=Math.round(this.liveElevation);
this.updateDisplay();
this.updateVisuals();
}
}else if(this.dragTarget==='distance'){
var deltaY=this.mouse.y-this.dragStartMouseY;
var sensitivity=3;
var newDist=this.dragStartDistance-deltaY*sensitivity;
this.liveDistance=Math.max(0,Math.min(10,newDist));
this.state.distance=Math.round(this.liveDistance*10)/10;
this.updateDisplay();
this.updateVisuals();
}
}
onPointerUp(){
if(this.isDragging){
var handles=[
{mesh:this.azimuthHandle,glow:this.azGlow},
{mesh:this.elevationHandle,glow:this.elGlow},
{mesh:this.distanceHandle,glow:this.distGlow}
];
for(var i=0;i<handles.length;i++){
this.setHandleScale(handles[i].mesh,handles[i].glow,1.0);
}
}
this.isDragging=false;
this.dragTarget=null;
this.renderer.domElement.style.cursor='default';
}
onResize(){
var w=this.canvasContainer.clientWidth;
var h=this.canvasContainer.clientHeight;
if(w===0||h===0) return;
this.camera.aspect=w/h;
this.camera.updateProjectionMatrix();
this.renderer.setSize(w,h);
}
startAnimate(){
if(this._animating) return;
this._animating=true;
var self=this;
function loop(){
if(!self._animating) return;
requestAnimationFrame(loop);
self.time+=0.01;
var pulse=1+Math.sin(self.time*2)*0.03;
self.camGlow.scale.setScalar(pulse);
self.glowRing.rotation.z+=0.003;
self.renderer.render(self.scene,self.camera);
}
loop();
}
generatePrompt(){
var hAngle=this.state.azimuth%360;
var hDirection;
if(hAngle<22.5||hAngle>=337.5){
hDirection='front view';
}else if(hAngle<67.5){
hDirection='front-right quarter view';
}else if(hAngle<112.5){
hDirection='right side view';
}else if(hAngle<157.5){
hDirection='back-right quarter view';
}else if(hAngle<202.5){
hDirection='back view';
}else if(hAngle<247.5){
hDirection='back-left quarter view';
}else if(hAngle<292.5){
hDirection='left side view';
}else{
hDirection='front-left quarter view';
}
var vDirection;
if(this.state.elevation<-15){
vDirection='low-angle shot';
}else if(this.state.elevation<15){
vDirection='eye-level shot';
}else if(this.state.elevation<45){
vDirection='elevated shot';
}else{
vDirection='high-angle shot';
}
var distance;
if(this.state.distance<2){
distance='wide shot';
}else if(this.state.distance<6){
distance='medium shot';
}else{
distance='close-up';
}
return '<sks> '+hDirection+' '+vDirection+' '+distance;
}
updateDisplay(){
var prompt=this.generatePrompt();
if(this.promptEl) this.promptEl.textContent=prompt;
if(this.onChange) this.onChange(prompt);
}
resetToDefaults(){
this.state.azimuth=0;
this.state.elevation=0;
this.state.distance=5;
this.liveAzimuth=0;
this.liveElevation=0;
this.liveDistance=5;
this.updateVisuals();
this.updateDisplay();
}
updateImage(url){
if(!url) return;
var self=this;
var img=new Image();
img.onload=function(){
var tex=new THREE.Texture(img);
tex.needsUpdate=true;
self.planeMat.map=tex;
self.planeMat.color.set(0xffffff);
self.planeMat.needsUpdate=true;
var ar=img.width/img.height;
var maxSize=1.5;
var scaleX,scaleY;
if(ar>1){
scaleX=maxSize;
scaleY=maxSize/ar;
}else{
scaleY=maxSize;
scaleX=maxSize*ar;
}
self.imagePlane.scale.set(scaleX,scaleY,1);
self.imageFrame.scale.set(scaleX,scaleY,1);
};
img.src=url;
}
destroy(){
this._animating=false;
if(this._boundOnMove) window.removeEventListener('mousemove',this._boundOnMove);
if(this._boundOnUp) window.removeEventListener('mouseup',this._boundOnUp);
if(this._boundOnResize) window.removeEventListener('resize',this._boundOnResize);
if(this.renderer){
this.renderer.dispose();
if(this.renderer.domElement&&this.renderer.domElement.parentNode){
this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
}
}
}
}
