# Agent State Machine

An agent represents a human debt-collection specialist who handles calls.
Each agent has exactly one lifecycle state at any time.

## States

| State | Meaning |
|---|---|
| `OFFLINE` | Agent is not logged in |
| `AVAILABLE` | Logged in and ready to take a call |
| `RESERVED` | Atomically claimed by the dialer; call not yet initiated |
| `DIALING` | The telecom provider is setting up the outbound call |
| `CONNECTED` | Agent is on a live call with a borrower |
| `WRAP_UP` | Call ended; agent doing post-call administration |
| `PAUSED` | Agent is on a break |

## State Diagram

```
                        ┌──────────┐
                        │  OFFLINE │
                        └────┬─────┘
                             │ login / go available
                             ▼
                        ┌──────────┐ ◄─────────────────────────────┐
                        │AVAILABLE │                               │
                        └─┬────┬───┘                               │
               reserve ───┘    └─── pause                         │
                   │                  │                             │
                   ▼                  ▼                             │
           ┌──────────┐         ┌──────────┐                      │
           │ RESERVED │         │  PAUSED  │                      │
           └─────┬────┘         └──────────┘                      │
                 │ call initiated                                   │
                 │ (or released on failure)                         │
                 ▼                    ▼                             │
          ┌──────────┐         ┌──────────┐                       │
          │ DIALING  │────────►│AVAILABLE │ (call failed)         │
          └─────┬────┘         └──────────┘                       │
                │ answered                                          │
                ▼                                                   │
         ┌──────────┐                                              │
         │CONNECTED │                                              │
         └─────┬────┘                                              │
               │ call ends                                          │
               ▼                                                    │
        ┌──────────┐                                               │
        │ WRAP_UP  │ ──────────────────────────────────────────────┘
        └──────────┘    wrap-up complete → AVAILABLE
```

## Valid Transitions

```python
AGENT_VALID_TRANSITIONS = {
    OFFLINE:    {AVAILABLE},
    AVAILABLE:  {RESERVED, PAUSED, OFFLINE},
    RESERVED:   {DIALING, AVAILABLE},    # AVAILABLE = reservation released
    DIALING:    {CONNECTED, AVAILABLE},  # AVAILABLE = call failed
    CONNECTED:  {WRAP_UP},
    WRAP_UP:    {AVAILABLE, OFFLINE},
    PAUSED:     {AVAILABLE, OFFLINE},
}
```

## Invalid Transition Examples

| Attempt | Why it fails |
|---|---|
| `OFFLINE → CONNECTED` | Must go through AVAILABLE → RESERVED → DIALING first |
| `AVAILABLE → CONNECTED` | Cannot skip RESERVED and DIALING |
| `CONNECTED → AVAILABLE` | Must pass through WRAP_UP first |
| `WRAP_UP → DIALING` | Cannot take a new call without going AVAILABLE first |

All invalid transitions raise `AgentStateError` in `AgentService.transition_state()`.

## Concurrency Safety

The `AVAILABLE → RESERVED` transition uses an atomic SQL UPDATE:

```sql
UPDATE agents
SET state = 'RESERVED', reserved_at = NOW()
WHERE id = <agent_id> AND state = 'AVAILABLE';
```

Only the worker that sees `rowcount == 1` succeeds.
All others see `rowcount == 0` and fail gracefully.

## Crash Recovery

`reserved_at` is set when an agent enters RESERVED state.
The `expire_stale_reservations()` method in `AgentService` releases any
reservation older than `reservation_lease_seconds` (default: 60 seconds).
