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
/** Claimed metadata only. Known/supported masks do not confer permissions. */
export interface AdapterDescriptor {
  schema_version: 1;
  domain: 'golem.adapter-descriptor.v1';
  adapter_id: string;
  adapter_version: string;
  session_id: string;
  current_agent: 0 | 1;
  protocol_version: 1;
  stages: number;
  features_known: number;
  features_supported: number;
  inputs_known: number;
  inputs_supported: number;
  simulation: 0 | 1 | 2;
  hidden_prompt_known: 0 | 1 | 2;
  sandbox: 0 | 1 | 2 | 3 | 4 | 5;
  effect: 0 | 1 | 2;
  tools: { id: string; digest: string }[];
}
/** Synchronous Node-only binding. Load trusted native code from an absolute path.
 * No subprocess/provider execution. Use a worker thread for large replay inputs.
 * Replayed states do not verify acceptance, CAS or execution authority. */
export class Engine {
  constructor(addonPath: string);
  validate(capsule: Capsule | string | Uint8Array): ValidationResult;
  replay(journal: Uint8Array): ReplayResult;
  describeAdapter(descriptor: AdapterDescriptor | string | Uint8Array): AdapterDescriptor;
}
