# Parser improvement plan

## Purpose
Keep the document registration contract explicit and bounded.

## Scope
Only document registration is included; product code is outside this work.

## Parents
This initial plan has no upstream document revisions.

## Evidence
The current public API and the parser fixture define the observed baseline.

## Decisions
Store exact UTF-8 bytes instead of rewriting authored Markdown during registration.

## Requirements
REQ-1 requires byte-identical retrieval of the committed revision.

## Work
Implement bounded validation and verify the immutable registration receipt.

## Validation
Read the committed content and compare its SHA-256 digest to the receipt.

## Risks
Structural validation does not establish semantic correctness or business acceptance.

## Acceptance
REQ-1 is checked by byte comparison and a corruption rejection test.
