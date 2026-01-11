// font-repository.js
const fmFontRepository={
store: null,
init() {
this.store=localforage.createInstance({
name: 'fm-fontStorage',
storeName: 'fm-userFonts'
});
},

async saveUploadedFont(name,buffer) {
try {
await this.store.setItem(name,{
name,
buffer,
type: 'upload'
});
return true;
} catch (error) {
console.error('Failed to save font:',error);
return false;
}
},

async getFont(name) {
try {
return await this.store.getItem(name);
} catch (error) {
console.error('Failed to retrieve font:',error);
return null;
}
},

async getAllFonts() {
const fonts=[];
try {
await this.store.iterate((value)=>{
fonts.push(value);
});
return fonts;
} catch (error) {
console.error('Failed to retrieve font list:',error);
return [];
}
},

async deleteFont(name) {
try {
await this.store.removeItem(name);
return true;
} catch (error) {
console.error('Failed to delete font:',error);
return false;
}
},

async saveLocalFont(name) {
try {
await this.store.setItem(name,{
name,
type: 'local'
});
return true;
} catch (error) {
console.error('Failed to save local font:',error);
return false;
}
},

async saveWebFont(name,url) {
try {
await this.store.setItem(name,{
name,
url,
type: 'web'
});
return true;
} catch (error) {
console.error('Failed to save web font:',error);
return false;
}
}
};