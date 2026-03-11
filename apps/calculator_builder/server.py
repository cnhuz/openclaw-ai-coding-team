from __future__ import annotations

import argparse
import html
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from .emailer import send_result_email
from .formula import FormulaError, compile_formula, eval_formula
from .storage import Storage
from .stripe_integration import create_checkout_session, stripe_enabled
from .unlock_token import UnlockTokenSigner
from .webhook import post_webhook


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def esc(v: Any) -> str:
    return html.escape(str(v))


def load_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return None
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except Exception:
        return None


def load_form_body(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    data = parse_qs(raw, keep_blank_values=True)
    return {k: (v[0] if v else "") for k, v in data.items()}


def render_page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    .muted {{ color: #666; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 14px; margin: 12px 0; }}
    code, pre {{ background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }}
    pre {{ padding: 12px; overflow: auto; }}
    input, select, textarea {{ width: 100%; padding: 8px; margin: 6px 0 12px; }}
    label {{ font-weight: 600; }}
    button {{ padding: 8px 12px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .danger {{ color: #b00020; }}
    .ok {{ color: #156f2a; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""


@dataclass
class App:
    storage: Storage
    host: str
    port: int


class Handler(BaseHTTPRequestHandler):
    server_version = "CalculatorBuilderMVP/0.1"

    def do_GET(self) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            return self._handle_home(app)
        if path == "/create":
            return self._handle_create(app, qs)
        if path.startswith("/edit/"):
            calc_id = path.split("/", 2)[2]
            return self._handle_edit(app, calc_id)
        if path.startswith("/c/"):
            calc_id = path.split("/", 2)[2]
            embed = qs.get("embed", [""])[0] == "1"
            return self._handle_calc(app, calc_id, qs, embed=embed)
        if path == "/webhook-receiver":
            return self._handle_webhook_receiver(app)
        if path == "/pay/dev":
            return self._handle_pay_dev(app, qs)
        if path == "/pay/stripe/success":
            return self._handle_pay_stripe_success(app, qs)
        if path == "/pay/stripe/cancel":
            return self._handle_pay_stripe_cancel(app, qs)
        if path.startswith("/r/"):
            calc_id = path.split("/", 2)[2]
            return self._handle_results(app, calc_id, qs)

        self._send_text(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/submit/"):
            calc_id = path.split("/", 2)[2]
            return self._handle_submit(app, calc_id)
        if path.startswith("/save/"):
            calc_id = path.split("/", 2)[2]
            return self._handle_save(app, calc_id)
        if path == "/webhook-receiver":
            payload = load_json_body(self) or {}
            # store receiver log in memory for demo (server process lifetime)
            bucket: list[dict[str, Any]] = getattr(self.server, "webhook_events", [])  # type: ignore[attr-defined]
            bucket.append({"received_at": now_iso(), "payload": payload})
            setattr(self.server, "webhook_events", bucket)  # type: ignore[attr-defined]
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        self._send_text(HTTPStatus.NOT_FOUND, "not found")

    # --------------------------- handlers ---------------------------

    def _handle_home(self, app: App) -> None:
        calcs = app.storage.list_calculators()
        templates = app.storage.list_templates()

        rows = [
            "<h1>Calculator Builder (MVP)</h1>",
            "<p class='muted'>Config-driven builder (no drag). Hosted URL + embed + webhook + email + (optional) payment unlock.</p>",
        ]

        rows.append("<div class='card'><h2>Templates</h2>")
        if not templates:
            rows.append("<p class='muted'>No templates found. Ensure data/templates/*.json exist.</p>")
        else:
            rows.append("<ul>")
            for t in templates:
                name = esc(t.get("name", t.get("id", "template")))
                tid = esc(t.get("id", ""))
                fname = self._template_filename_from_id(tid)
                rows.append(
                    f"<li><b>{name}</b> - {esc(t.get('description',''))} "
                    f"<a href='/create?template={esc(fname)}'>Create</a></li>"
                )
            rows.append("</ul>")
        rows.append("</div>")

        rows.append("<div class='card'><h2>Calculators</h2>")
        rows.append("<p><a href='/create'>Create blank</a></p>")
        if not calcs:
            rows.append("<p class='muted'>No calculators yet.</p>")
        else:
            rows.append("<ul>")
            for c in calcs:
                cid = esc(c.get("id", ""))
                rows.append(
                    f"<li><b>{esc(c.get('name', cid))}</b> "
                    f"<span class='muted'>({cid})</span> "
                    f"<a href='/c/{cid}'>Open</a> | <a href='/edit/{cid}'>Edit</a></li>"
                )
            rows.append("</ul>")
        rows.append("</div>")

        self._send_html(HTTPStatus.OK, render_page("Calculator Builder", "\n".join(rows)))

    def _template_filename_from_id(self, template_id: str) -> str:
        mapping = {
            "tpl_pricing": "pricing",
            "tpl_roi": "roi",
            "tpl_volume_discount": "volume_discount",
        }
        return mapping.get(template_id, template_id)

    def _handle_create(self, app: App, qs: dict[str, list[str]]) -> None:
        template = (qs.get("template") or [""])[0].strip()
        if template:
            tpl = app.storage.load_template(template)
            calc_id = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
            calc = dict(tpl)
            calc["id"] = calc_id
            calc["name"] = tpl.get("name", "Calculator")
            calc["created_at"] = now_iso()
            calc["updated_at"] = now_iso()
            app.storage.save_calculator(calc)
            return self._redirect(f"/edit/{calc_id}")

        calc_id = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
        calc = {
            "id": calc_id,
            "name": "Untitled calculator",
            "description": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "require_email_for_full_result": False,
            "webhook_url": "",
            "payment": {"enabled": False},
            "fields": [
                {"key": "x", "label": "X", "type": "number", "min": 0, "max": 100, "step": 1, "default": 10},
                {"key": "y", "label": "Y", "type": "number", "min": 0, "max": 100, "step": 1, "default": 20},
                {"key": "result", "label": "Result", "type": "result", "format": "number", "formula": "x + y"},
            ],
        }
        app.storage.save_calculator(calc)
        return self._redirect(f"/edit/{calc_id}")

    def _handle_edit(self, app: App, calc_id: str) -> None:
        try:
            calc = app.storage.load_calculator(calc_id)
        except FileNotFoundError:
            return self._send_text(HTTPStatus.NOT_FOUND, "calculator not found")

        hosted = f"http://{app.host}:{app.port}/c/{calc_id}"
        embed = f"<iframe src=\"{hosted}?embed=1\" style=\"width:100%;height:520px;border:0\"></iframe>"

        submissions = app.storage.list_submissions(calc_id, limit=20)

        rows = [
            f"<h1>Edit: {esc(calc.get('name', calc_id))}</h1>",
            f"<p><a href='/'>Home</a> | <a href='/c/{esc(calc_id)}'>Open calculator</a></p>",
            "<div class='row'>",
            "<div class='card'>",
            "<h2>Config (JSON)</h2>",
            f"<form method='POST' action='/save/{esc(calc_id)}'>",
            f"<textarea name='config' rows='28'>{esc(json.dumps(calc, ensure_ascii=False, indent=2))}</textarea>",
            "<button type='submit'>Save</button>",
            "</form>",
            "</div>",
            "<div class='card'>",
            "<h2>Hosted URL</h2>",
            f"<p><a href='/c/{esc(calc_id)}'>{esc(hosted)}</a></p>",
            "<h2>Embed snippet (iframe)</h2>",
            f"<pre>{esc(embed)}</pre>",
            "<p class='muted'>Embed mode uses ?embed=1.</p>",
            "<h2>Recent submissions</h2>",
        ]
        if not submissions:
            rows.append("<p class='muted'>No submissions yet.</p>")
        else:
            rows.append("<pre>" + esc("\n".join(json.dumps(s, ensure_ascii=False) for s in submissions)) + "</pre>")
        rows += ["</div>", "</div>"]

        self._send_html(HTTPStatus.OK, render_page("Edit calculator", "\n".join(rows)))

    def _handle_calc(self, app: App, calc_id: str, qs: dict[str, list[str]], *, embed: bool) -> None:
        try:
            calc = app.storage.load_calculator(calc_id)
        except FileNotFoundError:
            return self._send_text(HTTPStatus.NOT_FOUND, "calculator not found")

        fields = calc.get("fields", [])
        if not isinstance(fields, list):
            fields = []

        title = str(calc.get("name", calc_id))
        header = "" if embed else f"<p><a href='/'>Admin</a> | <a href='/edit/{esc(calc_id)}'>Edit</a></p>"

        rows = [
            f"<h1>{esc(title)}</h1>" if not embed else f"<h2>{esc(title)}</h2>",
            header,
        ]
        if calc.get("description"):
            rows.append(f"<p class='muted'>{esc(calc.get('description'))}</p>")

        # If user comes back from a payment success, show a helpful notice.
        if qs.get("paid", [""])[0] == "1":
            rows.append("<p class='ok'><b>Payment recorded.</b> You can now view the full results for your submission.</p>")

        rows.append(f"<form method='POST' action='/submit/{esc(calc_id)}'>")

        for f in fields:
            if not isinstance(f, dict):
                continue
            ftype = f.get("type")
            if ftype == "result":
                continue
            key = str(f.get("key", "")).strip()
            if not key:
                continue
            label = str(f.get("label", key))
            default = f.get("default", "")
            rows.append(f"<label for='{esc(key)}'>{esc(label)}</label>")

            if ftype in ("number",):
                rows.append(
                    f"<input type='number' name='{esc(key)}' value='{esc(default)}' "
                    f"step='{esc(f.get('step', 1))}' min='{esc(f.get('min',''))}' max='{esc(f.get('max',''))}'>"
                )
            elif ftype == "text":
                rows.append(f"<input type='text' name='{esc(key)}' value='{esc(default)}'>")
            elif ftype == "slider":
                rows.append(
                    f"<input type='range' name='{esc(key)}' value='{esc(default)}' "
                    f"step='{esc(f.get('step', 1))}' min='{esc(f.get('min',0))}' max='{esc(f.get('max',100))}' "
                    f"oninput='document.getElementById(\"{esc(key)}_mirror\").value=this.value'>"
                )
                rows.append(
                    f"<input id='{esc(key)}_mirror' type='number' value='{esc(default)}' "
                    f"oninput='this.form[\"{esc(key)}\"].value=this.value'>"
                )
            elif ftype == "select":
                rows.append(f"<select name='{esc(key)}'>")
                opts = f.get("options", [])
                if not isinstance(opts, list):
                    opts = []
                for opt in opts:
                    if isinstance(opt, dict):
                        oval = str(opt.get("value", ""))
                        olab = str(opt.get("label", oval))
                    else:
                        oval = str(opt)
                        olab = oval
                    selected = " selected" if str(default) == oval else ""
                    rows.append(f"<option value='{esc(oval)}'{selected}>{esc(olab)}</option>")
                rows.append("</select>")
            elif ftype == "checkbox":
                checked = " checked" if bool(default) else ""
                rows.append(f"<input type='checkbox' name='{esc(key)}' value='1'{checked}>")
            else:
                rows.append(f"<input type='text' name='{esc(key)}' value='{esc(default)}'>")

        rows.append("<label for='email'>Email</label>")
        rows.append("<input type='email' name='email' placeholder='you@example.com'>")

        rows.append("<button type='submit'>Compute</button>")
        rows.append("</form>")

        self._send_html(HTTPStatus.OK, render_page(title, "\n".join(rows)))

    def _handle_submit(self, app: App, calc_id: str) -> None:
        form = load_form_body(self)
        try:
            calc = app.storage.load_calculator(calc_id)
        except FileNotFoundError:
            return self._send_text(HTTPStatus.NOT_FOUND, "calculator not found")

        fields = calc.get("fields", [])
        if not isinstance(fields, list):
            fields = []

        email = form.get("email", "").strip()
        inputs: dict[str, Any] = {}
        for f in fields:
            if not isinstance(f, dict):
                continue
            ftype = f.get("type")
            if ftype == "result":
                continue
            key = str(f.get("key", "")).strip()
            if not key:
                continue
            raw = form.get(key, "")
            if ftype in ("number", "slider"):
                try:
                    inputs[key] = float(raw) if raw != "" else float(f.get("default", 0) or 0)
                except ValueError:
                    return self._send_error_page(calc, f"Invalid number for {key}")
            elif ftype == "checkbox":
                inputs[key] = raw == "1" or raw.lower() == "on"
            else:
                inputs[key] = raw

        results: dict[str, Any] = {}
        errors: list[str] = []
        for f in fields:
            if not isinstance(f, dict) or f.get("type") != "result":
                continue
            key = str(f.get("key", "result"))
            formula = str(f.get("formula", "")).strip()
            if not formula:
                continue
            try:
                compiled = compile_formula(formula)
                results[key] = eval_formula(compiled, {**inputs, **results})
            except FormulaError as e:
                errors.append(f"{key}: {e}")

        if errors:
            return self._send_error_page(calc, "Formula error(s):<br>" + "<br>".join(esc(e) for e in errors))

        require_email = bool(calc.get("require_email_for_full_result"))
        payment = calc.get("payment") or {}
        payment_enabled = bool(payment.get("enabled"))
        payment_mode = str(payment.get("mode", "optional"))

        can_show_full = True
        if require_email and not email:
            can_show_full = False

        # If payment is required, we always gate full results until success callback.
        if payment_enabled and payment_mode == "required":
            can_show_full = False

        submission_id = secrets.token_urlsafe(10)
        submission = {
            "submission_id": submission_id,
            "calculator_id": calc_id,
            "timestamp": now_iso(),
            "email": email,
            "inputs": inputs,
            "results": results,
            # Append-only store: we do not mutate paid flag after checkout; use signed unlock token instead.
            "paid": False,
        }

        app.storage.append_submission(calc_id, submission)

        webhook_ok, webhook_msg = post_webhook(str(calc.get("webhook_url", "")), submission)

        # Compose result view links.
        # - Base link: shows results (or locked screen)
        # - Unlock link: can be generated after payment success and shared back to user
        result_link = f"http://{app.host}:{app.port}/r/{calc_id}?" + urlencode({"submission_id": submission_id})
        unlock_link = ""
        if payment_enabled and payment_mode == "required":
            signer = UnlockTokenSigner.from_env()
            token = signer.sign(calculator_id=calc_id, submission_id=submission_id, scope="pay")
            unlock_link = f"http://{app.host}:{app.port}/r/{calc_id}?" + urlencode(
                {"submission_id": submission_id, "token": token}
            )

        email_status = "email not provided"
        if email:
            try:
                body = [
                    f"Calculator: {calc.get('name', calc_id)} ({calc_id})",
                    f"Submitted at: {submission['timestamp']}",
                    "",
                    f"View results: {result_link}",
                    f"Unlock (after payment): {unlock_link or '-'}",
                    "",
                    "Inputs:",
                    json.dumps(inputs, ensure_ascii=False, indent=2),
                    "",
                    "Results:",
                    json.dumps(results, ensure_ascii=False, indent=2),
                ]
                email_status = send_result_email(
                    app.storage,
                    to_email=email,
                    subject=f"Your results: {calc.get('name', calc_id)}",
                    body_text="\n".join(body),
                    calc_id=calc_id,
                )
            except Exception as e:
                email_status = f"email send failed: {e}"

        # Decide next action for payment
        pay_html = ""
        if payment_enabled:
            amount = int(payment.get("amount_cents", 0) or 0)
            currency = str(payment.get("currency", "usd"))

            success_url = f"http://{app.host}:{app.port}/pay/stripe/success?" + urlencode(
                {"calculator_id": calc_id, "submission_id": submission_id}
            )
            cancel_url = f"http://{app.host}:{app.port}/pay/stripe/cancel?" + urlencode(
                {"calculator_id": calc_id, "submission_id": submission_id}
            )

            if stripe_enabled():
                ok, url_or_err = create_checkout_session(
                    amount_cents=amount,
                    currency=currency,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={"calculator_id": calc_id, "submission_id": submission_id},
                )
                if ok:
                    pay_html = f"<p><a href='{esc(url_or_err)}'>Pay with Stripe</a></p>"
                else:
                    pay_html = f"<p class='danger'>Stripe error: {esc(url_or_err)}</p>"
            else:
                pay_html = (
                    "<p class='muted'>Stripe not configured. DEV mode payment simulation is available.</p>"
                    + f"<p><a href='/pay/dev?{urlencode({'calculator_id': calc_id, 'submission_id': submission_id})}'>Simulate payment</a></p>"
                )

        rows = [
            f"<h1>{esc(calc.get('name', calc_id))}</h1>",
            f"<p><a href='/c/{esc(calc_id)}'>Back</a> | <a href='/edit/{esc(calc_id)}'>Admin</a></p>",
            "<div class='card'>",
            "<h2>Submission</h2>",
            f"<p><b>ID:</b> {esc(submission_id)}</p>",
            f"<p><b>Email:</b> {esc(email or '-')}</p>",
            f"<p><b>Email status:</b> {esc(email_status)}</p>",
            f"<p><b>Webhook:</b> {'<span class=ok>ok</span>' if webhook_ok else '<span class=danger>failed</span>'} {esc(webhook_msg)}</p>",
            f"<p><b>Results link:</b> <a href='{esc(result_link)}'>{esc(result_link)}</a></p>",
            (f"<p><b>Unlock link:</b> <a href='{esc(unlock_link)}'>{esc(unlock_link)}</a></p>" if unlock_link else ""),
            "</div>",
        ]

        if can_show_full:
            rows.append("<div class='card'><h2>Results</h2>")
            rows.append("<pre>" + esc(json.dumps(results, ensure_ascii=False, indent=2)) + "</pre>")
            rows.append("</div>")
        else:
            rows.append("<div class='card'>")
            rows.append("<h2>Results locked</h2>")
            if require_email and not email:
                rows.append("<p class='danger'>Email is required to unlock full results.</p>")
            if payment_enabled and payment_mode == "required":
                rows.append("<p class='danger'>Payment is required to unlock full results.</p>")
            rows.append(pay_html)
            rows.append("</div>")

        self._send_html(HTTPStatus.OK, render_page("Results", "\n".join(rows)))

    def _handle_results(self, app: App, calc_id: str, qs: dict[str, list[str]]) -> None:
        sub_id = (qs.get("submission_id") or [""])[0].strip()
        token = (qs.get("token") or [""])[0].strip()

        try:
            calc = app.storage.load_calculator(calc_id)
        except FileNotFoundError:
            return self._send_text(HTTPStatus.NOT_FOUND, "calculator not found")

        sub = app.storage.find_submission(calc_id, sub_id)
        if not sub:
            return self._send_text(HTTPStatus.NOT_FOUND, "submission not found")

        require_email = bool(calc.get("require_email_for_full_result"))
        payment = calc.get("payment") or {}
        payment_enabled = bool(payment.get("enabled"))
        payment_mode = str(payment.get("mode", "optional"))

        signer = UnlockTokenSigner.from_env()
        paid_ok = signer.verify(token=token, calculator_id=calc_id, submission_id=sub_id, scope="pay")

        can_show_full = True
        if require_email and not sub.get("email"):
            can_show_full = False
        if payment_enabled and payment_mode == "required" and not paid_ok:
            can_show_full = False

        pay_hint = ""
        if payment_enabled and payment_mode == "required" and not paid_ok:
            pay_hint = "<p class='danger'>Payment required. Please complete checkout to unlock.</p>"

        rows = [
            f"<h1>{esc(calc.get('name', calc_id))}</h1>",
            f"<p><a href='/c/{esc(calc_id)}'>Back to calculator</a> | <a href='/edit/{esc(calc_id)}'>Admin</a></p>",
            "<div class='card'>",
            "<h2>Submission</h2>",
            f"<p><b>ID:</b> {esc(sub_id)}</p>",
            f"<p><b>Timestamp:</b> {esc(sub.get('timestamp','-'))}</p>",
            f"<p><b>Email:</b> {esc(sub.get('email','-') or '-')}</p>",
            "</div>",
        ]

        if can_show_full:
            rows.append("<div class='card'><h2>Results</h2>")
            rows.append("<pre>" + esc(json.dumps(sub.get("results", {}), ensure_ascii=False, indent=2)) + "</pre>")
            rows.append("</div>")
        else:
            rows.append("<div class='card'><h2>Results locked</h2>")
            rows.append(pay_hint)
            rows.append("</div>")

        self._send_html(HTTPStatus.OK, render_page("Results", "\n".join(rows)))

    def _handle_save(self, app: App, calc_id: str) -> None:
        form = load_form_body(self)
        raw = form.get("config", "")
        try:
            calc = json.loads(raw)
            if not isinstance(calc, dict):
                raise ValueError("config must be a JSON object")
            calc["id"] = calc_id
            calc["updated_at"] = now_iso()
            fields = calc.get("fields")
            if not isinstance(fields, list):
                raise ValueError("fields must be a list")
            app.storage.save_calculator(calc)
        except Exception as e:
            body = render_page(
                "Save error",
                f"<h1>Save error</h1><p class='danger'>{esc(e)}</p><p><a href='/edit/{esc(calc_id)}'>Back</a></p>",
            )
            self._send_html(HTTPStatus.BAD_REQUEST, body)
            return

        self._redirect(f"/edit/{calc_id}")

    def _handle_webhook_receiver(self, app: App) -> None:
        events: list[dict[str, Any]] = getattr(self.server, "webhook_events", [])  # type: ignore[attr-defined]
        rows = [
            "<h1>Webhook receiver (local)</h1>",
            "<p class='muted'>POST JSON to this endpoint to capture demo webhooks.</p>",
            "<p><a href='/'>Home</a></p>",
        ]
        if not events:
            rows.append("<p class='muted'>No events yet.</p>")
        else:
            rows.append("<pre>" + esc(json.dumps(events[-20:], ensure_ascii=False, indent=2)) + "</pre>")
        self._send_html(HTTPStatus.OK, render_page("Webhook receiver", "\n".join(rows)))

    def _handle_pay_dev(self, app: App, qs: dict[str, list[str]]) -> None:
        calc_id = (qs.get("calculator_id") or [""])[0]
        sub_id = (qs.get("submission_id") or [""])[0]
        signer = UnlockTokenSigner.from_env()
        token = signer.sign(calculator_id=calc_id, submission_id=sub_id, scope="pay")
        redirect_url = f"/r/{calc_id}?" + urlencode({"submission_id": sub_id, "token": token})
        return self._redirect(redirect_url)

    def _handle_pay_stripe_success(self, app: App, qs: dict[str, list[str]]) -> None:
        calc_id = (qs.get("calculator_id") or [""])[0]
        sub_id = (qs.get("submission_id") or [""])[0]
        signer = UnlockTokenSigner.from_env()
        token = signer.sign(calculator_id=calc_id, submission_id=sub_id, scope="pay")
        redirect_url = f"/r/{calc_id}?" + urlencode({"submission_id": sub_id, "token": token})
        return self._redirect(redirect_url)

    def _handle_pay_stripe_cancel(self, app: App, qs: dict[str, list[str]]) -> None:
        calc_id = (qs.get("calculator_id") or [""])[0]
        rows = [
            "<h1>Stripe cancelled</h1>",
            "<p class='danger'>Payment cancelled.</p>",
            f"<p><a href='/c/{esc(calc_id)}'>Back to calculator</a></p>",
        ]
        self._send_html(HTTPStatus.OK, render_page("Stripe cancel", "\n".join(rows)))

    # --------------------------- helpers ---------------------------

    def _send_html(self, status: HTTPStatus, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: HTTPStatus, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def _send_error_page(self, calc: dict[str, Any], message_html: str) -> None:
        rows = [
            f"<h1>{esc(calc.get('name','Calculator'))}</h1>",
            f"<p class='danger'>{message_html}</p>",
            "<p><a href='javascript:history.back()'>Back</a></p>",
        ]
        self._send_html(HTTPStatus.BAD_REQUEST, render_page("Error", "\n".join(rows)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()

    app_root = Path(__file__).resolve().parent
    storage = Storage(root=app_root / "data")
    storage.ensure()

    for name in ("pricing", "roi", "volume_discount"):
        path = storage.templates_dir / f"{name}.json"
        if not path.exists():
            pass

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.app = App(storage=storage, host=args.host, port=args.port)  # type: ignore[attr-defined]
    httpd.webhook_events = []  # type: ignore[attr-defined]

    print(f"Calculator Builder MVP running on http://{args.host}:{args.port}")
    print("Admin: /")
    print("Webhook receiver: /webhook-receiver")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
