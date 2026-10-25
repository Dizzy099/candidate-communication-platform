import threading
import time


class TokenBucket:
    """In-process token bucket (the simulator runs as a single process)."""

    def __init__(self, rate_per_second: float, burst: float, clock=time.monotonic):
        self.rate = rate_per_second
        self.capacity = burst
        self.tokens = burst
        self.clock = clock
        self.updated = clock()
        self.lock = threading.Lock()

    def take(self) -> float:
        """Consume a token. Returns 0 when allowed, else seconds to wait."""
        with self.lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            return (1 - self.tokens) / self.rate
