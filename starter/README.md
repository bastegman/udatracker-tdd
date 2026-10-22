# Udatracker Starter Code

This directory contains the Udatracker order tracker: a Flask backend built test-first (red → green → refactor) and the small frontend that ships with the starter. The git history shows the cycles: each `test: … (red)` commit is followed by the `feat: … (green)` commit that makes it pass, plus the occasional `refactor:`.

```
.
├── backend
│   ├── __init__.py
│   ├── app.py                       # API layer: parses requests, maps errors to HTTP
│   ├── in_memory_storage.py         # storage: a dict that lives in memory
│   ├── order_tracker.py             # business logic and validation
│   ├── requirements.txt
│   └── tests
│       ├── __init__.py
│       ├── test_api.py              # provided by the course, unchanged
│       ├── test_api_extra.py        # extra API tests (errors, filters, DELETE)
│       ├── test_in_memory_storage.py
│       └── test_order_tracker.py    # unit tests with a mocked storage
├── frontend
│   ├── css
│   │   └── style.css
│   ├── index.html
│   └── js
│       └── script.js
├── .dockerignore
├── .flake8
├── Dockerfile
├── pytest.ini
└── README.md
```

## Setup, run and test

From this `starter/` directory:

```bash
python -m venv venv
source venv/bin/activate              # Windows: .\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

python -m backend.app                 # then open http://127.0.0.1:5000/
pytest                                # all tests; also works from the repository root
```

- Debug mode is on by default, as in the starter. `FLASK_DEBUG=0 python -m backend.app` turns it off.
- `PORT` changes the port. On macOS, AirPlay Receiver often holds port 5000, so use `PORT=5001 python -m backend.app`.
- Style check (PEP 8): `uvx flake8`, or `pip install flake8 && flake8`. The `.flake8` file excludes only the provided `test_api.py`, which must stay unmodified.

## API reference

All request and response bodies are JSON. An order looks like this:

```json
{"order_id": "ORD001", "item_name": "Laptop", "quantity": 1, "customer_id": "CUST001", "status": "pending"}
```

| Method | Path | Input | Success | Errors |
|--------|------|-------|---------|--------|
| POST | `/api/orders` | body: `order_id`, `item_name`, `quantity`, `customer_id`, optional `status` | `201` + order, `Location` header | `400`, `409` |
| GET | `/api/orders` | optional query: `status`, `customer_id` (combinable) | `200` + list of orders | `400` |
| GET | `/api/orders/<order_id>` | | `200` + order | `400`, `404` |
| PUT | `/api/orders/<order_id>/status` | body: `{"new_status": "..."}` | `200` + updated order | `400`, `404` |
| PUT | `/api/orders/<order_id>` | same as above (alias) | `200` + updated order | `400`, `404` |
| DELETE | `/api/orders/<order_id>` | | `204 No Content` | `400`, `404` |

Validation rules:

- `order_id`, `item_name` and `customer_id` must be non-empty strings. Surrounding whitespace is stripped. `order_id` cannot contain `/` or be `.` or `..`, because it is used as a URL path segment.
- `quantity` must be an integer of at least 1. `true`, `1.5` and `"2"` are rejected.
- `status` and `new_status` must be `pending`, `processing` or `shipped`. A new order defaults to `pending`.
- Unknown body fields are ignored.

Every error is a JSON object with a single message:

| Status | When |
|--------|------|
| `400 Bad Request` | invalid or missing fields, a body that is not a JSON object, an invalid filter value |
| `404 Not Found` | unknown order ID, or unknown `/api/...` route |
| `405 Method Not Allowed` | unsupported method on an `/api/...` route |
| `409 Conflict` | an order with that ID already exists |
| `500 Internal Server Error` | unexpected failure; no internal details are returned (with debug mode on, Flask shows its debugger instead) |

```json
{"error":"Order with ID 'ORD001' already exists."}
```

Sample `curl` commands (server running on port 5000):

```bash
# Create an order (status defaults to "pending")
curl -i -X POST http://127.0.0.1:5000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"order_id": "ORD001", "item_name": "Laptop", "quantity": 1, "customer_id": "CUST001"}'

# Fetch it
curl http://127.0.0.1:5000/api/orders/ORD001

# Update its status (both URLs do the same)
curl -X PUT http://127.0.0.1:5000/api/orders/ORD001/status \
  -H "Content-Type: application/json" -d '{"new_status": "shipped"}'
curl -X PUT http://127.0.0.1:5000/api/orders/ORD001 \
  -H "Content-Type: application/json" -d '{"new_status": "processing"}'

# List all orders, or filter by status and/or customer
curl http://127.0.0.1:5000/api/orders
curl "http://127.0.0.1:5000/api/orders?status=processing"
curl "http://127.0.0.1:5000/api/orders?customer_id=CUST001&status=processing"

# Delete it
curl -i -X DELETE http://127.0.0.1:5000/api/orders/ORD001
```

## Docker (local use)

```bash
docker build -t udatracker .
docker run --rm -p 5000:5000 udatracker      # on macOS: -p 5001:5000 if port 5000 is taken
```

Then open http://127.0.0.1:5000/. The image is based on `python:3.12-slim`, runs as an unprivileged user with `FLASK_DEBUG=0` and serves both the API and the frontend. There is a single service, so there is no `docker-compose.yml`.

## Design notes

- Layers: `order_tracker.py` holds the business rules and validates the order data. `app.py` only checks what is specific to HTTP (a JSON object body, the required fields, an ID that fits in a URL) and translates results and exceptions. `in_memory_storage.py` just stores dicts. The valid statuses are defined once, in `VALID_STATUSES`.
- Errors are handled centrally with Flask error handlers: `ValueError` → 400, `DuplicateOrderError` → 409, `OrderNotFoundError` → 404, and Flask's own HTTP errors under `/api/` → JSON with their status.
- Filtering by `status` and `customer_id` is done in `OrderTracker.list_orders`, so the route passes both query parameters straight through.
- The frontend now renders order fields with `textContent` instead of `innerHTML` (an order named `<img src=x onerror=...>` used to run script) and URL-encodes IDs.

## Reflection

- **Design trade-off:** I separated commands from queries. `get_order_by_id` returns `None` for an unknown ID, while `update_order_status` and `delete_order` raise `OrderNotFoundError`. Exceptions are mapped to status codes in one place, which keeps the views thin. `DuplicateOrderError` subclasses `ValueError` so the course test still passes while the API returns 409.
- **Testing insight:** when I made `list_orders_by_status` delegate to the new `list_orders`, `test_list_orders_by_status_rejects_invalid_status[None]` failed. `list_orders` treats `None` as "no filter", so `None` would have returned every order. So I kept the status check before delegating.
- **Next step:** the duplicate check is check-then-save, so two simultaneous POSTs on the threaded dev server could both succeed. An atomic `save_if_absent` in storage, or a database unique constraint, would close that race.
