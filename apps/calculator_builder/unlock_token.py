from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass


class UnlockTokenError(Exception):
    pass


@dataclass(frozen=True)
class UnlockTokenSigner:
    secret: bytes

    @staticmethod
    def from_env() -> "UnlockTokenSigner":
        raw = os.environ.get("CALC_BUILDER_TOKEN_SECRET", "").strip()
        if raw:
            secret = raw.encode("utf-8")
        else:
            # MVP fallback: stable-ish per host/user if not set. Not for production.
            secret = ("dev-secret:" + os.getcwd()).encode("utf-8")
        return UnlockTokenSigner(secret=secret)

    def sign(self, *, calculator_id: str, submission_id: str, scope: str = "pay") -> str:
        msg = f"{scope}|{calculator_id}|{submission_id}".encode("utf-8")
        sig = hmac.new(self.secret, msg, hashlib.sha256).hexdigest()
        return sig

    def verify(self, *, token: str, calculator_id: str, submission_id: str, scope: str = "pay") -> bool:
        if not token:
            return False
        expected = self.sign(calculator_id=calculator_id, submission_id=submission_id, scope=scope)
        return hmac.compare_digest(expected, token)
