from __future__ import annotations

import json
import urllib.request
from typing import Any


def post_webhook(url: str, payload: dict[str, Any], timeout: float = 5.0) -> tuple[bool, str]:
    if not url or not url.strip():
        return (True, "webhook disabled")

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "calculator-builder-mvp"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(2000)
            return (200 <= resp.status < 300, f"{resp.status} {body.decode('utf-8', 'ignore')}")
    except Exception as e:
        return (False, str(e))
