"""Manages stock levels."""

def reserve_items(items):
    """Which API updates inventory when an order is placed."""
    for i in items:
        _decrement_stock(i['sku'], i['qty'])

def _decrement_stock(sku, qty):
    # FIXME: no negative-stock guard yet
    pass
