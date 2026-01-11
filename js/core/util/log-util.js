

function objectToJsonString(obj) {
const seen=new WeakSet();
return JSON.stringify(obj,(key,value)=>{
if (typeof value==="object"&&value!==null) {
if (seen.has(value)) {
return "[Circular]";
}
seen.add(value);
}
if (typeof value==="function") {
return "[Function]";
}
if (value instanceof HTMLElement) {
return `[HTMLElement: ${value.tagName}]`;
}
return value;
},2);
}


const syncLog=(...args)=>{
const getDetailedInfo=(arg)=>{
if (arg===null) return 'null';
if (arg===undefined) return 'undefined';
if (typeof arg==='function') return `[Function: ${arg.name || 'anonymous'}]`;
if (typeof arg==='symbol') return arg.toString();
if (typeof arg!=='object') return arg;

if (Array.isArray(arg)) {
return `[Array(${arg.length})] ${JSON.stringify(arg, (key, value) => {
        if (typeof value === 'function') return '[Function]';
        if (value && typeof value === 'object' && !Array.isArray(value)) return '[Object]';
        return value;
      }, 2)}`;
}

return `[Object] ${JSON.stringify(arg, (key, value) => {
      if (typeof value === 'function') return '[Function]';
      if (value && typeof value === 'object' && !Array.isArray(value)) return '[Object]';
      return value;
    }, 2)}`;
};

const formattedArgs=args.map(getDetailedInfo);
console.log(...formattedArgs);
};