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

    # 1. First check if raw JSON string is provided in .env (FIREBASE_CREDENTIALS_JSON)
    json_str = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
    if json_str and json_str.strip():
        try:
            import json
            raw = json_str.strip()
            # Remove wrapping quotes — docker-compose env_file may keep them
            if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                raw = raw[1:-1]

            # Docker-compose env_file can double-escape: \\n becomes literal backslash+n
            # Try parsing as-is first, then with unescaping
            try:
                cred_dict = json.loads(raw)
            except json.JSONDecodeError:
                # The env_file parser may have mangled \n — try replacing literal \\n
                raw_fixed = raw.replace("\\n", "\n")
                cred_dict = json.loads(raw_fixed)

            # Fix private_key newlines — multiple formats possible from env_file
            if "private_key" in cred_dict:
                pk = cred_dict["private_key"]
                # Replace literal two-char \n sequences with real newlines
                if "\\n" in pk:
                    pk = pk.replace("\\n", "\n")
                # Some env parsers produce \\\\n
                if "\\\\n" in pk:
                    pk = pk.replace("\\\\n", "\n")
                # Ensure the key starts with proper PEM header
                pk = pk.strip()
                cred_dict["private_key"] = pk
                # Diagnostic logging (safe — only shows first/last chars)
                logger.info("private_key starts with: %s ... ends with: %s (len=%d)",
                            repr(pk[:30]), repr(pk[-30:]), len(pk))

            logger.info("Firebase JSON parsed OK. project_id=%s, client_email=%s",
                        cred_dict.get("project_id"), cred_dict.get("client_email"))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _app_initialized = True
            logger.info("Firebase Admin SDK initialized successfully from FIREBASE_CREDENTIALS_JSON in .env.")
            return True
        except json.JSONDecodeError as e:
            logger.error("FIREBASE_CREDENTIALS_JSON is not valid JSON: %s (first 100 chars: %s)", e, json_str[:100])
        except Exception as e:
            logger.error("Failed to init Firebase from FIREBASE_CREDENTIALS_JSON: %s", e)

    # 2. Check file path
    key_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "lalganjeats-firebase-adminsdk-fbsvc-bee7b16141.json")
    if not os.path.isabs(key_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_path = os.path.join(base_dir, key_path)
        if os.path.exists(resolved_path):
            key_path = resolved_path

    if not os.path.exists(key_path):
        logger.warning("FCM key file not found at %s. Push notifications disabled.", key_path)
        return False

    try:
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _app_initialized = True
        logger.info("Firebase Admin SDK initialized successfully from file %s.", key_path)
        return True
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin SDK from file: %s", e)
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
                    sound="default",
                    channel_id="lalganjeats_orders",
                    priority="max",
                    default_sound=True,
                    default_vibrate_timings=True,
                ),
            ),
        )
        response = messaging.send(msg)
        logger.info("FCM push sent successfully: %s", response)
        return True
    except Exception as e:
        logger.warning("Failed to send FCM push to token %s...: %s", token[:15] if token else "", e)
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
                    sound="default",
                    channel_id="lalganjeats_orders",
                    priority="max",
                    default_sound=True,
                    default_vibrate_timings=True,
                ),
            ),
        )
        response = messaging.send_each_for_multicast(msg)
        logger.info("FCM multicast sent. Success count: %s / %s", response.success_count, len(valid_tokens))
        return response.success_count
    except Exception as e:
        logger.warning("Failed to send FCM multicast push: %s", e)
        return 0
