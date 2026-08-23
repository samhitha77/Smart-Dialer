"""
SmartDialer Simulator — discrete-time simulation engine.

How the simulation works
─────────────────────────
Time is divided into "ticks" (each tick ~ 2 seconds in real life).
Each tick the simulator:
  1. Advances in-progress calls (decrement remaining duration).
  2. Completes calls that have run their course.
  3. Runs a dialing cycle (progressive or predictive).
  4. Collects metrics.

No real time passes — the simulator runs as fast as the CPU allows.
This lets us test many hours of campaign behaviour in seconds.

Why discrete-time simulation?
  - No threading complexity.
  - Fully deterministic with a fixed random seed.
  - Easy to inspect state at any tick.
  - Generates metrics for every tick — easy to plot.

Usage:
  python simulation/simulator.py
"""

import os
import sys
import random
import math
from dataclasses import dataclass, field
from typing import Optional

# Allow imports from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import agent as agent_mod, borrower as borrower_mod  # noqa: F401
from app.models import call as call_mod, provider_event as pe_mod  # noqa: F401
from app.models.agent import AgentState, Agent
from app.models.borrower import BorrowerState, Borrower
from app.models.call import Call, CallState, CALL_TERMINAL_STATES
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.providers.base import TelecomProvider
from app.dialer.progressive import ProgressiveDialer
from app.dialer.predictive import PredictivePacingEngine, PacingRecommendation
from app.allocation.call_allocator import CallAllocator
from app.safety.safety_controller import SafetyController, SystemSnapshot, SafetyAction
from simulation.scenarios import Scenario, ALL_SCENARIOS


# ---------------------------------------------------------------------------
# Per-tick active call tracker (in-memory, not DB)
# ---------------------------------------------------------------------------

@dataclass
class ActiveCall:
    """Tracks a simulated in-progress call."""
    call_id: int
    agent_id: int
    borrower_id: int
    provider_call_id: str
    ticks_remaining: int       # How many ticks until this call ends
    answered: bool = False


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------

@dataclass
class TickMetrics:
    tick: int = 0
    available_agents: int = 0
    calls_initiated: int = 0
    calls_connected: int = 0
    calls_failed: int = 0
    calls_completed: int = 0
    ringing_calls: int = 0
    pacing_recommendation: int = 0
    safety_approved: int = 0
    safety_action: str = ""
    provider_health: float = 1.0
    answer_rate: float = 0.0


@dataclass
class SimulationResults:
    scenario_name: str = ""
    tick_metrics: list[TickMetrics] = field(default_factory=list)
    total_initiated: int = 0
    total_connected: int = 0
    total_failed: int = 0
    total_completed: int = 0
    safety_approvals: int = 0
    safety_reductions: int = 0
    safety_rejections: int = 0
    provider_failures: int = 0
    peak_agent_utilization: float = 0.0


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------

class Simulator:
    """
    Runs a single scenario through discrete-time simulation.
    Maintains its own in-memory SQLite database per run.
    """

    def __init__(self, scenario: Scenario, seed: int = 42):
        self.scenario = scenario
        random.seed(seed)

        # Fresh in-memory DB for this simulation run.
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

        # Services
        self.agent_svc = AgentService(self.db)
        self.borrower_svc = BorrowerService(self.db)
        self.call_svc = CallService(self.db)

        # Provider
        if scenario.provider == "b":
            self.provider: TelecomProvider = ProviderB(
                failure_rate=0.25, timeout_rate=0.10
            )
        else:
            self.provider = ProviderA(failure_rate=0.05)

        # In-memory active call tracker
        self.active_calls: list[ActiveCall] = []

        # Track agent IDs for drop simulation
        self.agent_ids: list[int] = []

        # Adjust answer rate for Scenario D mid-run
        self._current_answer_rate = scenario.answer_rate

        # Results
        self.results = SimulationResults(scenario_name=scenario.name)

    def run(self) -> SimulationResults:
        """Run the full simulation and return metrics."""
        print(f"\n{'='*60}")
        print(f"Scenario: {self.scenario.name}")
        print(f"  {self.scenario.description}")
        print(f"{'='*60}")

        self._seed_database()

        for tick in range(1, self.scenario.num_ticks + 1):
            self._handle_tick_events(tick)
            metrics = self._run_tick(tick)
            self.results.tick_metrics.append(metrics)

            if tick % 10 == 0:
                print(
                    f"  Tick {tick:3d}: "
                    f"agents_avail={metrics.available_agents:3d} "
                    f"initiated={metrics.calls_initiated:3d} "
                    f"connected={metrics.calls_connected:3d} "
                    f"safety={metrics.safety_action} "
                    f"health={metrics.provider_health:.2f}"
                )

        self._compute_totals()
        self._print_summary()
        return self.results

    def _seed_database(self) -> None:
        """Create agents and borrowers for this scenario."""
        for i in range(self.scenario.num_agents):
            a = self.agent_svc.create_agent(f"Agent-{i}")
            self.agent_svc.transition_state(a.id, AgentState.AVAILABLE)
            self.agent_ids.append(a.id)

        for i in range(self.scenario.num_borrowers):
            self.borrower_svc.create_borrower(f"Borrower-{i}", f"555{i:07d}")

    def _handle_tick_events(self, tick: int) -> None:
        """Handle mid-simulation events like outages and agent drops."""
        scenario = self.scenario

        # Provider outage
        if (
            scenario.simulate_outage_at_tick is not None
            and tick == scenario.simulate_outage_at_tick
            and isinstance(self.provider, ProviderB)
        ):
            print(f"  *** TICK {tick}: Provider B OUTAGE starts ***")
            self.provider.set_outage(True)

        # Recover from outage after 10 ticks
        if (
            scenario.simulate_outage_at_tick is not None
            and tick == scenario.simulate_outage_at_tick + 10
            and isinstance(self.provider, ProviderB)
        ):
            print(f"  *** TICK {tick}: Provider B RECOVERS ***")
            self.provider.set_outage(False)

        # Agent availability drop
        if (
            scenario.simulate_agent_drop
            and tick == scenario.agent_drop_at_tick
            and self.agent_ids
        ):
            drop_count = min(scenario.agents_to_drop, len(self.agent_ids))
            print(f"  *** TICK {tick}: {drop_count} agents go OFFLINE ***")
            for agent_id in self.agent_ids[:drop_count]:
                agent = self.db.get(Agent, agent_id)
                if agent and agent.state == AgentState.AVAILABLE.value:
                    agent.state = AgentState.OFFLINE.value
            self.db.commit()

        # Scenario D: answer rate drops at tick 20
        if scenario.name.startswith("D") and tick == 20:
            print(f"  *** TICK {tick}: Answer rate drops from {self._current_answer_rate:.0%} to 15% ***")
            self._current_answer_rate = 0.15

    def _run_tick(self, tick: int) -> TickMetrics:
        """Execute one simulation tick."""
        metrics = TickMetrics(tick=tick)

        # Step 1: Advance active calls and complete those that are done.
        self._advance_calls(metrics)

        # Step 2: Run dialing cycle.
        self._run_dialing_cycle(metrics)

        # Step 3: Collect snapshot metrics.
        metrics.available_agents = self.agent_svc.count_available_agents()
        metrics.ringing_calls = len(
            [c for c in self.active_calls if not c.answered]
        )
        metrics.provider_health = self.provider.get_health().health_score
        metrics.answer_rate = self._current_answer_rate

        return metrics

    def _advance_calls(self, metrics: TickMetrics) -> None:
        """
        For each active call, simulate whether it gets answered and
        decrement its remaining duration.
        """
        still_active = []
        for ac in self.active_calls:
            # If not yet answered, simulate answer probability.
            if not ac.answered:
                if random.random() < self._current_answer_rate:
                    ac.answered = True
                    metrics.calls_connected += 1
                    self.results.total_connected += 1
                    # Update DB: move agent to CONNECTED.
                    agent = self.db.get(Agent, ac.agent_id)
                    if agent:
                        agent.state = AgentState.CONNECTED.value
                    # Borrower to IN_CALL.
                    borrower = self.db.get(Borrower, ac.borrower_id)
                    if borrower:
                        borrower.state = BorrowerState.IN_CALL.value
                    call = self.db.get(Call, ac.call_id)
                    if call:
                        call.state = CallState.CONNECTED.value
                    self.db.commit()
                else:
                    # Still ringing — if we've waited too long, treat as failed.
                    ac.ticks_remaining -= 1
                    if ac.ticks_remaining <= 0:
                        self._complete_call(ac, answered=False)
                        metrics.calls_failed += 1
                        self.results.total_failed += 1
                        self.results.provider_failures += 1
                        continue
                    still_active.append(ac)
                    continue

            # Answered call — count down duration.
            ac.ticks_remaining -= 1
            if ac.ticks_remaining <= 0:
                self._complete_call(ac, answered=True)
                metrics.calls_completed += 1
                self.results.total_completed += 1
            else:
                still_active.append(ac)

        self.active_calls = still_active

    def _complete_call(self, ac: ActiveCall, answered: bool) -> None:
        """Release an agent and borrower after a call ends."""
        agent = self.db.get(Agent, ac.agent_id)
        if agent:
            agent.state = AgentState.AVAILABLE.value
            agent.reserved_at = None

        borrower = self.db.get(Borrower, ac.borrower_id)
        if borrower:
            borrower.state = BorrowerState.COMPLETED.value if answered else BorrowerState.PENDING.value

        call = self.db.get(Call, ac.call_id)
        if call:
            call.state = CallState.COMPLETED.value if answered else CallState.FAILED.value

        self.db.commit()

    def _run_dialing_cycle(self, metrics: TickMetrics) -> None:
        """Run one dialing cycle and update metrics."""
        if self.scenario.dialing_mode == "predictive":
            self._run_predictive_cycle(metrics)
        else:
            self._run_progressive_cycle(metrics)

    def _run_progressive_cycle(self, metrics: TickMetrics) -> None:
        """Run the progressive dialer for one tick."""
        available_agents = self.db.query(Agent).filter(
            Agent.state == AgentState.AVAILABLE.value
        ).all()

        pending_borrowers = self.db.query(Borrower).filter(
            Borrower.state == BorrowerState.PENDING.value
        ).limit(len(available_agents)).all()

        provider_health = self.provider.get_health()

        # Safety Controller check
        from app.safety.safety_controller import SystemSnapshot
        snapshot = SystemSnapshot(
            available_agents=len(available_agents),
            ringing_calls=sum(1 for c in self.active_calls if not c.answered),
            connected_calls=sum(1 for c in self.active_calls if c.answered),
            reserved_calls=0,
            answer_rate=self._current_answer_rate,
            provider_health=provider_health,
            total_active_calls=len(self.active_calls),
        )
        ctrl = SafetyController()
        decision = ctrl.evaluate(
            requested_calls=len(available_agents), snapshot=snapshot
        )

        metrics.safety_action = decision.action.value
        metrics.safety_approved = decision.approved_calls
        metrics.pacing_recommendation = len(available_agents)
        self._update_safety_counters(decision.action)

        if decision.approved_calls == 0:
            return

        initiated = 0
        for agent, borrower in zip(available_agents[:decision.approved_calls], pending_borrowers):
            result = self._initiate_simulated_call(agent, borrower)
            if result:
                initiated += 1

        metrics.calls_initiated = initiated
        self.results.total_initiated += initiated

    def _run_predictive_cycle(self, metrics: TickMetrics) -> None:
        """Run the predictive pacing engine for one tick."""
        available_count = self.db.query(Agent).filter(
            Agent.state == AgentState.AVAILABLE.value
        ).count()
        ringing = sum(1 for c in self.active_calls if not c.answered)
        connected = sum(1 for c in self.active_calls if c.answered)

        answer_rate = self._current_answer_rate
        if answer_rate <= 0:
            metrics.pacing_recommendation = 0
            return

        # Pipeline-fill formula (same as PredictivePacingEngine)
        target_new_connections = max(0, available_count - connected)
        expected_from_ringing = math.floor(ringing * answer_rate)
        connections_needed = max(0, target_new_connections - expected_from_ringing)
        calls_needed = math.ceil(connections_needed / answer_rate) if connections_needed > 0 else 0

        provider_health = self.provider.get_health()
        health_dampened = math.floor(calls_needed * provider_health.health_score)

        metrics.pacing_recommendation = health_dampened

        # Safety check
        from app.safety.safety_controller import SystemSnapshot
        snapshot = SystemSnapshot(
            available_agents=available_count,
            ringing_calls=ringing,
            connected_calls=connected,
            reserved_calls=0,
            answer_rate=answer_rate,
            provider_health=provider_health,
            total_active_calls=len(self.active_calls),
        )
        ctrl = SafetyController()
        decision = ctrl.evaluate(requested_calls=health_dampened, snapshot=snapshot)

        metrics.safety_action = decision.action.value
        metrics.safety_approved = decision.approved_calls
        self._update_safety_counters(decision.action)

        if decision.approved_calls == 0:
            return

        available_agents = self.db.query(Agent).filter(
            Agent.state == AgentState.AVAILABLE.value
        ).limit(decision.approved_calls).all()

        pending_borrowers = self.db.query(Borrower).filter(
            Borrower.state == BorrowerState.PENDING.value
        ).limit(decision.approved_calls).all()

        initiated = 0
        for agent, borrower in zip(available_agents, pending_borrowers):
            result = self._initiate_simulated_call(agent, borrower)
            if result:
                initiated += 1

        metrics.calls_initiated = initiated
        self.results.total_initiated += initiated

    def _initiate_simulated_call(self, agent: Agent, borrower: Borrower) -> bool:
        """
        Simulate initiating a call for the given agent and borrower.
        Returns True if successful.
        """
        result = self.provider.initiate_call(borrower.phone_number, agent.id)
        if result.result.value != "SUCCESS":
            self.results.provider_failures += 1
            return False

        # Mark agent as DIALING, borrower as RESERVED.
        agent.state = AgentState.DIALING.value
        borrower.state = BorrowerState.RESERVED.value

        # Create call record.
        call = Call(
            agent_id=agent.id,
            borrower_id=borrower.id,
            state=CallState.INITIATED.value,
            provider_call_id=result.provider_call_id,
            dialing_mode=self.scenario.dialing_mode,
        )
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)

        # Randomise call duration around the scenario average.
        duration = max(1, int(random.gauss(
            self.scenario.avg_call_duration_ticks,
            self.scenario.avg_call_duration_ticks * 0.2
        )))

        self.active_calls.append(ActiveCall(
            call_id=call.id,
            agent_id=agent.id,
            borrower_id=borrower.id,
            provider_call_id=result.provider_call_id,
            ticks_remaining=duration,
        ))
        return True

    def _update_safety_counters(self, action: SafetyAction) -> None:
        if action == SafetyAction.APPROVE:
            self.results.safety_approvals += 1
        elif action == SafetyAction.REDUCE:
            self.results.safety_reductions += 1
        elif action == SafetyAction.REJECT:
            self.results.safety_rejections += 1

    def _compute_totals(self) -> None:
        """Calculate peak agent utilisation."""
        for m in self.results.tick_metrics:
            utilization = 1.0 - (m.available_agents / self.scenario.num_agents)
            if utilization > self.results.peak_agent_utilization:
                self.results.peak_agent_utilization = utilization

    def _print_summary(self) -> None:
        r = self.results
        print(f"\n  Summary for: {r.scenario_name}")
        print(f"    Total initiated  : {r.total_initiated}")
        print(f"    Total connected  : {r.total_connected}")
        print(f"    Total failed     : {r.total_failed}")
        print(f"    Total completed  : {r.total_completed}")
        print(f"    Safety approvals : {r.safety_approvals}")
        print(f"    Safety reductions: {r.safety_reductions}")
        print(f"    Safety rejections: {r.safety_rejections}")
        print(f"    Provider failures: {r.provider_failures}")
        print(f"    Peak utilization : {r.peak_agent_utilization:.1%}")


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def generate_charts(all_results: list[SimulationResults], output_dir: str) -> None:
    """Generate matplotlib charts for each scenario."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend (no display needed)
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping charts.")
        return

    os.makedirs(output_dir, exist_ok=True)

    for results in all_results:
        ticks = [m.tick for m in results.tick_metrics]
        initiated = [m.calls_initiated for m in results.tick_metrics]
        connected = [m.calls_connected for m in results.tick_metrics]
        available = [m.available_agents for m in results.tick_metrics]
        health = [m.provider_health for m in results.tick_metrics]
        safety_approved = [m.safety_approved for m in results.tick_metrics]

        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        fig.suptitle(f"Scenario: {results.scenario_name}", fontsize=13)

        # Plot 1: Calls per tick
        axes[0].bar(ticks, initiated, label="Initiated", alpha=0.6, color="steelblue")
        axes[0].bar(ticks, connected, label="Connected", alpha=0.6, color="green", bottom=initiated)
        axes[0].set_ylabel("Calls")
        axes[0].set_title("Calls Initiated and Connected per Tick")
        axes[0].legend()

        # Plot 2: Agent availability
        axes[1].plot(ticks, available, label="Available Agents", color="orange")
        axes[1].plot(ticks, safety_approved, label="Safety Approved", color="purple", linestyle="--")
        axes[1].set_ylabel("Count")
        axes[1].set_title("Agent Availability vs Safety-Approved Calls")
        axes[1].legend()

        # Plot 3: Provider health
        axes[2].plot(ticks, health, label="Provider Health", color="red")
        axes[2].axhline(y=0.7, color="orange", linestyle="--", label="Health threshold (0.7)")
        axes[2].set_ylabel("Health Score")
        axes[2].set_xlabel("Tick")
        axes[2].set_title("Provider Health Score")
        axes[2].set_ylim(0, 1.05)
        axes[2].legend()

        plt.tight_layout()
        safe_name = results.scenario_name.replace(" ", "_").replace("—", "-").replace("/", "-")
        filepath = os.path.join(output_dir, f"{safe_name}.png")
        plt.savefig(filepath, dpi=100)
        plt.close(fig)
        print(f"  Chart saved: {filepath}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    all_results = []

    for scenario in ALL_SCENARIOS:
        sim = Simulator(scenario, seed=42)
        results = sim.run()
        all_results.append(results)

    print("\nGenerating charts...")
    generate_charts(all_results, output_dir)
    print("\nSimulation complete.")
