# RegWatch — Design Document

## 1. Problem Statement
RBI publishes hundreds of circulars, master directions, and amendments every year, and compliance teams have to manually work out what changed, whether it applies to them, and route it internally — a slow process where things get missed. RegWatch automates this: it continuously watches for new RBI publications, determines exactly what changed and who it affects, and delivers a cited alert to the right teams.

## 2. Goals & Non-Goals
Non Goals : 
Not legal advice — the system surfaces and summarises, it does not rule
RBI only — no SEBI, IRDAI, or MeitY in v1
English only
Not real-time — hourly polling is appropriate for this domain
Not a general chatbot
No historical backfill — "detect what's published from today onward" first; backfill is a separate, later problem

Goals : 
Every RBI publication gets reliably discovered — with a provable guarantee that nothing is silently missed, even during a burst of publications
Every claim about what changed is backed by a citation that resolves to real, verifiable text — any claim that doesn't gets rejected, not delivered
Subscribers are sent the appropriate alerts that they care about 
Every stage detects and surfaces its own failures rather than failing silently, so a "quiet" stage and a broken one are never mistaken for each other

## 3. System Context

1. **Watch** — continuously checks RBI's RSS feed for new or changed publications, and hands off a reference to each one it discovers.
2. **Fetch** — retrieves the actual content behind each reference, fingerprints it, and stores it immutably.
3. **Parse** — breaks that content down into individual, addressable clauses.
4. **Diff** — compares a new clause against whatever older clause it amends, and identifies exactly what changed.
5. **Assess** — uses an LLM to turn a detected change into a plain-language judgment (what changed, who it affects, the deadline), with every claim backed by a citation that resolves to real text.
6. **Deliver** — matches that judgment against subscriber interests, sends the alert, and records that it was sent.

## 4. Data Model

### Notifications

Created by the Watch stage. Stores the identity of every notification we've discovered — every later stage in the pipeline refers back to a row here rather than duplicating this information.

| Field | Description |
|---|---|
| Notification ID | RBI's own sequential ID for this notification — how every other table will refer back to it |
| Title | The notification's title |
| Link | URL to the notification's page, used by Fetch to retrieve its content |
| pubDate | The date RBI published the notification |
| discovered_at | The date/time our system found it (not the same as pubDate) |

### notification_content

Created by the Fetch stage. Stores the actual content of a notification — either the RSS `description` body (for RBI) or downloaded content (for sources that don't provide it upfront) — along with a fingerprint used to detect changes. Each row corresponds to a row in `notifications` via Notification ID.

| Field | Description |
|---|---|
| Notification ID | References the notification in `notifications` — checked first to see if this notification still needs fetching |
| raw_content | The actual content, either the RSS `description` body (RBI) or downloaded page content, depending on source |
| Hash | A fingerprint of `raw_content`, used to detect if the content has changed since it was last fetched |
| fetched_at | The date/time our system fetched it |

### clauses

Created by the Parse stage. Breaks a notification's `raw_content` into individual, addressable clauses — one row per clause, many rows per notification. Each row links back to `notifications` via Notification ID.

| Field | Description |
|---|---|
| Notification ID | References the notification in `notifications` — one notification maps to many clause rows |
| clause_number | The clause's position within the original document |
| clause_content | The actual text of that clause or paragraph |

### amendments

Created by the Diff stage. Acts as the arrow connecting two clauses — the clause doing the amending (source) and the clause being amended (target). Purely structural: no judgment or duplicated text is stored here, both are derived by joining back to `clauses` when needed.

| Field | Description |
|---|---|
| source_notification_id | Notification containing the clause that is doing the amending |
| source_clause_number | The specific clause, within the source notification, that contains the amending text |
| target_notification_id | Notification containing the clause being amended |
| target_clause_number | The specific clause, within the target notification, being changed |

### assessments

Created by the Assess stage. Produces a judgment for one source clause — what changed, who it affects, and the deadline. One assessment can cover multiple target clauses, across the same or different notifications, and is identified by the modifying (source) clause's notification ID and clause number.

| Field | Description |
|---|---|
| source_notification_id | Notification ID of the modifying (source) clause |
| source_clause_number | The specific clause within that notification performing the modification |
| summary | A short summary of what changed |
| applicability | Who the changes affect |
| deadline | Deadline to comply with the changes |
| assessed_at | When the assessment was completed |

### citations

Created by the Assess stage. Provides the proof behind every assessment, so claims aren't just AI hallucinations — every field of an assessment has citations pointing back to the actual clauses in the original RBI notifications that support it.

| Field | Description |
|---|---|
| source_notification_id | Identifies which assessment this citation belongs to |
| source_clause_number | Identifies which assessment this citation belongs to |
| assessment_field | Which field of the assessment (`summary`, `applicability`, or `deadline`) this citation supports |
| cited_notification_id | Notification ID of the notification containing the proof clause |
| cited_clause_number | The clause within that notification providing the proof |

### subscribers

Stores subscriber identities.

| Field | Description |
|---|---|
| subscriber_id | Our own invented identity for the subscriber — a primary key, since nothing external hands us one |
| name | The subscriber's name |
| email | Used to reach them — the only delivery channel supported in v1 |

### subscriber_categories

Maps subscribers to the categories they care about, so alerts can be matched and sent correctly. One subscriber can map to many categories.

| Field | Description |
|---|---|
| subscriber_id | References the subscriber in `subscribers` |
| category | The category this subscriber cares about — must be drawn from the same fixed list Assess uses for `applicability`, so matching is reliable |

### assessment_categories

Created by the Assess stage. Maps each assessment to one or more categories from the fixed list, enabling reliable matching against `subscriber_categories`.

| Field | Description |
|---|---|
| source_notification_id | Identifies which assessment this category belongs to |
| source_clause_number | Identifies which assessment this category belongs to |
| category | The category this assessment falls under — from the same fixed list used in `subscriber_categories` |

### deliveries

Created by the Deliver stage. An audit trail of every alert successfully sent to a subscriber — its existence proves delivery happened, preventing needless resending.

| Field | Description |
|---|---|
| source_notification_id | Identifies which assessment was delivered |
| source_clause_number | Identifies which assessment was delivered |
| subscriber_id | Which subscriber received the alert |
| delivered_at | When the alert was delivered |

### confirmed_dead_ids

Created by the Fetch stage. Tracks notification IDs confirmed to be permanently inaccessible or non-existent, so we never waste time and network resources retrying them.

| Field | Description |
|---|---|
| notification_id | The ID confirmed to be dead |
| confirmed_dead_at | When we confirmed this ID as dead |

### confirmed_dead_emails

Created by the Deliver stage. Tracks subscribers whose email address has permanently bounced, so we never waste effort retrying a delivery that will never succeed.

| Field | Description |
|---|---|
| subscriber_id | References the subscriber in `subscribers` — not the raw email, since contact details can change |
| confirmed_dead_at | When we confirmed this address as permanently undeliverable |

*More tables will be added here as we design them — one at a time, following the same process.*

## 5. Interface Contracts Between Stages

Watch — reads: the RBI RSS feed (external). Creates: rows in notifications.

Fetch - reads : a row from notifications. Creates : a row in notification_content 

Parse - reads : a row from notification_content. Creates : May create single or multiple rows in clauses 

Diff - reads : a row (a singular clause) from clauses. Creates : a row in amendments which maps each clause to the clause it modifies

Assess - reads : rows from amendments, joined against clauses to get the actual old and new text. Creates : a row in assessments (the modifying clause, what changed, who it affects, and the deadline), plus supporting rows in citations and assessment_categories.

Deliver - reads : assessment_categories joined against subscriber_categories to find matching subscribers, then assessments (for the alert content) and subscribers (for the email address). Creates : a row in deliveries for each alert successfully sent.


## 6. Failure-Mode Table

### Watch

| Failure | How we detect it | How we respond |
|---|---|---|
| RBI publishes more items than the feed holds before we poll again, so some fall off unseen | Compare the oldest ID currently in the feed against the last processed ID — a gap means items are missing in between | Fetch each missing ID directly |
| RBI's feed is unreachable (network issue or site down) | The poll request itself fails or times out | Retry with backoff; if down for an unusually long stretch, send an alert to distinguish "RBI is quiet" from "our poller is broken" |
| The same notification ID gets discovered twice | A row for that ID already exists in `notifications` | Skip it — existence proves we've already seen it |

### Fetch

| Failure | How we detect it | How we respond |
|---|---|---|
| Fetch runs more than once for the same notification ID (a retry after a crash, or a bug) and gets different content each time | Compare the newly fetched content's hash against the hash already stored in `notification_content` — a mismatch means this happened | Flag for investigation — this shouldn't happen under normal operation, and points to either a bug in our own logic or instability in RBI's page during the fetch |
| The specific notification's page is unreachable (network issue, timeout, RBI's server errors out) | The fetch request itself fails or times out | Retry with backoff; if persistently failing, flag for investigation |
| Trying to fetch a notification that isn't publicly accessible, or an invalid notification ID | A soft-404 — a fixed "not found" message in the HTTP response body, even though the request itself succeeds | Add a row to `confirmed_dead_ids` for that notification ID, and never retry it again |


### Parse

| Failure | How we detect it | How we respond |
|---|---|---|
| Parse produces zero clauses for a notification that has real content (covers both an outright crash and Parse silently failing to handle unusual HTML — both leave the identical signature) | The notification has a row in `notification_content` but no rows in `clauses` | Flag for investigation |
| Parse produces clauses that are wrong — garbled text, page furniture like nav menus, incorrectly split or merged paragraphs | No reliable automatic detection; cheap heuristics (e.g. suspiciously short clauses, abnormal clause counts) can catch *some* cases | Flag suspicious documents for manual review; true quality measurement happens via the labelled-sample process from Phase 4, not real-time detection |


### Diff

| Failure | How we detect it | How we respond |
|---|---|---|
| A source clause clearly amends something, but the target notification doesn't exist in our system at all — often because it's an older document published before RegWatch started running | Reference resolution finds no matching row in `notifications` for the stated target | Log as out-of-scope for v1 — expected under "no historical backfill," not a bug. Assess can still produce a partial judgment from the source clause's own text (applicability/deadline don't need the target at all), just without a full old-vs-new comparison. See Open Questions for a possible future on-demand fetch |
| A reference is too vague to confidently resolve to one specific target clause (ambiguous prose, no clean link, multiple plausible matches) | Reference extraction finds zero confident matches, or several with no way to pick one | Flag for manual review rather than guessing — a wrong automatic match would silently corrupt `amendments` with a false pairing |
| Diff resolves a reference to a plausible but wrong target clause (a false positive — two different documents happen to have similarly numbered paragraphs) | No reliable automatic detection, same honesty as Parse's garbled-clause problem | No clean fix in v1 — flag as a known risk; real improvement later would mean favoring explicit links over prose number-matching, or building a labelled eval set |


### Assess

| Failure | How we detect it | How we respond |
|---|---|---|
| The LLM hallucinates a citation | No row in `clauses` matches both the cited notification ID and the cited clause number together | Reject the LLM's output |
| The LLM API call fails | Network error, rate limit, or service outage | Wait and retry; if it keeps failing, alert |
| The LLM's output doesn't match the required schema | Output fails schema validation | Retry with a limit; alert if it's still failing once that limit is reached |

### Deliver

| Failure | How we detect it | How we respond |
|---|---|---|
| The email send attempt fails (network issue, provider error) | Send attempt fails | Wait and retry; alert if it keeps failing |
| A subscriber's email address is permanently invalid (bad address, invalid domain) | A permanent failure code from the provider, not a temporary one | Add a row to `confirmed_dead_emails` for that subscriber; no automatic fix — someone has to manually correct the address |
| Matching quietly produces zero deliveries when it shouldn't (e.g. a misconfigured category list) | No single-item signal exists for this; detected by noticing deliveries have unexpectedly dropped to zero for an unusually long stretch | Alert — likely points to a misconfiguration, not a one-off content issue |


## 7. Capacity Estimates

**What we actually measured**: RBI publishes roughly 1–1.5 notifications/day (ADR-0001: the RSS feed held 10 items, oldest ~8 days, measured 2026-07-24).

**Notifications**: ~500/year (1–1.5/day × 365).

**Clauses**: the average number of clauses per document isn't known yet — no real RBI document has been parsed. Using a working assumption of ~10-20 clauses/document, that's roughly 7,000-8,000 clauses/year — several times larger than `notifications`, as expected from the one-to-many relationship.

**Total data volume**: even at the higher end, each row is small (a clause is a paragraph of text, a few hundred bytes). That puts total growth at a few megabytes a year, climbing to maybe tens of megabytes over several years — trivially small for Postgres. This is the concrete evidence behind the brief's "one database is enough" decision, rather than just a hunch.

**Tables that don't scale with RBI's publication rate**: `subscribers`, `subscriber_categories`, and `deliveries` scale with product adoption — how many subscribers actually sign up — not with how much RBI publishes. There's no honest number to estimate here yet, and inventing one wouldn't mean anything.

**LLM cost per document**: not yet estimable. It depends on which model gets chosen and how many tokens a typical Assess call uses — decisions that happen in Phase 7. Will be tracked and published once that layer exists, per the brief's cost-tracking requirement.

## 8. Open Questions
<!--
Track anything unresolved here so it doesn't get lost between sessions.
-->

- Should clause numbering preserve RBI's own numbering scheme from the source document (e.g. "3.2" for a sub-point), instead of a plain sequential count assigned by our parser? Parked until Phase 4, when the parser is actually built against real documents.

- On-demand targeted fetch for Diff: when a source clause references a target document (via a resolvable ID/link) that doesn't exist in our system — usually because it predates RegWatch — we could trigger a one-off fetch + parse of just that document instead of logging it as out-of-scope. This reuses the same "fetch a known ID directly" mechanism as ADR-0001's gap recovery, and needs no new tables, so it's a clean addition later rather than a redesign. Deferred for v1 because it adds a new cross-stage trigger (Diff invoking Fetch/Parse mid-flight), breaking the otherwise clean "stages only read forward" pipeline shape — worth revisiting once the core pipeline is working end-to-end.

- Diff/Assess inconsistency: Diff's failure table says "Assess can still produce a partial judgment" when a target document is missing (Diff's Failure 1). But Assess's interface contract only reads from `amendments` rows, which never get created when Diff's Failure 1 happens — so there's currently no actual path for Assess to run in that case. The promise isn't achievable with what we've built yet. Needs a real decision on how Assess would read a source clause that never got a full `amendments` row, before this can be considered resolved.
