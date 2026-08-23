"""
Simulation scenarios definition.

Each scenario is a dataclass describing the parameters of a simulated
dialing campaign.  The simulator reads these and runs each one.
"""

from dataclasses import dataclass, field


@dataclass
class Scenario:
    """All parameters needed to describe a dialing simulation."""
    name: str
    description: str

    # How many agents participate.
    num_agents: int

    # How many borrowers are in the campaign.
    num_borrowers: int

    # Probability (0–1) that a ringing call is answered.
    answer_rate: float

    # Average length of a connected call in simulation ticks.
    avg_call_duration_ticks: int

    # Number of simulation time ticks to run.
    num_ticks: int

    # Dialing mode: "progressive" or "predictive".
    dialing_mode: str = "progressive"

    # Provider to use: "a" (reliable) or "b" (chaotic).
    provider: str = "a"

    # If using Provider B, whether to trigger an outage mid-simulation.
    simulate_outage_at_tick: int | None = None

    # If True, agents disappear at tick agent_drop_at_tick.
    simulate_agent_drop: bool = False
    agent_drop_at_tick: int = 0
    agents_to_drop: int = 0


# ---------------------------------------------------------------------------
# The four required scenarios from the spec
# ---------------------------------------------------------------------------

SCENARIO_A = Scenario(
    name="A — Low Answer Rate",
    description="20% answer rate, 120-tick calls. Tests predictive over-dialing risk.",
    num_agents=20,
    num_borrowers=200,
    answer_rate=0.20,
    avg_call_duration_ticks=12,
    num_ticks=60,
    dialing_mode="predictive",
    provider="a",
)

SCENARIO_B = Scenario(
    name="B — Medium Answer Rate",
    description="50% answer rate, 90-tick calls. Balanced dialing conditions.",
    num_agents=20,
    num_borrowers=200,
    answer_rate=0.50,
    avg_call_duration_ticks=9,
    num_ticks=60,
    dialing_mode="predictive",
    provider="a",
)

SCENARIO_C = Scenario(
    name="C — High Answer Rate",
    description="70% answer rate, 180-tick calls. Long calls, fewer needed.",
    num_agents=20,
    num_borrowers=200,
    answer_rate=0.70,
    avg_call_duration_ticks=18,
    num_ticks=60,
    dialing_mode="predictive",
    provider="a",
)

SCENARIO_D = Scenario(
    name="D — Changing Conditions with Provider B",
    description=(
        "Starts at 50% answer rate, drops to 15% at tick 20. "
        "Provider B (chaotic). Outage at tick 35. Agent drop at tick 15."
    ),
    num_agents=30,
    num_borrowers=300,
    answer_rate=0.50,          # Starting rate; drops mid-simulation
    avg_call_duration_ticks=10,
    num_ticks=80,
    dialing_mode="predictive",
    provider="b",
    simulate_outage_at_tick=35,
    simulate_agent_drop=True,
    agent_drop_at_tick=15,
    agents_to_drop=10,
)

ALL_SCENARIOS = [SCENARIO_A, SCENARIO_B, SCENARIO_C, SCENARIO_D]
