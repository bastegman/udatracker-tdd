import pytest
from unittest.mock import Mock
from ..order_tracker import (VALID_STATUSES, DuplicateOrderError,
                             OrderNotFoundError, OrderTracker)

# --- Fixtures for Unit Tests ---


@pytest.fixture
def mock_storage():
    """
    Provides a mock storage object for tests.
    This mock will be configured to simulate various storage behaviors.
    """
    mock = Mock()
    # By default, mock get_order to return None (no order found)
    mock.get_order.return_value = None
    # By default, mock get_all_orders to return an empty dict
    mock.get_all_orders.return_value = {}
    return mock


@pytest.fixture
def order_tracker(mock_storage):
    """
    Provides an OrderTracker instance initialized with the mock_storage.
    """
    return OrderTracker(mock_storage)


# --- add_order: example tests from the course README (cycles 1 and 2) ---


def test_add_order_successfully(order_tracker, mock_storage):
    """Tests adding a new order with default 'pending' status."""
    order_tracker.add_order("ORD001", "Laptop", 1, "CUST001")

    # We expect save_order to be called once
    mock_storage.save_order.assert_called_once()


def test_add_order_raises_error_if_exists(order_tracker, mock_storage):
    """Tests that adding an order with a duplicate ID raises a ValueError."""
    # Simulate that the storage finds an existing order
    mock_storage.get_order.return_value = {"order_id": "ORD_EXISTING"}

    with pytest.raises(ValueError, match="Order with ID 'ORD_EXISTING' already exists."):
        order_tracker.add_order("ORD_EXISTING", "New Item", 1, "CUST001")


# --- add_order: stored details, defaults and validation ---

VALID_ORDER = {
    "order_id": "ORD001",
    "item_name": "Laptop",
    "quantity": 2,
    "customer_id": "CUST001",
}


def test_add_order_stores_details_with_pending_default(order_tracker,
                                                       mock_storage):
    order_tracker.add_order("ORD001", "Laptop", 2, "CUST001")

    mock_storage.save_order.assert_called_once_with("ORD001", {
        "order_id": "ORD001",
        "item_name": "Laptop",
        "quantity": 2,
        "customer_id": "CUST001",
        "status": "pending",
    })


def test_add_order_returns_the_new_order(order_tracker):
    order = order_tracker.add_order(**VALID_ORDER)

    assert order == {**VALID_ORDER, "status": "pending"}


@pytest.mark.parametrize("status", VALID_STATUSES)
def test_add_order_accepts_every_valid_status(order_tracker, mock_storage,
                                              status):
    order = order_tracker.add_order(**VALID_ORDER, status=status)

    assert order["status"] == status
    mock_storage.save_order.assert_called_once()


def test_add_order_strips_surrounding_whitespace(order_tracker, mock_storage):
    order = order_tracker.add_order(" ORD001 ", " Laptop ", 2, " CUST001 ")

    assert order == {**VALID_ORDER, "status": "pending"}
    mock_storage.get_order.assert_called_once_with("ORD001")


@pytest.mark.parametrize("field, value", [
    pytest.param("order_id", "", id="empty order_id"),
    pytest.param("order_id", "   ", id="blank order_id"),
    pytest.param("order_id", None, id="missing order_id"),
    pytest.param("order_id", 123, id="non-string order_id"),
    pytest.param("item_name", "", id="empty item_name"),
    pytest.param("customer_id", "", id="empty customer_id"),
    pytest.param("customer_id", None, id="missing customer_id"),
    pytest.param("quantity", 0, id="zero quantity"),
    pytest.param("quantity", -3, id="negative quantity"),
    pytest.param("quantity", 1.5, id="float quantity"),
    pytest.param("quantity", "2", id="string quantity"),
    pytest.param("quantity", True, id="bool quantity"),
    pytest.param("quantity", None, id="missing quantity"),
    pytest.param("status", "delivered", id="unknown status"),
    pytest.param("status", "Shipped", id="status in wrong case"),
    pytest.param("status", "", id="empty status"),
])
def test_add_order_rejects_invalid_input(order_tracker, mock_storage,
                                         field, value):
    with pytest.raises(ValueError, match=field):
        order_tracker.add_order(**{**VALID_ORDER, field: value})

    mock_storage.save_order.assert_not_called()


def test_add_order_duplicate_raises_duplicate_order_error(order_tracker,
                                                         mock_storage):
    mock_storage.get_order.return_value = {"order_id": "ORD001"}

    with pytest.raises(DuplicateOrderError,
                       match="Order with ID 'ORD001' already exists."):
        order_tracker.add_order(**VALID_ORDER)

    # Still a ValueError, so callers that only expect validation errors work.
    assert issubclass(DuplicateOrderError, ValueError)
    mock_storage.save_order.assert_not_called()


# --- get_order_by_id ---


def test_get_order_by_id_returns_existing_order(order_tracker, mock_storage):
    stored = {**VALID_ORDER, "status": "pending"}
    mock_storage.get_order.return_value = stored

    assert order_tracker.get_order_by_id("ORD001") == stored
    mock_storage.get_order.assert_called_once_with("ORD001")


def test_get_order_by_id_returns_none_for_unknown_id(order_tracker,
                                                     mock_storage):
    assert order_tracker.get_order_by_id("UNKNOWN") is None
    mock_storage.get_order.assert_called_once_with("UNKNOWN")


def test_get_order_by_id_strips_surrounding_whitespace(order_tracker,
                                                       mock_storage):
    order_tracker.get_order_by_id("  ORD001 ")

    mock_storage.get_order.assert_called_once_with("ORD001")


@pytest.mark.parametrize("order_id", ["", "   ", None, 42],
                         ids=["empty", "blank", "None", "int"])
def test_get_order_by_id_rejects_invalid_id(order_tracker, mock_storage,
                                            order_id):
    with pytest.raises(ValueError, match="order_id"):
        order_tracker.get_order_by_id(order_id)

    mock_storage.get_order.assert_not_called()


# --- update_order_status ---


def test_update_order_status_changes_pending_to_shipped(order_tracker,
                                                        mock_storage):
    mock_storage.get_order.return_value = {**VALID_ORDER, "status": "pending"}

    updated = order_tracker.update_order_status("ORD001", "shipped")

    assert updated == {**VALID_ORDER, "status": "shipped"}
    mock_storage.get_order.assert_called_once_with("ORD001")
    mock_storage.save_order.assert_called_once_with(
        "ORD001", {**VALID_ORDER, "status": "shipped"})


def test_update_order_status_does_not_mutate_the_fetched_dict(order_tracker,
                                                              mock_storage):
    stored = {**VALID_ORDER, "status": "pending"}
    mock_storage.get_order.return_value = stored

    order_tracker.update_order_status("ORD001", "processing")

    assert stored["status"] == "pending"


def test_update_order_status_unknown_order_raises_not_found(order_tracker,
                                                            mock_storage):
    with pytest.raises(OrderNotFoundError,
                       match="Order with ID 'UNKNOWN' not found."):
        order_tracker.update_order_status("UNKNOWN", "shipped")

    # A lookup failure, deliberately not a ValueError (the API maps it to 404).
    assert issubclass(OrderNotFoundError, LookupError)
    assert not issubclass(OrderNotFoundError, ValueError)
    mock_storage.save_order.assert_not_called()


@pytest.mark.parametrize("new_status", ["delivered", "SHIPPED", "", None],
                         ids=["unknown", "wrong case", "empty", "None"])
def test_update_order_status_rejects_invalid_status(order_tracker,
                                                    mock_storage, new_status):
    mock_storage.get_order.return_value = {**VALID_ORDER, "status": "pending"}

    with pytest.raises(ValueError, match="new_status"):
        order_tracker.update_order_status("ORD001", new_status)

    mock_storage.save_order.assert_not_called()


@pytest.mark.parametrize("order_id", ["", "   ", None],
                         ids=["empty", "blank", "None"])
def test_update_order_status_rejects_empty_order_id(order_tracker,
                                                    mock_storage, order_id):
    with pytest.raises(ValueError, match="order_id"):
        order_tracker.update_order_status(order_id, "shipped")

    mock_storage.get_order.assert_not_called()
    mock_storage.save_order.assert_not_called()


# --- list_all_orders and list_orders_by_status ---

STORED_ORDERS = {
    "A1": {"order_id": "A1", "item_name": "Pen", "quantity": 1,
           "customer_id": "C1", "status": "pending"},
    "A2": {"order_id": "A2", "item_name": "Ink", "quantity": 2,
           "customer_id": "C2", "status": "shipped"},
    "A3": {"order_id": "A3", "item_name": "Pad", "quantity": 3,
           "customer_id": "C1", "status": "shipped"},
}


def ids_of(orders):
    return [order["order_id"] for order in orders]


def test_list_all_orders_returns_every_order(order_tracker, mock_storage):
    mock_storage.get_all_orders.return_value = STORED_ORDERS

    assert order_tracker.list_all_orders() == list(STORED_ORDERS.values())


def test_list_all_orders_returns_empty_list_without_orders(order_tracker):
    assert order_tracker.list_all_orders() == []


def test_list_orders_by_status_returns_only_matching(order_tracker,
                                                     mock_storage):
    mock_storage.get_all_orders.return_value = STORED_ORDERS

    assert ids_of(order_tracker.list_orders_by_status("shipped")) == [
        "A2", "A3"]
    assert ids_of(order_tracker.list_orders_by_status("pending")) == ["A1"]


def test_list_orders_by_status_returns_empty_list_if_none_match(order_tracker,
                                                                mock_storage):
    mock_storage.get_all_orders.return_value = STORED_ORDERS

    assert order_tracker.list_orders_by_status("processing") == []


@pytest.mark.parametrize("status", ["delivered", "", None],
                         ids=["unknown", "empty", "None"])
def test_list_orders_by_status_rejects_invalid_status(order_tracker, status):
    with pytest.raises(ValueError, match="status"):
        order_tracker.list_orders_by_status(status)
