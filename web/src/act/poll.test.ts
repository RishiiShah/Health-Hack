import { test } from 'node:test';
import assert from 'node:assert/strict';
import { startPolling } from './poll.ts';

const flush = async () => { await Promise.resolve(); await Promise.resolve(); };

test('mounted shift polling refreshes assignments and acceptance without overlapping requests', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let resolve!: (value: { on_shift: boolean; consults: string[] }) => void;
  let calls = 0;
  const received: { on_shift: boolean; consults: string[] }[] = [];
  const stop = startPolling(() => { calls++; return new Promise((done) => { resolve = done; }); },
    (value) => received.push(value), assert.fail, 2000);
  assert.equal(calls, 1);
  t.mock.timers.tick(10_000);
  assert.equal(calls, 1); // a slow request cannot overlap a newer one
  resolve({ on_shift: false, consults: [] });
  await flush();
  t.mock.timers.tick(2000);
  resolve({ on_shift: true, consults: ['newly assigned'] });
  await flush();
  assert.deepEqual(received.map((v) => v.on_shift), [false, true]);
  assert.deepEqual(received[1].consults, ['newly assigned']);
  stop();
  t.mock.timers.tick(10_000);
  assert.equal(calls, 2);
});

test('cleanup aborts requests and ignores responses from an old page or session', async () => {
  let resolve!: (value: string) => void;
  let signal!: AbortSignal;
  const received: string[] = [];
  const stop = startPolling((s) => { signal = s; return new Promise<string>((done) => { resolve = done; }); },
    (v) => received.push(v), assert.fail, 2000);
  stop();
  assert.equal(signal.aborted, true);
  resolve('old session data');
  await flush();
  assert.deepEqual(received, []);
});

test('polling retries failed requests and one-shot calls remain one-shot', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let calls = 0;
  const errors: unknown[] = [], received: number[] = [];
  const stop = startPolling(async () => { if (++calls === 1) throw new Error('offline'); return calls; },
    (v) => received.push(v), (e) => errors.push(e), 2000);
  await flush();
  t.mock.timers.tick(2000);
  await flush();
  assert.equal(errors.length, 1);
  assert.deepEqual(received, [2]);
  stop();
  startPolling(async () => ++calls, (v) => received.push(v), assert.fail, 0);
  await flush();
  t.mock.timers.tick(10_000);
  assert.equal(calls, 3);
});
