"""Shared test fixtures.

Production defaults are secure-by-default (auth required, etc). Tests should
opt out explicitly per test rather than rely on those defaults, so disable
auth-gating here and let individual tests re-enable when they're specifically
exercising the auth gate.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def _disable_auth_gate(monkeypatch):
    # Only set if a test hasn't already provided its own value.
    if "REQUIRE_AUTH_FOR_RUNS" not in os.environ:
        monkeypatch.setenv("REQUIRE_AUTH_FOR_RUNS", "false")
    if "BASE_DOMAIN" not in os.environ:
        monkeypatch.setenv("BASE_DOMAIN", "fastaisolution.com")
    yield
