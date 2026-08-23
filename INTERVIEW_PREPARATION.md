# Interview Preparation — SmartDialer

All answers refer directly to the code in this project.
Read each answer and make sure you can explain it in your own words.

---

## Q1. Explain the entire architecture.

**Simple version:**
The system has four layers stacked on top of each other.  The dialer decides
how many calls to make.  The Safety Controller decides if that's safe.
The Allocator actually makes the calls.  The provider is the phone company.

**Technical answer (refer to `docs/architecture.md`):**
```
Campaign → Pacing Engine → Safety Controller → Call Allocator → Provider
```
- **Pacing Engine** (`progressive.py` or `predictive.py`): Recommends a call count.
- **Safety Controller** (`safety_controller.py`): Approves, reduces, or rejects that count.
- **Call Allocator** (`call_allocator.py`): The only module that calls `provider.initiate_call()`.
- **Event Processor** (`event_processor.py`): Handles webhook events from the provider with idempotency and out-of-order protection.

The pacing engine has no import of any provider class.  This is enforced architecturally.

---

## Q2. Why did you choose this technology stack?

- **Python**: Assignment requirement; SQLAlchemy makes the atomic UPDATE pattern clear.
- **FastAPI**: Fast, auto-generates API docs, well-typed with Pydantic.
- **SQLite**: Zero-config; supports the atomic rowcount reservation trick identically to Postgres.
- **No Kafka/Redis**: Assignment explicitly discourages unnecessary infrastructure.
  The database IS the lock server — no extra component needed.

---

## Q3. Explain Progressive Dialing.

**Simple version:** If I have 10 agents free, I make at most 10 calls.
One call per free agent.  Safe and simple.

**Technical answer (refer to `app/dialer/progressive.py`):**
1. Count AVAILABLE agents → `n_available`.
2. Pass `n_available` through the Safety Controller.
3. For each approved slot: atomically reserve an agent, atomically reserve a borrower, create a call record, ask the allocator to initiate.
4. If anything fails → release resources.

Core guarantee: `new calls ≤ available agents`.

---

## Q4. Explain Predictive Pacing.

**Simple version:** If only 20% of people answer, I need to dial 5 calls to get 1 answered.
So for 10 free agents I dial 50 calls. But the Safety Controller limits that.

**Technical answer (refer to `app/dialer/predictive.py`):**
```
target_new_connections = available_agents - connected_calls
expected_from_ringing   = ringing_calls * answer_rate
connections_still_needed = target_new_connections - expected_from_ringing
calls_needed             = ceil(connections_still_needed / answer_rate)
recommended              = floor(calls_needed * provider_health_score)
```
This is the **pipeline-fill model**: we calculate how many calls we need to
dial to keep all available agents busy, accounting for the answer rate and
already in-flight ringing calls.

---

## Q5. Why can't Predictive Pacing call the provider directly?

**Simple version:** If the pacing engine could call the provider, it could
bypass the safety limits. We'd lose control of how many calls get made.

**Technical answer:**
`app/dialer/predictive.py` has no import of `ProviderA`, `ProviderB`, or
`CallAllocator`.  It only reads system state and produces a `PacingRecommendation`.

The `recommend_and_evaluate()` method passes the recommendation through
`SafetyController.evaluate()`.  The allocator — which has the provider — is
called separately, only by the Progressive Dialer or the API endpoint,
**after** the Safety Controller approves.

This is enforced by the `test_safety_controller_has_no_provider_import` test,
which reads the actual source file and asserts it contains no provider imports.

---

## Q6. What does the Safety Controller do?

**Simple version:** The Safety Controller is the gatekeeper. Even if the
pacing engine says "dial 100 calls", the Safety Controller might say "only
10 are safe right now".

**Technical answer (refer to `app/safety/safety_controller.py`):**
It takes `requested_calls` and a `SystemSnapshot` and applies 6 checks in order:
1. HARD REJECT if provider health < 0.20
2. HARD REJECT if total active calls ≥ hard cap (500)
3. FALLBACK TO PROGRESSIVE if answer rate < 5%
4. Compute `max_safe = available_agents - ringing - connected - reserved`
5. Apply unanswered cap: `floor(available_agents × 0.5)`
6. Dampen by provider health: `floor(candidate × health_score)`

Returns `SafetyDecision(action, approved_calls, reason)`.

---

## Q7. Two workers try to reserve the same agent. What happens?

**Simple version:** Both try to update the same database row.
The database only lets one update win. The other sees it changed and gives up.

**Technical answer (refer to `app/services/agent_service.py`, `atomic_reserve()`):**
```python
result = db.execute(
    UPDATE agents
    SET state='RESERVED', reserved_at=now
    WHERE id=agent_id AND state='AVAILABLE'
)
return result.rowcount == 1
```
SQLite serialises concurrent writes.  Only one `UPDATE` sees the row in AVAILABLE
state.  That one updates 1 row → returns True.
The other sees 0 rows updated → returns False → skips gracefully.

Proven by `test_concurrent_agent_reservation()`: 10 threads, exactly 1 winner.

---

## Q8. How do you prevent duplicate borrower allocation?

Identical mechanism to agent reservation.
```python
UPDATE borrowers SET state='RESERVED' WHERE id=? AND state='PENDING'
```
Only the worker that gets `rowcount == 1` proceeds.
See `BorrowerService.atomic_reserve()` and `test_concurrent_borrower_reservation()`.

---

## Q9. What happens when the worker crashes?

**Simple version:** The reservation has a timer on it. If the timer expires,
the reservation is automatically released so another worker can try.

**Technical answer:**
Every agent and borrower has `reserved_at` (timestamp) and
`reservation_lease_seconds` (default 60).

`AgentService.expire_stale_reservations()` checks:
```python
if now >= reserved_at + lease_duration:
    agent.state = AVAILABLE
```
This runs as a periodic background task.
Tested in `test_worker_crash_lease_expiry_releases_agent()`:
We manually set `reserved_at` to 2 minutes ago, run the expiry, confirm the
agent is AVAILABLE again.

---

## Q10. What happens when the provider sends ANSWERED twice?

**Simple version:** The second one is ignored. Every event has a unique ID.
We check the ID before processing.

**Technical answer (refer to `app/services/event_processor.py`):**
1. Receive `event_id` (a UUID from the provider).
2. Query `provider_events` table: `WHERE event_id = ?`
3. If found → log as duplicate → return without processing.
4. If not found → process → insert record with this `event_id`.

The `provider_events.event_id` column has a UNIQUE index.
Even in a race (two threads receiving the same event simultaneously),
the second `INSERT` raises `IntegrityError`, caught and treated as duplicate.

Tested in `test_duplicate_event_is_ignored()`.

---

## Q11. What happens when provider events arrive out of order?

**Simple version:** We check if the event makes sense for the current call state.
If not, we throw it away safely.

**Technical answer:**
Before applying any transition, the `EventProcessor` checks:
```python
allowed = CALL_VALID_TRANSITIONS[current_state]
if target_state not in allowed:
    record_event(processed=False, reason="Out-of-order")
    return  # Do not change call state
```
Example: call is in INITIATED state, COMPLETED arrives.
`CALL_VALID_TRANSITIONS[INITIATED] = {RINGING, FAILED, CANCELLED}`.
COMPLETED is not in that set → discard.

Tested in `test_out_of_order_event_is_discarded()`.

---

## Q12. What happens during provider outage?

**Simple version:** We detect the high failure rate and stop dialing.
When health recovers, dialing resumes automatically.

**Technical answer:**
1. `ProviderB.set_outage(True)` → `get_health()` returns `health_score=0.0`.
2. Safety Controller Guard 1: `0.0 < 0.20` → REJECT all calls.
3. Predictive Engine: `floor(calls_needed * 0.0) = 0` → recommends 0.
4. Dialing stops completely.
5. When `set_outage(False)` → health_score recovers over time as calls succeed.
6. Safety Controller approves again.

Tested in `test_provider_outage_reduces_recommendation()` and in Scenario D simulation.

---

## Q13. What happens if answer rate falls from 70% to 10%?

**Simple version:** The Safety Controller's fallback kicks in.
We switch to progressive mode where we only dial as many calls as we have free agents.

**Technical answer:**
`MIN_ANSWER_RATE_FOR_PREDICTIVE = 0.05`.
At 10% answer rate, we're still above the threshold.
The Safety Controller's unanswered cap (`MAX_UNANSWERED_RATIO = 0.5`) becomes
the binding constraint:
```
unanswered_cap = floor(available_agents * 0.5)
```
If 10 agents are available, we allow at most 5 ringing calls.
This prevents flooding with calls no one answers.

In the Predictive Engine, the formula produces:
```
connections_needed = target / answer_rate = target / 0.10
= 10x more calls needed → dampened by health and safety
```
Safety Controller reduces this aggressively.

---

## Q14. Why did your algorithm decide to initiate 17 calls instead of 10?

**(Example interview question — answer based on your actual numbers)**

The predictive engine calculated:
- 20 available agents
- 3 already connected
- 5 currently ringing
- 40% answer rate
- Provider health: 0.95

```
target_new_connections = 20 - 3 = 17
expected_from_ringing  = floor(5 × 0.40) = 2
connections_still_needed = 17 - 2 = 15
calls_needed = ceil(15 / 0.40) = 38
health_dampened = floor(38 × 0.95) = 36
```

The engine recommended 36. The Safety Controller reduced to 17 because:
```
max_safe = 20 - 5 (ringing) - 3 (connected) = 12  → further reduced by unanswered cap
```
The final approved count reflects the most conservative of all constraints.

---

## Q15. What happens if agent availability suddenly drops?

**Simple version:** The dialer asks the database how many agents are available
before every cycle. If agents disappear, the next cycle automatically uses fewer.

**Technical answer:**
`ProgressiveDialer.run_cycle()` calls `agent_service.get_available_agents()`
at the start of every cycle.  This is a live DB query.
If 40 agents just went OFFLINE, the query returns 60, not 100.
The Safety Controller then works with the real number.

There is no caching of agent count.  Stale data is impossible.

Tested in `test_agent_availability_drop_reduces_calls()`.

---

## Q16. What is idempotency?

**Simple version:** Running the same operation twice gives the same result as
running it once. The second run is a no-op.

**Technical answer in our context:**
A provider event with `event_id = "EVT-ABC123"` processed twice must result in
exactly one state transition.  We guarantee this by storing all processed event
IDs in `provider_events` and checking before processing:
```python
if db.query(ProviderEvent).filter(event_id=event_id).exists():
    return  # Already processed
```
The UNIQUE constraint on `event_id` is the database-level guarantee.

---

## Q17. What is concurrency?

**Simple version:** Multiple workers doing things at the same time.
The problem is when they try to use the same resource — like two people reaching
for the last train ticket.

**Technical answer in our context:**
Two dialing workers run simultaneously.  Both see Agent 101 as AVAILABLE.
Both try to reserve it.  Without safety:
- Both UPDATE → both see 1 row updated → both think they won → two calls for one agent.

With our solution:
- Database serialises the two UPDATEs.
- Only one sees the row in AVAILABLE state → updates 1 row.
- The other sees 0 rows updated → loses gracefully.

---

## Q18. Why did you use a database transaction/atomic update?

**Simple version:** A single SQL statement either succeeds completely or fails
completely. You can't get half-updated data.

**Technical answer:**
The `UPDATE agents SET state='RESERVED' WHERE id=? AND state='AVAILABLE'`
is a single atomic statement.  The database evaluates the condition AND applies
the update in one indivisible operation.

No lock explicitly acquired.  No race window between reading and writing.
This is the standard pattern for optimistic concurrency control in relational databases.

---

## Q19. What is the biggest bottleneck at 100,000 agents?

**Answer (refer to `load_test/load_test.py`, bottleneck_analysis()):**

At 1,000 agents: SQLite handles it fine.
At 10,000 agents: SQLite's single-writer lock becomes the bottleneck.
At 100,000 agents: Two bottlenecks:

1. **Database write throughput**: The `SELECT available agents` query returns
   100,000 rows; needs `LIMIT` to only fetch what we need.
2. **Single-node database**: Postgres row-level locking solves SQLite's issue,
   but even Postgres has limits (~50k writes/sec on one node).
   Solution: Shard agents by `campaign_id % N` across N database nodes.

The Safety Controller, pacing formula, and idempotency logic scale to infinity
— they're all O(1) computations, not O(agents).

---

## Q20. What would you improve if you had another week?

1. **Switch to PostgreSQL** with row-level locking for true concurrent writes.
2. **Add a real scheduling loop** so the dialer runs automatically every N seconds
   instead of being triggered by API calls.
3. **Add a proper answer-rate tracking table** (time-windowed, not just last N calls)
   for more accurate predictive pacing.
4. **Add campaign-level configuration**: different answer rates, provider choices,
   and safety limits per campaign.
5. **Add real webhook signature verification** for the provider event endpoint.
6. **Add WRAP_UP → AVAILABLE auto-transition** after a configurable timer.
7. **Write integration tests** with a running FastAPI server (using httpx TestClient).
