"""
Firebase Cloud Messaging (FCM) push notification service.
Sends background notifications to Hotel Partner and Delivery Partner apps even when closed/killed.
"""
from __future__ import annotations

import logging
import os
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    _FIREBASE_AVAILABLE = True
except ImportError:
    firebase_admin = None
    credentials = None
    messaging = None
    _FIREBASE_AVAILABLE = False

_app_initialized = False


def init_firebase() -> bool:
    global _app_initialized
    if _app_initialized:
        return True

    if not _FIREBASE_AVAILABLE:
        logger.warning("firebase-admin package not installed. Push notifications disabled.")
        return False

    # --- Approach 1: File-based credentials (most reliable in Docker) ---
    key_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "lalganjeats-firebase-adminsdk-fbsvc-bee7b16141.json")
    if not os.path.isabs(key_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_path = os.path.join(base_dir, key_path)
        if os.path.exists(resolved_path):
            key_path = resolved_path

    if os.path.exists(key_path) and os.path.isfile(key_path):
        try:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            _app_initialized = True
            logger.warning("[FCM] Firebase Admin SDK initialized from file: %s", key_path)
            return True
        except Exception as e:
            logger.error("[FCM] Failed to initialize from file %s: %s", key_path, e)
    else:
        logger.warning("[FCM] Key file not found at %s, trying env var...", key_path)

    # --- Approach 2: JSON string from environment variable ---
    json_str = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
    if json_str and json_str.strip():
        try:
            import json
            raw = json_str.strip()
            # Remove wrapping quotes — docker-compose env_file may keep them
            if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                raw = raw[1:-1]

            try:
                cred_dict = json.loads(raw)
            except json.JSONDecodeError:
                raw_fixed = raw.replace("\\n", "\n")
                cred_dict = json.loads(raw_fixed)

            # Fix private_key newlines
            if "private_key" in cred_dict:
                pk = cred_dict["private_key"]
                if "\\n" in pk:
                    pk = pk.replace("\\n", "\n")
                pk = pk.strip()
                cred_dict["private_key"] = pk
                logger.warning("[FCM] private_key starts with: %s (len=%d)", repr(pk[:27]), len(pk))

            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _app_initialized = True
            logger.warning("[FCM] Firebase Admin SDK initialized from FIREBASE_CREDENTIALS_JSON env var.")
            return True
        except json.JSONDecodeError as e:
            logger.error("[FCM] FIREBASE_CREDENTIALS_JSON is not valid JSON: %s", e)
        except Exception as e:
            logger.error("[FCM] Failed to init from FIREBASE_CREDENTIALS_JSON: %s", e)

    logger.error("[FCM] All Firebase init approaches failed. Push notifications disabled.")
    return False


def send_push_notification(
    token: str | None,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> bool:
    """Send high-priority push notification to a single FCM device token."""
    if not token or not token.strip():
        return False

    if not _app_initialized:
        if not init_firebase():
            return False

    try:
        data_payload = {str(k): str(v) for k, v in (data or {}).items()}
        msg = messaging.Message(
            token=token.strip(),
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data_payload,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    title=title,
                    body=body,
                    sound="order_alert",
                    channel_id="lalganjeats_urgent_orders",
                    priority="max",
                    default_vibrate_timings=True,
                ),
            ),
        )
        response = messaging.send(msg)
        logger.warning("[FCM] Push sent OK: %s", response)
        return True
    except Exception as e:
        logger.warning("[FCM] Failed to send push to token %s...: %s", token[:15] if token else "", e)
        return False


def send_multicast_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send high-priority push notification to multiple device tokens."""
    valid_tokens = [t.strip() for t in tokens if t and t.strip()]
    if not valid_tokens:
        return 0

    if not _app_initialized:
        if not init_firebase():
            return 0

    try:
        data_payload = {str(k): str(v) for k, v in (data or {}).items()}
        msg = messaging.MulticastMessage(
            tokens=valid_tokens,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data_payload,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    title=title,
                    body=body,
                    sound="order_alert",
                    channel_id="lalganjeats_urgent_orders",
                    priority="max",
                    default_vibrate_timings=True,
                ),
            ),
        )
        response = messaging.send_each_for_multicast(msg)
        logger.warning("[FCM] Multicast: %d/%d succeeded", response.success_count, len(valid_tokens))
        # Log individual failures for debugging
        if response.failure_count > 0:
            for i, send_response in enumerate(response.responses):
                if send_response.exception:
                    logger.warning("[FCM] Token %d failed: %s", i, send_response.exception)
        return response.success_count
    except Exception as e:
        logger.warning("[FCM] Failed to send multicast push: %s", e)
        return 0
