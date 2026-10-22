# This module contains the OrderTracker class, which encapsulates the core
# business logic for managing orders.
#
# OrderTracker validates every input and enforces the order rules; storage is
# injected (see InMemoryStorage). Problems are reported as exceptions so that
# callers such as the Flask API can map them to HTTP responses:
#   ValueError          -> invalid input (blank ID, bad quantity or status)
#   DuplicateOrderError -> an order with that ID already exists

# Allowed order statuses. They match the options offered by the frontend.
VALID_STATUSES = ("pending", "processing", "shipped")


class DuplicateOrderError(ValueError):
    """Raised when adding an order whose ID is already in use.

    It subclasses ValueError, so code that only expects validation errors
    (the course's example test, for instance) still catches it, while the
    API can tell it apart and answer 409 Conflict.
    """


def _require_text(value, field: str) -> str:
    """Return `value` stripped, or raise ValueError if it is not a
    non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field}' must be a non-empty string.")
    return value.strip()


def _validate_quantity(quantity) -> None:
    # bool is a subclass of int, so True would otherwise count as 1.
    if (isinstance(quantity, bool) or not isinstance(quantity, int)
            or quantity < 1):
        raise ValueError(
            f"'quantity' must be a positive integer, got {quantity!r}.")


def _validate_status(status) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}; 'status' must be one of: "
            f"{', '.join(VALID_STATUSES)}.")


class OrderTracker:
    """
    Manages customer orders, providing functionalities to add, update,
    and retrieve order information.
    """
    def __init__(self, storage):
        required_methods = ['save_order', 'get_order', 'get_all_orders']
        for method in required_methods:
            if not hasattr(storage, method) or not callable(getattr(storage, method)):
                raise TypeError(f"Storage object must implement a callable '{method}' method.")
        self.storage = storage

    def add_order(self, order_id: str, item_name: str, quantity: int,
                  customer_id: str, status: str = "pending") -> dict:
        """Create an order, save it and return it.

        Raises ValueError for invalid input and DuplicateOrderError if the
        ID is already taken. IDs and the item name are stripped first.
        """
        order_id = _require_text(order_id, "order_id")
        item_name = _require_text(item_name, "item_name")
        customer_id = _require_text(customer_id, "customer_id")
        _validate_quantity(quantity)
        _validate_status(status)

        if self.storage.get_order(order_id) is not None:
            raise DuplicateOrderError(
                f"Order with ID '{order_id}' already exists.")

        order = {
            "order_id": order_id,
            "item_name": item_name,
            "quantity": quantity,
            "customer_id": customer_id,
            "status": status,
        }
        self.storage.save_order(order_id, order)
        return order

    def get_order_by_id(self, order_id: str):
        """Return the order with this ID, or None if there is none.

        This is a query, so a missing order is a normal answer (None), not
        an error. An empty or non-string ID raises ValueError.
        """
        order_id = _require_text(order_id, "order_id")
        return self.storage.get_order(order_id)

    def update_order_status(self, order_id: str, new_status: str):
        pass

    def list_all_orders(self):
        pass

    def list_orders_by_status(self, status: str):
        pass
