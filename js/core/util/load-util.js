// ユーティリティ関数：エラーハンドリングとログ出力を行う
async function safeLoad(loadFunction,...args) {
try {
await loadFunction(...args);
console.log(`Successfully loaded: ${args[0]}`);
} catch (error) {
console.error(`Failed to load: ${args[0]}`,error);
}
}

// JavaScript ファイルを読み込む関数
async function loadJS(filePath,appendTo='body') {
const script=document.createElement('script');
script.src=filePath;
script.type='text/javascript';
const target=appendTo==='head' ? document.head : document.body;
return new Promise((resolve,reject)=>{
script.onload=resolve;
script.onerror=reject;
target.appendChild(script);
});
}

// CSS ファイルを読み込む関数
async function loadCSS(filePath) {
const link=document.createElement('link');
link.href=filePath;
link.rel='stylesheet';
link.type='text/css';
return new Promise((resolve,reject)=>{
link.onload=resolve;
link.onerror=reject;
document.head.appendChild(link);
});
}

// 画像を読み込む関数
async function loadImage(filePath,appendTo,altText='') {
const img=document.createElement('img');
img.src=filePath;
img.alt=altText;
return new Promise((resolve,reject)=>{
img.onload=()=>{
document.querySelector(appendTo).appendChild(img);
resolve();
};
img.onerror=reject;
});
}

// HTMLを読み込む関数
async function loadHTML(filePath,appendTo) {
const response=await fetch(filePath);
if (!response.ok) throw new Error('Network response was not ok');
const html=await response.text();
document.querySelector(appendTo).innerHTML=html;
}

// 音声ファイルを読み込む関数
function loadAudio(filePath,appendTo) {
const audio=document.createElement('audio');
audio.src=filePath;
audio.controls=true;
document.querySelector(appendTo).appendChild(audio);
}

// 動画ファイルを読み込む関数
function loadVideo(filePath,appendTo) {
const video=document.createElement('video');
video.src=filePath;
video.controls=true;
document.querySelector(appendTo).appendChild(video);
}

// iframeを使用してファイルを読み込む関数
function loadIframe(filePath,appendTo) {
const iframe=document.createElement('iframe');
iframe.src=filePath;
document.querySelector(appendTo).appendChild(iframe);
}

// // 使用例
// async function loadResources() {
//   await safeLoad(loadJS, 'path/to/script.js', 'head');
//   await safeLoad(loadCSS, 'path/to/styles.css');
//   await safeLoad(loadImage, 'path/to/image.jpg', '#imageContainer', 'Description of image');
//   await safeLoad(loadHTML, 'path/to/content.html', '#htmlContainer');
//   loadAudio('path/to/audio.mp3', '#audioContainer');
//   loadVideo('path/to/video.mp4', '#videoContainer');
//   loadIframe('path/to/page.html', '#iframeContainer');
// }

// // リソースの読み込みを開始
// loadResources();