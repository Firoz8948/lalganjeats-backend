from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth import service


def test_login_requires_explicit_legal_acceptance():
    user = SimpleNamespace(
        legal_terms_version=None,
        legal_terms_accepted_at=None,
    )
    with pytest.raises(HTTPException) as exc:
        service.record_legal_acceptance(
            user,
            accepted=False,
            version="2026-08-17",
        )
    assert exc.value.status_code == 400


def test_legal_acceptance_records_version_and_timestamp():
    user = SimpleNamespace(
        legal_terms_version=None,
        legal_terms_accepted_at=None,
    )
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    service.record_legal_acceptance(
        user,
        accepted=True,
        version="2026-08-17",
        now=now,
    )
    assert user.legal_terms_version == "2026-08-17"
    assert user.legal_terms_accepted_at == now
