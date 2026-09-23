import { createRequire } from 'node:module';
import { isAbsolute } from 'node:path';
import { Buffer } from 'node:buffer';

const require = createRequire(import.meta.url);
export class GolemError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'GolemError';
    this.status = status;
  }
}

export class Engine {
  #call;
  constructor(addonPath) {
    if (typeof addonPath !== 'string' || !isAbsolute(addonPath)) {
      throw new TypeError('addonPath must be an explicit absolute path');
    }
    const addon = require(addonPath);
    if (addon.abiVersion !== 1 || typeof addon.call !== 'function') {
      throw new Error('unsupported Golem binding ABI');
    }
    this.#call = addon.call.bind(addon);
  }

  #invoke(operation, bytes) {
    const limit = operation === 1 ? 131072 : operation === 3 ? 16384 : 16777216;
    if (bytes.byteLength === 0 || bytes.byteLength > limit) {
      throw new GolemError(1, 'empty or oversized input');
    }
    // A shared buffer could change during the native parser call. Reject it,
    // including Buffer views, before taking an owned, ordinary byte snapshot.
    if (typeof SharedArrayBuffer !== 'undefined' && bytes.buffer instanceof SharedArrayBuffer) {
      throw new TypeError('shared buffers are not supported');
    }
    let value;
    try {
      value = JSON.parse(this.#call(operation, Buffer.from(bytes)));
    } catch (error) {
      if (Number.isInteger(error?.golemStatus)) {
        throw new GolemError(error.golemStatus, error.message);
      }
      throw error;
    }
    if (value === null || typeof value !== 'object' || value.schema_version !== 1) {
      throw new Error('unsupported Golem result schema');
    }
    return value;
  }

  validate(capsule) {
    if (capsule instanceof Uint8Array) return this.#invoke(1, capsule);
    if (typeof capsule !== 'string') {
      if (capsule === null || typeof capsule !== 'object' || Array.isArray(capsule)) {
        throw new TypeError('capsule must be an object, JSON string or Uint8Array');
      }
      capsule = JSON.stringify(capsule);
    }
    if (typeof capsule !== 'string') throw new TypeError('capsule is not JSON serializable');
    return this.#invoke(1, Buffer.from(capsule, 'utf8'));
  }

  replay(journal) {
    if (!(journal instanceof Uint8Array)) throw new TypeError('journal must be a Uint8Array');
    return this.#invoke(2, journal);
  }

  describeAdapter(descriptor) {
    if (descriptor instanceof Uint8Array) return this.#invoke(3, descriptor);
    if (typeof descriptor !== 'string') {
      if (descriptor === null || typeof descriptor !== 'object' || Array.isArray(descriptor)) {
        throw new TypeError('descriptor must be an object, JSON string or Uint8Array');
      }
      descriptor = JSON.stringify(descriptor);
    }
    if (typeof descriptor !== 'string') throw new TypeError('descriptor is not JSON serializable');
    return this.#invoke(3, Buffer.from(descriptor, 'utf8'));
  }
}
