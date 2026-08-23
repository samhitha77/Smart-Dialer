# Architecture Decision Document

This document records every significant design decision made during the
SmartDialer prototype, explaining what was chosen, why, and what trade-offs
were accepted.

---

## 1. Why Python?

**What:** Python 3.11+ as the implementation language.

**Why:**
- The assignment explicitly requests it.
- Python's SQLAlchemy ORM makes the atomic UPDATE pattern transparent and easy
  to understand.
- FastAPI is the fastest Python web framework and auto-generates API docs.
- The test suite (pytest) is mature and produces clear output.
- The entire system can be explained in an interview without JVM/GC/classpath
  complexity.

**What it makes harder:**
- Python's GIL limits true CPU parallelism.
- In production, a high-throughput dialer would likely use Go or Java for the
  hot path.  For this prototype, Python's I/O-bound nature (DB writes,
  provider HTTP calls) means the GIL is rarely a bottleneck.

---

## 2. Why SQLite?

**What:** SQLite as the persistence layer.

**Why:**
- Zero configuration — no database server to install or run.
- Supports the `UPDATE ... WHERE state='AVAILABLE'` atomic rowcount trick that
  is the core of our concurrency-safe reservation system.
- In WAL (Write-Ahead Log) mode, SQLite allows one concurrent writer and many
  concurrent readers — sufficient for a prototype.
- The schema is simple enough that SQLite is not a constraint.

**What it makes harder:**
- SQLite has one writer at a time.  At high concurrency (>50 threads writing
  simultaneously), lock wait time increases.
- For production at 10,000+ agents, switch to PostgreSQL.  The reservation
  logic requires **zero changes** — the SQL is identical.

---

## 3. Why NOT Kafka, Redis, or Kubernetes?

**What:** No message queues, caches, or orchestration systems.

**Why:**
- The assignment explicitly states: *"Do NOT introduce Kafka, Redis, Kubernetes,
  unless there is a strong technical reason."*
- Our concurrency problem (two workers racing to reserve an agent) is perfectly
  solved at the database level.  Adding Redis for a distributed lock would be a
  more complex solution to the same problem.
- A message queue (Kafka) would add deployment complexity and make the
  test suite require a running broker.
- The prototype must be runnable with `pip install -r requirements.txt`
  and `uvicorn app.main:app` — nothing else.

**What it makes harder:**
- Without a message queue, the dialing loop runs on a schedule (or on
  API request) rather than being event-driven.  In production, a dedicated
  dialer process would publish call initiation events to a queue.

---

## 4. Why separate the Pacing Engine and Safety Controller?

**What:** Predictive pacing is in `app/dialer/predictive.py`.
The Safety Controller is in `app/safety/safety_controller.py`.
They are separate classes with no shared imports.

**Why:**
- **Single responsibility:** The pacing engine answers "how many calls should
  we make?" The Safety Controller answers "how many are actually safe?"
  These are different questions.
- **Bypass prevention:** If pacing and safety were the same class, a bug in
  the pacing logic could accidentally disable the safety checks.
- **Testability:** The Safety Controller is a pure function of a
  `SystemSnapshot` dataclass.  It can be tested without a database.
- **Architectural enforcement:** The pacing engine has no import of any
  provider class.  The only path to the provider is:
  `Pacing → Safety → Allocator → Provider`.

**What it makes harder:**
- An extra function call per cycle.  Negligible in practice.

---

## 5. How is agent reservation made concurrency-safe?

**What:** An atomic SQL UPDATE with a conditional WHERE clause and rowcount check.

**How it works:**
```sql
UPDATE agents
SET state = 'RESERVED', reserved_at = NOW()
WHERE id = <agent_id> AND state = 'AVAILABLE';
```

- If `rowcount == 1` → we updated the row → we won the race → success.
- If `rowcount == 0` → someone else changed the state first → we lost → return False.

**Why this works:**
SQLite (and PostgreSQL) guarantee that an `UPDATE` statement is atomic.
Two concurrent `UPDATE` statements on the same row are serialised internally
by the database engine.  Only one sees the row in `AVAILABLE` state.
The other sees `RESERVED` and updates 0 rows.

This eliminates the need for external distributed locks (Redis, ZooKeeper).
The database itself is the lock server.

**What it makes harder:**
- If the database goes down, no reservations can be made.
- SQLite serialises all writes, so high concurrency increases lock wait time.

---

## 6. How is idempotency handled?

**What:** Every provider event has a unique `event_id`.
The `provider_events` table stores all processed event IDs with a UNIQUE index.

**How it works:**
```python
existing = db.query(ProviderEvent).filter(ProviderEvent.event_id == event_id).first()
if existing:
    return  # Duplicate — silently ignore
# Otherwise: process the event and insert a record.
```

A race condition where two workers receive the same event simultaneously
is handled by the database's UNIQUE constraint — the second insert raises
`IntegrityError`, which is caught and treated as a duplicate.

**Why:**
Provider B can send the same event twice.  Without idempotency, a call could
transition RINGING → RINGING and corrupt state.

---

## 7. How are out-of-order events handled?

**What:** Before applying any event, the `EventProcessor` checks
`CALL_VALID_TRANSITIONS`.

**How it works:**
```python
allowed = CALL_VALID_TRANSITIONS[current_state]
if target_state not in allowed:
    # Discard — do not update the call state
    log("Out-of-order event discarded")
    return
```

The event is still recorded in `provider_events` with `processed=False` and
a `discard_reason` explaining what happened.

**Why:**
Provider B can send `COMPLETED` before `RINGING`.  If we applied it blindly,
the call would jump from `INITIATED` to `COMPLETED`, skipping important
intermediate states and leaving the agent permanently in DIALING state.

---

## 8. How is worker crash recovery handled?

**Strategy:** Reservation lease timeout.

**How it works:**
Every agent and borrower has `reserved_at` (timestamp) and
`reservation_lease_seconds` (default: 60).

A background task `expire_stale_reservations()` periodically runs:
```python
if now >= reserved_at + lease_duration:
    agent.state = AVAILABLE  # Release the stuck reservation
```

**Scenario this handles:**
```
Agent reserved → borrower reserved → call created → WORKER CRASHES
```
Without recovery, the agent and borrower would stay RESERVED forever.
After 60 seconds, the lease expires and both are freed.

**Why this approach:**
- Simple and self-contained.  No need for a distributed heartbeat system.
- The recovery is automatic.  No human intervention required.
- 60 seconds is generous — a normal call initiation takes < 5 seconds.

**Trade-off:**
A reservation stuck by a slow network (not a crash) might be incorrectly
expired.  The call initiation would then fail when the agent is no longer
DIALING.  The failure handler releases resources cleanly.

---

## 9. How does provider health affect pacing?

**In the Predictive Engine:**
```python
health_dampened = floor(calls_needed * provider_health_score)
```
A provider at 60% health causes the engine to recommend 40% fewer calls.

**In the Safety Controller:**
1. If `health_score < 0.20` → REJECT all calls immediately.
2. Otherwise → `approved = floor(candidate * health_score)`.

**The combination means:**
- A degraded provider first reduces recommendations, then reduces approvals.
- An outaged provider (score = 0.0) → both engine and controller agree on 0.

---

## 10. What would change at 100,000 agents?

| Layer | Current (SQLite) | At 100,000 agents |
|---|---|---|
| Database | SQLite single file | PostgreSQL with partitioning |
| Reservation query | `SELECT * WHERE state='AVAILABLE'` (all rows) | `SELECT ... LIMIT <approved_count>` |
| Writer concurrency | 1 writer at a time | Row-level locking in Postgres |
| Safety Controller | Stateless function | Unchanged — O(1), infinitely scalable |
| Pacing formula | O(1) | Unchanged |
| Dialing loop | Synchronous per-cycle | Async workers per campaign shard |
| Agent pool query | Returns N rows | Paginated / sharded by campaign |
| Connection pooling | SQLAlchemy default | PgBouncer in front of Postgres |

The core architecture (atomic UPDATE rowcount, Safety Controller, idempotent
events) requires **no changes**.  Only the database backend and connection
handling change.
