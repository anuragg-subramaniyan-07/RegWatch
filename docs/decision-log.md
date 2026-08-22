# RegWatch — Decision Log

## Session 1 — 2026-08-03

### What we built
ADR-0001 - RSS gap detection 
ADR-0002 - Append only pipeline

Data models for all the various stages : Watch , Fetch , Parse, Diff , Assess and Deliver 

Tables needed for all the stages 

### What we decided, and why

- RSS gap detection via sequential ID reconciliation — see ADR-0001.
- Append-only, one-record-per-completed-stage instead of a single evolving row — see ADR-0002.
- **Assessments are grouped by source clause**, not by whole notification and not by individual target amendment. Grouping by notification risked mashing unrelated changes together; grouping by individual amendment risked splitting one coherent RBI action (one clause amending several targets) into duplicate, fragmented assessments.
- **Diff makes no substantive/cosmetic judgment call** — that's deferred entirely to Assess. Diff only detects that a difference exists (mechanical, deterministic). Putting an LLM in Diff too would mean paying to read the same text twice, and would make an early pipeline gate non-deterministic and harder to test.
- **Citations are tracked per field** (`summary`, `applicability`, `deadline` each have their own citations), not as one shared pool per assessment — matches the brief's literal wording on the citation guarantee and gives a stricter, individually-checkable proof for every claim.
- **`applicability` (free text) and `category` (fixed list) are kept as separate fields**, even though both describe "who's affected." Free text is for a human reading the alert; the fixed-list category exists purely so subscriber matching can be an exact comparison instead of guessing at AI-generated prose.
- **Subscribers get an invented `subscriber_id` (primary key)** rather than using email as their identity, so contact details can change without needing to update every table that refers to them.
- **Delivery is email-only for v1** — keeps scope small, avoids integrating a separate SMS/phone provider for no proven need yet.
- **Repeated principle: compute or join instead of storing a duplicate.** Applied to `Link` (not re-stored on `notification_content`), `parsed_at` (not stored per-clause), the RSS watermark (computed via `MAX(id)`, not stored separately), and whether an amendment's text actually changed (derived via join, not stored as a flag).

### Still open

- Should clause numbering preserve RBI's own numbering scheme (e.g. "3.2") instead of a plain sequential count? Parked until Phase 4, when the parser is built against real documents.
- Distinguishing "a stage hasn't started yet" from "a stage started and failed" — flagged as an open gap in ADR-0002's consequences, likely solved later with a job/run-tracking mechanism, not by any table we've built.
- Retry policy for gap-filled IDs that turn out to be permanently non-public (soft-404) — flagged in ADR-0001, not yet decided.
- What happens if the same notification ID is discovered twice by Watch — flagged during the `notifications` table design, deferred to the Failure-Mode Table.
- Remaining design doc sections not yet written: Problem Statement, Goals & Non-Goals, System Context, Failure-Mode Table, Capacity Estimates.

## Session 2 — 2026-08-22

### What we built
- The complete Failure-Mode Table — all six stages (Watch, Fetch, Parse, Diff, Assess, Deliver), each with real, reasoned failure modes rather than filler rows.
- Two new tables: `confirmed_dead_ids` (Fetch) and `confirmed_dead_emails` (Deliver) — both following the same "existence proves a permanent state, stop retrying" pattern.
- The remaining design doc sections: Problem Statement, Goals & Non-Goals, System Context, Capacity Estimates.
- This closes out the entire design document — all 8 sections, all 12 tables.

### What we decided, and why
- **Parse's "crashes" and "produces zero clauses" failure modes were merged into one row**, once we realized they leave an identical signature (content exists, no clauses exist) — but only *because* Parse must write all of a notification's clauses inside one atomic transaction. Without that guarantee, a crash could leave a silently incomplete, dangerous partial result instead of a clean zero. This is the reason a database transaction (all-or-nothing writes) is required here, not optional.
- **Diff's "target doesn't exist" and "reference is too ambiguous to resolve" failure modes are genuinely different**, even though both end in "no confident target." The distinction is *where* resolution fails: extraction succeeding but lookup failing (safe to degrade gracefully, we know exactly what's missing) versus extraction itself failing (risky to guess, could silently corrupt `amendments` with a wrong pairing).
- **On-demand targeted fetch for Diff** (recovering an old, out-of-scope referenced document by fetching its specific known ID, reusing ADR-0001's mechanism) was deliberately deferred rather than built now — it's cheap and doesn't require new tables, but it does add a new cross-stage trigger that breaks the pipeline's otherwise clean "stages only read forward" shape. Parked in Open Questions, not rejected.
- **Discovered a real inconsistency**: Diff's failure table promises Assess can still produce a partial judgment when a target is missing, but Assess's interface only reads from `amendments` — which never gets created in that exact case. The promise currently has no path to being fulfilled. Parked in Open Questions rather than papered over.
- **Citation validation has two levels, and we're only building the weaker one for now**: checking a citation "exists somewhere in our database" is not the same as checking it was part of what was actually handed to the LLM for that specific call. The stronger check matters much more once real retrieval (Phase 6) gives the LLM a much larger pool to potentially misattribute from. Not solved now, named honestly for later.
- **Goals were rewritten from mechanism to outcome.** The first draft mostly restated the six pipeline stages' jobs — redundant with System Context. Rewrote as four checkable promises: reliable discovery (ties to ADR-0001), the citation guarantee (ties to Assess/citations), correct subscriber routing, and system-wide failure surfacing (ties to the whole Failure-Mode Table) — the last one added as its own goal since it was built into every single stage today, not just Watch.
- **Capacity Estimates grounded in the one real measurement we have** (ADR-0001's ~1-1.5 notifications/day) rather than invented numbers: ~500 notifications/year, ~7,000-8,000 clauses/year, all of it trivially small for Postgres — real evidence behind the brief's "one database is enough" call. Explicitly left LLM cost-per-document and subscriber-driven tables (deliveries, subscribers) as not-yet-estimable, rather than faking precision.

### Still open
- Should clause numbering preserve RBI's own numbering scheme (e.g. "3.2") instead of a plain sequential count? Parked until Phase 4.
- Distinguishing "a stage hasn't started yet" from "a stage started and failed" — still needs a future job/run-tracking mechanism (ADR-0002).
- On-demand targeted fetch for Diff — designed, deliberately deferred, not built.
- The Diff/Assess inconsistency — needs a real decision on how Assess would read a source clause that never got a full `amendments` row.
- The "weak vs strong" citation check — current check only confirms a citation exists in our database, not that it was part of what was actually retrieved for that call. More important once Phase 6 retrieval exists.
- **Resolved this session, no longer open**: retry policy for permanently-dead gap-filled IDs (now `confirmed_dead_ids` + Fetch's failure table), and duplicate notification discovery (Watch's failure table).
- Next up per the brief's Phase 1 checklist: repo scaffolding, CI, and Docker Compose — the design/data-model/ADR side of Phase 1 is now fully done.
