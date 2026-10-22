# Flask API layer for Udatracker. The views only parse HTTP input and turn
# results or exceptions into HTTP responses; the business rules live in
# OrderTracker (backend/order_tracker.py).

from flask import Flask, request, jsonify, send_from_directory
from backend.order_tracker import OrderNotFoundError, OrderTracker
from backend.in_memory_storage import InMemoryStorage

app = Flask(__name__, static_folder='../frontend')
in_memory_storage = InMemoryStorage()
order_tracker = OrderTracker(in_memory_storage)


@app.errorhandler(OrderNotFoundError)
def handle_order_not_found(error):
    return jsonify(error=str(error)), 404


@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/api/orders', methods=['POST'])
def add_order_api():
    data = request.get_json()
    order = order_tracker.add_order(**data)
    return jsonify(order), 201


@app.route('/api/orders/<string:order_id>', methods=['GET'])
def get_order_api(order_id):
    order = order_tracker.get_order_by_id(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    return jsonify(order), 200


@app.route('/api/orders/<string:order_id>/status', methods=['PUT'])
def update_order_status_api(order_id):
    data = request.get_json()
    order = order_tracker.update_order_status(order_id, data["new_status"])
    return jsonify(order), 200


@app.route('/api/orders', methods=['GET'])
def list_orders_api():
    orders = order_tracker.list_orders(status=request.args.get("status"))
    return jsonify(orders), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
