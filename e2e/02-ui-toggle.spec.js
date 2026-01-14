import{test,expect}from'@playwright/test';
import{createConsoleCollector}from'./helpers/console-error-checker.js';
test.describe('Sidebar Panel Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
await page.waitForTimeout(500);
});
const sidebarPanels=[
{icon:'#intro_svg-container-vertical',panel:'#svg-container-vertical',name:'Vertical Templates'},
{icon:'#intro_svg-container-landscape',panel:'#svg-container-landscape',name:'Landscape Templates'},
{icon:'#intro_page-manager-area',panel:'#panel-manager-area',name:'Page Manager'},
{icon:'#intro_custom-panel-manager-area',panel:'#custom-panel-manager-area',name:'Panel Manager'},
{icon:'#intro_auto-generate-area',panel:'#auto-generate-area',name:'Auto Generate'},
{icon:'#intro_prompt-manager-area',panel:'#prompt-manager-area',name:'Prompt Manager'},
{icon:'#intro_speech-bubble-area1',panel:'#speech-bubble-area1',name:'Speech Bubble'},
{icon:'#intro_speech-bubble-area2',panel:'#speech-bubble-area2',name:'Custom Bubble'},
{icon:'#intro_text-area',panel:'#text-area',name:'Text'},
{icon:'#intro_text-area2',panel:'#text-area2',name:'Image Text'},
{icon:'#intro_tool-area',panel:'#tool-area',name:'Pen Tool'},
{icon:'#intro_manga-tone-area',panel:'#manga-tone-area',name:'Tone'},
{icon:'#intro_manga-effect-area',panel:'#manga-effect-area',name:'Effect'},
{icon:'#intro_rough-manager-area',panel:'#rough-manager-area',name:'Rough'},
{icon:'#intro_controle-area',panel:'#controle-area',name:'Control'},
{icon:'#intro_shape-area',panel:'#shape-area',name:'Shape'},
];
for(const{icon,panel,name}of sidebarPanels){
test(`should show ${name} panel after click`,async({page})=>{
await page.locator(icon).click({force:true});
await page.waitForTimeout(500);
await expect(page.locator(panel)).toBeVisible({timeout:5000});
});
}
test('should switch panels when clicking different icons',async({page})=>{
const console=createConsoleCollector(page);
await page.locator('#intro_svg-container-vertical').click({force:true});
await page.waitForTimeout(500);
await expect(page.locator('#svg-container-vertical')).toBeVisible({timeout:5000});
await page.locator('#intro_page-manager-area').click({force:true});
await page.waitForTimeout(500);
await expect(page.locator('#panel-manager-area')).toBeVisible({timeout:5000});
await expect(page.locator('#svg-container-vertical')).not.toBeVisible();
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should have no console errors during panel navigation',async({page})=>{
const console=createConsoleCollector(page);
for(const{icon}of sidebarPanels.slice(0,5)){
await page.locator(icon).click({force:true});
await page.waitForTimeout(300);
}
const errors=console.getErrors();
expect(errors,`Console errors: ${errors.join(', ')}`).toHaveLength(0);
});
});
test.describe('Navbar Dropdown Tests',()=>{
test.beforeEach(async({page})=>{
await page.goto('/');
await page.waitForSelector('#desu-nav',{state:'visible',timeout:10000});
});
test('should open File dropdown and show menu items',async({page})=>{
const console=createConsoleCollector(page);
const fileMenu=page.locator('[data-i18n="file"]').first();
await fileMenu.click();
await page.waitForTimeout(300);
await expect(page.locator('#projectSave')).toBeVisible();
await expect(page.locator('#projectLoad')).toBeVisible();
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should open Canvas dropdown and show menu items',async({page})=>{
const console=createConsoleCollector(page);
const canvasMenu=page.locator('[data-i18n="canvas"]').first();
await canvasMenu.click();
await page.waitForTimeout(300);
await expect(page.locator('#toggleGridButton')).toBeVisible();
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should open Help dropdown and show menu items',async({page})=>{
const console=createConsoleCollector(page);
const helpMenu=page.locator('[data-i18n="help"]').first();
await helpMenu.click();
await page.waitForTimeout(300);
await expect(page.locator('[data-i18n="shortcutPage"]')).toBeVisible();
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
test('should open Language dropdown and show options',async({page})=>{
const console=createConsoleCollector(page);
const langMenu=page.locator('[data-i18n="language"]').first();
await langMenu.click();
await page.waitForTimeout(300);
await expect(page.locator('[data-i18n="english"]')).toBeVisible();
await expect(page.locator('[data-i18n="japanese"]')).toBeVisible();
const errors=console.getErrors();
expect(errors).toHaveLength(0);
});
});
