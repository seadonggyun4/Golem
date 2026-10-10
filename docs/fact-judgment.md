# Execution facts and judgment deltas

Per-judgment `evidence_verification` uses the [common contract](evidence-verification.md),
separating the declaration from parser checks and referenced execution facts.

`tools/judgment_record.py` is the ordinary-task contract consumed by
`agent_io.py judgment-facts`, `judgment-write`, and `judgment-view`.
No hypothesis, intervention, case enrollment, or research schema is required.
Existing native research validation and Work authority remain unchanged.

## Contract

1. Run an explicitly approved command plan through the existing recorder.
2. `judgment-facts BUNDLE --project-id PROJECT --work-id WORK` validates the
   complete observation inventory and returns content-addressed step facts.
   Exit codes, failed launches, timeout reasons, NOT_RUN, executable/log hashes,
   source snapshots and provider usage stay recorder-owned, not manually authored.
3. Provide only changed judgments in a `golem.judgment-delta.v1` object:

```json
{"schema":"golem.judgment-delta.v1","actor":"agent",
 "set":{"next_action":{"text":"Investigate the recorded failure",
                         "fact_ids":["COPY_EXACT_FACT_ID_FROM_FACTS_VIEW"]}},
 "remove":[]}
```

4. `judgment-write BUNDLE --project-id PROJECT --work-id WORK --delta DELTA.json
   --output NEW_DIRECTORY` publishes an immutable private bundle. For subsequent
   changes supply `--since PREVIOUS_DIRECTORY --revision EXACT_RECORD_SHA256`.
   Unchanged judgments need not be repeated; empty set/remove is valid.
5. `judgment-view NEW_DIRECTORY` derives current judgments and the latest delta
   by validated replay. No separate status, assessment, or report is authored.

The actor ID is a declaration, not authenticated identity. Project and Work are
explicit; conflicting recorded scope or provider attribution is rejected.
Unscoped executions are marked DECLARED_BINDING, not a native WorkRun binding.
Each judgment cites one or more facts from its current observation. Fact IDs bind
the complete recorded step to its observation revision, preventing cross-run
substitution. A prose assertion remains DECLARED_NOT_VERIFIED even if exit=0.
Carried judgments are HISTORICAL_REQUIRES_REVIEW, even for identical source hashes.
Neither tool mutates native Work, approves execution, or establishes QA PASS.

## Integrity and limits

The bundle stores immutable delta entries, exact observation snapshots, and parent
entry hashes. Replay checks revisions, parent links, references, and change shape.
Baseline revision mismatch is an error, not an implicit full rewrite or rebase.
Publication refuses overwrites and overlapping evidence directories. Manifest is
written last; partial directories are not valid bundles. Hashes detect accidental
corruption, not a malicious rewrite with recomputed hashes or producer forgery.

Limits: 256 entries, 64 active judgment keys, 64 changes/removals per entry,
32 fact references and 8192 characters per judgment, plus the existing bounded
JSON input size. This is a bounded handoff contract, not an unbounded event store.
Long histories require an explicitly designed migration, not silent truncation.

Raw streams remain in the original observation bundle. Snapshots support judgment
replay without it, but **not** standalone raw-evidence validation or export recovery.
`raw_embedded=false` makes that distinction explicit. Reopen the original intact
bundle for stream inspection. Evidence may contain sensitive arguments and paths;
private modes do not redact or authorize disclosure.

## Research basis

Reviewed sources and engineering applications (not measured cost-saving claims):

- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), core entities, activities,
  derivation and responsibility: keep execution observations separate from
  attributed interpretations. This JSON contract is not a claim of PROV compliance.
- Koop et al., *Bridging Workflow and Data Provenance using Strong Links*
  (SSDBM 2010), abstract/introduction and strong-link design:
  [paper](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/11/stronglinks-ssdbm2010.pdf).
  Bind references to content and run identity rather than filenames alone.
  Unlike the paper's managed storage, this contract does not embed raw outputs.
- Abiteboul, Hull and Vianu, *Foundations of Databases* (1995), chapter 11,
  [Design and Dependencies](https://webdam.di.ens.fr/Alice/pdfs/Chapter-11.pdf),
  introductory design criteria: preserve information and metadata while avoiding
  update anomalies. The application here is one replayed judgment state instead
  of separately maintained copies; this is not a formal normalization proof.

Tests use actual local subprocess observations, not fabricated PASS artifacts:
ordinary task, empty delta, replacement/removal, failed and unrun steps,
wrong baseline/Work, unknown evidence, corruption, replay checks and CLI views.
