import{test,expect}from'@playwright/test';
import{createConsoleCollector}from'./helpers/console-error-checker.js';
test.describe('Page Manager Button Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.locator('#intro_page-manager-area').click({force:true});
await expect(page.locator('#panel-manager-area')).toBeVisible({timeout:5000});
});
test('should click A4-H button without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#A4-H').click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should click A4-V button without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#A4-V').click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should click B4-H button without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#B4-H').click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should click CustomPanelButton without error',async({page})=>{
const console=createConsoleCollector(page);
await page.fill('#customPanelSizeX','800');
await page.fill('#customPanelSizeY','600');
await page.locator('#CustomPanelButton').click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should toggle knife mode',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#knifeModeButton').click({force:true});
await page.waitForTimeout(300);
await page.locator('#knifeModeButton').click({force:true});
await page.waitForTimeout(300);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
test.describe('Panel Manager Button Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.locator('#intro_custom-panel-manager-area').click({force:true});
await expect(page.locator('#custom-panel-manager-area')).toBeVisible({timeout:5000});
});
const shapeButtons=[
{id:'#addSquare',name:'Square'},
{id:'#addTallRect',name:'Tall Rectangle'},
{id:'#addWideRect',name:'Wide Rectangle'},
{id:'#addTriangle',name:'Triangle'},
{id:'#addCircle',name:'Circle'},
{id:'#addStar',name:'Star'},
];
for(const{id,name}of shapeButtons){
test(`should add ${name} without error`,async({page})=>{
const console=createConsoleCollector(page);
await page.locator(id).click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors,`Error adding ${name}: ${errors.join(', ')}`).toHaveLength(0);
});
}
});
test.describe('Auto Generate Button Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.locator('#intro_auto-generate-area').click({force:true});
await expect(page.locator('#auto-generate-area')).toBeVisible({timeout:5000});
});
test('should click random cut button without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#panelRandamCutButton').click({force:true});
await page.waitForTimeout(1000);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
test.describe('Canvas Menu Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
});
test('should toggle grid without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('[data-i18n="canvas"]').first().click();
await page.waitForTimeout(300);
await page.locator('#toggleGridButton').click({force:true});
await page.waitForTimeout(500);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
