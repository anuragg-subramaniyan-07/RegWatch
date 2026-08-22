# ADR 0001: Detect and recover RSS feed gaps using sequential ID reconciliation

## Status
Accepted

## Context
The RSS feed only shows the 10 latest items. If we poll once an hour and a bunch of items get published in between, older items (which we never read) get flushed from the feed before we see them — meaning we silently miss changes we should have tracked.

We measured this on 2026-07-24: the feed held 10 items, and the oldest one was about 8 days old, meaning RBI is publishing roughly 1-1.5 notifications a day right now. That's a thin buffer — a single unusually busy day could push more than 10 items through before our next check.

## Options Considered
Option A: increase polling frequency — instead of polling every hour, poll every 15-20 minutes. Problem: if a large dump happens even within that smaller window, we still miss items. This isn't a real solution, just a band-aid that lowers the odds without ever giving us certainty.

Option B: keep track of the last item ID we've fully processed. Each time we poll, compare it against the oldest ID currently in the feed. Since notification IDs are sequential integers, any gap between the two tells us exactly which IDs we missed — not a guess, a certainty. We then fetch each of those specific IDs directly. This works even though blindly probing random unpublished IDs is unreliable (per our earlier RSS research) — the difference here is we already know these specific IDs exist, we just haven't fetched them yet.

## Decision
We chose Option B: track the last processed ID, detect any gap on each poll by comparing it to the oldest ID in the current feed, and directly fetch every ID in that gap rather than relying on polling frequency to avoid misses.

## Consequences
- We need a small persistent store for "the last ID we've fully processed" between polling runs — this is state the Watch stage now owns.
- Some IDs we try to fetch in a gap may return the "No Notification Found" soft-404 — meaning that ID was never a public notification (e.g. an internal or withdrawn entry), not a miss. We need a clear rule that stops retrying an ID once we've confirmed this, rather than treating it as "not published yet" forever. This retry policy is still open — future work.
- Items recovered through gap-filling will be discovered later than items caught on a normal poll, so their alerts may go out later than usual. Accepted trade-off: a late-but-correct alert beats a silently missing one.
- We keep hourly polling as sufficient — correctness no longer depends on catching everything within the poll window, which removes the pressure to also adopt Option A.
