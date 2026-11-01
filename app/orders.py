"""Read-only, session-bound order access. No conversational identity inputs."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.repository import Repository


@dataclass(frozen=True, repr=False)
class DemoSessionConfig:
    """Trusted local startup configuration, NEVER a chat/tool argument.

    This explicit local impersonation mode is not production authentication.
    A real deployment must replace it with a verified session adapter.
    """

    enabled: bool = False
    customer_id: int | None = None


@dataclass(frozen=True)
class OrderLineView:
    product_id: int
    product_name: str
    quantity: int
    historical_unit_price_brl: None = None


@dataclass(frozen=True)
class OrderView:
    order_id: int
    order_date: date
    status: str
    total_brl: Decimal
    tracking_code: str | None
    estimated_delivery: date | None
    items: tuple[OrderLineView, ...]
    warnings: tuple[str, ...]
    actual_delivery: None = None
    source: str = "CSV snapshot; freshness unknown; not live shipment information"


@dataclass(frozen=True)
class OrderLookupResult:
    status: str
    order: OrderView | None
    message: str


_UNAVAILABLE = OrderLookupResult(
    "unavailable", None, "Order information is unavailable for this session."
)


@dataclass(frozen=True, init=False)
class OrderService:
    """One instance per trusted session; expose ONLY lookup_order to future tools.

    Ownership is checked here, before constructing any output. Frozen attributes
    prevent accidental rebinding, not hostile Python execution in this process.
    Raw repository objects and DemoSessionConfig must never enter tool schemas.
    """

    _repository: Repository = field(repr=False)
    _customer_id: int | None = field(repr=False)

    def __init__(self, repository: Repository, config: DemoSessionConfig = DemoSessionConfig()):
        if type(config) is not DemoSessionConfig or type(config.enabled) is not bool:
            raise ValueError("Invalid local demo session configuration")
        if config.enabled:
            if (type(config.customer_id) is not int or config.customer_id < 1
                    or config.customer_id not in repository._customers):
                raise ValueError("Invalid local demo session configuration")
            customer_id = config.customer_id
        else:
            if config.customer_id is not None:
                raise ValueError("Demo identity requires explicit local opt-in")
            customer_id = None
        object.__setattr__(self, "_repository", repository)
        object.__setattr__(self, "_customer_id", customer_id)

    def lookup_order(self, order_id: int) -> OrderLookupResult:
        """Malformed, missing, anonymous, and foreign orders share one response.

        No names, email, phone, address, customer ID, payment data, or free-text
        order notes are included. There are no mutation or identity setter APIs.
        """
        if self._customer_id is None or type(order_id) is not int or not 1 <= order_id < 10**12:
            return _UNAVAILABLE
        order = self._repository._orders.get(order_id)
        if order is None or order.customer_id != self._customer_id:
            return _UNAVAILABLE
        # No output containing order data is constructed before the ownership check.
        items = tuple(
            OrderLineView(item.product_id, self._repository.products[item.product_id].name, item.quantity)
            for item in self._repository._items if item.order_id == order.order_id
        )
        warnings = ["unknown_freshness", "actual_delivery_unavailable", "historical_unit_prices_unavailable"]
        if order.tracking_code is None:
            warnings.append("tracking_unavailable")
        if order.estimated_delivery is None:
            warnings.append("estimated_delivery_unavailable")
        if not items:
            warnings.append("line_items_unavailable")
        if any(w.code == "historical_total_difference" and w.source == "orders.csv"
               and w.record_id == str(order.order_id) for w in self._repository.warnings):
            warnings.append("historical_total_difference")
        view = OrderView(order.order_id, order.order_date, order.status, order.total_brl,
                         order.tracking_code, order.estimated_delivery, items, tuple(warnings))
        return OrderLookupResult("available", view, "Recorded order information; no action was taken.")
