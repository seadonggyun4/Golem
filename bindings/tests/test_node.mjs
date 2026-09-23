import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { Worker } from 'node:worker_threads';

const [addonPath, root, installed] = process.argv.slice(2);
const moduleUrl = installed ? pathToFileURL(resolve(installed)).href
  : pathToFileURL(resolve(root, 'bindings/typescript/index.mjs')).href;
const { Engine, GolemError } = await import(moduleUrl);
const engine = new Engine(addonPath);
const capsule = readFileSync(resolve(root, 'samples/work-capsules/basic.json'));
const fixture = name => Buffer.from(readFileSync(resolve(root, `tests/c/fixtures/journal/v1_${name}.hex`), 'utf8').replace(/\s/g, ''), 'hex');
const journal = fixture('default');
const descriptor = readFileSync(resolve(root, 'samples/adapter-descriptor.json'));
const described = engine.describeAdapter(descriptor);
assert.deepEqual(described, JSON.parse(descriptor));
assert.deepEqual(engine.describeAdapter(descriptor.toString()), described);
assert.deepEqual(engine.describeAdapter(described), described);
assert.throws(() => engine.describeAdapter({ ...described, features_supported: 1 }), GolemError);
assert.throws(() => engine.describeAdapter(Buffer.alloc(16385)), GolemError);
assert.throws(() => engine.describeAdapter(42), TypeError);
const validated = engine.validate(capsule);
assert.equal(validated.valid, true);
assert.equal(validated.stages.length, 6);
assert.deepEqual(engine.validate(JSON.parse(capsule)), validated);
assert.deepEqual(engine.validate(capsule.toString()), validated);
validated.stages.pop();
assert.equal(engine.validate(capsule).stages.length, 6);
for (const input of ['{}', '{"id":"a","id":"b"}', Buffer.from([255]), Buffer.concat([capsule, Buffer.from([0])])]) {
  assert.throws(() => engine.validate(input), error => error instanceof GolemError && Number.isInteger(error.status));
}
const replay = engine.replay(journal);
assert.equal(replay.state, 'SUCCEEDED');
assert.equal(replay.journal_records, '13');
assert.equal(BigInt(replay.journal_bytes), BigInt(journal.length));
assert.equal(replay.acceptance_verified, false);
assert.equal(replay.bundle_verified, false);
assert.equal(engine.replay(fixture('reentry')).state, 'SUCCEEDED');
assert.equal(engine.replay(fixture('cancelled')).state, 'CANCELLED');
const padded = Buffer.concat([Buffer.from([0]), journal, Buffer.from([0])]);
assert.deepEqual(engine.replay(padded.subarray(1, -1)), replay);
const created = 32 + journal.readUInt32LE(12);
assert.equal(engine.replay(journal.subarray(0, created)).state, 'READY');
assert.equal(engine.replay(journal.subarray(0, created + 64)).recovery_action, 'RECONCILE_ATTEMPT');
for (const input of [Buffer.alloc(0), journal.subarray(0, -1), fixture('invalid_transition')]) {
  assert.throws(() => engine.replay(input), GolemError);
}
assert.throws(() => engine.replay('journal.bin'), TypeError);
assert.throws(() => new Engine('relative.node'), TypeError);
assert.throws(() => engine.replay(new Uint8Array(new SharedArrayBuffer(64))), TypeError);
const require = createRequire(import.meta.url);
const native = require(addonPath);
assert.throws(() => native.call(1.5, capsule), TypeError);
assert.throws(() => native.call(1, new Uint16Array(10)), TypeError);
assert.throws(() => native.call(1, new Uint8Array(new SharedArrayBuffer(64))), TypeError);
const transferable = new ArrayBuffer(8);
const detachedView = new Uint8Array(transferable);
structuredClone(transferable, { transfer: [transferable] });
assert.throws(() => native.call(1, detachedView));
assert.throws(() => native.call(1, new Uint8Array(0)));
for (let i = 0; i < 100; i++) assert.equal(engine.replay(journal).state, 'SUCCEEDED');
await Promise.all(Array.from({ length: 4 }, () => new Promise((accept, reject) => {
  const worker = new Worker(`
    const { parentPort, workerData } = require('node:worker_threads');
    import(workerData.url).then(({ Engine }) => {
      const engine = new Engine(workerData.addon);
      for (let i = 0; i < 25; i++) {
        if (engine.replay(workerData.bytes).state !== 'SUCCEEDED') throw new Error('bad replay');
      }
      parentPort.postMessage('ok');
    });`, { eval: true, workerData: { url: moduleUrl, addon: addonPath, bytes: journal } });
  let complete = false;
  worker.once('message', value => { complete = value === 'ok'; });
  worker.once('error', reject);
  worker.once('exit', code => code === 0 && complete ? accept() : reject(new Error('worker failed')));
})));
console.log('Node binding: validation, replay, invalid inputs, ownership, worker isolation passed');
