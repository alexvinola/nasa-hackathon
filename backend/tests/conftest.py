"""Shared set-up for every backend test."""

import os

# The suite sends hundreds of requests from one client in a few seconds, far over what a HUD does. The rate limit
# has its own tests (unit/test_guardrails.py), which install a limiter of their own.
os.environ["PULSAR_RATE_LIMITS"] = "off"
