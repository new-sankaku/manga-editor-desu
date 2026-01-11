const isPWAEligible=()=>{
if (typeof window==="undefined") return false;
const isSecureContext=
window.isSecureContext||
location.hostname==="localhost"||
location.hostname==="127.0.0.1";
const isValidProtocol=
window.location.protocol==="https:"||
(window.location.protocol==="http:"&&
(location.hostname==="localhost"||location.hostname==="127.0.0.1"));
const isValidPath=window.location.pathname.startsWith("/");
return (
"serviceWorker" in navigator&&
isSecureContext&&
isValidProtocol&&
isValidPath
);
};

let deferredPrompt;
let registration;

if (typeof window!=="undefined") {
window.addEventListener("load",function () {
if (isPWAEligible()) {
navigator.serviceWorker
.register("/SP-MangaEditer/service-worker.js")
.then(function (reg) {
registration=reg;
serviceLogger.info("Service Worker Register Success:",registration.scope);
checkInstallState();
})
.catch(function (error) {
serviceLogger.error("Service Worker Register Failed:",error);
});
}
});
}

window.addEventListener("beforeinstallprompt",(e)=>{
e.preventDefault();
deferredPrompt=e;
updateInstallButtonVisibility(true);
});

window.addEventListener("appinstalled",(e)=>{
deferredPrompt=null;
updateInstallButtonVisibility(false);
});


async function clearCache() {
try {
const keys=await caches.keys();
await Promise.all(keys.map((key)=>caches.delete(key)));
return true;
} catch (err) {
serviceLogger.error("Cache clear failed:",err);
return false;
}
}

function checkInstallState() {
if (
window.matchMedia("(display-mode: standalone)").matches||
window.navigator.standalone===true
) {
updateInstallButtonVisibility(false);
} else {
updateInstallButtonVisibility(true);
}
}

function updateInstallButtonVisibility(showInstall) {
const installButton=$("pwa-install-button");

if (!installButton) return;

const canInstall=
typeof window!=='undefined'&&
'serviceWorker' in navigator&&
(window.location.protocol==='https:'||
(window.location.protocol==='http:'&&
(window.location.hostname==='localhost'||
window.location.hostname==='127.0.0.1')))&&
deferredPrompt&&
showInstall;

installButton.style.display=canInstall ? 'block' : 'none';
}

document.addEventListener("DOMContentLoaded",function () {
const installButton=$("pwa-install-button");
installButton.addEventListener("click",async ()=>{
if (deferredPrompt) {
deferredPrompt.prompt();
const {outcome}=await deferredPrompt.userChoice;
if (outcome==="accepted") {
deferredPrompt=null;
updateInstallButtonVisibility(false);
}
}
});

checkInstallState();
});
