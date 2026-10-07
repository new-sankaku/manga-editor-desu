"""P13 追記だけの記録で、再開・ロック・取り消し・同時保存を扱えるか（一覧 5-1 5-2 5-3 5-9 4-15）。
SQLite 1ファイル。結果は out/result.json。"""
import json
import multiprocessing as mp
import os
import pathlib
import random
import sqlite3
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
DB = OUT / 'work.db'

SCHEMA = """
create table if not exists ev(id integer primary key autoincrement, ts real, actor text, kind text, target text, body text);
create table if not exists lock(target text primary key, holder text, token integer, expires real);
create table if not exists fence(target text primary key, token integer);
create table if not exists val(target text primary key, v text, ver integer);
"""


def con():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute('pragma journal_mode=wal')
    c.execute('pragma synchronous=full')
    c.executescript(SCHEMA)
    return c


def log(c, actor, kind, target, body):
    c.execute('insert into ev(ts,actor,kind,target,body) values(?,?,?,?,?)', (time.time(), actor, kind, target, json.dumps(body, ensure_ascii=False)))


# ---------- 5-1 落ちても続きから ----------
def job_worker(job, steps):
    """1工程ずつ「終わった」を記録する。記録に残った所の次から始める。"""
    c = con()
    done = {json.loads(b)['step'] for (b,) in c.execute("select body from ev where kind='step_done' and target=?", (job,))}
    for s in range(steps):
        if s in done:
            continue
        time.sleep(0.03)  # 工程の本体（生成など）の代わり
        c.execute('begin immediate')
        # 同じ工程を二重に記録しない（再開時に同じ工程が走った場合の守り）
        if not c.execute("select 1 from ev where kind='step_done' and target=? and json_extract(body,'$.step')=?", (job, s)).fetchone():
            log(c, 'ai', 'step_done', job, {'step': s})
        c.execute('commit')


def test_resume(trials=20, steps=30):
    res = []
    for t in range(trials):
        job = f'job{t}'
        kills = 0
        while True:
            p = subprocess.Popen([sys.executable, __file__, 'worker', job, str(steps)])
            try:
                p.wait(timeout=random.uniform(0.1, 0.6))
                break
            except subprocess.TimeoutExpired:
                p.kill()  # 途中で落とす
                p.wait()
                kills += 1
        c = con()
        got = [json.loads(b)['step'] for (b,) in c.execute("select body from ev where kind='step_done' and target=? order by id", (job,))]
        res.append({'job': job, 'kills': kills, 'ok': sorted(got) == list(range(steps)) and len(got) == steps})
    return {'trials': trials, 'steps': steps, 'total_kills': sum(r['kills'] for r in res),
            'all_ok': all(r['ok'] for r in res), 'detail': res}


# ---------- 5-2 ロック・期限・取り返し・古い持ち主の書き込みを拒む ----------
def acquire(c, target, who, ttl, force=False):
    c.execute('begin immediate')
    now = time.time()
    row = c.execute('select holder, token, expires from lock where target=?', (target,)).fetchone()
    if row and row[2] > now and row[0] != who and not force:
        c.execute('commit')
        return None
    tok = (c.execute('select token from fence where target=?', (target,)).fetchone() or [0])[0] + 1
    c.execute('insert or replace into fence values(?,?)', (target, tok))
    c.execute('insert or replace into lock values(?,?,?,?)', (target, who, tok, now + ttl))
    log(c, who, 'lock', target, {'token': tok, 'force': force, 'took_from': row[0] if row and row[2] > now else None})
    c.execute('commit')
    return tok


def write(c, target, who, tok, v):
    """最新の札（token）を持つ者だけ書ける。古い札の書き込みは拒んで記録する。"""
    c.execute('begin immediate')
    cur = (c.execute('select token from fence where target=?', (target,)).fetchone() or [0])[0]
    if cur != tok:
        log(c, who, 'write_refused', target, {'token': tok, 'current': cur})
        c.execute('commit')
        return False
    ver = (c.execute('select ver from val where target=?', (target,)).fetchone() or [0])[0]
    c.execute('insert or replace into val values(?,?,?)', (target, v, ver + 1))
    log(c, who, 'write', target, {'v': v, 'ver': ver + 1})
    c.execute('commit')
    return True


def racer(who, n, q, go, use_lock, key):
    """読んでから少し待って書く。ロックが無いと、間に他の者が書いた分が消える。"""
    c = con()
    go.wait()
    ok = tries = 0
    while ok < n:
        tries += 1
        if use_lock and acquire(c, 'panel-race', who, ttl=5) is None:
            time.sleep(random.uniform(0, 0.002))
            continue
        cnt = int((c.execute('select v from val where target=?', (key,)).fetchone() or ['0'])[0])
        time.sleep(0.001)
        c.execute('insert or replace into val values(?,?,0)', (key, str(cnt + 1)))
        ok += 1
        if use_lock:
            c.execute('delete from lock where target=? and holder=?', ('panel-race', who))
    q.put((who, ok, tries))


def race(use_lock, key):
    q, go = mp.Queue(), mp.Event()
    ps = [mp.Process(target=racer, args=(w, 100, q, go, use_lock, key)) for w in ('human', 'ai1', 'ai2')]
    [p.start() for p in ps]
    time.sleep(1.0)
    go.set()
    [p.join() for p in ps]
    got = [q.get() for _ in ps]
    counter = int(con().execute('select v from val where target=?', (key,)).fetchone()[0])
    done = sum(g[1] for g in got)
    return {'writes': done, 'counter': counter, 'lost': done - counter, 'waits': sum(g[2] - g[1] for g in got)}


def test_lock():
    c = con()
    r = {}
    # 同時に取り合う。ロック無し（対照）では書き込みが消え、ロック有りでは消えない
    r['race_without_lock'] = race(False, 'counter_nolock')
    r['race_with_lock'] = race(True, 'counter_lock')
    # 期限切れで次の人が取れる
    t1 = acquire(c, 'p3', 'ai', ttl=0.3)
    blocked = acquire(c, 'p3', 'human', ttl=5) is None
    time.sleep(0.35)
    t2 = acquire(c, 'p3', 'human', ttl=5)
    r['expiry'] = {'blocked_while_valid': blocked, 'taken_after_expiry': t2 is not None,
                   'stale_write_refused': write(c, 'p3', 'ai', t1, 'AIの古い書き込み') is False,
                   'new_holder_can_write': write(c, 'p3', 'human', t2, '人の書き込み') is True}
    # 人がAIから取り返す（期限内でも）
    a = acquire(c, 'p4', 'ai', ttl=60)
    h = acquire(c, 'p4', 'human', ttl=60, force=True)
    r['takeover'] = {'human_took': h is not None,
                     'ai_write_refused': write(c, 'p4', 'ai', a, 'x') is False,
                     'recorded': c.execute("select count(*) from ev where kind='lock' and target='p4' and json_extract(body,'$.force')=1").fetchone()[0] == 1}
    return r


# ---------- 5-3 取り消しに他の人の操作が重なったとき ----------
def op(c, actor, target, new):
    old = (c.execute('select v from val where target=?', (target,)).fetchone() or [None])[0]
    c.execute('insert or replace into val values(?,?,0)', (target, new))
    log(c, actor, 'set', target, {'old': old, 'new': new})
    return c.execute('select max(id) from ev').fetchone()[0]


def undo(c, actor, evid):
    """自分の操作を取り消す。今の値が自分の書いた値でなければ、黙って戻さず「ぶつかった」と記録する。"""
    target, body = c.execute('select target, body from ev where id=?', (evid,)).fetchone()
    b = json.loads(body)
    cur = c.execute('select v from val where target=?', (target,)).fetchone()[0]
    if cur != b['new']:
        log(c, actor, 'undo_conflict', target, {'undo_of': evid, 'mine': b['new'], 'now': cur})
        return 'conflict'
    c.execute('update val set v=? where target=?', (b['old'], target))
    log(c, actor, 'undo', target, {'undo_of': evid})
    return 'undone'


def test_undo():
    c = con()
    op(c, 'human', 'p1.serif', '初めの台詞')
    e1 = op(c, 'human', 'p1.serif', '人の直し')
    op(c, 'ai', 'p1.serif', 'AIの直し')  # 人の直しの上にAIが重ねた
    e2 = op(c, 'human', 'p2.serif', '人だけが触った')
    r1 = undo(c, 'human', e1)
    v1 = c.execute("select v from val where target='p1.serif'").fetchone()[0]
    r2 = undo(c, 'human', e2)
    return {'overlapped': {'result': r1, 'value_kept': v1 == 'AIの直し'}, 'alone': {'result': r2}}


# ---------- 5-9 2人の保存がぶつかったら別の版に ----------
def save(c, doc, who, base, content):
    c.execute('begin immediate')
    head = (c.execute("select max(json_extract(body,'$.ver')) from ev where kind='save' and target=?", (doc,)).fetchone()[0]) or 0
    ver = head + 1
    branch = base != head
    log(c, who, 'save', doc, {'ver': ver, 'base': base, 'branch': branch, 'content': content})
    c.execute('commit')
    return ver, branch


def test_save_conflict():
    c = con()
    save(c, 'ep1', 'A', 0, '初版')
    a = save(c, 'ep1', 'A', 1, 'Aの直し')  # A は版1を元に保存
    b = save(c, 'ep1', 'B', 1, 'Bの直し')  # B も版1を元に保存 → ぶつかる
    kept = [json.loads(x)['content'] for (x,) in c.execute("select body from ev where kind='save' and target='ep1' order by id")]
    return {'A': a, 'B': b, 'B_became_branch': b[1] is True, 'both_kept': 'Aの直し' in kept and 'Bの直し' in kept}


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        job_worker(sys.argv[2], int(sys.argv[3]))
        sys.exit(0)
    for f in OUT.glob('work.db*'):
        f.unlink()
    t0 = time.time()
    result = {'resume': test_resume(), 'lock': test_lock(), 'undo': test_undo(), 'save_conflict': test_save_conflict()}
    result['events'] = con().execute('select count(*) from ev').fetchone()[0]
    result['sec'] = round(time.time() - t0, 1)
    result['sqlite'] = sqlite3.sqlite_version
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    d = dict(result)
    d['resume'] = {k: v for k, v in result['resume'].items() if k != 'detail'}
    print(json.dumps(d, ensure_ascii=False, indent=1))
