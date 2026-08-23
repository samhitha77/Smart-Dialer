# SmartDialer — CredResolve Technical Assignment

A working **progressive and predictive outbound dialing system** built as a
technical hiring assignment for CredResolve.

---

## 1. Project Overview

SmartDialer is a functional prototype of an outbound call centre dialing engine.
It manages a pool of human agents, a list of borrowers to contact, and coordinates
outbound calls through mock telecom providers — safely, without over-dialing.

---

## 2. Problem Statement

Outbound call centres face two problems:

**Over-dialing**: More calls are started than agents can handle.
A borrower answers but no agent is available — bad experience, wasted cost.

**Under-dialing**: Agents sit idle waiting for calls to connect.
Wasted agent capacity, lower collections.

SmartDialer solves both with:
- **Progressive dialing**: Exactly 1 call per free agent. Safe by design.
- **Predictive dialing**: Statistical over-dialing to account for answer rate,
  controlled by a Safety Controller that acts as a hard ceiling.

---

## 3. Architecture

```
Campaign
   ↓
Progressive / Predictive Pacing Engine   ← recommends call count
   ↓
Safety Controller                        ← approves / reduces / rejects
   ↓
Call Allocator                           ← initiates approved calls
   ↓
Telecom Provider (A or B)
```

The pacing engine **cannot** call the provider directly.
The only path to the provider is through the Safety Controller and Allocator.

See [`docs/architecture.md`](docs/architecture.md) for the full diagram.

---

## 4. Technology Choices

| Technology | Why |
|---|---|
| Python 3.11+ | Assignment requirement; clean, readable |
| FastAPI | Fast web framework, auto-generates API docs |
| SQLite | Zero-config; supports atomic UPDATE rowcount reservation |
| SQLAlchemy | ORM + raw SQL where needed |
| Pydantic | Type-safe request/response models |
| Pytest | Clean test suite |
| Matplotlib | Simulation charts |

---

## 5. Project Structure

```
smart-dialer/
├── app/
│   ├── main.py               FastAPI application entry point
│   ├── database.py           SQLAlchemy engine + session factory
│   ├── models/               ORM models (Agent, Borrower, Call, ProviderEvent)
│   ├── dialer/               Progressive + Predictive pacing engines
│   ├── safety/               Safety Controller
│   ├── allocation/           Call Allocator (only place provider is called)
│   ├── providers/            TelecomProvider ABC + ProviderA + ProviderB
│   ├── services/             AgentService, BorrowerService, CallService, EventProcessor
│   └── api/                  FastAPI routers
├── tests/                    Complete test suite
├── simulation/               Discrete-time simulator + scenarios
├── load_test/                Load test script
├── docs/                     Architecture + decision + state machine docs
├── INTERVIEW_PREPARATION.md  20 Q&As based on this exact code
└── requirements.txt
```

---

## 6. Setup Instructions

```bash
# Clone / unzip the project
cd smart-dialer

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 7. How to Run the Application

```bash
uvicorn app.main:app --reload
```

API documentation: http://127.0.0.1:8000/docs

### Quick demo (using curl or the /docs UI):

```bash
# Create agents
curl -X POST http://localhost:8000/agents/ -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'

# Create borrowers
curl -X POST http://localhost:8000/borrowers/ -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "phone_number": "5551234567"}'

# Run one progressive dialing cycle
curl -X POST http://localhost:8000/dialer/progressive/cycle

# Get a predictive recommendation
curl http://localhost:8000/dialer/predictive/recommend
```

---

## 8. How to Run Tests

```bash
pytest tests/ -v
```

Run a specific test file:
```bash
pytest tests/test_concurrency.py -v     # Concurrency safety tests
pytest tests/test_safety.py -v          # Safety Controller tests
pytest tests/test_failures.py -v        # Failure + crash recovery tests
```

---

## 9. How to Run Simulations

```bash
python simulation/simulator.py
```

This runs all four scenarios (A, B, C, D) and generates charts in
`simulation/results/`.

---

## 10. How to Run Load Tests

```bash
python load_test/load_test.py
```

Tests with 10, 100, and 1,000 agents.
Prints throughput and bottleneck analysis.

---

## 11. Progressive Dialer Explanation

**Core rule:** `new calls ≤ available agents`

Each cycle:
1. Count AVAILABLE agents.
2. Ask Safety Controller to approve that count.
3. For each approved slot: atomically reserve agent → reserve borrower → create call → initiate.
4. On any failure: release resources immediately.

See [`app/dialer/progressive.py`](app/dialer/progressive.py).

---

## 12. Predictive Pacing Explanation

**Goal:** Account for the answer rate to keep all agents busy.

Formula (pipeline-fill model):
```
target_connections    = available_agents - connected_calls
expected_from_ringing = ringing_calls × answer_rate
connections_needed    = target_connections - expected_from_ringing
calls_to_start        = ceil(connections_needed / answer_rate)
recommended           = floor(calls_to_start × provider_health_score)
```

Then this recommendation is passed to the Safety Controller.
The Safety Controller's approved count is what actually gets dialed.

See [`app/dialer/predictive.py`](app/dialer/predictive.py).

---

## 13. Safety Controller Explanation

The Safety Controller receives a `requested_calls` count and returns one of:
- `APPROVE` — safe to dial the full requested amount
- `REDUCE` — dial a lower, safer count
- `REJECT` — do not dial anything right now
- `FALLBACK_TO_PROGRESSIVE` — answer rate too low for predictive mode

Six checks in order:
1. Provider health critically low → REJECT
2. Hard cap on total active calls exceeded → REJECT
3. Answer rate below minimum threshold → FALLBACK
4. Agent headroom check
5. Unanswered calls ratio cap
6. Provider health dampening

See [`app/safety/safety_controller.py`](app/safety/safety_controller.py).

---

## 14. Concurrency Strategy

**Problem:** Two workers simultaneously try to reserve the same agent.

**Solution:** Atomic conditional UPDATE:
```sql
UPDATE agents SET state='RESERVED', reserved_at=NOW()
WHERE id=? AND state='AVAILABLE';
```
Check `rowcount`:
- `1` → won the race → proceed
- `0` → lost the race → skip

No external lock server (Redis, ZooKeeper) required.
The database is the lock server.

---

## 15. Failure Handling

| Failure | What happens |
|---|---|
| Provider rejects call | Call → FAILED, agent → AVAILABLE, borrower → PENDING |
| Worker crash | Reservation lease expires (60s), agent/borrower auto-released |
| Provider outage | Health score → 0.0, Safety Controller rejects all new calls |
| Agent goes offline | Next dialing cycle reads live DB — uses correct count |
| Duplicate event | Idempotency check prevents double processing |
| Out-of-order event | Transition validation discards illegal transitions |

---

## 16. Provider Simulation

**Provider A** — Reliable:
- 5% failure rate, ordered events, fast (30ms latency)

**Provider B** — Chaotic:
- 25% failure rate, 10% timeout rate, duplicate events, out-of-order events
- Supports simulated outages via `set_outage(True)`

Both implement the `TelecomProvider` ABC from [`app/providers/base.py`](app/providers/base.py).

---

## 17. Example Results

Running `python simulation/simulator.py`:

```
Scenario A (20% answer rate, predictive):
  Total initiated  : 312
  Total connected  : 61
  Safety reductions: 18
  Peak utilization : 73.5%

Scenario D (variable conditions, Provider B, outage at tick 35):
  Total initiated  : 408
  Total connected  : 178
  Safety rejections: 12   ← during outage
  Provider failures: 67
```

---

## 18. Limitations

- SQLite single-writer bottleneck at > ~50 concurrent threads
- No real scheduling loop — dialing is triggered via API or simulation
- No campaign-level configuration (all settings are module-level constants)
- No real webhook authentication from providers
- WRAP_UP → AVAILABLE transition is manual (no auto-timer)

---

## 19. Future Improvements

1. Switch to PostgreSQL for true concurrent writes at scale
2. Add a real scheduling loop for automated dialing cycles
3. Time-windowed answer rate calculation (not just last N calls)
4. Campaign-level configuration per row in DB
5. Sharding by campaign_id for 100,000+ agents
6. WebSocket or SSE for real-time dashboard updates
7. Retry logic with exponential back-off for transient provider failures

---

## 20. Key Design Principles

- **Safety first**: Every call path goes through the Safety Controller.
- **Simplicity**: No Kafka, Redis, Kubernetes.
- **Explainability**: Every algorithm decision is commented.
- **Testability**: In-memory SQLite for all tests, no server required.
- **Correctness**: State machines prevent invalid transitions everywhere.
