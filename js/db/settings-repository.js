class SettingsRepository {
constructor(storageKey='app_settings') {
this.storageKey=storageKey;
this.initialized=false;
}

async init() {
if (this.initialized) return;
try {
await localforage.ready();
this.initialized=true;
} catch (error) {
throw new Error(`Failed to initialize localforage: ${error.message}`);
}
}

async setSetting(key,value) {
await this.init();
try {
let settings=await this.getAllSettings();
settings[key]=value;
await localforage.setItem(this.storageKey,settings);
return true;
} catch (error) {
throw new Error(`Failed to set setting ${key}: ${error.message}`);
}
}

async setSettingWithExpiry(key,value,ttlMinutes) {
const expiryTime=new Date().getTime()+(ttlMinutes*60*1000);
const valueWithExpiry={
value: value,
expiry: expiryTime
};
return this.setSetting(key,valueWithExpiry);
}

async getSetting(key,defaultValue=null) {
await this.init();
try {
const settings=await this.getAllSettings();
if (!settings.hasOwnProperty(key)) return defaultValue;

const value=settings[key];
if (this.isExpiredValue(value)) {
await this.removeSetting(key);
return defaultValue;
}

return this.isExpiryObject(value) ? value.value : value;
} catch (error) {
throw new Error(`Failed to get setting ${key}: ${error.message}`);
}
}

isExpiryObject(value) {
return value&&typeof value==='object'&&'value' in value&&'expiry' in value;
}

isExpiredValue(value) {
if (!this.isExpiryObject(value)) return false;
return new Date().getTime()>value.expiry;
}

async getAllSettings() {
await this.init();
try {
const settings=await localforage.getItem(this.storageKey);
return settings||{};
} catch (error) {
throw new Error(`Failed to get all settings: ${error.message}`);
}
}

async removeSetting(key) {
await this.init();
try {
let settings=await this.getAllSettings();
if (settings.hasOwnProperty(key)) {
delete settings[key];
await localforage.setItem(this.storageKey,settings);
return true;
}
return false;
} catch (error) {
throw new Error(`Failed to remove setting ${key}: ${error.message}`);
}
}

async clearAllSettings() {
await this.init();
try {
await localforage.setItem(this.storageKey,{});
return true;
} catch (error) {
throw new Error(`Failed to clear settings: ${error.message}`);
}
}

async hasKey(key) {
await this.init();
try {
const settings=await this.getAllSettings();
return settings.hasOwnProperty(key);
} catch (error) {
throw new Error(`Failed to check key ${key}: ${error.message}`);
}
}

async updateSetting(key,value) {
await this.init();
try {
let settings=await this.getAllSettings();
if (settings.hasOwnProperty(key)) {
if (typeof settings[key]==='object'&&!Array.isArray(settings[key])&&value!==null&&typeof value==='object') {
settings[key]={...settings[key],...value};
} else {
settings[key]=value;
}
await localforage.setItem(this.storageKey,settings);
return true;
}
return false;
} catch (error) {
throw new Error(`Failed to update setting ${key}: ${error.message}`);
}
}

async getKeys() {
await this.init();
try {
const settings=await this.getAllSettings();
return Object.keys(settings);
} catch (error) {
throw new Error(`Failed to get keys: ${error.message}`);
}
}

async setMultiple(keyValuePairs) {
await this.init();
try {
let settings=await this.getAllSettings();
for (const [key,value] of Object.entries(keyValuePairs)) {
settings[key]=value;
}
await localforage.setItem(this.storageKey,settings);
return true;
} catch (error) {
throw new Error(`Failed to set multiple settings: ${error.message}`);
}
}

async removeMultiple(keys) {
await this.init();
try {
let settings=await this.getAllSettings();
let removed=0;
for (const key of keys) {
if (settings.hasOwnProperty(key)) {
delete settings[key];
removed++;
}
}
await localforage.setItem(this.storageKey,settings);
return removed;
} catch (error) {
throw new Error(`Failed to remove multiple settings: ${error.message}`);
}
}

async validateType(key,expectedType) {
const value=await this.getSetting(key);
if (value===null) return false;

switch(expectedType) {
case 'string':
return typeof value==='string';
case 'number':
return typeof value==='number';
case 'boolean':
return typeof value==='boolean';
case 'object':
return typeof value==='object'&&value!==null;
case 'array':
return Array.isArray(value);
default:
return false;
}
}
}


const settingsRepository=new SettingsRepository();

// // 有効期限付きの設定
// await settings.setSettingWithExpiry('temporaryToken', 'abc123', 30); // 30分後に期限切れ

// // 複数の設定を一度に保存
// await settings.setMultiple({
//   theme: 'dark',
//   fontSize: 14,
//   notifications: true
// });

// // 複数のキーを一度に削除
// await settings.removeMultiple(['theme', 'fontSize']);

// // 全てのキーを取得
// const allKeys = await settings.getKeys();

// // 値の型を検証
// const isString = await settings.validateType('username', 'string');
// const isNumber = await settings.validateType('age', 'number');
// const isArray = await settings.validateType('permissions', 'array');