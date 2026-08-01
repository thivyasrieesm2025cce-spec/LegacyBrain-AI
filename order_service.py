"""Handles order creation and payment calculation for the store."""
import inventory_service
from tax_utils import calculate_gst

class OrderService:
    """Creates orders and computes totals."""

    def create_order(self, items):
        """Creates a new order from a list of items."""
        # TODO: add discount code support
        total = self.calculate_payment(items)
        inventory_service.reserve_items(items)
        return total

    def calculate_payment(self, items):
        """Where payment is calculated, including GST."""
        subtotal = sum(i['price'] * i['qty'] for i in items)
        gst = calculate_gst(subtotal)
        return subtotal + gst
