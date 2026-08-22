# Project Brief: RegWatch — Regulatory Change Intelligence

Paste this entire document as your first message in a new Claude Code session.

---

## Who I am and what I need from you

I'm a pre-final-year Computer Science student. I have working knowledge of Python and basic exposure to Docker, Kubernetes and CI/CD, but I have never built a production-grade system end to end. I'm building this project over roughly three months as the flagship item on my resume, targeting software engineering roles that involve AI integration.

**Your job is not to build this for me. Your job is to teach me to build it.**

That distinction governs everything below. If at any point you find yourself producing a large amount of code quickly so we can "make progress," you have misunderstood the assignment. I would rather finish 60% of this project understanding every line than 100% of it understanding none.

---

## How I want you to work with me

### The core loop

For every unit of work, follow this cycle:

1. **Explain the problem** we're about to solve and why it matters in this system.
2. **Present the options** — at least two realistic approaches, with genuine trade-offs. Not a strawman and a winner.
3. **Ask me to choose** and give my reasoning, before you tell me yours.
4. **Tell me what you'd choose and why**, including what we're giving up. If I chose differently and I'm wrong, say so directly and explain why. If I chose differently and it's defensible, say that too.
5. **Write the code in small pieces** — one function, one module, one concept at a time.
6. **Explain immediately after writing**, line by line where the concept is new to me, at a higher level where it's a pattern I've already seen.
7. **Check my understanding** by asking me a question about what we just wrote. Not "does that make sense?" — a real question that I can get wrong.
8. **Only then move on.**

Never write more than roughly 50 lines of code without stopping to explain. Never write two files in a row without checking in.

### Teaching from primary sources

When we use a language feature, library, protocol, or pattern I haven't used before, **teach it from the official documentation, not from your own summary.** Link me to the specific page. Tell me which section to read. Where the docs are dense, explain what the docs are actually saying and why it's written that way.

This applies to, among other things:
- Python: type hints, dataclasses, async/await, context managers, the standard library modules we use
- Pydantic: validation model, v2 specifics, why runtime validation matters at system boundaries
- FastAPI: dependency injection, request/response models, why it's built on the ASGI standard
- HTTP: status codes, caching headers, conditional requests, content negotiation
- SQL and PostgreSQL: indexing, transactions, isolation levels, the specific features we lean on
- REST/API design: resource modelling, idempotency, pagination, versioning, error shapes
- Docker: images vs containers, layer caching, why multi-stage builds exist
- Git: branching model, atomic commits, writing commit messages that explain *why*
- Testing: unit vs integration, fixtures, what makes a test valuable vs noise
- Later: Terraform, AWS primitives, CI/CD, observability

Before we first use any of these, give me a short primer with links and tell me what to read. Don't dump a curriculum on me up front — introduce each thing at the moment it becomes relevant, so I learn it in context.

### Pace and checkpoints

- I will sometimes say **"pause"** — when I do, stop and let me read, run, and break things before we continue.
- I will sometimes say **"let me try this one"** — when I do, give me the interface and the requirements, let me write the implementation, then review it honestly. Point out what's wrong, what's fragile, and what's fine.
- At the end of each work session, summarise: what we built, what decisions we made, what's still open. Write this into the project's decision log.

### How to correct me

Be direct. If my design is wrong, say it's wrong and explain the failure it will cause. Don't soften it into a suggestion. I am here to be taught, and false encouragement wastes my time. Equally, don't manufacture criticism when something is genuinely fine.

---

## The project

### The problem

Indian financial institutions — banks, NBFCs, payment companies — operate under continuous regulatory supervision. The RBI publishes hundreds of circulars, master directions, and amendments each year. Changes are surgical: a circular typically amends a specific paragraph of a document published years earlier. Compliance teams manually read everything published, work out what changed, work out whether it affects them, and route it internally. It's slow and things get missed.

### What we're building

A system that continuously watches the RBI, detects when a regulation changes, determines what changed and who it affects, and delivers a cited alert to subscribed teams.

The pipeline, in stages:

1. **Watch** — poll RBI sources, emit references to new or changed documents
2. **Fetch and store** — retrieve content, hash it, deduplicate, archive immutably
3. **Parse** — turn documents into a structured tree of clauses
4. **Diff** — align clauses across versions and classify changes as substantive or cosmetic
5. **Assess** — use an LLM to produce a structured, cited judgment: what changed, who it affects, what the deadline is
6. **Deliver** — match assessments against subscription profiles and send alerts

The AI is a component inside a real distributed system, not the whole project. The system's value is that it runs continuously and notices things.

### Explicit non-goals for v1

State these back to me if I ever start drifting into them:

- Not legal advice — the system surfaces and summarises, it does not rule
- RBI only — no SEBI, IRDAI, or MeitY in v1
- English only
- Not real-time — hourly polling is appropriate for this domain
- Not a general chatbot
- **No historical backfill** — "detect what's published from today onward" first; backfill is a separate, later problem

Scoping ruthlessly is part of what I'm here to learn. Push back if I try to expand scope mid-build.

---

## Research I've already done — do not redo this

I surveyed the RBI's publication surface before writing any code. Here's what I found. Use it; don't re-derive it.

**The notifications listing** is at `https://rbi.org.in/Scripts/NotificationUser.aspx`. Content is in the raw HTML (no JavaScript rendering needed). Each entry gives two links: an HTML page (`NotificationUser.aspx?Id=NNNNN&Mode=0`) and a PDF on a separate host (`rbidocs.rbi.org.in`). The date is **not** attached to each row — it appears as a header row above a group of entries, so a parser has to carry the current date forward as it walks the rows.

**Year and month navigation does not use URLs.** The links are `href="#"` and trigger ASP.NET postbacks. There is no fetchable URL for "June 2024." Historical access would require replaying `__VIEWSTATE` and `__EVENTTARGET` form fields. This is a real obstacle and one of the reasons backfill is deferred.

**Document IDs are sequential integers.** Each notification gets the next integer.

**Probing an unpublished ID returns a soft 404** — the page loads with HTTP 200 and displays "No Notification Found." Status code alone is not a reliable success signal here; content must be validated. Also, a missing ID is ambiguous between "not published yet" and "permanent gap," so ID probing is not a reliable primary discovery mechanism.

**There is an RSS feed** at `https://rbi.org.in/notifications_rss.xml`. This is the key finding. Each `<item>` contains:
- `<title>` — the notification title
- `<link>` — the HTML page URL, containing the `Id`
- `<pubDate>` — RFC 822 timestamp
- `<description>` — **the full body of the circular as HTML**, not a summary

That `<description>` field is significant. It gives us the circular's own reference number and department code, its date, its explicit addressee (e.g. "All Authorised Dealer Category-I Banks" — which is the applicability field, stated outright), cross-reference links to other circulars carrying their `Id`s, and in many cases an explicit table of which older circulars are repealed. Structured HTML with paragraph tags, headings and tables — which means for anything published from now on, we may not need PDF parsing at all.

**Open question I have not yet checked:** how many items the feed holds and how far back the oldest one goes. This determines the maximum safe polling gap. Have me verify this early.

---

## Technical direction

I've provisionally settled on the following. Treat these as starting positions, not commandments — if you think one is wrong for this project, argue the case and I'll listen.

**Backend:** Python 3.12, FastAPI, Pydantic v2
**Database:** PostgreSQL 16 with `pgvector`, migrations via Alembic
**Retrieval:** hybrid — Postgres full-text search plus dense vectors, fused, then reranked
**LLM layer:** API-based, with schema-constrained structured outputs. **No orchestration framework** — I want to write the orchestration explicitly so I understand it.
**Frontend:** Next.js with TypeScript and Tailwind, kept deliberately small
**Testing:** pytest, with recorded HTML/XML fixtures so the test suite never touches the network
**Later:** Docker, Terraform, AWS, GitHub Actions, OpenTelemetry

**Deliberate simplifications for the early phases:**
- Scheduling starts as a plain script plus cron. No Temporal, no Celery. I want to feel the problems those tools solve before adopting them. If and when the pain is real, we discuss upgrading — and you should tell me when you think we've hit that point.
- One database. If I propose adding a dedicated vector store or a search engine, challenge me on whether the measured benefit justifies a third consistency problem.

---

## Non-code deliverables I want you to insist on

These matter as much as the code. Do not let me skip them.

**A design document**, written before the main build, covering: problem statement, non-goals, data model, failure modes, rough capacity estimates.

**Architecture Decision Records** — one short file per significant decision, in the format: context, options considered, decision, consequences. Every time we make a real choice, we write one. Prompt me to write it; review what I write.

**A failure-mode table per stage** — what can go wrong, how we detect it, how we respond.

**A decision log** updated at the end of each session.

**Git discipline** — small commits, conventional commit messages, PR descriptions that explain the reasoning rather than restating the diff.

**Cost tracking** — once the LLM layer exists, we instrument cost per document processed and I publish the number in the README.

---

## Phase plan

Roughly twelve weeks. Adjust as we learn, but keep me honest about scope.

| Phase | Focus |
|---|---|
| 1 | Design doc, data model, ADRs, repo scaffolding, CI, Docker Compose |
| 2 | Watch stage — RSS adapter behind a source-agnostic interface, fixtures, tests |
| 3 | Fetch and store — hashing, idempotency, immutable archive, Postgres schema |
| 4 | Parse — HTML body into a clause tree; measure parse quality on a labelled sample |
| 5 | Diff — clause alignment across versions, substantive vs cosmetic classification |
| 6 | Retrieval — chunking, hybrid search, reranking. Golden eval dataset built **first** |
| 7 | AI assessment — schema-constrained output with enforced citation resolution |
| 8 | API and delivery — subscriptions, matching, alerts |
| 9 | Frontend — change feed, diff view, search |
| 10 | Containerisation and CI/CD pipeline |
| 11 | Terraform, AWS deployment, observability with OpenTelemetry |
| 12 | Load testing, cost analysis, README with architecture diagram and eval numbers, demo video |

The infrastructure and cloud phases are not optional extras — they're a specific thing I want to learn properly, so treat Terraform and AWS with the same teaching depth as the application code.

---

## Two design principles I want held throughout

**Silence is suspicious.** A scraper that returns zero results looks exactly like a quiet week at the regulator. Anywhere the system can fail silently, we need an explicit detector. Keep raising this.

**Every AI claim carries a resolvable citation.** If a generated field cites a clause that doesn't resolve to real retrieved text, we reject the output. This is an architectural guarantee, not a prompt instruction.

---

## Start here

Don't write any code yet. Begin by:

1. Confirming you've read and understood this brief, and flagging anything in it you think is a bad idea.
2. Walking me through what a design document for this system should contain, and why each section earns its place.
3. Then starting the design process with me — beginning with the data model, since getting the entities right is worth more than any code we write later.

Ask me questions. Make me justify things. Let's begin.