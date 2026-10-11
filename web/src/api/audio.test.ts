import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { createAudioPlayer } from "./audio.ts";
import { clearSession, saveSession } from "../auth/session.ts";

const originals = { fetch: globalThis.fetch, create: URL.createObjectURL, revoke: URL.revokeObjectURL, Audio: globalThis.Audio };
let instances: FakeAudio[], revoked: string[], statuses: boolean[], errors: string[], urls: number;
let blocked = false;

class FakeAudio extends EventTarget {
  src: string;
  paused = false;
  constructor(src: string) { super(); this.src = src; instances.push(this); }
  async play() { if (blocked) throw new DOMException('gesture required', 'NotAllowedError'); }
  pause() { this.paused = true; }
  removeAttribute() { this.src = ''; }
  load() {}
}

beforeEach(() => {
  const target = new EventTarget();
  globalThis.dispatchEvent = target.dispatchEvent.bind(target);
  clearSession();
  saveSession({ token: 'private-audio', expires_at: Date.now() / 1000 + 600,
    user: { email: 'lead@example.test', name: 'Lead', role: 'lead', role_label: 'Clinical lead', physician_id: null } });
  instances = []; revoked = []; statuses = []; errors = []; urls = 0; blocked = false;
  globalThis.Audio = FakeAudio as unknown as typeof Audio;
  URL.createObjectURL = () => `blob:audio-${++urls}`;
  URL.revokeObjectURL = (url) => { revoked.push(url); };
  globalThis.fetch = async (_path, init) => {
    assert.equal(new Headers(init?.headers).get('Authorization'), 'Bearer private-audio');
    return new Response('synthetic audio', { headers: { 'Content-Type': 'audio/mpeg' } });
  };
});
afterEach(() => {
  globalThis.fetch = originals.fetch;
  globalThis.Audio = originals.Audio;
  URL.createObjectURL = originals.create;
  URL.revokeObjectURL = originals.revoke;
});

const player = () => createAudioPlayer((active) => statuses.push(active), (error) => errors.push(error));

test('media uses a blob URL and releases it on completion or explicit stop', async () => {
  const audio = player();
  await audio.play('/offers/example/audio');
  assert.equal(instances[0].src, 'blob:audio-1');
  instances[0].dispatchEvent(new Event('ended'));
  assert.deepEqual(revoked, ['blob:audio-1']);
  assert.equal(statuses.at(-1), false);
  await audio.play('/offers/example/audio');
  audio.stop();
  assert.equal(instances[1].paused, true);
  assert.deepEqual(revoked, ['blob:audio-1', 'blob:audio-2']);
  assert.deepEqual(errors, []);
});

test('unmount or muting aborts media fetch and ignores a late response', async () => {
  let finish!: (response: Response) => void;
  let signal!: AbortSignal;
  globalThis.fetch = (_path, init) => { signal = init!.signal!; return new Promise((resolve) => { finish = resolve; }); };
  const audio = player();
  const pending = audio.play('/alerts/example/audio');
  audio.stop();
  assert.equal(signal.aborted, true);
  finish(new Response('late audio'));
  await pending;
  assert.equal(instances.length, 0);
  assert.equal(urls, 0);
  assert.deepEqual(errors, []);
});

test('speech outages and browser playback failures are visible and release media', async () => {
  const audio = player();
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Speech is unavailable.' }),
    { status: 503, headers: { 'Content-Type': 'application/json' } });
  await audio.play('/offers/example/audio');
  assert.deepEqual(errors, ['Speech is unavailable.']);
  globalThis.fetch = async () => new Response('audio');
  blocked = true;
  await audio.play('/offers/example/audio');
  assert.match(errors[1], /browser blocked playback/);
  assert.deepEqual(revoked, ['blob:audio-1']);
  blocked = false;
  await audio.play('/offers/example/audio');
  instances[1].dispatchEvent(new Event('error'));
  assert.match(errors[2], /could not be played/);
  assert.deepEqual(revoked, ['blob:audio-1', 'blob:audio-2']);
});
