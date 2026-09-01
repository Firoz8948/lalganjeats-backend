from types import SimpleNamespace

from app.modules.orders.item_lines import serialize_order_item


def test_variant_line_uses_transfer_price():
    item = SimpleNamespace(
        name="Kaju Katli",
        quantity=1,
        variant_label="250gm",
        actual_price=80,
        price=120,
    )
    row = serialize_order_item(item)
    assert row["line_label"] == "250gmx1 = Kaju Katli = ₹80"
    assert row["variant_label"] == "250gm"
    assert row["line_total"] == 80


def test_qty_two_without_variant():
    item = SimpleNamespace(
        name="Samosa",
        quantity=2,
        variant_label=None,
        actual_price=15,
        price=20,
    )
    row = serialize_order_item(item)
    assert row["line_label"] == "x2 = Samosa = ₹30"
