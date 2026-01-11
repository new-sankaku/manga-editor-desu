class ArrayBufferUtils {
static async toArrayBuffer(data) {
if (data===null||data===undefined) {
throw new Error('Data is null or undefined');
}
if (data instanceof ArrayBuffer) {
return data;
}
if (ArrayBuffer.isView(data)) {
return data.buffer;
}
if (data instanceof Blob) {
return await data.arrayBuffer();
}
if (typeof data==='number') {
return new ArrayBuffer(data);
}
if (Array.isArray(data)) {
return new Uint8Array(data).buffer;
}
if (typeof data==='string') {
return new TextEncoder().encode(data).buffer;
}
throw new Error('Unsupported data type');
}

static fromArrayBufferToString(buffer) {
return new TextDecoder().decode(buffer);
}

static fromArrayBufferToArray(buffer) {
return Array.from(new Uint8Array(buffer));
}

static fromArrayBufferToBlob(buffer,mimeType='application/octet-stream') {
return new Blob([buffer],{type: mimeType});
}

static fromArrayBufferToNumber(buffer) {
const view=new DataView(buffer);
if (buffer.byteLength===4) {
return view.getInt32(0);
}
if (buffer.byteLength===8) {
return view.getFloat64(0);
}
throw new Error('Unsupported number format');
}

static empty2SharedArrayBuffer(size) {
return new SharedArrayBuffer(size);
}
}