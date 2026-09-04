"""Helpers for delivery-partner dashboard active orders."""


def merge_active_order_payloads(*groups) -> list[dict]:
    """Keep every assigned in-progress order, oldest first.

    Old APKs only render ``active_order``. The dashboard still returns the
    full list as ``active_orders``; this merge also folds in the legacy
    single card plus any locally remembered accepts so the first order
    cannot disappear when a second one is accepted.
    """
    by_id: dict[int, dict] = {}
    for group in groups:
        items = group if isinstance(group, list) else [group]
        for item in items:
            if not item or not isinstance(item, dict):
                continue
            oid = item.get("id")
            if oid is None:
                continue
            by_id[int(oid)] = item
    return sorted(
        by_id.values(),
        key=lambda row: (row.get("created_at") or "", int(row["id"])),
    )
