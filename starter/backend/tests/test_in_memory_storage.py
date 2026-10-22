"""Unit tests for InMemoryStorage, the storage behind the running app."""
import pytest

from ..in_memory_storage import InMemoryStorage

ORDER = {"order_id": "ORD001", "item_name": "Laptop", "quantity": 1,
         "customer_id": "CUST001", "status": "pending"}


@pytest.fixture
def storage():
    return InMemoryStorage()


def test_get_order_returns_none_for_unknown_id(storage):
    assert storage.get_order("UNKNOWN") is None


def test_save_order_stores_a_copy(storage):
    order = dict(ORDER)
    storage.save_order("ORD001", order)

    order["status"] = "shipped"  # the caller changes its own dict afterwards

    assert storage.get_order("ORD001") == ORDER


def test_get_order_returns_a_copy(storage):
    storage.save_order("ORD001", ORDER)

    storage.get_order("ORD001")["status"] = "shipped"

    assert storage.get_order("ORD001")["status"] == "pending"


def test_get_all_orders_returns_copies(storage):
    storage.save_order("ORD001", ORDER)

    storage.get_all_orders()["ORD001"]["status"] = "shipped"

    assert storage.get_order("ORD001")["status"] == "pending"


def test_clear_removes_every_order(storage):
    storage.save_order("ORD001", ORDER)

    storage.clear()

    assert storage.get_all_orders() == {}


def test_delete_order_removes_only_that_order(storage):
    storage.save_order("ORD001", ORDER)
    storage.save_order("ORD002", {**ORDER, "order_id": "ORD002"})

    storage.delete_order("ORD001")

    assert storage.get_order("ORD001") is None
    assert list(storage.get_all_orders()) == ["ORD002"]


def test_delete_order_ignores_unknown_id(storage):
    # Storage stays dumb: deciding that a missing order is an error is
    # OrderTracker's job, so deleting an unknown ID here is a no-op.
    storage.delete_order("UNKNOWN")

    assert storage.get_all_orders() == {}
