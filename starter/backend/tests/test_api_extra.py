"""Extra integration tests for the API, on top of the provided test_api.py.

They cover the error contract ({"error": "..."} with 400, 404, 405, 409 and
500), the customer filter, DELETE, the PUT alias and the run options.
"""
import pytest

from backend.app import app, in_memory_storage, order_tracker, run_options

NEW_ORDER = {"order_id": "X001", "item_name": "Desk", "quantity": 2,
             "customer_id": "C1"}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    in_memory_storage.clear()
    with app.test_client() as test_client:
        yield test_client
    in_memory_storage.clear()


def post_order(client, **overrides):
    return client.post("/api/orders", json={**NEW_ORDER, **overrides})


def assert_json_error(response, status_code, fragment=""):
    """Every API error is a JSON object with a single 'error' message."""
    assert response.status_code == status_code
    assert response.is_json
    body = response.get_json()
    assert set(body) == {"error"}
    assert fragment in body["error"]


# --- POST /api/orders ---


def test_add_order_returns_new_order_and_its_location(client):
    response = post_order(client)

    assert response.status_code == 201
    assert response.get_json() == {**NEW_ORDER, "status": "pending"}
    assert response.headers["Location"].endswith("/api/orders/X001")


def test_add_order_ignores_unknown_fields(client):
    response = post_order(client, note="leave it at the door")

    assert response.status_code == 201
    assert "note" not in response.get_json()


def test_add_order_missing_fields_returns_400_naming_them(client):
    response = client.post("/api/orders", json={"order_id": "X001"})

    assert_json_error(response, 400, "item_name, quantity, customer_id")


@pytest.mark.parametrize("overrides, fragment", [
    pytest.param({"quantity": 0}, "quantity", id="zero quantity"),
    pytest.param({"quantity": "2"}, "quantity", id="string quantity"),
    pytest.param({"order_id": "  "}, "order_id", id="blank order_id"),
    pytest.param({"order_id": "A/B"}, "order_id", id="slash in order_id"),
    pytest.param({"status": "delivered"}, "status", id="unknown status"),
])
def test_add_order_invalid_values_return_400(client, overrides, fragment):
    assert_json_error(post_order(client, **overrides), 400, fragment)


def test_add_order_duplicate_id_returns_409(client):
    post_order(client)

    response = post_order(client, item_name="Chair")

    assert_json_error(response, 409, "Order with ID 'X001' already exists.")
    assert client.get("/api/orders/X001").get_json()["item_name"] == "Desk"


@pytest.mark.parametrize("request_kwargs", [
    pytest.param({"data": "X001", "content_type": "text/plain"},
                 id="text body"),
    pytest.param({"data": "{oops", "content_type": "application/json"},
                 id="malformed JSON"),
    pytest.param({"json": ["X001", "Desk"]}, id="JSON array"),
    pytest.param({}, id="no body"),
])
def test_add_order_body_that_is_not_a_json_object_returns_400(
        client, request_kwargs):
    response = client.post("/api/orders", **request_kwargs)

    assert_json_error(response, 400, "JSON object")


# --- GET and PUT errors ---


def test_get_unknown_order_returns_404_json(client):
    response = client.get("/api/orders/NOPE")

    assert_json_error(response, 404, "Order with ID 'NOPE' not found.")


def test_get_order_with_blank_id_returns_400(client):
    assert_json_error(client.get("/api/orders/%20"), 400, "order_id")


def test_update_unknown_order_returns_404(client):
    response = client.put("/api/orders/NOPE/status",
                          json={"new_status": "shipped"})

    assert_json_error(response, 404, "Order with ID 'NOPE' not found.")


def test_update_with_invalid_status_returns_400_and_keeps_order(client):
    post_order(client)

    response = client.put("/api/orders/X001/status",
                          json={"new_status": "lost"})

    assert_json_error(response, 400, "new_status")
    assert client.get("/api/orders/X001").get_json()["status"] == "pending"


def test_update_without_new_status_returns_400(client):
    post_order(client)

    response = client.put("/api/orders/X001/status",
                          json={"status": "shipped"})

    assert_json_error(response, 400, "new_status")


def test_update_with_non_json_body_returns_400(client):
    post_order(client)

    response = client.put("/api/orders/X001/status", data="shipped",
                          content_type="text/plain")

    assert_json_error(response, 400, "JSON object")


def test_list_orders_with_invalid_status_returns_400(client):
    assert_json_error(client.get("/api/orders?status=lost"), 400, "status")


# --- errors raised by Flask itself ---


def test_unknown_api_route_returns_404_json(client):
    assert_json_error(client.get("/api/unknown"), 404)


def test_unsupported_method_on_api_route_returns_405_json(client):
    response = client.patch("/api/orders")

    assert_json_error(response, 405)
    assert "POST" in response.headers["Allow"]


def test_unknown_page_outside_the_api_keeps_flask_html_404(client):
    response = client.get("/no-such-page.html")

    assert response.status_code == 404
    assert not response.is_json


def test_unexpected_error_returns_500_json_without_details(client,
                                                           monkeypatch):
    def fail(**filters):
        raise RuntimeError("storage exploded")

    monkeypatch.setattr(order_tracker, "list_orders", fail)
    # Testing mode re-raises unhandled errors; turn that off to see the 500.
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

    response = client.get("/api/orders")

    assert_json_error(response, 500)
    assert "exploded" not in response.get_json()["error"]


# --- GET /api/orders?customer_id=... ---


@pytest.fixture
def three_orders(client):
    post_order(client, order_id="A1", customer_id="C1")
    post_order(client, order_id="A2", customer_id="C2", status="shipped")
    post_order(client, order_id="A3", customer_id="C1", status="shipped")


def ids_in(response):
    assert response.status_code == 200
    return [order["order_id"] for order in response.get_json()]


def test_list_orders_filters_by_customer(client, three_orders):
    assert ids_in(client.get("/api/orders?customer_id=C1")) == ["A1", "A3"]
    assert ids_in(client.get("/api/orders?customer_id=C9")) == []


def test_list_orders_combines_customer_and_status(client, three_orders):
    response = client.get("/api/orders?customer_id=C1&status=shipped")

    assert ids_in(response) == ["A3"]


def test_list_orders_with_blank_customer_returns_400(client):
    assert_json_error(client.get("/api/orders?customer_id="), 400,
                      "customer_id")


# --- DELETE /api/orders/<order_id> ---


def test_delete_order_returns_204_and_removes_it(client):
    post_order(client)

    response = client.delete("/api/orders/X001")

    assert response.status_code == 204
    assert response.data == b""
    assert client.get("/api/orders/X001").status_code == 404
    assert client.get("/api/orders").get_json() == []


def test_delete_unknown_order_returns_404(client):
    response = client.delete("/api/orders/NOPE")

    assert_json_error(response, 404, "Order with ID 'NOPE' not found.")


def test_delete_twice_returns_404_the_second_time(client):
    post_order(client)
    client.delete("/api/orders/X001")

    assert_json_error(client.delete("/api/orders/X001"), 404)


# --- PUT: /api/orders/<id>/status (starter, test_api.py) and /api/orders/<id>
# (rubric) are the same operation ---


@pytest.mark.parametrize("url", ["/api/orders/X001/status",
                                 "/api/orders/X001"])
def test_update_status_works_on_both_put_routes(client, url):
    post_order(client)

    response = client.put(url, json={"new_status": "processing"})

    assert response.status_code == 200
    assert response.get_json() == {**NEW_ORDER, "status": "processing"}
    assert client.get("/api/orders/X001").get_json()["status"] == "processing"


def test_put_alias_reports_errors_like_the_status_route(client):
    response = client.put("/api/orders/NOPE", json={"new_status": "shipped"})

    assert_json_error(response, 404, "Order with ID 'NOPE' not found.")


# --- run options for `python -m backend.app` ---


@pytest.mark.parametrize("environ, debug", [
    pytest.param({}, True, id="unset: on, as in the starter"),
    pytest.param({"FLASK_DEBUG": "1"}, True, id="1"),
    pytest.param({"FLASK_DEBUG": "true"}, True, id="true"),
    pytest.param({"FLASK_DEBUG": "0"}, False, id="0"),
    pytest.param({"FLASK_DEBUG": "False"}, False, id="False"),
    pytest.param({"FLASK_DEBUG": "no"}, False, id="no"),
])
def test_run_options_read_debug_from_flask_debug(environ, debug):
    assert run_options(environ)["debug"] is debug


def test_run_options_bind_all_interfaces_on_port_5000_by_default():
    assert run_options({}) == {"host": "0.0.0.0", "port": 5000,
                               "debug": True}


def test_run_options_read_port_from_the_environment():
    assert run_options({"PORT": "5050"})["port"] == 5050
