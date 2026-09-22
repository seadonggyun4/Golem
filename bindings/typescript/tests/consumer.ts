import { Engine, GolemError, type Capsule, type ReplayResult } from '@golem-awe/runtime';
const engine = new Engine('/explicit/trusted/golem_node.node');
const capsule: Capsule = {
  id: 'typed', goal: 'check declarations', scope: ['local'], stages: ['planning'],
  permissions: { planning: 'DENY' }, acceptance: ['validated'], expected_artifacts: [], required_gates: []
};
const valid: true = engine.validate(capsule).valid;
const replay: ReplayResult = engine.replay(new Uint8Array());
const records: bigint = BigInt(replay.journal_records);
const code: number = new GolemError(1, 'invalid').status;
// @ts-expect-error counters must not silently lose uint64 precision
const unsafe: number = replay.journal_records;
// @ts-expect-error replay does not load a filesystem path
engine.replay('journal.bin');
// @ts-expect-error no unsupported stage names
capsule.stages = ['deployment'];
void valid; void records; void code; void unsafe;
