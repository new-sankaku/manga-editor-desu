
let comfyUI=null;
let comfyUIUrls=null;

let sdWebUI=null;
let sdWebUIUrls=null;


document.addEventListener('DOMContentLoaded',()=>{
sdWebUI=new SDWebUIEndpoints();
sdWebUIUrls=sdWebUI.urls;

comfyUI=new ComfyUIEndpoints();
comfyUIUrls=comfyUI.urls;

setInterval(apiHeartbeat,1000*15);
$('apiHeartbeatCheckbox').addEventListener('change',function () {
apiHeartbeat();
});
apiHeartbeat();
});

