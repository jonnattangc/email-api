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

Each client in the request body spawns its own `threading.Thread`; threads are fire-and-forget (not joined before the HTTP response is returned).

### Key modules

- **`http-server.py`** — Flask entry point. All routes under `/email` delegate to `UtilEmail`. CORS is restricted to `dev.jonnattan.com` and `api.jonnattan.cl`.
- **`util_email.py`** — Handles auth, request parsing, MySQL client lookup, and thread dispatch. The `clients` table holds per-client IMAP credentials, WhatsApp config, and a `meta_filter` JSON field.
- **`gmail_processor.py`** — Connects **only to Gmail** via hardcoded `imap.gmail.com:993`. Reads `meta_filter` for folder, lookback days (`ago`), and IMAP search filter string.
- **`amodel.py`** — Abstract base class (`AModel`) for processors. Implements `evaluate_and_save()`, `save_transaction()`, `send_waza_message()`, and `get_tutor_data()`. Subclasses must implement `process_mail()` and `get_data_waza()`.
- **`trx_cole.py`** (`TrxTesoreria`) — Processes Tenpo bank transfer emails for a school treasury. Filters **within `process_mail()`** by sender `no-reply@tenpo.cl` and subject `comprobante de transferencia` before calling the LLM. Also calls `get_tutor_data()` to look up parent/student info by RUT.
- **`trx_logia.py`** (`TrxBcp`) — Processes BCP bank transfer emails for a lodge. Applies **no sender/subject filter** — all emails matching the IMAP filter are sent to the LLM.
- **`cipher.py`** — AES-CBC encrypt/decrypt using `pycryptodome`. IV is hardcoded; key comes from `AES_KEY` env var.

### `meta_filter` JSON structure (stored in `clients` table)

```json
{ "folder": "INBOX", "ago": 3, "filter": "ALL" }
```

`filter` is passed directly as an IMAP search criterion (e.g. `FROM "no-reply@tenpo.cl"`).

### LLM API contract

Processors POST to `LLM_API_URL` with `Authorization: LLM_AUTH`:

```json
{ "type": "clear", "data": { "prompt": "...", "assistantType": "..." } }
```

Expected response: `{ "result": "<raw JSON string, may have ```json fences>" }`. Both processors strip markdown fences before calling `json.loads()`.

### `save_transaction()` expected dict keys

The dict returned by `process_mail()` and passed to `save_transaction()` must include:

`origen_transferencia`, `rut_de_origen`, `banco_de_origen`, `numero_cuenta_de_origen`, `monto_transferencia`, `fecha` (dd-mm-yyyy), `hora` (HH:MM:SS), `codigo_transferencia`, `comment`, `msg_id`, `md5sum`

### Adding a new client processor

1. Create a new class in `app/` extending `AModel`.
2. Call `super().__init__(client=client)` — `AModel.__init__` uses `**kwargs`, so the keyword argument is required.
3. Implement `process_mail(message)` to filter and extract data from emails, then call `self.save_transaction()`.
4. Implement `get_data_waza(data_msg)` to format the WhatsApp notification payload.
5. Add a branch in `util_email.py:message_process()` matching the client's `company_name` from the DB.
6. Insert the client record in the `clients` MySQL table with appropriate `meta_filter` JSON.

### Deduplication

Each email is deduplicated by `Message-ID` + MD5 hash of the raw email body, stored in the `Trx` table. `get_transaction()` checks before saving.

### Cron trigger

`cron/verify_news.sh` runs a `curl` POST to the `/email/news` endpoint with a list of client API keys. This is the only trigger — there is no polling loop inside the service itself.
