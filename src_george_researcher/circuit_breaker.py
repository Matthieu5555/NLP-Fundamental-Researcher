"""
Circuit breaker pattern for external API calls.

Prevents cascading failures by temporarily blocking calls to failing services.
Thread-safe implementation suitable for multi-threaded applications.

Usage:
    breaker = get_circuit_breaker("openrouter")

    if breaker.is_open():
        return cached_response_or_error()

    try:
        result = call_external_api()
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise

States:
    CLOSED: Normal operation, requests flow through
    OPEN: Service failing, requests blocked for reset_timeout seconds
    HALF_OPEN: Testing if service recovered, allows limited requests

Configuration (impact of changing values):
    failure_threshold: Number of failures before circuit opens
        - INCREASING: More tolerant of transient failures but slower to react to outages
        - DECREASING: Faster reaction to outages but may trip on transient errors
    reset_timeout: Seconds to wait before allowing retry attempts
        - INCREASING: More time for service to recover, but longer outage for users
        - DECREASING: Faster recovery detection, but may overwhelm recovering service
    success_threshold: Successes needed in HALF_OPEN to close circuit
        - INCREASING: More confident service is recovered before full traffic
        - DECREASING: Faster return to normal operation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single service.

    Thread-safe: Uses a lock to protect state modifications.

    Args:
        name: Service name (for logging)
        failure_threshold: Failures before opening circuit (default: 5)
        reset_timeout: Seconds before trying again (default: 60)
        success_threshold: Successes in half-open to close (default: 2)
    """
    name: str
    failure_threshold: int = 5
    reset_timeout: int = 60
    success_threshold: int = 2

    _failures: int = field(default=0, init=False, repr=False)
    _successes: int = field(default=0, init=False, repr=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False, repr=False)
    _state: str = field(default="closed", init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def is_open(self) -> bool:
        """
        Check if circuit is open (blocking requests).

        Returns:
            True if requests should be blocked, False if allowed
        """
        with self._lock:
            if self._state == "closed":
                return False

            if self._state == "open":
                # Check if we should transition to half-open
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.reset_timeout:
                        logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (reset timeout expired)")
                        self._state = "half_open"
                        self._successes = 0
                        return False
                return True

            # half_open: allow request through
            return False

    def record_failure(self):
        """
        Record a failed request.

        Call this when an API call fails. Will potentially open the circuit.
        """
        with self._lock:
            self._failures += 1
            self._last_failure_time = datetime.now()

            if self._state == "half_open":
                # Any failure in half-open reopens circuit
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failure during recovery test)")
                self._state = "open"
            elif self._failures >= self.failure_threshold:
                logger.warning(f"Circuit {self.name}: CLOSED -> OPEN ({self._failures} consecutive failures)")
                self._state = "open"

    def record_success(self):
        """
        Record a successful request.

        Call this when an API call succeeds. Will potentially close the circuit.
        """
        with self._lock:
            if self._state == "half_open":
                self._successes += 1
                if self._successes >= self.success_threshold:
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (service recovered)")
                    self._state = "closed"
                    self._failures = 0
            elif self._state == "closed":
                # Reset failure count on success
                self._failures = 0

    def get_state(self) -> Dict:
        """
        Get current state for monitoring.

        Returns:
            Dict with circuit state information
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failures": self._failures,
                "successes_in_half_open": self._successes if self._state == "half_open" else 0,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "failure_threshold": self.failure_threshold,
                "reset_timeout_seconds": self.reset_timeout,
            }

    def reset(self):
        """
        Manually reset the circuit breaker to closed state.

        Use with caution - typically for testing or manual intervention.
        """
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._successes = 0
            self._last_failure_time = None
            logger.info(f"Circuit {self.name}: Manually reset to CLOSED")


# =============================================================================
# GLOBAL CIRCUIT BREAKER REGISTRY
# =============================================================================

_breakers: Dict[str, CircuitBreaker] = {}
_breakers_lock = Lock()


def get_circuit_breaker(
    service: str,
    failure_threshold: int = 5,
    reset_timeout: int = 60,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Thread-safe: Uses a lock to protect the global registry.

    Args:
        service: Service identifier (e.g., "openrouter", "gemini_search")
        failure_threshold: Failures before opening circuit
        reset_timeout: Seconds before allowing retries
        success_threshold: Successes needed to close circuit

    Returns:
        CircuitBreaker instance for the service
    """
    with _breakers_lock:
        if service not in _breakers:
            _breakers[service] = CircuitBreaker(
                name=service,
                failure_threshold=failure_threshold,
                reset_timeout=reset_timeout,
                success_threshold=success_threshold,
            )
            logger.debug(f"Created circuit breaker for service: {service}")
        return _breakers[service]


def get_all_breaker_states() -> Dict[str, Dict]:
    """
    Get states of all circuit breakers (for monitoring endpoint).

    Returns:
        Dict mapping service names to their circuit breaker states
    """
    with _breakers_lock:
        return {name: breaker.get_state() for name, breaker in _breakers.items()}


def reset_all_breakers():
    """
    Reset all circuit breakers to closed state.

    Use with caution - typically for testing or manual intervention.
    """
    with _breakers_lock:
        for breaker in _breakers.values():
            breaker.reset()
