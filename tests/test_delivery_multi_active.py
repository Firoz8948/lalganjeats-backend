from app.modules.delivery.actives import merge_active_order_payloads


def test_merge_keeps_every_assigned_order_oldest_first():
    newer = {
        "id": 99,
        "order_number": "LE-2026-00098",
        "created_at": "2026-09-04T06:20:09+00:00",
    }
    older = {
        "id": 100,
        "order_number": "LE-2026-00099",
        "created_at": "2026-09-04T05:47:28+00:00",
    }

    merged = merge_active_order_payloads([newer], older)

    assert [row["order_number"] for row in merged] == [
        "LE-2026-00099",
        "LE-2026-00098",
    ]


def test_merge_does_not_drop_the_first_order_when_only_latest_is_active_order():
    first = {
        "id": 100,
        "order_number": "LE-2026-00099",
        "created_at": "2026-09-04T05:47:28+00:00",
    }
    second = {
        "id": 99,
        "order_number": "LE-2026-00098",
        "created_at": "2026-09-04T05:52:16+00:00",
    }

    merged = merge_active_order_payloads([second], second, [first])

    assert {row["id"] for row in merged} == {99, 100}
    assert merged[0]["id"] == 100
