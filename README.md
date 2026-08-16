# Payment Orchestration & Transaction Routing System

## Overview

This is a simulation of a payment orchestration layer - the kind of system
that sits between a merchant's checkout page and multiple payment service
providers (PSPs), deciding which PSP should handle each transaction, retrying
on failure, and making sure the same payment request never gets processed
twice.

**No real payment gateway is involved anywhere in this project.** All three
PSPs (Alpha, Beta, Gamma) are simulated using configurable success rates and
latency values. This is a portfolio/learning project, not a production
payment system.

## Why I Built This

Companies like Razorpay, Juspay, and Stripe run orchestration layers that
route a single payment across multiple downstream providers to maximize
success rate and minimize latency, while making sure retries and network
issues never cause a customer to be charged twice. I wanted to build a
simplified, understandable version of that idea - one I can fully explain,
not something copy-pasted from a tutorial.

## Features

- **Payment API** - create and look up payments over REST
- **Simulated PSP routing** - picks the best PSP using a simple, explainable
  scoring formula (not ML)
- **Retry logic** - automatically retries with a different PSP on failure
  (up to a configurable limit)
- **Idempotency** - duplicate requests with the same idempotency key never
  create a second transaction
- **Transaction state machine** - CREATED → PROCESSING → SUCCESS/FAILED
  (with RETRYING in between when needed)
- **Dashboard** - live summary stats, PSP performance, transaction history,
  and a demo payment form
- **Demo controls** - toggle a PSP active/inactive or change its success
  rate directly from the dashboard, to demonstrate routing/retry behaviour
- **Analytics endpoints** - success rate, average latency, per-PSP
  performance, computed with SQL, not in the frontend
- **Tests** - pytest tests covering payment creation, idempotency, routing,
  and retries

## Architecture

```
Client (browser)
     |
     v
FastAPI app (main.py)
     |
     v
Payment API (routes/payments.py)
     |
     v
Payment Orchestrator (services/payment_service.py)
     |
     +--> Idempotency check (transactions table)
     |
     +--> PSP Routing (services/routing_service.py)
     |         |
     |         v
     |    Selected PSP
     |         |
     |         v
     +--> Simulated PSP call (services/psp_service.py)
     |         |
     |    success? --- no --> retry with next-best PSP (up to MAX_RETRIES)
     |         |
     |        yes
     |         |
     v         v
Transaction saved to SQLite (SQLAlchemy models)
     |
     v
Dashboard / Analytics (routes/analytics.py)
```

## Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **Database:** SQLite + SQLAlchemy ORM
- **Frontend:** plain HTML/CSS/JavaScript (no framework, no build step)
- **Testing:** pytest
- **Deployment:** Render (or any platform that can run a standard `uvicorn`
  command)

## Database Schema

**`transactions`**

| Column | Notes |
|---|---|
| `id` | internal primary key |
| `transaction_id` | public-facing ID, e.g. `TXN1A2B3C4D5E` |
| `order_id`, `customer_id` | from the merchant's request |
| `amount`, `currency`, `payment_method` | payment details |
| `idempotency_key` | **unique** - this is what prevents duplicate payments |
| `status` | CREATED / PROCESSING / SUCCESS / FAILED / RETRYING |
| `selected_psp` | the PSP that finally handled the payment |
| `attempted_psps` | comma-separated list of every PSP tried |
| `retry_count` | how many retries happened |
| `processing_time_ms` | total simulated latency across all attempts |
| `created_at`, `updated_at` | timestamps |

**`psps`**

| Column | Notes |
|---|---|
| `id` | internal primary key |
| `name` | e.g. "PSP Alpha" |
| `success_rate` | 0-1, used to simulate success/failure |
| `avg_latency_ms` | used to simulate processing delay |
| `is_active` | inactive PSPs are never selected by the router |

The two tables are related only loosely (`selected_psp` stores the PSP name
rather than a foreign key) - this was a deliberate simplification since a
transaction can touch multiple PSPs across retries, and the string is enough
for a project this size.

## Routing Logic

The router doesn't pick a PSP randomly, and it doesn't use machine learning.
It calculates a simple score for every **active** PSP:

```
score = (success_rate * 100) - (avg_latency_ms * LATENCY_WEIGHT)
```

`LATENCY_WEIGHT` (0.05 by default) controls how much latency matters
relative to success rate. The PSP with the highest score is selected first.

Example, using the default seed values:

| PSP | Success Rate | Latency | Score |
|---|---|---|---|
| Alpha | 92% | 450ms | 92 - 22.5 = **69.5** |
| Beta | 86% | 250ms | 86 - 12.5 = **73.5** |
| Gamma | 95% | 600ms | 95 - 30.0 = **65.0** |

In this case Beta wins, because its lower latency outweighs Alpha and
Gamma's slightly higher success rates. Changing `LATENCY_WEIGHT` changes how
aggressively the router favours speed over reliability.

## Idempotency

A client can accidentally send the same payment request twice - a mobile
app retrying after a timeout, a user double-clicking "Pay", etc. To handle
this safely:

1. Every payment request carries an `idempotency_key`.
2. `idempotency_key` has a **unique constraint** at the database level.
3. Before creating a transaction, the orchestrator checks if a transaction
   with that key already exists. If it does, the existing transaction is
   returned immediately - no new processing happens.
4. As a safety net for race conditions (two identical requests arriving at
   almost the same time), the API also catches the `IntegrityError` that
   the unique constraint would raise, and falls back to fetching the
   existing row instead of crashing.

This is implemented in `app/services/payment_service.py::create_payment`
and `app/routes/payments.py::create_payment`.

## Retry Mechanism

If the selected PSP simulation fails:

1. The transaction status moves to `RETRYING`.
2. The router picks the next-best **active** PSP, excluding any PSP that
   already failed for this transaction.
3. This repeats up to `MAX_RETRIES` (default: 2) additional attempts.
4. If a retry succeeds, the transaction is marked `SUCCESS` with
   `selected_psp` set to whichever PSP finally worked.
5. If retries are exhausted, or no more active PSPs are available, the
   transaction is marked `FAILED`.

Every attempted PSP is recorded in `attempted_psps`, so the full retry path
is visible for any transaction.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/payments` | Create (or return existing, if duplicate key) a payment |
| GET | `/api/payments` | List transactions, optional `status`, `psp`, `transaction_id` filters |
| GET | `/api/payments/{transaction_id}` | Get one transaction |
| GET | `/api/psps` | List PSP configuration |
| PATCH | `/api/psps/{psp_name}` | Update a PSP's `success_rate` / `is_active` (used by the demo panel) |
| GET | `/api/analytics/summary` | Overall stats: totals, success rate, avg latency |
| GET | `/api/analytics/psps` | Per-PSP performance stats |
| GET | `/health` | Basic health check |

## Running Locally

```bash
git clone <your-repo-url>
cd payment-orchestrator

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Then open **http://localhost:8000** - the dashboard is served directly from
the FastAPI app.

## Testing

```bash
pytest -v
```

Tests cover payment creation, idempotency (duplicate key handling), PSP
routing/scoring, and retry behaviour on failure.


## Demo Scenarios

1. **Normal payment** - fill the form and submit. Should succeed on the
   first attempt with the default configuration.

2. **Retry in action** - the router's score is `success_rate*100 -
   latency_ms*0.05`, so just dropping a PSP's success rate to 0% usually
   also drops its score below the others, meaning it won't be picked
   first at all. To reliably force a fail-then-retry-succeed sequence,
   set up a clear "will fail first" vs "backup" pair using the demo panel:
   - Deactivate the third PSP so only two are in play.
   - PSP #1 ("fails first"): success rate `0`, latency low (e.g. `50`) -
     keeps its score just above zero so it's still picked first, and it
     will always fail the simulated call.
   - PSP #2 ("backup"): success rate `1`, latency high (e.g. `3000`) -
     pushes its score below PSP #1's, so it's only tried on retry, and it
     will always succeed.
   - Submit a payment - `attempted_psps` will show both PSPs and
     `retry_count` will be 1.

3. **Duplicate request** - submit a payment, then submit it again with the
   exact same idempotency key. The same transaction ID comes back both
   times.

4. **PSP deactivation** - toggle a PSP inactive in the demo panel. New
   payments will never route to it, and you can watch the router shift its
   choice.

Remember to reset the PSPs back to their default values (success rate,
latency, active) after the demo via the same panel.
