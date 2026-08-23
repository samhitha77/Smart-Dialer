# Call State Machine

A call represents a single dialing attempt connecting one agent to one borrower.

## States

| State | Meaning |
|---|---|
| `QUEUED` | Waiting to be processed (not used in current flow; reserved for future queue) |
| `RESERVED` | Agent + borrower reserved; call record created; not yet sent to provider |
| `INITIATED` | Sent to the telecom provider; awaiting acknowledgement |
| `RINGING` | Provider confirmed the phone is ringing at borrower's end |
| `ANSWERED` | Borrower picked up; connecting to agent |
| `CONNECTED` | Live two-way conversation in progress |
| `COMPLETED` | Call ended normally ✓ — **terminal** |
| `FAILED` | Call ended abnormally ✗ — **terminal** |
| `CANCELLED` | Cancelled before connecting — **terminal** |

## State Diagram

```
QUEUED ──► RESERVED ──► INITIATED ──► RINGING ──► ANSWERED ──► CONNECTED ──► COMPLETED
                │              │             │           │
                ▼              ▼             ▼           ▼
           CANCELLED        FAILED       FAILED       FAILED
```

## Valid Transitions

```python
CALL_VALID_TRANSITIONS = {
    QUEUED:    {RESERVED, CANCELLED},
    RESERVED:  {INITIATED, CANCELLED, FAILED},
    INITIATED: {RINGING,   FAILED,    CANCELLED},
    RINGING:   {ANSWERED,  FAILED,    CANCELLED},
    ANSWERED:  {CONNECTED, FAILED},
    CONNECTED: {COMPLETED, FAILED},
    COMPLETED: {},   # Terminal — no further transitions
    FAILED:    {},   # Terminal
    CANCELLED: {},   # Terminal
}
```

## Terminal States

`COMPLETED`, `FAILED`, and `CANCELLED` are terminal.
No transitions are allowed from these states.
Attempting a transition raises `CallStateError`.

## Provider Event Mapping

Provider webhook events map to call states as follows:

| Provider Event | Mapped Call State |
|---|---|
| `RINGING` | `RINGING` |
| `ANSWERED` | `ANSWERED` |
| `CONNECTED` | `CONNECTED` |
| `COMPLETED` | `COMPLETED` |
| `FAILED` | `FAILED` |
| `TIMEOUT` | `FAILED` |
| `CANCELLED` | `CANCELLED` |

## Idempotency

Every provider event carries a unique `event_id`.
Before processing, the `EventProcessor` checks if `event_id` already exists
in the `provider_events` table.
- If **found** → silently discard (duplicate event).
- If **not found** → process and insert record.

## Out-of-Order Protection

Before applying any state transition, the `EventProcessor` checks
`CALL_VALID_TRANSITIONS`.

Example — Provider B sends `COMPLETED` before `RINGING`:
```
Current state: INITIATED
Event received: COMPLETED
CALL_VALID_TRANSITIONS[INITIATED] = {RINGING, FAILED, CANCELLED}
COMPLETED ∉ allowed → discard with reason "Out-of-order"
```

The call remains in `INITIATED` state.
The event is recorded in `provider_events` with `processed=False`.

## Resource Release on Failure

When a call reaches `FAILED` or `CANCELLED`:
- The associated agent is released back to `AVAILABLE`.
- The associated borrower is released back to `PENDING` (eligible for retry).

This is handled automatically by `EventProcessor._handle_side_effects()`.
