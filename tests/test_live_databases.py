"""Opt-in health checks for installed drivers and real databases."""

import json
import os

import pytest

from procora import connect


@pytest.mark.parametrize(
    ("backend", "variable"),
    [
        ("sqlserver", "PROCORA_SQLSERVER_OPTIONS"),
        ("postgresql", "PROCORA_POSTGRESQL_OPTIONS"),
        ("mysql", "PROCORA_MYSQL_OPTIONS"),
    ],
)
def test_live_database_when_configured(backend, variable):
    raw = os.environ.get(variable)
    if not raw:
        pytest.skip(f"{variable} is not configured")
    database = connect(backend, **json.loads(raw))
    assert database.ping() is True
