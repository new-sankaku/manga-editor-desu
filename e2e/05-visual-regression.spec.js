import{test,expect}from'@playwright/test';
test.describe('Visual Regression Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.waitForTimeout(1000);
});
test('initial canvas state',async({page})=>{
const canvas=page.locator('.canvas-container');
await expect(canvas).toHaveScreenshot('canvas-initial.png',{
maxDiffPixelRatio:0.02,
});
});
test('canvas after adding A4 panel',async({page})=>{
await page.locator('#intro_page-manager-area').click({force:true});
await page.waitForSelector('#panel-manager-area',{state:'visible',timeout:5000});
await page.locator('#A4-H').click({force:true});
await page.waitForTimeout(1000);
const canvas=page.locator('.canvas-container');
await expect(canvas).toHaveScreenshot('canvas-a4-panel.png',{
maxDiffPixelRatio:0.02,
});
});
test('canvas after adding square shape',async({page})=>{
await page.locator('#intro_custom-panel-manager-area').click({force:true});
await page.waitForSelector('#custom-panel-manager-area',{state:'visible',timeout:5000});
await page.locator('#addSquare').click({force:true});
await page.waitForTimeout(500);
const canvas=page.locator('.canvas-container');
await expect(canvas).toHaveScreenshot('canvas-square.png',{
maxDiffPixelRatio:0.02,
});
});
test('canvas with grid enabled',async({page})=>{
await page.locator('[data-i18n="canvas"]').first().click();
await page.waitForTimeout(300);
await page.locator('#toggleGridButton').click({force:true});
await page.waitForTimeout(500);
const canvas=page.locator('.canvas-container');
await expect(canvas).toHaveScreenshot('canvas-grid.png',{
maxDiffPixelRatio:0.02,
});
});
});
test.describe('UI Visual Regression Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.waitForTimeout(500);
});
test('sidebar panel - page manager',async({page})=>{
await page.locator('#intro_page-manager-area').click({force:true});
await page.waitForSelector('#panel-manager-area',{state:'visible',timeout:5000});
await page.waitForTimeout(300);
const panel=page.locator('#panel-manager-area');
await expect(panel).toHaveScreenshot('panel-page-manager.png',{
maxDiffPixelRatio:0.02,
});
});
test('navbar state',async({page})=>{
const navbar=page.locator('#desu-nav');
await expect(navbar).toHaveScreenshot('navbar.png',{
maxDiffPixelRatio:0.02,
});
});
test('full page screenshot',async({page})=>{
await expect(page).toHaveScreenshot('full-page.png',{
fullPage:false,
maxDiffPixelRatio:0.02,
});
});
});
