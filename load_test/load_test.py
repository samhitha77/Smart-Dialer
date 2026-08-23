"""
Load test for the SmartDialer reservation and allocation system.

Tests the system with increasing agent counts:
  10 -> 100 -> 1,000 agents

Measures:
  - Reservation throughput (reservations per second)
  - Call allocation throughput (allocations per second)
  - Average processing time per reservation
  - Failure rate

Also answers the question:
  "What would be the bottleneck at 10,000 or 100,000 agents?"

Usage:
  python load_test/load_test.py
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import agent as agent_mod, borrower as borrower_mod  # noqa: F401
from app.models import call as call_mod, provider_event as pe_mod  # noqa: F401
from app.models.agent import AgentState
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.providers.provider_a import ProviderA
from app.dialer.progressive import ProgressiveDialer


import tempfile

def make_db():
    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_file.name
    temp_file.close()
    
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 60.0, "check_same_thread": False},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode = WAL;")
        conn.exec_driver_sql("PRAGMA synchronous = NORMAL;")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session, engine, db_path


def load_test_reservations(num_agents: int) -> dict:
    """
    Measure how quickly we can atomically reserve N agents using concurrent worker pool.
    Each task tries to reserve an agent to measure throughput and processing latency.
    """
    from app.models.agent import Agent
    Session, engine, db_path = make_db()

    try:
        # Fast bulk setup: create N agents all in AVAILABLE state.
        setup_db = Session()
        for i in range(num_agents):
            setup_db.add(Agent(name=f"LoadAgent-{i}", state=AgentState.AVAILABLE.value))
        setup_db.commit()
        agent_ids = [a.id for a in setup_db.query(Agent.id).all()]
        setup_db.close()

        def reserve_one(agent_id: int) -> bool:
            db = Session()
            try:
                worker_svc = AgentService(db)
                return worker_svc.atomic_reserve(agent_id)
            finally:
                db.close()

        max_workers = min(16, max(1, num_agents // 2))
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(reserve_one, agent_ids))
        elapsed = time.perf_counter() - start

        successes = sum(1 for r in results if r)
        failures = len(results) - successes

        return {
            "num_agents": num_agents,
            "elapsed_seconds": round(elapsed, 4),
            "successes": successes,
            "failures": failures,
            "throughput_per_second": round(num_agents / elapsed, 1) if elapsed > 0 else 0,
            "avg_ms_per_reservation": round(elapsed * 1000 / num_agents, 3) if num_agents > 0 else 0,
            "failure_rate": round(failures / num_agents, 4) if num_agents > 0 else 0,
        }
    finally:
        engine.dispose()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


def load_test_dialing_cycles(num_agents: int) -> dict:
    """
    Run dialing cycle with N agents and measure throughput.
    This tests the full progressive dialer path: reserve + allocate + initiate.
    """
    from app.models.agent import Agent
    from app.models.borrower import Borrower, BorrowerState
    Session, engine, db_path = make_db()

    try:
        # Fast bulk setup
        setup_db = Session()
        for i in range(num_agents):
            setup_db.add(Agent(name=f"CycleAgent-{i}", state=AgentState.AVAILABLE.value))
            setup_db.add(Borrower(name=f"CycleBorrower-{i}", phone_number=f"555{i:07d}", state=BorrowerState.PENDING.value))
        setup_db.commit()
        setup_db.close()

        db = Session()
        provider = ProviderA(failure_rate=0.0)
        dialer = ProgressiveDialer(db, provider)

        start = time.perf_counter()
        result = dialer.run_cycle()
        elapsed = time.perf_counter() - start

        db.close()

        return {
            "num_agents": num_agents,
            "elapsed_seconds": round(elapsed, 4),
            "attempted": result.attempted,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "throughput_per_second": round(result.attempted / elapsed, 1) if elapsed > 0 else 0,
            "avg_ms_per_call": round(elapsed * 1000 / max(result.attempted, 1), 3),
        }
    finally:
        engine.dispose()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


def print_table(rows: list[dict], title: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")
    if not rows:
        return
    headers = list(rows[0].keys())
    col_width = max(len(h) for h in headers) + 2
    header_line = "  " + "".join(h.ljust(col_width) for h in headers)
    print(header_line)
    print("  " + "-" * (col_width * len(headers)))
    for row in rows:
        line = "  " + "".join(str(row[h]).ljust(col_width) for h in headers)
        print(line)


def bottleneck_analysis() -> None:
    print("""
===================================================================
  BOTTLENECK ANALYSIS: What breaks at 10,000 or 100,000 agents?
===================================================================

At our current scale (1,000 agents), SQLite handles everything fine.
SQLite serialises writes, so each reservation is a fast row update.

At 10,000 agents:
-----------------
  Bottleneck: SQLite write serialisation.
  Problem: Concurrent UPDATE operations queue up. SQLite allows only
           one writer at a time. With 10,000 threads writing simultaneously,
           lock contention time dominates over actual work time.
  Solution: Switch to PostgreSQL with row-level locking. The same
            "UPDATE WHERE state='AVAILABLE'" trick works identically,
            but Postgres can run many concurrent writers.

At 100,000 agents:
------------------
  Bottleneck 1: Single database node.
  Problem: Even Postgres on one node has limits (~10,000-50,000 writes/sec).
           100,000 concurrent reservations would overwhelm a single primary.
  Solution: Partition agents into shards (e.g. by campaign_id or
            agent_id % N). Each shard has its own DB node.
            Reservations only contend within the same shard.

  Bottleneck 2: The progressive dialer's "fetch all available agents"
                query returns 100,000 rows per cycle.
  Solution: Add LIMIT to the query (only fetch as many as you need to
            fill approved call slots). This is O(approved_calls)
            instead of O(all_agents).

  Bottleneck 3: SQLite connection pooling.
  Solution: Use a proper connection pooler (PgBouncer for Postgres).

  What DOES NOT change:
  The core architecture (atomic UPDATE rowcount) is correct at any scale.
  The Safety Controller is stateless -- it scales infinitely.
  The pacing formula is O(1) -- it scales infinitely.

Summary:
  Scale       Bottleneck                   Solution
  ----------  ---------------------------  -----------------------------
  1,000       None (SQLite fine)           Current design works
  10,000      SQLite write lock            Switch to PostgreSQL
  100,000     Single DB node               Shard by campaign/agent range
  1,000,000   Network + DB layer           Distributed reservation queue
              (reservation service)        (e.g. optimistic locking + retry)
""")


if __name__ == "__main__":
    agent_counts = [10, 100, 1_000]

    # Test 1: Reservation throughput
    reservation_results = []
    for n in agent_counts:
        print(f"Running reservation load test: {n} agents...")
        r = load_test_reservations(n)
        reservation_results.append(r)

    print_table(reservation_results, "Reservation Throughput")

    # Test 2: Dialing cycle throughput
    cycle_results = []
    for n in agent_counts:
        print(f"Running dialing cycle load test: {n} agents...")
        r = load_test_dialing_cycles(n)
        cycle_results.append(r)

    print_table(cycle_results, "Dialing Cycle Throughput")

    bottleneck_analysis()
