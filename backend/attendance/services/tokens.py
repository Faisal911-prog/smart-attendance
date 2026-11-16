"""Rotating, HMAC-signed QR tokens.

This module is deliberately independent of Django so that it can be unit
tested (and reasoned about in the thesis) on its own.

Design
------
Time is divided into windows of ``interval`` seconds. The token of a lecture
session for window ``w`` is::

    <session_id>.<w>.<first 96 bits of HMAC-SHA256(secret, "<session_id>:<w>")>

* The secret is random, unique per session and never leaves the server.
* The server recomputes the HMAC, so it stores no tokens at all.
* A token is accepted for its own window and ``grace_windows`` older windows
  (to tolerate the time a student needs to scan and submit).
* Only the server clock is used, so phone clocks cannot be abused.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

SIGNATURE_LENGTH = 24  # hexadecimal characters = 96 bits
MAX_TOKEN_LENGTH = 100
_HEX = set("0123456789abcdef")


class TokenError(Exception):
    """Base class; ``code`` is the machine-readable rejection reason."""

    code = "INVALID_TOKEN"


class MalformedToken(TokenError):
    code = "INVALID_TOKEN"


class InvalidSignature(TokenError):
    code = "INVALID_TOKEN"


class ExpiredToken(TokenError):
    code = "EXPIRED_TOKEN"


@dataclass(frozen=True)
class ParsedToken:
    session_id: int
    window: int
    signature: str


def new_secret() -> str:
    """256-bit random secret, hex encoded."""
    return secrets.token_hex(32)


def window_index(now: float, interval: int) -> int:
    return int(now // interval)


def _signature(secret: str, session_id: int, window: int) -> str:
    message = f"{session_id}:{window}".encode("ascii")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return digest[:SIGNATURE_LENGTH]


def make_token(secret: str, session_id: int, interval: int, now: float | None = None) -> str:
    """Return the token that is valid for the window containing ``now``."""
    now = time.time() if now is None else now
    window = window_index(now, interval)
    return f"{session_id}.{window}.{_signature(secret, session_id, window)}"


def seconds_until_rotation(interval: int, now: float | None = None) -> float:
    """Seconds left before the currently displayed token is replaced."""
    now = time.time() if now is None else now
    return interval - (now % interval)


def parse_token(token: str) -> ParsedToken:
    """Split a token into its parts without trusting any of them."""
    if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
        raise MalformedToken("Token has the wrong type or length.")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise MalformedToken("Token must have three parts.")
    session_part, window_part, signature = parts
    for number in (session_part, window_part):
        if not (number.isascii() and number.isdigit()):
            raise MalformedToken("Token numbers must be decimal digits.")
    if len(signature) != SIGNATURE_LENGTH or not set(signature) <= _HEX:
        raise MalformedToken("Token signature has the wrong format.")
    return ParsedToken(int(session_part), int(window_part), signature)


def verify_token(
    secret: str,
    parsed: ParsedToken,
    interval: int,
    grace_windows: int = 1,
    now: float | None = None,
) -> None:
    """Raise a ``TokenError`` unless ``parsed`` is authentic and fresh."""
    now = time.time() if now is None else now
    expected = _signature(secret, parsed.session_id, parsed.window)
    if not hmac.compare_digest(expected, parsed.signature):
        raise InvalidSignature("Signature mismatch.")
    age = window_index(now, interval) - parsed.window
    if age < 0:
        raise InvalidSignature("Token window lies in the future.")
    if age > grace_windows:
        raise ExpiredToken("Token has expired.")
