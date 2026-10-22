# This module contains the OrderTracker class, which encapsulates the core
# business logic for managing orders.
#
# OrderTracker validates every input and enforces the order rules; storage is
# injected (see InMemoryStorage). Problems are reported as exceptions so that
# callers such as the Flask API can map them to HTTP responses:
#   ValueError          -> invalid input (blank ID, bad quantity or status)
#   DuplicateOrderError -> an order with that ID already exists
#   OrderNotFoundError  -> a command targets an order that does not exist

from typing import Optional

# Allowed order statuses. They match the options offered by the frontend.
VALID_STATUSES = ("pending", "processing", "shipped")


class DuplicateOrderError(ValueError):
    """Raised when adding an order whose ID is already in use.

    It subclasses ValueError, so code that only expects validation errors
    (the course's example test, for instance) still catches it, while the
    API can tell it apart and answer 409 Conflict.
    """


class OrderNotFoundError(LookupError):
    """Raised when a command (such as a status update) targets an unknown
    order ID. Deliberately not a ValueError: the input was well formed."""

    def __init__(self, order_id: str):
        super().__init__(f"Order with ID '{order_id}' not found.")
        self.order_id = order_id


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


def _validate_status(status, field: str = "status") -> None:
    # A tuple membership test also copes with unhashable JSON values.
    if status not in VALID_STATUSES:
        raise ValueError(
            f"'{field}' must be one of: {', '.join(VALID_STATUSES)}; "
            f"got {status!r}.")


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

    def update_order_status(self, order_id: str, new_status: str) -> dict:
        """Change the status of an existing order and return the result.

        This is a command, so an unknown ID is an error and raises
        OrderNotFoundError. Invalid input raises ValueError.
        """
        order_id = _require_text(order_id, "order_id")
        _validate_status(new_status, "new_status")
        # Save a new dict rather than mutating whatever storage returned.
        updated = {**self._get_existing_order(order_id), "status": new_status}
        self.storage.save_order(order_id, updated)
        return updated

    def list_all_orders(self) -> list:
        """Return every order as a list (empty if there are none)."""
        return self.list_orders()

    def list_orders_by_status(self, status: str) -> list:
        """Return the orders with the given status.

        An unknown status raises ValueError instead of silently matching
        nothing, so a typo such as 'shiped' is reported to the caller.
        """
        # Validate here as well: list_orders reads None as "no filter", but
        # this method requires a status, so None must not return everything.
        _validate_status(status)
        return self.list_orders(status=status)

    def list_orders(self, status: Optional[str] = None,
                    customer_id: Optional[str] = None) -> list:
        """Return the orders matching every filter that is given.

        Both filters are optional and can be combined; None means "do not
        filter on this field". Invalid filter values raise ValueError.
        """
        if status is not None:
            _validate_status(status)
        if customer_id is not None:
            customer_id = _require_text(customer_id, "customer_id")
        return [
            order for order in self.storage.get_all_orders().values()
            if (status is None or order["status"] == status)
            and (customer_id is None or order["customer_id"] == customer_id)
        ]

    def _get_existing_order(self, order_id: str) -> dict:
        order = self.storage.get_order(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order
