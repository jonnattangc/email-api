# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the service

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (must be executed from app/ directory since imports are relative)
cd app && python http-server.py 8070

# Build and run via Docker
docker build -t emailservice:dev .
docker compose up
```

The server listens on port `8070` and exposes routes under `/email`.

## Environment variables

Required env vars (typically in `../envs/email_api.env` for Docker):

| Variable | Purpose |
|---|---|
| `HOST_BD`, `USER_BD`, `PASS_BD`, `PORT_BD`, `SCHEMA_BD` | MySQL connection |
| `API_KEY` | Inbound request authentication (`x-api-key` header) |
| `AES_KEY` | AES-CBC encryption key (32 bytes used) |
| `NOTIFICATION_URL` | External API endpoint for WhatsApp notifications |
| `LLM_API_URL`, `LLM_AUTH` | LLM service for parsing email body into structured JSON |

## Architecture

### Request flow

```
cron/verify_news.sh  →  POST /email/news  →  UtilEmail.request_process()
                                               │
                                               ├─ Auth: x-api-key header validated
                                               ├─ Optional AES-CBC decryption of body
                                               └─ Per client in request body:
                                                    Thread → message_process()
                                                               │
                                                               ├─ GMailProcessor.read_email()  (IMAP)
                                                               └─ Processor.evaluate_and_save()
                                                                    │
                                                                    ├─ process_mail() → LLM API → parse JSON
                                                                    ├─ AModel.save_transaction() → MySQL Trx table
                                                                    └─ AModel.send_waza_message() → NOTIFICATION_URL
```

### Key modules

- **`http-server.py`** — Flask entry point. All routes under `/email` delegate to `UtilEmail`.
- **`util_email.py`** — Handles auth, request parsing, MySQL client lookup, and thread dispatch. The `clients` table holds per-client IMAP credentials, WhatsApp config, and a `meta_filter` JSON field (`folder`, `ago` days lookback, `filter` IMAP filter string).
- **`gmail_processor.py`** — Connects to Gmail via IMAP SSL, selects the configured folder, searches by date and filter, returns raw email dicts.
- **`amodel.py`** — Abstract base class (`AModel`) for processors. Implements `evaluate_and_save()`, `save_transaction()`, `send_waza_message()`, and `get_tutor_data()`. Subclasses must implement `process_mail()` and `get_data_waza()`.
- **`trx_cole.py`** (`TrxTesoreria`) — Processes Tenpo bank transfer emails for a school treasury. Filters by sender `no-reply@tenpo.cl` and subject `comprobante de transferencia`. Uses LLM to extract fields, then looks up tutor/student info via `get_tutor_data()`.
- **`trx_logia.py`** (`TrxBcp`) — Processes BCP bank transfer emails for a lodge. Similar LLM extraction flow without tutor lookup.
- **`cipher.py`** — AES-CBC encrypt/decrypt using `pycryptodome`. IV is hardcoded; key comes from `AES_KEY` env var.

### Adding a new client processor

1. Create a new class in `app/` extending `AModel`.
2. Implement `process_mail(message)` to filter and extract data from emails, then call `self.save_transaction()`.
3. Implement `get_data_waza(data_msg)` to format the WhatsApp notification payload.
4. Add a branch in `util_email.py:message_process()` matching the client's `company_name` from the DB.
5. Insert the client record in the `clients` MySQL table with appropriate `meta_filter` JSON.

### Deduplication

Each email is deduplicated by `Message-ID` + MD5 hash of the raw email body, stored in the `Trx` table. `get_transaction()` checks before saving.

### Cron trigger

`cron/verify_news.sh` runs a `curl` POST to the `/email/news` endpoint with a list of client API keys. This is the only trigger — there is no polling loop inside the service itself.
