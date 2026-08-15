"""
Delivery-partner webhooks / event hooks.
Keep DP-specific side effects here (not mixed into hotel or customer modules).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def on_offer_created(order, partner, distance_km: float) -> None:
    logger.info(
        "[DP webhook] offer created order=%s partner=%s km=%s",
        order.id,
        partner.id,
        distance_km,
    )


def on_offer_accepted(order, partner) -> None:
    logger.info(
        "[DP webhook] offer accepted order=%s partner=%s",
        order.id,
        partner.id,
    )


def on_offer_rejected(order_id: int, partner_id: int) -> None:
    logger.info(
        "[DP webhook] offer rejected order=%s partner=%s",
        order_id,
        partner_id,
    )


def on_picked_up(order, partner) -> None:
    logger.info(
        "[DP webhook] picked up order=%s partner=%s",
        order.id,
        partner.id,
    )


def on_delivered(order, partner) -> None:
    logger.info(
        "[DP webhook] delivered order=%s partner=%s",
        order.id,
        partner.id,
    )
