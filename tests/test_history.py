from app.modules.payments.history import (
    PAGE_SIZE,
    cash_status_label,
    paginated_result,
)


def test_paginated_result_caps_page_size_at_10():
    result = paginated_result(page=2, page_size=50, total=25, items=["a"])
    assert result["page"] == 2
    assert result["page_size"] == PAGE_SIZE
    assert result["total"] == 25
    assert result["total_pages"] == 3
    assert result["items"] == ["a"]


def test_paginated_result_empty():
    result = paginated_result(page=1, page_size=10, total=0, items=[])
    assert result["total_pages"] == 0
    assert result["page"] == 1


def test_cash_status_labels():
    assert cash_status_label("paid") == "Paid"
    assert cash_status_label("failed") == "Payment cancelled"
    assert cash_status_label("cancelled") == "Payment cancelled"
    assert cash_status_label("pending") == "Pending"
