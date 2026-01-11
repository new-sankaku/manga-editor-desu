const LogLevel={
TRACE: 0,
DEBUG: 1,
INFO: 2,
WARN: 3,
ERROR: 4,
SILENT: 5
};

function SimpleLogger(moduleName,defaultLevel=LogLevel.INFO) {
let currentLevel=defaultLevel;

function getCallerMethodName() {
try {
const stackFrames=StackTrace.getSync();

for (let i=0;i<stackFrames.length;i++) {
const frame=stackFrames[i];
const fileName=frame.getFileName()||'';

if (!fileName.includes('stacktrace')&&!fileName.includes('logger.js')) {
const functionName=frame.getFunctionName()||frame.getMethodName()||'anonymous';

let fileNameShort=fileName ? fileName.split('/').pop() : 'unknown';
fileNameShort=fileNameShort.split('?')[0];

const lineNumber=frame.getLineNumber()||'';
return `${fileNameShort}:${lineNumber} ${functionName}`;
}
}

return 'unknown';
} catch (e) {
return 'unknown';
}
}

function getFullStackTrace() {
try {
const stackFrames=StackTrace.getSync();
let fullTrace=[];

for (let i=0;i<stackFrames.length;i++) {
const frame=stackFrames[i];
const fileName=frame.getFileName()||'unknown';
const fileNameShort=fileName.split('/').pop().split('\\').pop();
const functionName=frame.getFunctionName()||frame.getMethodName()||'anonymous';
const lineNumber=frame.getLineNumber()||'';
const columnNumber=frame.getColumnNumber()||'';

fullTrace.push(`    at ${functionName} (${fileNameShort}:${lineNumber}:${columnNumber})`);
}

return fullTrace.join('\n');
} catch (e) {
return 'Missing Stacktrace: '+e.message;
}
}

function formatMessage(level,message,methodName) {
const caller=methodName||getCallerMethodName();
const time=new Date().toTimeString().split(' ')[0];

let emoji='⬛ ';
let colorCode='';

switch(level) {
case 'WARN':
emoji='🟧 ';
colorCode='\x1b[33m';
break;
case 'ERROR':
emoji='🟥 ';
colorCode='\x1b[31m';
break;
default:
colorCode='\x1b[0m';
}

const resetCode='\x1b[0m';
return `${colorCode}${emoji}${time} ${level} [${moduleName}] [${caller}] ${message}${resetCode}`;
}

function isValidMethodName(str) {
return typeof str==='string'&&
str.includes(':')&&
!str.startsWith('[{')&&
!str.startsWith('{');
}

return {
trace: function(...args) {
if (currentLevel<=LogLevel.TRACE) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

console.log(formatMessage('TRACE',message,methodName));
}
},

debug: function(...args) {
if (currentLevel<=LogLevel.DEBUG) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

console.log(formatMessage('DEBUG',message,methodName));
}
},

info: function(...args) {
if (currentLevel<=LogLevel.INFO) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

console.info(formatMessage('INFO',message,methodName));
}
},

warn: function(...args) {
if (currentLevel<=LogLevel.WARN) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

console.warn(formatMessage('WARN',message,methodName));
}
},

error: function(...args) {
if (currentLevel<=LogLevel.ERROR) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

console.error(formatMessage('ERROR',message,methodName));
}
},

traceWithStack: function(...args) {
if (currentLevel<=LogLevel.TRACE) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

const formattedMessage=formatMessage('TRACE',message,methodName);
const stackTrace=getFullStackTrace();
console.log(`${formattedMessage}\nStack Trace:\n${stackTrace}`);
}
},

debugWithStack: function(...args) {
if (currentLevel<=LogLevel.DEBUG) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

const formattedMessage=formatMessage('DEBUG',message,methodName);
const stackTrace=getFullStackTrace();
console.log(`${formattedMessage}\nStack Trace:\n${stackTrace}`);
}
},

infoWithStack: function(...args) {
if (currentLevel<=LogLevel.INFO) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

const formattedMessage=formatMessage('INFO',message,methodName);
const stackTrace=getFullStackTrace();
console.info(`${formattedMessage}\nStack Trace:\n${stackTrace}`);
}
},

warnWithStack: function(...args) {
if (currentLevel<=LogLevel.WARN) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

const formattedMessage=formatMessage('WARN',message,methodName);
const stackTrace=getFullStackTrace();
console.warn(`${formattedMessage}\nStack Trace:\n${stackTrace}`);
}
},

errorWithStack: function(...args) {
if (currentLevel<=LogLevel.ERROR) {
let methodName=null;
let messageArgs=args;

if (args.length>1&&isValidMethodName(args[args.length-1])) {
methodName=args[args.length-1];
messageArgs=args.slice(0,args.length-1);
}

const message=messageArgs.map(arg=>
typeof arg==='object' ? JSON.stringify(arg) : String(arg)
).join(' ');

const formattedMessage=formatMessage('ERROR',message,methodName);
const stackTrace=getFullStackTrace();
console.error(`${formattedMessage}\nStack Trace:\n${stackTrace}`);
}
},

setLevel: function(level) {
if (typeof level==='string') {
switch (level.toLowerCase()) {
case 'trace': currentLevel=LogLevel.TRACE;break;
case 'debug': currentLevel=LogLevel.DEBUG;break;
case 'info': currentLevel=LogLevel.INFO;break;
case 'warn': currentLevel=LogLevel.WARN;break;
case 'error': currentLevel=LogLevel.ERROR;break;
case 'silent': currentLevel=LogLevel.SILENT;break;
default: currentLevel=LogLevel.INFO;
}
} else {
currentLevel=level;
}
return currentLevel;
},

getLevel: function() {
switch (currentLevel) {
case LogLevel.TRACE: return 'trace';
case LogLevel.DEBUG: return 'debug';
case LogLevel.INFO: return 'info';
case LogLevel.WARN: return 'warn';
case LogLevel.ERROR: return 'error';
case LogLevel.SILENT: return 'silent';
default: return 'unknown';
}
}
};
}

const logger=SimpleLogger('main',LogLevel.INFO);
const workflowLogger=SimpleLogger('workflow',LogLevel.INFO);
const eventLogger=SimpleLogger('event',LogLevel.INFO);
const comfyuiLogger=SimpleLogger('comfyui',LogLevel.INFO);
const sdwebuiLogger=SimpleLogger('sdwebui',LogLevel.INFO);
const dbLogger=SimpleLogger('db',LogLevel.INFO);
const canvasLogger=SimpleLogger('canvas',LogLevel.INFO);
const projectLogger=SimpleLogger('project',LogLevel.INFO);
const layerLogger=SimpleLogger('layer',LogLevel.INFO);
const fontLogger=SimpleLogger('font',LogLevel.INFO);
const uiLogger=SimpleLogger('ui',LogLevel.INFO);
const effectLogger=SimpleLogger('effect',LogLevel.INFO);
const textLogger=SimpleLogger('text',LogLevel.INFO);
const imageLogger=SimpleLogger('image',LogLevel.INFO);
const panelLogger=SimpleLogger('panel',LogLevel.INFO);
const compressionLogger=SimpleLogger('compression',LogLevel.INFO);
const serviceLogger=SimpleLogger('service',LogLevel.INFO);
