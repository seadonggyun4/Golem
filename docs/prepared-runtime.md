# Prepared Runtime Cache

`<golem/prepared_runtime.h>` adds a bounded cache for provider/plugin discovery
and preparation results. Unlike the profile parser memo, it retains the actual
immutable output of a trusted host's discovery callback. It does not create a new
agent, embed provider SDKs, or change persisted Work/profile schemas.

## Host Integration

Create one cache per trusted host/authority scope with fixed callbacks and context.
The host supplies three operations:

1. `observe`: check live authorization and compute a digest of all preparation
   dependencies. Include provider account/endpoint scope (nonsecret identifiers),
   catalog revision or observation epoch, plugin inventory, executable/tool
   content identities, config, policy and callback/recipe revision. Unknown or
   unverifiable freshness is an error, not a reusable all-zero default.
2. `prepare`: perform read-only provider/plugin discovery, validate its result and
   serialize a secret-free manifest into the supplied bounded buffer. Include the
   manifest format version. Never return credentials, authorization grants, file
   descriptors, SDK pointers or mutable process state. The cache does not parse
   provider-specific bytes or independently certify callback truthfulness.
3. `clock_ns`: a monotonic clock with one domain for the cache lifetime.

The observer should be cheaper than discovery: for example, a trusted catalog
revision or digest of a maintained local manifest. If no trustworthy cheap
invalidation signal exists, observation must do the necessary work or refuse
reuse. TTL alone is not proof of unchanged remote state.

```c
golem_prepared_options options = {
    .size = sizeof(options), .version = 1,
    .capacity = 16, .max_bytes = 65536, .ttl_ns = 1000000000,
    .context = host,
    .observe = observe_current_authority_and_dependencies,
    .prepare = discover_and_encode_manifest,
    .clock_ns = host_monotonic_clock
};
golem_prepared_cache *cache = NULL;
/* Check each returned status; callbacks above are host implementations. */
golem_status status = golem_prepared_cache_create(&options, NULL, &cache);
```

On success, acquire with a parsed profile, read the borrowed result with
`golem_prepared_runtime_view`, consume/copy it, then release. Keep the cache alive
across preparations; creating it per request defeats reuse. A CLI process exiting
does not leave a persistent cache. The existing profile registration, current-agent
binding, descriptor checked-dispatch and lease checks still govern actual work.
The caller can store manifest bytes and returned digests using existing CAS APIs;
this cache neither registers a Work nor claims an execution receipt.

## Reuse And Invalidation

The key is canonical profile identity plus observed dependency identity. JSON
member order does not affect the profile digest. Each hit checks live authority,
dependencies and monotonic time. On misses, the cache observes again after
preparation and rejects changed dependencies or expired preparation. TTL begins
before preparation, not after it, and equality with expiry is already expired.

Failures are not memoized and do not fall back to stale data. Failed acquisitions
conservatively invalidate all future hits. Explicit invalidation has the same
effect. Clock rollback is rejected until the clock reaches its prior high-water
mark; changing clock domains requires a new cache. Already borrowed bytes remain
readable for inspection but do not retain authorization or freshness.

Slots use bounded round-robin replacement. A pinned slot is never overwritten;
full pinned capacity reports backpressure before invoking preparation. Options
and allocator descriptors are copied, their contexts borrowed. There are at most
64 entries of 64 KiB and one temporary preparation buffer. A miss is published only
after all checks and hashing succeed; allocation failure preserves caller outputs.
The implementation is serialized, not a concurrent single-flight service.
Callbacks must be bounded, respect their buffer and not reenter the same cache.
The cache cannot interrupt a hanging arbitrary C callback. Run external probes
through the existing bounded supervisor/descriptor contract, not raw subprocesses.

## Verification And Scope

`runtime_profile_prepared` checks 100 warm acquisitions with exactly one discovery,
live checks on every hit, payload digest, immediate revocation, pinned capacity,
expiry, clock rollback, preparation-time change/expiry, failure retry, oversized
output, reentrancy refusal and allocator failure/leak accounting. These are
deterministic contract tests, not live-provider performance results. Real-agent
and operational experiments belong to the separate thesis roadmap.

No automatic wiring of every daemon/agent path is implied. A host adopts this API
explicitly, supplying its real discovery and authority adapters. Persisted shared
caches, automatic plugin loading, remote leases and cross-process invalidation
are outside this implementation.

## Research Basis

- Mokhov et al., [Build Systems a la Carte, section 4.2.2](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-final.pdf):
  verifying dependencies before result reuse motivates the separate observer and
  preparation result. This cache does not implement a general build system.
- Gray and Cheriton, [Leases, sections 2 and 5](https://www.cs.cmu.edu/afs/cs.cmu.edu/academic/class/15712-s12/www/papers/gray89.pdf):
  expiration and failure assumptions matter. Our local TTL is NOT their server
  lease protocol and cannot guarantee remote consistency.
- Saltzer and Schroeder, [Protection principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html):
  complete mediation informs live authorization checks even on cache hits.
- Beyer et al., *Site Reliability Engineering*, [Handling Overload](https://sre.google/sre-book/handling-overload/):
  bounded capacity and explicit backpressure, rather than unbounded retained work.
  Only the public chapter was consulted, not the entire textbook.

These sources inform design decisions; their experimental results are not Golem
measurements, and a host supplying incomplete dependency identity remains unsafe.
