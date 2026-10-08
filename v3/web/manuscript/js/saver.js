// 後ろで保存する所と、ページごとの取り消し・やり直し。
// 変更は先に画面へ当て（model.applyLocal）、保存は順に1つずつ送る。失敗したら止め、状態の所に
// 「もう一度送る」「この変更を捨てる」を出す（画像生成の画面 app.js の後ろの保存と同じ振る舞い）。
// 取り消しの記録はページごとに持つ。1つの記録は、1回の手の操作で送った出来事の id の並び。
// 複数のページにかかる操作（ページの並べ替え・見開き）は、かかったページのどれからでも取り消せる（同じ記録を共有する）。
import * as api from "../../js/api.js";

export class Saver {
  constructor({ workId, onState, onSaved, onError }) {
    this.workId = workId;
    this.jobs = [];
    this.running = false;
    this.failed = null;
    this.waiters = [];
    this.hist = new Map();
    this.undoing = false;
    this.onState = onState;
    this.onSaved = onSaved;
    this.onError = onError;
    // 測るため：最後の保存が済むまでの時間（ms）
    this.lastSaveMs = null;
  }

  // ops を1つの記録として送る。pages：記録を載せるページの id。reload：済んだ後にサーバーから読み直すか
  // send：ops を送る代わりに使う関数（絵を上げるなど、口が操作でないとき）。出来事の id の並びを返す
  submit({ label, pages, ops = [], reload = false, send = null }) {
    const started = performance.now();
    const ids = new Promise((resolve, reject) => {
      this.jobs.push({ label, reload, resolve, reject, run: send || (async () => {
        const out = [];
        for (const op of ops) out.push((await api.op(this.workId, op)).event_id);
        return out;
      }), started });
      this.pump();
    });
    const entry = { label, ids, pages };
    ids.catch(() => this.forget(entry));
    for (const p of pages) { const h = this.histOf(p); h.undo.push(entry); h.redo = []; }
    this.onState();
    return ids;
  }

  async pump() {
    if (this.running || this.failed) return;
    const job = this.jobs[0];
    if (!job) { for (const w of this.waiters.splice(0)) w.resolve(); this.onState(); return; }
    this.running = true;
    this.onState();
    try {
      const v = await job.run();
      this.jobs.shift();
      this.lastSaveMs = performance.now() - job.started;
      job.resolve(v);
      await this.onSaved(job, this.jobs.length === 0);
    } catch (e) {
      console.error(e);
      this.failed = { job, error: e };
      for (const w of this.waiters.splice(0)) w.reject(new Error(`保存できていない変更があります（${job.label}）`));
    }
    this.running = false;
    this.onState();
    this.pump();
  }

  idle() {
    if (this.failed) return Promise.reject(new Error(`保存できていない変更があります（${this.failed.job.label}）`));
    if (!this.jobs.length && !this.running) return Promise.resolve();
    return new Promise((resolve, reject) => this.waiters.push({ resolve, reject }));
  }

  retry() { this.failed = null; this.pump(); }

  // 保存できなかった変更と、その後の変更を捨てる。呼んだ側がサーバーから読み直す
  discard() {
    const jobs = this.jobs.splice(0);
    this.failed = null;
    for (const j of jobs) j.reject(new Error("捨てた"));
    this.onState();
  }

  pending() { return this.jobs.length; }

  histOf(pageId) {
    if (!this.hist.has(pageId)) this.hist.set(pageId, { undo: [], redo: [] });
    return this.hist.get(pageId);
  }

  forget(entry) {
    for (const h of this.hist.values()) { h.undo = h.undo.filter((x) => x !== entry); h.redo = h.redo.filter((x) => x !== entry); }
    this.onState();
  }

  can(pageId, dir) { return !!pageId && this.histOf(pageId)[dir].length > 0 && !this.undoing; }
  peek(pageId, dir) { const l = this.histOf(pageId)[dir]; return l.length ? l[l.length - 1] : null; }

  // 取り消す・やり直す。サーバーの出来事の取り消し（POST /events/{id}/undo）を新しい順に送る。
  // やり直しは、取り消しの出来事をさらに取り消す。済んだら呼んだ側が読み直す
  async step(pageId, dir) {
    if (this.undoing) return null;
    const h = this.histOf(pageId);
    const entry = h[dir][h[dir].length - 1];
    if (!entry) return null;
    this.undoing = true;
    this.onState();
    try {
      await this.idle();
      const ids = await entry.ids;
      const back = [];
      for (const id of [...ids].reverse()) back.push((await api.undo(this.workId, id)).event_id);
      const moved = { ...entry, ids: Promise.resolve(back) };
      for (const p of entry.pages) {
        const hh = this.histOf(p);
        const [from, to] = dir === "undo" ? [hh.undo, hh.redo] : [hh.redo, hh.undo];
        const i = from.indexOf(entry);
        if (i >= 0) from.splice(i, 1);
        to.push(moved);
      }
      return entry;
    } finally {
      this.undoing = false;
      this.onState();
    }
  }
}
