"""Circuit breaker state machine for resilient actor and tool dispatch."""

import time
from enum import Enum
from typing import Optional

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted on an open circuit."""
    pass

class CircuitBreaker:
    """Manages failure thresholds and cooldown windows to prevent cascading actor failures."""

    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_state_change: float = time.time()

    def can_execute(self) -> bool:
        """Evaluate if incoming call is permissible based on state and recovery timeouts."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if (now - self.last_state_change) >= self.recovery_time_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        """Record successful execution and close circuit if recovered."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.last_state_change = time.time()

    def record_failure(self) -> None:
        """Record failed execution and trip circuit open if threshold exceeded."""
        self.failure_count += 1
        self.last_state_change = time.time()
        if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
