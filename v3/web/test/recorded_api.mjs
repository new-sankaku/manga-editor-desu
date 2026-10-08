// 本物のサーバーの口の答えを録り（RECORD）、あとで録った答えで画面を通す（REPLAY）。画面の動きだけを確かめる試験に使う。
// - 録る：本物のサーバーへの画面からの呼び出しを、そのまま本物へ流し、答えを順に残す（/web/ の画面のファイルは残さない）
// - 返す：同じ「方法・道・利用者」の呼び出しに、録った順に答える。録った数より多く呼ばれた・録っていない呼び出しは
//   500 を返して誤りに数える（ほかの答えで埋めない）。JSON の本文は録ったときと同じかも確かめる（画面が送る操作が変わったら落ちる）
// 口の答えの形が変わったら、本物のサーバーに向けて RECORD=1 で録り直す（V3画面の一覧.md 4章）。
import { readFileSync, writeFileSync } from "node:fs";
import { serveWeb } from "./ui_common.mjs";

const keyOf = (method, url, user) => `${method} ${url.pathname}${url.search} ${user || "-"}`;
const isText = (type) => /json|text|javascript|svg/.test(type || "");

export class ApiRecorder {
  constructor(file, meta) { this.file = file; this.meta = meta; this.calls = []; }

  // origin（本物のサーバー）への呼び出しを本物へ流して残す。後で付けた page.route（偽にする分）が先に効くので、それは残らない
  async install(page, origin) {
    await page.route(`${origin}/**`, async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      const res = await route.fetch();
      if (!url.pathname.startsWith("/web/")) {
        const body = await res.body();
        const type = res.headers()["content-type"] || "";
        const ct = req.headers()["content-type"] || "";
        this.calls.push({ key: keyOf(req.method(), url, req.headers()["x-v3-user"]), status: res.status(), type,
                          request: ct.startsWith("application/json") && req.postData() ? JSON.parse(req.postData()) : null,
                          ...(isText(type) ? { text: body.toString("utf8") } : { base64: body.toString("base64") }) });
      }
      return route.fulfill({ response: res });
    });
  }

  save() {
    writeFileSync(this.file, JSON.stringify({ recorded_at: new Date().toISOString(), meta: this.meta, calls: this.calls }, null, 0) + "\n");
    console.log(`録った答え ${this.calls.length} 件 → ${this.file}`);
  }
}

export class ApiReplayer {
  constructor(file) {
    const rec = JSON.parse(readFileSync(file, "utf8"));
    this.meta = rec.meta;
    this.recordedAt = rec.recorded_at;
    this.queues = new Map();
    for (const c of rec.calls) {
      if (!this.queues.has(c.key)) this.queues.set(c.key, []);
      this.queues.get(c.key).push(c);
    }
    this.errors = [];
  }

  async install(page, origin) {
    await serveWeb(page, origin, async (route, url) => {
      const req = route.request();
      const key = keyOf(req.method(), url, req.headers()["x-v3-user"]);
      const c = (this.queues.get(key) || []).shift();
      if (!c) {
        this.errors.push(`録っていない呼び出し（または録った数より多い）：${key}`);
        return route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: `録っていない：${key}` }) });
      }
      const ct = req.headers()["content-type"] || "";
      if (c.request !== null && ct.startsWith("application/json")) {
        const sent = JSON.stringify(JSON.parse(req.postData() || "null"));
        if (sent !== JSON.stringify(c.request)) this.errors.push(`送った本文が録ったときと違う：${key}\n  今：${sent}\n  前：${JSON.stringify(c.request)}`);
      }
      return route.fulfill({ status: c.status, contentType: c.type,
                             body: c.text !== undefined ? c.text : Buffer.from(c.base64, "base64") });
    });
  }

  // 録ったのに呼ばれなかった答え（画面が呼ばなくなった口）
  unused() { return [...this.queues.entries()].filter(([, q]) => q.length).map(([k, q]) => `${k} ×${q.length}`); }
}
