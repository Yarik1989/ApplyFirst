import os
import tempfile

import pytest

from backend import config as cfg_module


@pytest.fixture
def tmp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.db")
        monkeypatch.setattr(cfg_module.settings, "database_path", path)
        yield path


@pytest.mark.asyncio
async def test_seen_and_alert_lifecycle(tmp_db):
    from backend import database as db

    await db.init_db()

    assert await db.is_seen("abc") is False
    await db.mark_seen("abc", "indeed", "RN", "Kaiser", "https://x/1")
    assert await db.is_seen("abc") is True

    alert_id = await db.record_alert("abc")
    assert isinstance(alert_id, int) and alert_id > 0

    assert await db.applies_today_count() == 0
    await db.set_alert_status(alert_id, "approved")
    assert await db.applies_today_count() == 1
