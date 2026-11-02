"""Every model call recorded with tokens, searches, latency and an estimated price; one budget per run."""
from dataclasses import dataclass
from threading import Lock

from shortlist.agent.models import ModelCall, Telemetry

FINISHING_RESERVE_USD = 0.15
# Work that finishes companies already researched, allowed past the budget within the reserve: the skeptic's checks of
# gathered evidence, a Shortlisted company's opening line and the email you ask for, each with its check. A live
# vanta.com run reached the budget with three Shortlisted companies and dropped all three opening lines.
FINISHING = ("skeptic", "pitch", "email")


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

    def check(self, reserve: float = 0.0):
        with self.lock:
            if self.telemetry.cost_usd >= self.telemetry.budget_usd:
                self.telemetry.budget_reached = True
            if self.telemetry.cost_usd >= self.telemetry.budget_usd + reserve:
                raise BudgetReached(f"Run budget of ${self.telemetry.budget_usd:.2f} reached")

    def reserve_for(self, operation: str) -> float:
        """What a call may spend past the budget: finishing work shares $0.15, never more than a third of the budget;
        anything else stops at the budget."""
        if not operation.startswith(FINISHING):
            return 0.0
        return min(FINISHING_RESERVE_USD, self.telemetry.budget_usd / 3)

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
