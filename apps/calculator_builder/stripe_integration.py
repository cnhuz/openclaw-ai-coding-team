from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


def stripe_enabled() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY", "").strip())


def create_checkout_session(
    *,
    amount_cents: int,
    currency: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> tuple[bool, str]:
    """Return (ok, url_or_error). Uses Stripe API if STRIPE_SECRET_KEY is set."""

    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        return (False, "STRIPE_SECRET_KEY not configured")

    # Minimal Stripe Checkout Session creation.
    params: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("line_items[0][price_data][currency]", currency),
        ("line_items[0][price_data][product_data][name]", "Calculator unlock"),
        ("line_items[0][price_data][unit_amount]", str(int(amount_cents))),
        ("line_items[0][quantity]", "1"),
    ]
    for k, v in metadata.items():
        params.append((f"metadata[{k}]", v))

    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            payload = json.loads(raw)
            url = payload.get("url")
            if not url:
                return (False, f"Stripe response missing url: {payload}")
            return (True, str(url))
    except Exception as e:
        return (False, str(e))
