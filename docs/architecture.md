# SmartDialer Architecture

## System Overview

SmartDialer is a functional prototype of a progressive and predictive
outbound dialing system for debt collection campaigns.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Campaign / API Layer                  │
│  POST /dialer/progressive/cycle                         │
│  GET  /dialer/predictive/recommend                      │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Pacing Engine         │
              │  Progressive Dialer      │  ← Recommends call count
              │  Predictive Engine       │  ← Recommends call count
              └────────────┬────────────┘
                           │ recommended_calls=N
                           │ (cannot proceed further alone)
              ┌────────────▼────────────┐
              │   Safety Controller      │  ← Final authority
              │                          │
              │  1. Provider health OK?  │
              │  2. Hard cap reached?    │
              │  3. Answer rate OK?      │
              │  4. Agent headroom?      │
              │  5. Unanswered cap?      │
              │  6. Health dampening     │
              │                          │
              │  → APPROVE / REDUCE /   │
              │    REJECT / FALLBACK     │
              └────────────┬────────────┘
                           │ approved_calls=M (≤ N)
              ┌────────────▼────────────┐
              │    Call Allocator        │  ← Executes M calls
              │                          │
              │  1. Agent → DIALING      │
              │  2. provider.initiate()  │
              │  3. Call → INITIATED     │
              │  4. On failure: release  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   Telecom Provider       │
              │  Provider A (reliable)   │
              │  Provider B (chaotic)    │
              └─────────────────────────┘
                           │
                           │ webhook events
                           ▼
              ┌────────────────────────┐
              │   Event Processor       │
              │                         │
              │  Idempotency check      │
              │  Out-of-order check     │
              │  State transition       │
              │  Agent/borrower update  │
              └────────────────────────┘
```

## Key Modules

| Module | File | Responsibility |
|---|---|---|
| Progressive Dialer | `app/dialer/progressive.py` | 1:1 agent-to-call cycle |
| Predictive Engine | `app/dialer/predictive.py` | Pipeline-fill recommendation |
| Safety Controller | `app/safety/safety_controller.py` | Final approval authority |
| Call Allocator | `app/allocation/call_allocator.py` | Provider interaction |
| Event Processor | `app/services/event_processor.py` | Idempotent event handling |
| Agent Service | `app/services/agent_service.py` | Agent lifecycle + reservation |
| Borrower Service | `app/services/borrower_service.py` | Borrower lifecycle + reservation |

## Database Schema

```
agents
  id, name, state, reserved_at, reservation_lease_seconds, created_at, updated_at

borrowers
  id, name, phone_number, state, reserved_at, reservation_lease_seconds, created_at, updated_at

calls
  id, agent_id, borrower_id, state, provider_call_id, dialing_mode
  initiated_at, answered_at, completed_at, created_at, updated_at

provider_events  (idempotency log)
  id, event_id (UNIQUE), call_id, event_type, processed, discard_reason, received_at
```

## Concurrency Safety

The critical operation — reserving an agent or borrower — uses a single
atomic SQL statement:

```sql
UPDATE agents
SET state='RESERVED', reserved_at=<now>
WHERE id=<id> AND state='AVAILABLE';
```

`rowcount == 1` → success.  `rowcount == 0` → lost the race → retry or skip.

This is the same pattern used by database-backed job queues (e.g. GoodJob in
Rails, Que in Postgres).  No external lock server required.
