"""ReCode scoring (max 100).

| Component   | Points | Rule                                                             |
|-------------|--------|------------------------------------------------------------------|
| Correctness | 60     | All tests pass, otherwise 0 (no partial credit).                 |
| Attempts    | 20     | 20 * 0.75^failed_attempts: diminishing returns after a few fails. |
| Speed       | 10     | Full within 5 min of starting, sliding to 1 point at 3 hours.     |
| Efficiency  | 10     | Runtime (7) + memory (3) relative to the reference solution.      |

Revealed hints subtract their cost from the total (never below zero).
"""

import math
from dataclasses import dataclass

CORRECTNESS_POINTS = 60
ATTEMPT_POINTS = 20
SPEED_POINTS = 10
EFFICIENCY_POINTS = 10

ATTEMPT_DECAY = 0.75
SPEED_FULL_SECONDS = 5 * 60
SPEED_FLOOR_SECONDS = 3 * 60 * 60
SPEED_FLOOR_POINTS = 1

# Runtime ratios (player / reference) -> points. Within 1.5x is full marks, 20x or worse is zero.
RUNTIME_FULL_RATIO = 1.5
RUNTIME_ZERO_RATIO = 20.0
MEMORY_FULL_RATIO = 1.25
MEMORY_ZERO_RATIO = 4.0


@dataclass
class ScoreBreakdown:
    correctness: float
    attempts: float
    speed: float
    efficiency: float
    hint_penalty: float

    @property
    def total(self):
        raw = self.correctness + self.attempts + self.speed + self.efficiency - self.hint_penalty
        return round(max(0.0, min(100.0, raw)), 2)


def attempt_points(failed_attempts):
    return round(ATTEMPT_POINTS * ATTEMPT_DECAY ** max(0, failed_attempts), 2)


def speed_points(seconds):
    if seconds <= SPEED_FULL_SECONDS:
        return float(SPEED_POINTS)
    if seconds >= SPEED_FLOOR_SECONDS:
        return float(SPEED_FLOOR_POINTS)
    fraction = (seconds - SPEED_FULL_SECONDS) / (SPEED_FLOOR_SECONDS - SPEED_FULL_SECONDS)
    return round(SPEED_POINTS - fraction * (SPEED_POINTS - SPEED_FLOOR_POINTS), 2)


def _ratio_score(ratio, full_ratio, zero_ratio):
    """1.0 at/below full_ratio, 0.0 at/above zero_ratio, log-linear in between."""
    if ratio <= full_ratio:
        return 1.0
    if ratio >= zero_ratio:
        return 0.0
    return 1 - math.log(ratio / full_ratio) / math.log(zero_ratio / full_ratio)


def efficiency_points(runtime_ms, reference_runtime_ms, memory_kb=None, reference_memory_kb=None):
    if not reference_runtime_ms or runtime_ms is None:
        time_part = 1.0
    else:
        # Below ~1ms the measurement is noise, so clamp both sides.
        ratio = max(runtime_ms, 0.05) / max(reference_runtime_ms, 0.05)
        time_part = _ratio_score(ratio, RUNTIME_FULL_RATIO, RUNTIME_ZERO_RATIO)
    if not reference_memory_kb or not memory_kb:
        mem_part = 1.0
    else:
        mem_part = _ratio_score(memory_kb / reference_memory_kb, MEMORY_FULL_RATIO, MEMORY_ZERO_RATIO)
    return round(EFFICIENCY_POINTS * (0.7 * time_part + 0.3 * mem_part), 2)


def score(*, solved, failed_attempts, solve_seconds, runtime_ms, reference_runtime_ms,
          memory_kb=None, reference_memory_kb=None, hint_penalty=0):
    if not solved:
        return ScoreBreakdown(0, 0, 0, 0, 0)
    return ScoreBreakdown(
        correctness=float(CORRECTNESS_POINTS),
        attempts=attempt_points(failed_attempts),
        speed=speed_points(solve_seconds),
        efficiency=efficiency_points(runtime_ms, reference_runtime_ms, memory_kb, reference_memory_kb),
        hint_penalty=float(hint_penalty),
    )
