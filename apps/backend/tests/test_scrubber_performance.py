"""R2-SEC-01: the secret scrubber must stay linear on adversarial input."""

import time

import pytest

from app.core.security_guardrails import scrub_sensitive_information

ADVERSARIAL = {
    "jwt": "eyJ-" * 262_144,
    "dburi": "postgres://a:" * 80_000,
    "privkey": "-----BEGIN PRIVATE KEY-----" * 38_000,
    "sk": "sk-" * 350_000,
}


@pytest.mark.parametrize("name", ADVERSARIAL)
def test_scrubber_is_linear_on_adversarial_input(name):
    started = time.perf_counter()
    scrub_sensitive_information(ADVERSARIAL[name], preserve_lines=True)
    assert time.perf_counter() - started < 2.0


def test_real_secrets_are_still_redacted():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
    text = f"token {jwt}\n{key}\nAKIAABCDEFGHIJKLMNOP\npostgresql://admin:pw@host/db"
    out = scrub_sensitive_information(text, preserve_lines=True)
    assert "eyJhbGci" not in out
    assert "MIIEow" not in out
    assert "AKIAABCDEFGHIJKLMNOP" not in out
    assert "admin:[REDACTED_PASSWORD]@host/db" in out
    assert out.count("\n") == text.count("\n")
