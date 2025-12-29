const objectInfoRepository = {
store: null,

init() {
this.store = localforage.createInstance({
name: "objectInfoStorage",
storeName: "comfyObjectInfo",
});
},

async saveObjectInfo(objectInfo) {
if (!objectInfo || Object.keys(objectInfo).length === 0) {
console.error("有効なObjectInfoが指定されていません");
return false;
}

try {
await this.store.setItem("latestObjectInfo", {
data: objectInfo,
updatedAt: new Date().toISOString(),
});
return true;
} catch (error) {
console.error("ObjectInfoの保存に失敗しました:", error);
return false;
}
},

async getObjectInfo() {
try {
const result = await this.store.getItem("latestObjectInfo");
return result ? result.data : null;
} catch (error) {
console.error("ObjectInfoの取得に失敗しました:", error);
return null;
}
},

async getLastUpdated() {
try {
const result = await this.store.getItem("latestObjectInfo");
return result ? result.updatedAt : null;
} catch (error) {
console.error("最終更新日時の取得に失敗しました:", error);
return null;
}
},
};

objectInfoRepository.init();
