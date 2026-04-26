# Identity Hub

The identity hub is the part of NASO that turns a stream of disconnected indicators into a master-identity graph an analyst can reason about. This page walks through the four pieces that make it work: normalization, near-duplicate detection, evidence-based merging, and risk scoring.

## Pipeline

```
ingest → upsert_identity (normalize + ON CONFLICT)
       → link to LeakHit (idempotent via ON CONFLICT)
       → mark_dirty for risk recompute
       → MITRE technique mapping
       → notification (if VIP or severity ≥ critical_threshold)

       merge_proposer.propose_and_merge runs on demand or on a schedule
       → gathers shared-leak pairs above a strength threshold
       → aggregate_confidence
       → merge_identities (writes a MergeEvent ledger row)
       → mark master_identity_id on the slave
```

Source files: [`identity_upsert.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/identity_upsert.py), [`merge_proposer.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/merge_proposer.py), [`entity_resolution.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/entity_resolution.py), [`risk_scoring_v2.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/risk_scoring_v2.py).

## Normalization

The `Identity.identifier` column stores the surface form the analyst typed; `Identity.normalized_identifier` stores the canonicalized key. The unique constraint is on `(tenant_id, type, normalized_identifier)`, so two analysts entering the same address in different forms collapse onto a single row.

Rules in [`shared/domain/normalization.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/normalization.py):

| Type    | Surface form                | Normalized                     |
|---------|-----------------------------|--------------------------------|
| email   | `Alice.B+spam@Gmail.com`    | `aliceb@gmail.com`             |
| email   | `bob@CORP.local`            | `bob@corp.local`               |
| phone   | `+1 (415) 555-0199`         | `14155550199`                  |
| domain  | `CORP.LOCAL`                | `corp.local`                   |
| handle  | as-is, lowercased + trimmed |                                |

Test matrix: [`backend/tests/test_normalization.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_normalization.py).

`upsert_identity` calls normalize, then runs `INSERT … ON CONFLICT (tenant_id, type, normalized_identifier) DO UPDATE` so concurrent ingest races don't produce duplicates.

## SimHash near-duplicate detection

Two breach dumps that differ only in whitespace, line endings, or formatting should collapse onto one `LeakHit`. NASO uses 64-bit [SimHash](https://en.wikipedia.org/wiki/SimHash) for that.

[`ingest_leak`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/leak_ingest.py) does:

1. **Canonicalize**: lowercase, strip punctuation, collapse whitespace. Stored in `LeakHit.normalized_content` as a secondary exact-match key.
2. **Hash**: 64-bit SimHash over the canonicalized content. Stored signed (as `bigint`) in `LeakHit.simhash64` with an index.
3. **Lookup**: candidate rows = same source, Hamming distance ≤ 3. If a candidate exists, the new ingest **bumps severity** on the existing row (monotonic — never downgrade) and merges metadata.

The Hamming threshold is conservative; 3 of 64 bits = ~5% disagreement. Test: [`backend/tests/test_simhash_dedup.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_simhash_dedup.py).

The AI co-analyst exposes this as the `find_near_duplicates` tool: paste a content blob, get back existing leaks that are a near-match.

## Evidence-based merging

Two identities should be merged when there's evidence they belong to the same person. The current implementation uses **shared leaks** as the evidence type:

- Two identifiers that appear in *the same* breach dump are likely the same person.
- The more shared leaks, and the higher their severity, the higher the merge confidence.

`merge_proposer.gather_shared_leak_pairs` computes the candidate set; `aggregate_confidence` rolls multiple evidence items into one number in [0, 1]. The merge runs only above a configurable confidence floor (`SHARED_LEAK_STRENGTH * count` ≥ threshold).

When a merge fires:

```python
merge_identities(db, master, slave, evidence=[...], confidence=0.84)
```

writes a `MergeEvent` row (the merge ledger), sets `slave.master_identity_id = master.id`, marks both identities dirty for risk recompute, and audits.

### Reverse merges

Soft reversal preserves the append-only ledger. Reversing a merge:

- Sets `MergeEvent.reversed_at = NOW()` + `reverse_reason`.
- Clears the slave's `master_identity_id`.
- Writes a fresh audit row for the reversal.

The original merge event stays — the ledger remains a complete history of "what was merged when, and which of those were later undone".

API: `POST /identities/merges/{event_id}/reverse` with `{ "reason": "..." }`.

### Invariants

The merge engine refuses several operations and raises explicit exceptions:

| Exception                | When                                                       |
|--------------------------|-----------------------------------------------------------|
| `CrossTenantMerge`       | master and slave belong to different tenants              |
| `VipInvariantViolation`  | merging a VIP-protected identity *into* a non-protected master (which would silently de-elevate it) |
| `InsufficientEvidence`   | confidence below the threshold                            |
| `MergeAlreadyExists`     | a non-reversed merge between the same pair already exists |

Tests: [`backend/tests/test_merge.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/tests/test_merge.py).

## Risk scoring v2

Scoring is **lazy**. `mark_dirty(identity_ids)` flips `Identity.risk_score_dirty = True`; a periodic worker drains dirty rows and recomputes. The reasons are detailed in [`risk_scoring_v2.py`](https://github.com/fabriziosalmi/naso/blob/main/shared/domain/services/risk_scoring_v2.py); the short version:

- Eager recompute on every linked-leak insert was N round trips per ingest, blocking the hot path.
- The walk up the merge cluster (so a slave's new leak bumps the master's score) only needs to happen once even if the slave gets many new leaks in a burst.

The score is a composite of:

- **Breadth**: number of distinct breach sources.
- **Depth**: severity scores of linked leak hits.
- **Recency**: timestamp of the most recent compromise.

Capped at `MAX_SEVERITY_SCORE = 100`. `CRITICAL_SCORE_THRESHOLD = 80` (env-overridable) is the line above which webhooks fire and the SPA shows the "Critical Risk" badge.

## VIP protection

Toggle via `PATCH /identities/{id}/protect` with `{ "is_protected": true }`. When set:

- The identity's name appears with the lock badge in the dashboard.
- Notifications fire even on lower-severity leaks.
- The merge engine refuses to merge it under a non-VIP master (`VipInvariantViolation`).

Audit: every toggle writes a row.

## API surface

| Endpoint                                     | Method | Notes                                                       |
|----------------------------------------------|--------|-------------------------------------------------------------|
| `/identities/`                               | GET    | List for the tenant; `?only_masters=1` filters slaves       |
| `/identities/`                               | POST   | Register a new monitored identity                           |
| `/identities/{id}/insights`                  | GET    | Deep profile + breach history + merged-identity tree        |
| `/identities/{id}/protect`                   | PATCH  | Toggle VIP                                                  |
| `/identities/{id}/merges`                    | GET    | Merge history for one identity                              |
| `/identities/merges`                         | GET    | Recent merges across the tenant                             |
| `/identities/merge`                          | POST   | Trigger automatic batch merge                               |
| `/identities/merge/preview`                  | GET    | Dry-run; returns candidate pairs + confidence               |
| `/identities/merge/execute`                  | POST   | Execute a caller-selected subset of candidates              |
| `/identities/merges/{event_id}/reverse`      | POST   | Reverse a merge (requires `reason`)                         |
| `/identities/graph`                          | GET    | Force-graph topology for the dashboard                      |
