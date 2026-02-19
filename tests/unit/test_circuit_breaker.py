"""Tests for the circuit breaker module."""

import pytest
from unittest.mock import patch
import time

from src_george_researcher.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
    get_all_breaker_states,
    reset_all_breakers,
)


class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Test that new circuit breakers start in closed state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.is_open() is False
        assert breaker.get_state()["state"] == "closed"

    def test_opens_after_failure_threshold(self):
        """Test that circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open() is True
        assert breaker.get_state()["state"] == "open"

    def test_does_not_open_before_threshold(self):
        """Test that circuit stays closed before reaching threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Record failures below threshold
        for _ in range(4):
            breaker.record_failure()

        assert breaker.is_open() is False

    def test_success_resets_failure_count(self):
        """Test that success resets the failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()

        # Success resets count
        breaker.record_success()

        # Should need 5 more failures to open
        for _ in range(4):
            breaker.record_failure()

        assert breaker.is_open() is False

        breaker.record_failure()  # 5th failure
        assert breaker.is_open() is True

    def test_transitions_to_half_open_after_timeout(self):
        """Test that circuit transitions to half-open after reset timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            reset_timeout=1  # 1 second for testing
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is True

        # Wait for timeout
        time.sleep(1.1)

        # Should transition to half-open
        assert breaker.is_open() is False
        assert breaker.get_state()["state"] == "half_open"

    def test_half_open_closes_on_success_threshold(self):
        """Test that half-open circuit closes after success threshold."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            reset_timeout=1,
            success_threshold=2
        )

        # Open and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(1.1)
        breaker.is_open()  # Triggers transition to half-open

        # Record successes
        breaker.record_success()
        assert breaker.get_state()["state"] == "half_open"

        breaker.record_success()
        assert breaker.get_state()["state"] == "closed"

    def test_half_open_reopens_on_failure(self):
        """Test that half-open circuit reopens on failure."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            reset_timeout=1,
            success_threshold=2
        )

        # Open and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(1.1)
        breaker.is_open()  # Triggers transition to half-open

        # Failure in half-open reopens
        breaker.record_failure()
        assert breaker.is_open() is True
        assert breaker.get_state()["state"] == "open"

    def test_manual_reset(self):
        """Test that manual reset returns to closed state."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is True

        # Manual reset
        breaker.reset()
        assert breaker.is_open() is False
        assert breaker.get_state()["state"] == "closed"
        assert breaker.get_state()["failures"] == 0


class TestGlobalRegistry:
    """Tests for the global circuit breaker registry."""

    def test_get_circuit_breaker_creates_new(self):
        """Test that get_circuit_breaker creates new breakers."""
        reset_all_breakers()

        breaker1 = get_circuit_breaker("service1")
        breaker2 = get_circuit_breaker("service2")

        assert breaker1.name == "service1"
        assert breaker2.name == "service2"
        assert breaker1 is not breaker2

    def test_get_circuit_breaker_returns_existing(self):
        """Test that get_circuit_breaker returns existing breaker."""
        reset_all_breakers()

        breaker1 = get_circuit_breaker("service1")
        breaker2 = get_circuit_breaker("service1")

        assert breaker1 is breaker2

    def test_get_all_breaker_states(self):
        """Test that get_all_breaker_states returns all states."""
        reset_all_breakers()

        get_circuit_breaker("service1")
        get_circuit_breaker("service2")

        states = get_all_breaker_states()

        assert "service1" in states
        assert "service2" in states
        assert states["service1"]["state"] == "closed"

    def test_reset_all_breakers(self):
        """Test that reset_all_breakers resets all circuits."""
        reset_all_breakers()

        # Use unique service name to get fresh breaker with our threshold
        breaker = get_circuit_breaker("service_reset_test", failure_threshold=2)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is True

        reset_all_breakers()

        # Breaker should be closed now
        assert breaker.is_open() is False
