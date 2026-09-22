// Service Worker: Cache management for HTTP/HTTPS deployment
var CACHE_VERSION='manga-editor-v4-local1';

// Fingerprinted or rarely-changing assets. Served cache-first: the URL is
// expected to change (?v=x.y) when the content changes.
var STATIC_EXTENSIONS=[
'.css','.js','.png','.jpg','.jpeg','.gif','.svg','.ico',
'.woff','.woff2','.ttf','.eot','.otf',
'.json'
];

// Documents are NOT cache-first. Their URLs never change, so cache-first would
// pin an old <head> (canonical, JSON-LD, meta) until CACHE_VERSION was bumped
// by hand. They use stale-while-revalidate instead: the cached copy is served
// immediately so offline still works, and the cache is refreshed in the
// background so the next load is current.
var DOCUMENT_EXTENSIONS=['.html'];

function isStaticAsset(url){
var pathname=url.pathname.toLowerCase();
return STATIC_EXTENSIONS.some(function(ext){
return pathname.endsWith(ext);
});
}

function isDocument(request,url){
if(request.mode==='navigate'){
return true;
}
var pathname=url.pathname.toLowerCase();
return DOCUMENT_EXTENSIONS.some(function(ext){
return pathname.endsWith(ext);
});
}

function isApiCall(url){
return url.pathname.includes('/api/');
}

self.addEventListener('install',function(event){
self.skipWaiting();
});

self.addEventListener('activate',function(event){
event.waitUntil(
caches.keys().then(function(keys){
return Promise.all(
keys.filter(function(key){
return key!==CACHE_VERSION;
}).map(function(key){
return caches.delete(key);
})
);
}).then(function(){
return self.clients.claim();
})
);
});

self.addEventListener('fetch',function(event){
var url=new URL(event.request.url);

if(url.protocol==='file:'){
return;
}

if(!url.pathname.startsWith('/')){
return;
}

if(event.request.method!=='GET'){
return;
}

if(isApiCall(url)){
event.respondWith(
fetch(event.request).then(function(response){
var clone=response.clone();
caches.open(CACHE_VERSION).then(function(cache){
cache.put(event.request,clone);
});
return response;
}).catch(function(){
return caches.match(event.request);
})
);
return;
}

if(isDocument(event.request,url)){
event.respondWith(
caches.open(CACHE_VERSION).then(function(cache){
return cache.match(event.request).then(function(cached){
var fromNetwork=fetch(event.request).then(function(response){
if(response&&response.status===200&&response.type==='basic'){
cache.put(event.request,response.clone());
}
return response;
});
if(cached){
event.waitUntil(fromNetwork.catch(function(){}));
return cached;
}
return fromNetwork;
});
})
);
return;
}

if(isStaticAsset(url)){
event.respondWith(
caches.match(event.request).then(function(cached){
if(cached){
return cached;
}
return fetch(event.request).then(function(response){
if(!response||response.status!==200||response.type!=='basic'){
return response;
}
var clone=response.clone();
caches.open(CACHE_VERSION).then(function(cache){
cache.put(event.request,clone);
});
return response;
});
})
);
return;
}

event.respondWith(
fetch(event.request).catch(function(){
return caches.match(event.request);
})
);
});
