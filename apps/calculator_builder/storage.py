from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Storage:
    root: Path

    @property
    def calculators_dir(self) -> Path:
        return self.root / "calculators"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def submissions_dir(self) -> Path:
        return self.root / "submissions"

    @property
    def views_dir(self) -> Path:
        return self.root / "views"

    @property
    def ratelimit_dir(self) -> Path:
        return self.root / "ratelimit"

    @property
    def outbox_dir(self) -> Path:
        return self.root / "outbox"

    def ensure(self) -> None:
        self.calculators_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.submissions_dir.mkdir(parents=True, exist_ok=True)
        self.views_dir.mkdir(parents=True, exist_ok=True)
        self.ratelimit_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    # -------------------- calculators / templates --------------------

    def list_calculators(self) -> list[dict[str, Any]]:
        self.ensure()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.calculators_dir.glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        rows.sort(key=lambda c: str(c.get("created_at", "")), reverse=True)
        return rows

    def list_templates(self) -> list[dict[str, Any]]:
        self.ensure()
        rows: list[dict[str, Any]] = []
        for path in sorted(self.templates_dir.glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        rows.sort(key=lambda t: str(t.get("name", "")))
        return rows

    def load_template(self, template_name: str) -> dict[str, Any]:
        path = (self.templates_dir / template_name).with_suffix(".json")
        if not path.exists():
            raise FileNotFoundError(f"template not found: {template_name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def calc_path(self, calc_id: str) -> Path:
        return (self.calculators_dir / calc_id).with_suffix(".json")

    def load_calculator(self, calc_id: str) -> dict[str, Any]:
        path = self.calc_path(calc_id)
        if not path.exists():
            raise FileNotFoundError(f"calculator not found: {calc_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_calculator(self, calc: dict[str, Any]) -> None:
        self.ensure()
        calc_id = str(calc.get("id") or "").strip()
        if not calc_id:
            raise ValueError("calculator id is required")
        path = self.calc_path(calc_id)
        path.write_text(json.dumps(calc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ------------------------- submissions --------------------------

    def submissions_path(self, calc_id: str) -> Path:
        return (self.submissions_dir / calc_id).with_suffix(".jsonl")

    def append_submission(self, calc_id: str, submission: dict[str, Any]) -> None:
        self.ensure()
        path = self.submissions_path(calc_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(submission, ensure_ascii=False) + "\n")

    def list_submissions(self, calc_id: str, limit: int = 50) -> list[dict[str, Any]]:
        path = self.submissions_path(calc_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-limit:][::-1]

    def count_submissions(self, calc_id: str) -> int:
        return self._count_jsonl_lines(self.submissions_path(calc_id))

    def find_submission(self, calc_id: str, submission_id: str) -> Optional[dict[str, Any]]:
        """Best-effort lookup in append-only JSONL (demo-scale only)."""

        submission_id = (submission_id or "").strip()
        if not submission_id:
            return None
        path = self.submissions_path(calc_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if str(row.get("submission_id", "")) == submission_id:
                    return row
        return None

    def export_submissions_csv(self, calc_id: str) -> str:
        """CSV export for submissions.

        Required columns per spec:
        - calculator_id
        - submitted_at
        - email
        - inputs
        - result
        """

        path = self.submissions_path(calc_id)
        rows: list[dict[str, Any]] = []
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue

        buf = io.StringIO()
        w = csv.DictWriter(
            buf,
            fieldnames=["calculator_id", "submitted_at", "email", "inputs", "result"],
            extrasaction="ignore",
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "calculator_id": r.get("calculator_id", calc_id),
                    "submitted_at": r.get("timestamp", ""),
                    "email": r.get("email", ""),
                    "inputs": json.dumps(r.get("inputs", {}), ensure_ascii=False, separators=(",", ":")),
                    "result": json.dumps(r.get("results", {}), ensure_ascii=False, separators=(",", ":")),
                }
            )
        return buf.getvalue()

    # --------------------------- views ------------------------------

    def views_path(self, calc_id: str) -> Path:
        return (self.views_dir / calc_id).with_suffix(".jsonl")

    def append_view(self, calc_id: str, view: dict[str, Any]) -> None:
        self.ensure()
        path = self.views_path(calc_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(view, ensure_ascii=False) + "\n")

    def count_views(self, calc_id: str) -> int:
        return self._count_jsonl_lines(self.views_path(calc_id))

    # ------------------------- rate limit ---------------------------

    def ratelimit_path(self, calc_id: str) -> Path:
        return (self.ratelimit_dir / calc_id).with_suffix(".jsonl")

    def allow_and_record_submission(
        self,
        *,
        calc_id: str,
        ip: str,
        now_ts: float,
        window_seconds: int,
        max_submissions: int,
    ) -> bool:
        """Simple persistent IP-based rate limit.

        Demo-scale implementation: reads and filters a JSONL file.
        """

        self.ensure()
        if window_seconds <= 0 or max_submissions <= 0:
            return True

        ip = (ip or "").strip()
        path = self.ratelimit_path(calc_id)
        hits: list[dict[str, Any]] = []
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            hits.append(json.loads(line))
                        except Exception:
                            continue
            except Exception:
                hits = []

        cutoff = now_ts - float(window_seconds)
        recent = [
            h
            for h in hits
            if str(h.get("ip", "")) == ip and float(h.get("ts", 0.0) or 0.0) >= cutoff
        ]
        if len(recent) >= max_submissions:
            return False

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ip": ip, "ts": now_ts}, ensure_ascii=False) + "\n")
        return True

    # ---------------------------- email -----------------------------

    def write_outbox_eml(self, calc_id: str, subject: str, eml_text: str) -> Path:
        self.ensure()
        safe_id = "".join(ch for ch in calc_id if ch.isalnum() or ch in "-_") or "calc"
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{safe_id}.eml"
        path = self.outbox_dir / filename
        path.write_text(eml_text, encoding="utf-8")
        return path

    # ---------------------------- utils -----------------------------

    def _count_jsonl_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        n = 0
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        n += 1
        except Exception:
            return 0
        return n
