function getSelectedTagifyValues(id) {
const tagify=getTagify(id);
if (tagify) {
const selectedValues=tagify.value.map(tag=>tag.value);
return selectedValues;
}
return [];
}


function fuzzyTagifySearch(query,text) {
const pattern=query.split("").map(char=>`(?=.*${char})`).join("");
const regex=new RegExp(pattern,"i");
return regex.test(text);
}

function searchTagify(listValues,searchvalue) {
const results=listValues
.filter(tag=>fuzzyTagifySearch(searchvalue,tag.n))
.map(tag=>({value: tag.n,n: tag.n,p: tag.p}));
return results;
}

function getTagify(id) {
const input=$(id);
if(input){
return input.tagify;
}else{
return null;
}
}


function updateTagifyDropdown(id,listValues,initialSelectedValues=[]) {
const tagify=getTagify(id);
if (!tagify) {
initializeTagify(id,listValues,initialSelectedValues);
}else{
const updatedTagify=getTagify(id);
updatedTagify.removeAllTags();
updatedTagify.settings.whitelist=listValues;
if (initialSelectedValues.length>0) {
const selectedTags=listValues
.filter(tag=>initialSelectedValues.includes(tag.n))
.map(tag=>({
value: tag.n,// valueプロパティを明示的に設定
n: tag.n,
p: tag.p
}));
console.log("updateTagifyDropdown selectedTags",selectedTags);
updatedTagify.addTags(selectedTags);
}
}
}

function initializeTagify(id,listValues,initialSelectedValues=[]) {
const input=$(id);
if (input&&!input.tagify) {
const tagifyInstance=new Tagify(input,{
whitelist: listValues.map(tag=>({value: tag.n,n: tag.n,p: tag.p})),
dropdown: {
maxItems: Infinity,
classname: "tags-look",
enabled: 0,
position: "text",
placeAbove: false,
scrollIntoView: true,
closeOnSelect: false
},
});

tagifyInstance.on('click',function(e) {
const removeBtn=e.detail.tag.querySelector('.tagify__tag__removeBtn');
if (removeBtn) {
removeBtn.click();
}
});

tagifyInstance.on('input',function (e) {
var searchvalue=e.detail.value;
if (searchvalue.length>0) {
const tagify=getTagify(id);
tagify.whitelist=searchTagify(listValues,searchvalue);
tagify.dropdown.show(searchvalue);
}
});

if (initialSelectedValues.length>0) {
const selectedTags=listValues
.filter(tag=>initialSelectedValues.includes(tag.n))
.map(tag=>({
value: tag.n,// valueプロパティを明示的に設定
n: tag.n,
p: tag.p
}));
// console.log("initializeTagify selectedTags", selectedTags);
tagifyInstance.addTags(selectedTags);
}

input.tagify=tagifyInstance;
}
}

