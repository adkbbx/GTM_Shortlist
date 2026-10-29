"""Every model call recorded with tokens, searches, latency and an estimated price; one budget per run."""
from dataclasses import dataclass
from threading import Lock

from shortlist.agent.models import ModelCall, Telemetry


class BudgetReached(RuntimeError):
    """The run's budget is spent: no new model calls start."""


@dataclass(frozen=True)
class Pricing:
    input_usd_per_m: float
    output_usd_per_m: float
    usd_per_search: float = 0.0

    def cost(self, input_tokens: int, output_tokens: int, searches: int = 0) -> float:
        return (input_tokens * self.input_usd_per_m + output_tokens * self.output_usd_per_m) / 1_000_000 \
            + searches * self.usd_per_search


class Meter:
    """Thread-safe call log and budget guard shared by every stage of one run."""

    def __init__(self, telemetry: Telemetry):
        self.telemetry = telemetry
        self.lock = Lock()

    @property
    def spent(self) -> float:
        with self.lock:
            return self.telemetry.cost_usd

    def check(self):
        with self.lock:
            if self.telemetry.cost_usd >= self.telemetry.budget_usd:
                self.telemetry.budget_reached = True
                raise BudgetReached(f"Run budget of ${self.telemetry.budget_usd:.2f} reached")

    def record(self, call: ModelCall):
        with self.lock:
            t = self.telemetry
            t.calls.append(call)
            t.model_calls += 1
            t.cost_usd = round(t.cost_usd + call.usd, 6)
            t.input_tokens += call.input_tokens
            t.output_tokens += call.output_tokens
            t.searches += call.searches
            if t.cost_usd >= t.budget_usd:
                t.budget_reached = True

    def fetched(self, count: int = 1):
        with self.lock:
            self.telemetry.pages_fetched += count

    def company_cost(self, domain: str) -> float:
        with self.lock:
            return round(sum(call.usd for call in self.telemetry.calls if call.company == domain), 6)

    def snapshot(self) -> Telemetry:
        with self.lock:
            return self.telemetry.model_copy(deep=True)
