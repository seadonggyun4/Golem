export type Stage = 'planning' | 'ux' | 'publishing' | 'development' | 'qa' | 'audit';
export type Autonomy = 'DENY' | 'AUTO_LOCAL' | 'ASK_ON_EXTERNAL_EFFECT' | 'ASK_ALWAYS';
export interface Capsule {
  schema_version?: 1;
  id: string;
  goal: string;
  scope: readonly string[];
  permissions: Partial<Record<Stage, Autonomy>>;
  stages: readonly Stage[];
  acceptance: readonly (string | { id: string; text: string; required_gates: readonly string[] })[];
  expected_artifacts: readonly string[];
  required_gates: readonly string[];
}
export interface ValidationResult {
  schema_version: 1;
  valid: true;
  id: string;
  stages: Stage[];
}
/** Counters remain decimal strings; use BigInt when arithmetic is needed. */
export interface ReplayResult {
  schema_version: 1;
  run_id: string;
  state: 'READY' | 'RUNNING' | 'FAILED' | 'BLOCKED' | 'SUCCEEDED' | 'CANCELLED';
  passed_stages: string;
  stage_count: string;
  bundle_verified: false;
  simulation: 'unknown';
  acceptance_verified: false;
  recovery_action: 'NONE' | 'CHECK_POLICY' | 'RECONCILE_ATTEMPT' | 'EVALUATE_REENTRY' | 'RESOLVE_BLOCK';
  journal_records: string;
  journal_bytes: string;
}
export class GolemError extends Error {
  readonly status: number;
  constructor(status: number, message: string);
}
/** Synchronous Node-only binding. Load trusted native code from an absolute path.
 * No subprocess/provider execution. Use a worker thread for large replay inputs.
 * Replayed states do not verify acceptance, CAS or execution authority. */
export class Engine {
  constructor(addonPath: string);
  validate(capsule: Capsule | string | Uint8Array): ValidationResult;
  replay(journal: Uint8Array): ReplayResult;
}
