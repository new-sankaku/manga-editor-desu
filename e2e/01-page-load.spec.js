import{test,expect}from'@playwright/test';
import{createConsoleCollector}from'./helpers/console-error-checker.js';
test.describe('Page Load Tests',()=>{
test('should load the page with correct title',async({page})=>{
await page.goto('/');
await expect(page).toHaveTitle(/Manga Editor/i);
});
test('should complete loading screen and show main UI',async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await expect(page.locator('#desu-nav')).toBeVisible();
await expect(page.locator('#head-id')).toBeVisible();
});
test('should have no critical console errors on load',async({page})=>{
const console=createConsoleCollector(page);
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.waitForTimeout(2000);
const errors=console.getErrors();
expect(errors,`Console errors found: ${errors.join(', ')}`).toHaveLength(0);
});
test('should initialize canvas',async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
const canvas=page.locator('canvas.upper-canvas');
await expect(canvas).toBeVisible();
});
test('should display sidebar',async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await expect(page.locator('#sidebar')).toBeVisible();
});
test('should load navbar menu items',async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await expect(page.locator('[data-i18n="file"]')).toBeVisible();
await expect(page.locator('[data-i18n="canvas"]')).toBeVisible();
await expect(page.locator('[data-i18n="help"]')).toBeVisible();
});
});
