import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("JARVIS_NO_WEBENGINE", "1")

from jarvis.config import AppConfig  # noqa: E402
from jarvis.data import generate_synthetic_candles  # noqa: E402
from jarvis.storage import Database  # noqa: E402

T0 = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def cfg():
    return AppConfig()


@pytest.fixture(scope="session")
def candles():
    return generate_synthetic_candles(3000, "M5", seed=11)


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()
