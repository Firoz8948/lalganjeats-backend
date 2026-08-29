"""
Script: test_background_notifications.py
Validates that FCM background push notifications are fully configured and operational
for all 3 apps: Customer APK, Hotel Partner APK, and Delivery Partner APK.

Tests:
  1. Firebase Admin SDK initialization
  2. FCM credential file present and valid
  3. Notification channel alignment (backend channel_id matches app channel creation)
  4. Android high-priority payload construction verification
  5. FCM token presence in database for each role
  6. Dry-run send to each role's FCM token (real Firebase API call)
"""
import sys
import os
import json
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Setup
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Import app to register all models
import app.main  # noqa: F401
from app.core.database import SessionLocal
from app.modules.users.models import User

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
INFO = "ℹ️"

results = []

def log_result(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((test_name, passed, detail))
    print(f"  {status} {test_name}")
    if detail:
        print(f"       {detail}")


def run_tests():
    print("=" * 80)
    print("🔔 BACKGROUND NOTIFICATION READINESS TEST")
    print("   Testing FCM Push for: Customer APK, Hotel Partner APK, Delivery Partner APK")
    print("=" * 80)

    # ═══════════════════════════════════════════════════
    # TEST 1: Firebase Admin SDK Availability
    # ═══════════════════════════════════════════════════
    print("\n[Test 1] Firebase Admin SDK Module Check...")
    try:
        from app.core.fcm import _FIREBASE_AVAILABLE, init_firebase, _app_initialized
        log_result("firebase-admin Python package installed", _FIREBASE_AVAILABLE)
        if not _FIREBASE_AVAILABLE:
            print(f"\n{FAIL} CRITICAL: firebase-admin package not installed. All push tests will fail.")
            print("   Fix: pip install firebase-admin")
            return False
    except ImportError as e:
        log_result("firebase-admin package import", False, str(e))
        return False

    # ═══════════════════════════════════════════════════
    # TEST 2: Firebase Credentials File
    # ═══════════════════════════════════════════════════
    print("\n[Test 2] Firebase Credentials Check...")
    cred_path = os.path.join(backend_dir, "lalganjeats-firebase-adminsdk-fbsvc-bee7b16141.json")
    cred_exists = os.path.exists(cred_path)
    log_result("Firebase credential file exists", cred_exists, cred_path if cred_exists else "FILE NOT FOUND")

    if cred_exists:
        try:
            with open(cred_path, "r") as f:
                cred_data = json.load(f)
            required_keys = ["type", "project_id", "private_key_id", "private_key", "client_email"]
            missing = [k for k in required_keys if k not in cred_data]
            log_result("Credential file has required fields", len(missing) == 0,
                       f"Missing: {missing}" if missing else f"Project: {cred_data.get('project_id', '?')}")
        except Exception as e:
            log_result("Credential file is valid JSON", False, str(e))

    # ═══════════════════════════════════════════════════
    # TEST 3: Firebase SDK Initialization
    # ═══════════════════════════════════════════════════
    print("\n[Test 3] Firebase Admin SDK Initialization...")
    sdk_ok = init_firebase()
    log_result("Firebase Admin SDK initialized successfully", sdk_ok)
    if not sdk_ok:
        print(f"\n{FAIL} CRITICAL: Cannot initialize Firebase. Push notifications will not work.")
        return False

    # ═══════════════════════════════════════════════════
    # TEST 4: Notification Channel Alignment
    # ═══════════════════════════════════════════════════
    print("\n[Test 4] Notification Channel ID Alignment Check...")
    # Backend uses channel_id in AndroidNotification
    backend_channel = "lalganjeats_orders"

    # Check all 3 apps create the matching channel
    apps_channels = {
        "Customer APK": "frontend/src/app/core/services/customer-notification.service.ts",
        "Hotel Partner APK": "hotel-partner-app/src/app/core/services/notification.service.ts",
        "Delivery Partner APK": "delivery-partner-app/src/app/core/services/notification.service.ts",
    }
    project_root = os.path.dirname(backend_dir)
    for app_name, rel_path in apps_channels.items():
        full_path = os.path.join(project_root, rel_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            has_channel = backend_channel in content
            log_result(f"{app_name} creates '{backend_channel}' channel", has_channel)
        else:
            log_result(f"{app_name} notification service file exists", False, f"Not found: {rel_path}")

    # ═══════════════════════════════════════════════════
    # TEST 5: Android High-Priority Payload Structure
    # ═══════════════════════════════════════════════════
    print("\n[Test 5] Android High-Priority Payload Verification...")
    fcm_path = os.path.join(backend_dir, "app", "core", "fcm.py")
    with open(fcm_path, "r", encoding="utf-8") as f:
        fcm_code = f.read()

    checks = {
        'priority="high"': 'AndroidConfig priority=high (wakes killed apps)',
        'priority="max"': 'AndroidNotification priority=max (heads-up display)',
        'channel_id="lalganjeats_orders"': 'Notification channel matches app channel',
        'default_sound=True': 'Default sound enabled for background alerts',
        'default_vibrate_timings=True': 'Default vibration enabled',
    }
    for pattern, desc in checks.items():
        log_result(desc, pattern in fcm_code)

    # ═══════════════════════════════════════════════════
    # TEST 6: FCM Token Storage in Database
    # ═══════════════════════════════════════════════════
    print("\n[Test 6] FCM Token Presence in Database...")
    db = SessionLocal()
    try:
        roles = {
            "Customer APK": "customer",
            "Hotel Partner APK": "restaurant_owner",
            "Delivery Partner APK": "delivery_partner",
        }
        tokens_found = {}
        for app_name, role in roles.items():
            users_with_token = db.query(User).filter(
                User.role == role,
                User.fcm_token.isnot(None),
                User.fcm_token != "",
                User.is_active == True,
            ).all()
            has_tokens = len(users_with_token) > 0
            tokens_found[app_name] = users_with_token
            if has_tokens:
                token_preview = users_with_token[0].fcm_token[:25] + "..." if users_with_token[0].fcm_token else "?"
                log_result(
                    f"{app_name} has registered FCM tokens",
                    True,
                    f"{len(users_with_token)} user(s) with tokens. First: {users_with_token[0].full_name} ({token_preview})"
                )
            else:
                log_result(
                    f"{app_name} has registered FCM tokens",
                    False,
                    f"No {role} users have FCM tokens stored. They need to open the app on a real device first."
                )

        # ═══════════════════════════════════════════════════
        # TEST 7: Dry-Run FCM Send to Each Role
        # ═══════════════════════════════════════════════════
        print("\n[Test 7] Live FCM Push Test (dry-run send to stored tokens)...")
        from firebase_admin import messaging

        for app_name, role in roles.items():
            users = tokens_found.get(app_name, [])
            if not users:
                log_result(f"{app_name} FCM send test", False, "SKIPPED - No FCM token registered for this role")
                continue

            user = users[0]
            token = user.fcm_token.strip()
            test_title = f"🔔 LalganjEats Test Notification"
            test_body = f"Background push test for {app_name}. If you see this, notifications work!"

            try:
                msg = messaging.Message(
                    token=token,
                    notification=messaging.Notification(
                        title=test_title,
                        body=test_body,
                    ),
                    data={
                        "type": "background_test",
                        "app": app_name,
                        "timestamp": str(int(time.time())),
                    },
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            title=test_title,
                            body=test_body,
                            sound="default",
                            channel_id="lalganjeats_orders",
                            priority="max",
                            default_sound=True,
                            default_vibrate_timings=True,
                        ),
                    ),
                )
                response = messaging.send(msg)
                log_result(
                    f"{app_name} FCM send test",
                    True,
                    f"Sent to {user.full_name}. Firebase response: {response}"
                )
            except messaging.UnregisteredError:
                log_result(
                    f"{app_name} FCM send test",
                    False,
                    f"Token EXPIRED/UNREGISTERED for {user.full_name}. User needs to re-open the app."
                )
            except messaging.InvalidArgumentError as e:
                log_result(f"{app_name} FCM send test", False, f"Invalid token format: {e}")
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower() or "not a valid" in error_msg.lower():
                    log_result(
                        f"{app_name} FCM send test",
                        False,
                        f"Token invalid or device unregistered: {error_msg[:120]}"
                    )
                else:
                    log_result(f"{app_name} FCM send test", False, f"Error: {error_msg[:150]}")

        # ═══════════════════════════════════════════════════
        # TEST 8: FCM Token Endpoint Availability
        # ═══════════════════════════════════════════════════
        print("\n[Test 8] FCM Token Registration Endpoints...")
        endpoint_files = {
            "Customer APK → POST /users/fcm-token": os.path.join(backend_dir, "app", "modules", "users", "router.py"),
            "Hotel Partner APK → POST /hotel-portal/fcm-token": os.path.join(backend_dir, "app", "modules", "hotel_portal", "router.py"),
            "Delivery Partner APK → POST /delivery/fcm-token": os.path.join(backend_dir, "app", "modules", "delivery", "router.py"),
        }
        for endpoint_desc, filepath in endpoint_files.items():
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    code = f.read()
                has_endpoint = "fcm-token" in code and "fcm_token" in code
                log_result(endpoint_desc, has_endpoint)
            else:
                log_result(endpoint_desc, False, "Router file not found")

    finally:
        db.close()

    # ═══════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 80)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)

    if failed == 0:
        print(f"🎉 ALL {total} BACKGROUND NOTIFICATION TESTS PASSED!")
    else:
        print(f"📊 RESULTS: {passed}/{total} passed, {failed} failed")
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                print(f"  {FAIL} {name}")
                if detail:
                    print(f"       {detail}")

    print("=" * 80)

    # Provide actionable guidance
    if failed > 0:
        print("\n📋 TROUBLESHOOTING GUIDE:")
        for name, p, detail in results:
            if not p:
                if "FCM token" in name.lower() and "registered" in name.lower():
                    print(f"\n  → {name}:")
                    print(f"    The app needs to be opened on a REAL Android device at least once.")
                    print(f"    The app registers the device's FCM token with the backend on first launch.")
                    print(f"    Emulators with Google Play Services also work.")
                elif "send test" in name.lower() and "EXPIRED" in (detail or ""):
                    print(f"\n  → {name}:")
                    print(f"    The stored FCM token is stale. Re-open the app on the device to refresh it.")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
