// 画面の試験をまとめて流す。ブラウザは1回だけ起こし（launchServer）、試験のファイルごとに別のプロセスで同時に流す。
// 各ファイルは PW_WS でそのブラウザにつなぎ、自分の context を作る（ui_common.mjs の openBrowser）。
//   node v3/web/test/run_ui.mjs fast              偽のサーバー・録った答えで通す（本物のサーバーは要らない）
//   node v3/web/test/run_ui.mjs full              fast ＋ 本物のサーバーで通す（V3_ORIGIN と CTRL が要る）
//   node v3/web/test/run_ui.mjs perf              原稿の画面の速さを測る（偽のサーバー）
//   V3_ORIGIN=http://127.0.0.1:<口>   full：本物のサーバー（/web を出し、V3_AUTH_MODE=dev_header。利用者 scr-admin を管理者に）
//   CTRL=http://127.0.0.1:<口+1>     full：ハーネスの動く見本（tests/integration/harness_screen_demo.py）の操作の口
//   IMAGEGEN_WEB=…/web/ IMAGEGEN_USER=…  full：画像生成の画面（本物の ComfyUI が要る）。無ければ流さず、流さなかったと出す
//   SHOTS=<フォルダ>                    画面の写しを撮る（ファイルごとに下のフォルダに分ける）。普段は撮らない
// 環境：NODE_PATH に playwright、PLAYWRIGHT_BROWSERS_PATH にブラウザ（V3画面の一覧.md 4章）
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { cpus } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const HERE = dirname(fileURLToPath(import.meta.url));

const suite = process.argv[2];
const shotsFor = (name) => (process.env.SHOTS ? { SHOTS: join(process.env.SHOTS, name) } : {});
const need = (name) => { if (!process.env[name]) throw new Error(`${suite} の組には ${name} が要る（run_ui.mjs の頭の説明）`); return process.env[name]; };

const FAST = [
  { name: "theme_check", file: "theme_check.mjs", env: {}, browser: false },
  { name: "keys_ui（偽のサーバー）", file: "keys_ui.mjs", env: shotsFor("keys") },
  { name: "manuscript_ui（偽のサーバー）", file: "manuscript_ui.mjs", env: { MOCK: "1", ...shotsFor("manuscript_mock") } },
  { name: "screens_ui（録った答え）", file: "screens_ui.mjs", env: { REPLAY: "1", ...shotsFor("screens_replay") } },
  // 図の重なりは、普段は一番広い窓と電話の幅だけ（1つの窓で約50秒）。間の 1280×800・1024×768 は full で流す
  { name: "harness_layout_ui（図の重なり・偽のサーバー）", file: "harness_layout_ui.mjs", env: { SIZES: "1920x1080,390x844", ...shotsFor("harness_layout") } },
];
function fullJobs() {
  const origin = need("V3_ORIGIN");
  const jobs = [
    ...FAST,
    { name: "manuscript_ui（本物のサーバー）", file: "manuscript_ui.mjs", env: { V3_ORIGIN: origin, ...shotsFor("manuscript") } },
    { name: "screens_ui（本物のサーバー）", file: "screens_ui.mjs", env: { V3_WEB: `${origin}/web/`, ...shotsFor("screens") } },
    { name: "harness_layout_ui（図の重なり・間の窓）", file: "harness_layout_ui.mjs", env: { SIZES: "1280x800,1024x768", ...shotsFor("harness_layout_mid") } },
    { name: "harness_ui（動く見本）", file: "harness_ui.mjs", env: { CTRL: need("CTRL"), ...shotsFor("harness") }, alone: true },
  ];
  if (process.env.IMAGEGEN_WEB) {
    jobs.push({ name: "image_generation_ui（本物の ComfyUI）", file: "image_generation_ui.mjs",
                env: { V3_WEB: process.env.IMAGEGEN_WEB, V3_USER: need("IMAGEGEN_USER"), ...shotsFor("image_generation") } });
  } else {
    console.log("image_generation_ui は流さない（IMAGEGEN_WEB が無い。本物の ComfyUI が要る）");
  }
  return jobs;
}
const PERF = [{ name: "manuscript_ui（速さを測る・偽のサーバー）", file: "manuscript_ui.mjs", env: { MOCK: "1", PERF: "1", ...shotsFor("manuscript_perf") } }];

const jobs = suite === "fast" ? FAST : suite === "full" ? fullJobs() : suite === "perf" ? PERF : null;
if (!jobs) throw new Error("組は fast・full・perf のどれか");

const server = await chromium.launchServer();
const t0 = Date.now();

function run(job) {
  return new Promise((resolve) => {
    const started = Date.now();
    const env = { ...process.env, ...job.env, ...(job.browser === false ? {} : { PW_WS: server.wsEndpoint() }) };
    // 本物と偽を同じ回で流すので、組ごとに決めた相手だけを渡す（外から渡された相手の設定は消す）
    for (const k of ["MOCK", "REPLAY", "RECORD", "PERF", "V3_ORIGIN", "V3_WEB", "CTRL", "SHOTS"]) if (!(k in job.env)) delete env[k];
    const child = spawn(process.execPath, [join(HERE, job.file)], { env });
    let out = "";
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { out += d; });
    child.on("close", (code) => resolve({ job, code, ms: Date.now() - started, out }));
  });
}

// 同時に流す数は CPU の数まで。alone の試験（変化が出るまでの遅れを測る）は、ほかが終わってから1本だけで流す
const limit = Math.max(1, Math.min(cpus().length, jobs.length));
const results = [];
const queue = jobs.filter((j) => !j.alone);
async function lane() { while (queue.length) results.push(await run(queue.shift())); }
await Promise.all(Array.from({ length: limit }, lane));
for (const j of jobs.filter((x) => x.alone)) results.push(await run(j));
await server.close();

let failed = 0;
for (const r of results) {
  if (r.code !== 0) { failed += 1; console.log(`\n===== 失敗：${r.job.name}\n${r.out}`); }
}
console.log("\n画面の試験（" + suite + "）");
for (const r of results) console.log(`${r.code === 0 ? "ok" : "NG"}  ${(r.ms / 1000).toFixed(1).padStart(6)} 秒  ${r.job.name}`);
console.log(`全体 ${((Date.now() - t0) / 1000).toFixed(1)} 秒（同時に ${limit} 本まで）`);
process.exit(failed ? 1 : 0);
