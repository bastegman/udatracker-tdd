# Flask API layer for Udatracker. The views only parse HTTP input and turn
# results or exceptions into HTTP responses; the business rules live in
# OrderTracker (backend/order_tracker.py).

from flask import Flask, request, jsonify, send_from_directory, url_for
from werkzeug.exceptions import HTTPException

from backend.order_tracker import (DuplicateOrderError, OrderNotFoundError,
                                   OrderTracker)
from backend.in_memory_storage import InMemoryStorage

app = Flask(__name__, static_folder='../frontend')
in_memory_storage = InMemoryStorage()
order_tracker = OrderTracker(in_memory_storage)

# Body fields POST /api/orders must contain; "status" is optional.
REQUIRED_ORDER_FIELDS = ("order_id", "item_name", "quantity", "customer_id")


# --- Error handlers: every API error is a JSON object {"error": "..."} ---

@app.errorhandler(ValueError)
def handle_validation_error(error):
    return jsonify(error=str(error)), 400


@app.errorhandler(DuplicateOrderError)
def handle_duplicate_order(error):
    # More specific than ValueError, so Flask picks this handler first.
    return jsonify(error=str(error)), 409


@app.errorhandler(OrderNotFoundError)
def handle_order_not_found(error):
    return jsonify(error=str(error)), 404


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Render errors raised by Flask itself (unknown route, wrong method,
    unexpected 500) as JSON under /api/; other pages keep Flask's HTML."""
    if request.path != "/api" and not request.path.startswith("/api/"):
        return error
    response = error.get_response()  # keeps the status and e.g. Allow
    response.data = app.json.dumps({"error": error.description})
    response.content_type = "application/json"
    return response


def _json_object() -> dict:
    """Return the request body, which must be a JSON object."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


def _require_fields(data: dict, fields) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(
            f"Missing required field(s): {', '.join(missing)}.")


# --- Frontend ---

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


# --- API ---

@app.route('/api/orders', methods=['POST'])
def add_order_api():
    data = _json_object()
    _require_fields(data, REQUIRED_ORDER_FIELDS)
    order_id = data["order_id"]
    if isinstance(order_id, str) and "/" in order_id:
        # The ID becomes one URL path segment, so '/' would make the order
        # unreachable through GET/PUT /api/orders/<order_id>.
        raise ValueError("'order_id' must not contain '/'.")

    fields = {field: data[field] for field in REQUIRED_ORDER_FIELDS}
    if "status" in data:  # otherwise OrderTracker applies its default
        fields["status"] = data["status"]
    order = order_tracker.add_order(**fields)

    location = url_for("get_order_api", order_id=order["order_id"])
    return jsonify(order), 201, {"Location": location}


@app.route('/api/orders/<string:order_id>', methods=['GET'])
def get_order_api(order_id):
    order = order_tracker.get_order_by_id(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    return jsonify(order), 200


# The starter (and test_api.py) use PUT .../<order_id>/status, while the
# project rubric lists PUT /api/orders/<order_id>. Both URLs are served by
# this one view, with the same body: {"new_status": "..."}.
@app.route('/api/orders/<string:order_id>', methods=['PUT'])
@app.route('/api/orders/<string:order_id>/status', methods=['PUT'])
def update_order_status_api(order_id):
    data = _json_object()
    _require_fields(data, ("new_status",))
    order = order_tracker.update_order_status(order_id, data["new_status"])
    return jsonify(order), 200


@app.route('/api/orders/<string:order_id>', methods=['DELETE'])
def delete_order_api(order_id):
    order_tracker.delete_order(order_id)
    return "", 204


@app.route('/api/orders', methods=['GET'])
def list_orders_api():
    # Both query parameters are optional; OrderTracker combines them.
    orders = order_tracker.list_orders(
        status=request.args.get("status"),
        customer_id=request.args.get("customer_id"),
    )
    return jsonify(orders), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
