# Calculator Builder (MVP)

A minimal **config-driven** web calculator builder (no drag) implemented using only the **Python standard library**.

This app is a runnable prototype to validate the market shape described in `TASK-OPP-8D564AD6F5`:
- calculator = lead gen + formulas + embed + webhook + (optional) payment unlock

## Quickstart

```bash
cd /home/ubuntu/code/openclaw-ai-coding-team
python3 -m apps.calculator_builder.server --host 127.0.0.1 --port 8787
```

Open:
- Admin home: http://127.0.0.1:8787/
- Example hosted calculator: http://127.0.0.1:8787/c/<calculator_id>
- Minimal embed mode: http://127.0.0.1:8787/c/<calculator_id>?embed=1

## Data layout

All data is stored under `apps/calculator_builder/data/`:
- Calculator configs: `data/calculators/<id>.json`
- Templates: `data/templates/<template>.json`
- Submissions: `data/submissions/<calculator_id>.jsonl`
- Email outbox (when SMTP not configured): `data/outbox/<timestamp>_<calculator_id>.eml`

## 10-min demo (end-to-end)

1) Start server (see Quickstart).
2) Go to Admin home `/`.
3) Create a calculator from template (Pricing / ROI / Volume Discount).
4) Open the hosted calculator URL `/c/<id>`.
5) Fill inputs and click **Compute**.
6) Enter an email and submit.
   - If SMTP env vars are not set, an `.eml` file is written to `data/outbox/`.
7) Verify webhook:
   - (Option A) Use the built-in receiver: set webhook_url in config to `http://127.0.0.1:8787/webhook-receiver`.
   - Submit again and check the receiver page at `/webhook-receiver`.
8) Payment unlock:
   - If `STRIPE_SECRET_KEY` not set: click the DEV "Simulate payment" flow.

## Email backend

If these env vars are set, the app will send mail via SMTP:

- `SMTP_HOST` (required)
- `SMTP_PORT` (optional, default 587)
- `SMTP_USER` (optional)
- `SMTP_PASS` (optional)
- `SMTP_FROM` (optional, default `no-reply@example.com`)

If not configured, the app writes a `.eml` file to the outbox.

## Stripe payment unlock

This prototype supports:
- Real mode: `STRIPE_SECRET_KEY` set (uses Stripe Checkout Sessions via HTTPS calls)
- DEV mode fallback: no key, simulates payment locally

Note: this is MVP wiring for demo; production requires full webhook verification, idempotency, and secure storage.

## Formula engine

Formulas are parsed by `ast` and evaluated by a strict whitelist evaluator:
- Numeric ops: `+ - * / **` (and unary +/-)
- Comparisons: `== != < <= > >=`
- Boolean: `and / or / not`
- Functions: `IF(cond, a, b)`, `min(a,b,...)`, `max(a,b,...)`

No `eval`, no attribute access, no subscripts, no comprehensions.

Unknown identifiers/functions return readable error messages.

## Local checks

```bash
python3 -m py_compile apps/calculator_builder/*.py apps/calculator_builder/**/*.py
```
