"""
SmartDialer — FastAPI application entry point.

The API exposes endpoints to:
  - Manage agents (create, list, state transitions)
  - Trigger dialing cycles (progressive and predictive)
  - Receive provider webhook events
  - Query campaign stats

The architecture enforces this call path:
  Pacing Engine → Safety Controller → Call Allocator → Provider
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the application begins serving requests."""
    # Create all database tables on startup (idempotent).
    init_db()
    yield
    # Shutdown: nothing to clean up for SQLite.


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SmartDialer",
    description="CredResolve SmartDialer — Progressive and Predictive Dialing Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Simple liveness probe."""
    return {"status": "ok", "service": "SmartDialer"}


# ---------------------------------------------------------------------------
# Import and register routers (added as each module is built)
# ---------------------------------------------------------------------------
from app.api import agents, borrowers, calls, dialer, events  # noqa: E402

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(borrowers.router, prefix="/borrowers", tags=["Borrowers"])
app.include_router(calls.router, prefix="/calls", tags=["Calls"])
app.include_router(dialer.router, prefix="/dialer", tags=["Dialer"])
app.include_router(events.router, prefix="/events", tags=["Events"])
