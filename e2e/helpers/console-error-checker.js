export const IGNORED_CONSOLE_ERRORS=[
/CORS/i,
/Cross-Origin/i,
/Access-Control-Allow-Origin/i,
/blocked by CORS policy/i,
/Failed to load resource.*CORS/i,
/net::ERR_FAILED/i,
/net::ERR_NAME_NOT_RESOLVED/i,
/net::ERR_TUNNEL_CONNECTION_FAILED/i,
/net::ERR_CONNECTION_REFUSED/i,
/net::ERR_INTERNET_DISCONNECTED/i,
/Failed to fetch/i,
/favicon\.ico/i,
/googletagmanager/i,
/google-analytics/i,
/analytics\.js/i,
/gtag/i,
/cdnjs\.cloudflare\.com/i,
/fonts\.googleapis\.com/i,
/fonts\.gstatic\.com/i,
/Unrecognized feature/i,
/Third-party cookie/i,
/DevTools/i,
/127\.0\.0\.1:7860/i,
/127\.0\.0\.1:8188/i,
/Tagify is not defined/i,
/jscolor is not defined/i,
/Error fetching initial icons/i,
/Service Worker Register Failed/i,
/bad HTTP response code/i,
/Failed to load resource/i,
];
export function shouldIgnoreError(message){
return IGNORED_CONSOLE_ERRORS.some(pattern=>pattern.test(message));
}
export function createConsoleCollector(page){
const errors=[];
const warnings=[];
page.on('console',msg=>{
const text=msg.text();
if(msg.type()==='error'&&!shouldIgnoreError(text)){
errors.push(text);
}
if(msg.type()==='warning'&&!shouldIgnoreError(text)){
warnings.push(text);
}
});
page.on('pageerror',error=>{
const message=error.message||error.toString();
if(!shouldIgnoreError(message)){
errors.push(`PageError: ${message}`);
}
});
return{
getErrors:()=>errors,
getWarnings:()=>warnings,
hasErrors:()=>errors.length>0,
clear:()=>{errors.length=0;warnings.length=0;},
};
}
