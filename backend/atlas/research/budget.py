import time
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from atlas.research.errors import BudgetExhausted, RunCancelled
from atlas.research.models import ResearchRun
from atlas.research.schemas import RunLimits


class Budget:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        run_id: str,
        limits: RunLimits,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.sessions, self.run_id, self.limits = sessions, run_id, limits
        self.clock = clock
        self.deadline = clock() + limits.max_seconds

    def check(self) -> None:
        with self.sessions() as session:
            run = session.get(ResearchRun, self.run_id)
            if run is None or run.cancel_requested or run.status == "cancelled":
                raise RunCancelled("cancelled", "Cancellation requested")
        if self.clock() >= self.deadline:
            raise BudgetExhausted("elapsed_time", "Elapsed research time limit reached")

    def remaining(self) -> float:
        self.check()
        return max(0.05, self.deadline - self.clock())

    def increment(self, key: str, cap: int | None = None, amount: int = 1) -> int:
        self.check()
        with self.sessions() as session:
            run = session.get(ResearchRun, self.run_id)
            assert run is not None
            value = int(run.stats.get(key, 0)) + amount
            if cap is not None and value > cap:
                raise BudgetExhausted(key, f"Research budget reached: {key}")
            run.stats = {**run.stats, key: value}
            session.commit()
            return value

    def model_request(self, requested_tokens: int, live: bool) -> int:
        self.check()
        with self.sessions() as session:
            run = session.get(ResearchRun, self.run_id)
            assert run is not None
            calls = int(run.stats.get("provider_requests", 0))
            reserved = int(run.stats.get("output_tokens_reserved", 0))
            if calls >= self.limits.max_model_requests:
                raise BudgetExhausted("model_requests", "Model request limit reached")
            allocation = min(requested_tokens, self.limits.max_output_tokens - reserved)
            if allocation < 256:
                raise BudgetExhausted("output_tokens", "Model output token budget reached")
            run.stats = {
                **run.stats,
                "provider_requests": calls + 1,
                "model_http_requests": int(run.stats.get("model_http_requests", 0)) + int(live),
                "output_tokens_reserved": reserved + allocation,
            }
            session.commit()
            return allocation

    def pause(self, seconds: float) -> None:
        until = self.clock() + seconds
        if seconds >= self.remaining():
            raise BudgetExhausted("elapsed_time", "Not enough time to honor source rate limits")
        while self.clock() < until:
            self.check()
            time.sleep(min(0.1, max(0, until - self.clock())))
