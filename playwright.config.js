import{defineConfig,devices}from'@playwright/test';
export default defineConfig({
testDir:'./e2e',
fullyParallel:true,
forbidOnly:!!process.env.CI,
retries:process.env.CI?2:0,
workers:process.env.CI?1:undefined,
reporter:'html',
timeout:60000,
expect:{
toHaveScreenshot:{
maxDiffPixelRatio:0.01,
threshold:0.2,
},
},
use:{
baseURL:'http://localhost:8000',
trace:'on-first-retry',
screenshot:'only-on-failure',
video:'retain-on-failure',
},
webServer:{
command:'python 99_server.py',
url:'http://localhost:8000',
reuseExistingServer:!process.env.CI,
timeout:30000,
},
projects:[
{
name:'chromium',
use:{...devices['Desktop Chrome']},
},
],
});
