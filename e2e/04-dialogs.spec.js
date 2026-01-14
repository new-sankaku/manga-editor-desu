import{test,expect}from'@playwright/test';
import{createConsoleCollector}from'./helpers/console-error-checker.js';
test.describe('File Menu Dialog Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
});
test('should open project save without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('[data-i18n="file"]').first().click();
await page.waitForTimeout(300);
await page.locator('#projectSave').click({force:true});
await page.waitForTimeout(1000);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should open settings save without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('[data-i18n="file"]').first().click();
await page.waitForTimeout(300);
await page.locator('#settingsSave').click({force:true});
await page.waitForTimeout(1000);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
test.describe('Speech Bubble Panel Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.locator('#intro_speech-bubble-area1').click({force:true});
await expect(page.locator('#speech-bubble-area1')).toBeVisible({timeout:5000});
});
test('should change speech bubble text direction',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#sbHorizontalText').click({force:true});
await page.waitForTimeout(200);
await page.locator('#sbVerticalText').click({force:true});
await page.waitForTimeout(200);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should adjust speech bubble opacity slider',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#speechBubbleOpacity').fill('50');
await page.waitForTimeout(300);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
test.describe('Language Change Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
});
test('should change language to Japanese without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('[data-i18n="language"]').first().click();
await page.waitForTimeout(300);
await page.locator('[data-i18n="japanese"]').click({force:true});
await page.waitForTimeout(1000);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should change language to English without error',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('[data-i18n="language"]').first().click();
await page.waitForTimeout(300);
await page.locator('[data-i18n="english"]').click({force:true});
await page.waitForTimeout(1000);
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
