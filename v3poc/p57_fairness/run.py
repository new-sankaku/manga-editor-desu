"""P57 作品をまたぐ順番を Temporal の公平さの鍵（fairness_key）で回せるか（V3サーバーの土台 9章、V3ハーネス設計 2.4の29）。
v3/server と同じ Temporal（temporalio/temporal:1.9.1、待ち行列の分割1つ）を別の口（64233）で立て、次を比べる。
- 作品Aが先に30件、少し後に作品Bが5件頼む。作業者は1件ずつ（同時実行1）。B の5件が何番目に送られるか
- 設定：公平さを切る（今の v3/server）／公平さを入れる（matching.enableFairness）
- 公平さを入れたうえで、重み（fairness_weight）を A 1・B 3 にしたとき
- 公平さと優先順位（priority_key。人1・AI3）を一緒に使ったとき、人の依頼が作品をまたいでも先に出るか
使い方: cd v3/server && uv run python ../../v3poc/p57_fairness/run.py"""
import asyncio
import json
import pathlib
import subprocess
import time
import uuid
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import Priority
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

HERE = pathlib.Path(__file__).resolve().parent
PORT = 64233
NAME = 'p57-temporal'
ORDER = []


@activity.defn
async def send(tag: str) -> str:
    ORDER.append(tag)
    await asyncio.sleep(0.05)
    return tag


@workflow.defn
class One:
    @workflow.run
    async def run(self, tag: str, prio: int | None, fkey: str | None, fw: float | None) -> str:
        return await workflow.execute_activity(
            send, tag, start_to_close_timeout=timedelta(seconds=30), task_queue='p57-service',
            priority=Priority(priority_key=prio, fairness_key=fkey, fairness_weight=fw))


def start_server(fair: bool):
    subprocess.run(['docker', 'rm', '-f', NAME], capture_output=True)
    cmd = ['docker', 'run', '-d', '--name', NAME, '-p', f'{PORT}:7233', 'temporalio/temporal:1.9.1',
           'server', 'start-dev', '--ip', '0.0.0.0',
           '--dynamic-config-value', 'matching.numTaskqueueReadPartitions=1',
           '--dynamic-config-value', 'matching.numTaskqueueWritePartitions=1']
    if fair:
        cmd += ['--dynamic-config-value', 'matching.enableFairness=true']
    subprocess.run(cmd, check=True, capture_output=True)


async def connect():
    for _ in range(60):
        try:
            return await Client.connect(f'localhost:{PORT}')
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError('Temporal に繋がらない')


async def case(client, jobs):
    """jobs: (tag, prio, fkey, fw) の並び。作業者を止めたまま全部頼み、溜まってから1件ずつ流す"""
    ORDER.clear()
    q = f'p57-ctl-{uuid.uuid4().hex[:6]}'
    handles = []
    # 流れの作業者だけ先に動かし、送信の作業者は後から動かす（送信の待ち行列に溜めるため）
    async with Worker(client, task_queue=q, workflows=[One], workflow_runner=UnsandboxedWorkflowRunner()):  # 試作の1ファイルに subprocess などを入れているため
        for tag, prio, fkey, fw in jobs:
            handles.append(await client.start_workflow(One.run, args=[tag, prio, fkey, fw], id=f'{q}-{tag}', task_queue=q))
            await asyncio.sleep(0.02)
        await asyncio.sleep(3)
        async with Worker(client, task_queue='p57-service', activities=[send], max_concurrent_activities=1):
            for h in handles:
                await h.result()
    return list(ORDER)


def positions(order, prefix):
    return [i + 1 for i, t in enumerate(order) if t.startswith(prefix)]


async def run_all(fair):
    start_server(fair)
    client = await connect()
    res = {}
    a30 = [(f'A{i:02d}', None, 'A', None) for i in range(30)]
    b5 = [(f'B{i:02d}', None, 'B', None) for i in range(5)]
    for rep in range(3):
        o = await case(client, a30 + b5)
        res.setdefault('A30_then_B5', []).append({'B_pos': positions(o, 'B'), 'order': o})
    a30w = [(t, p, k, 1.0) for t, p, k, _ in a30]
    b5w = [(t, p, k, 3.0) for t, p, k, _ in b5]
    o = await case(client, a30w + b5w)
    res['weight_A1_B3'] = {'B_pos': positions(o, 'B'), 'order': o}
    # A の AI の依頼20件の後に、B の AI 10件と A の人の依頼3件
    mix = [(f'A_ai{i:02d}', 3, 'A', None) for i in range(20)] + [(f'B_ai{i:02d}', 3, 'B', None) for i in range(10)] \
        + [(f'A_hu{i}', 1, 'A', None) for i in range(3)]
    o = await case(client, mix)
    res['priority_with_fairness'] = {'human_pos': positions(o, 'A_hu'), 'B_pos': positions(o, 'B_'), 'order': o}
    subprocess.run(['docker', 'rm', '-f', NAME], capture_output=True)
    return res


async def main():
    t0 = time.time()
    out = {'off': await run_all(False), 'on': await run_all(True)}
    out['seconds'] = round(time.time() - t0, 1)
    (HERE / 'out' / 'result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for k in ('off', 'on'):
        r = out[k]
        print(k, 'B位置', [x['B_pos'] for x in r['A30_then_B5']], '重み', r['weight_A1_B3']['B_pos'],
              '人', r['priority_with_fairness']['human_pos'], 'B(優先)', r['priority_with_fairness']['B_pos'])


if __name__ == '__main__':
    asyncio.run(main())
