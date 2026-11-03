"""Per-session conversation state: one explicit, verified source of context.

Holds only references to records that the deterministic services returned in
this session, plus intentions the customer stated explicitly. It never holds
identity, order ownership or authorization: orders stay bound to the session
configuration and are validated by OrderService on every lookup.
"""

from dataclasses import dataclass, field


@dataclass
class PurchaseIntent:
    """The customer said they want to buy; nothing is reserved or ordered."""
    product_id: int | None = None
    quantity: int | None = None
    category_id: int | None = None


@dataclass
class ConversationState:
    displayed_ids: tuple[int, ...] = ()   # last NON-EMPTY list shown to the customer (positions)
    focus_ids: tuple[int, ...] = ()       # products verified in the latest product turn or UI selection
    recent_ids: tuple[int, ...] = ()      # recently verified products, oldest first (bounded)
    last_category_id: int | None = None   # category of the last list the customer asked for
    purchase: PurchaseIntent | None = None
    card_shown_for: int | None = None     # product whose full card the customer just saw
    _recent_limit: int = field(default=6, repr=False)

    def reset(self):
        limit = self._recent_limit
        self.__init__()
        self._recent_limit = limit

    @property
    def selected_id(self) -> int | None:
        return self.focus_ids[0] if len(self.focus_ids) == 1 else None

    def remember(self, product_ids):
        ids = tuple(dict.fromkeys(product_ids))
        self.recent_ids = (tuple(i for i in self.recent_ids if i not in ids) + ids)[-self._recent_limit:]

    def show_list(self, product_ids, category_id=None):
        """A non-empty list was displayed: positions now refer to it."""
        if product_ids:
            self.displayed_ids = tuple(product_ids)
            self.focus_ids = ()
            self.card_shown_for = None
            self.last_category_id = category_id
            self.remember(product_ids)
            if self.purchase and self.purchase.product_id is not None:
                self.purchase = None  # a new list means the customer moved on from that product

    def focus(self, product_ids, *, card_shown=False):
        """Specific products were verified (or selected) this turn."""
        ids = tuple(dict.fromkeys(product_ids))
        if not ids:
            return
        if self.purchase and self.purchase.product_id is not None and self.purchase.product_id not in ids:
            self.purchase = None  # the customer moved on to another product
        self.focus_ids = ids
        self.card_shown_for = ids[0] if card_shown and len(ids) == 1 else None
        self.remember(ids)

    def want(self, *, product_id=None, quantity=None, category_id=None):
        """Record an explicitly stated purchase intention."""
        current = self.purchase or PurchaseIntent()
        if product_id is not None and product_id != current.product_id:
            current = PurchaseIntent(product_id=product_id, category_id=current.category_id)
        if quantity is not None:
            current.quantity = quantity
        if category_id is not None:
            current.category_id = category_id
        self.purchase = current
