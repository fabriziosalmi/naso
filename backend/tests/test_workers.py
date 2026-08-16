from unittest.mock import MagicMock, patch

import pytest

# patch() resolves "shared.tasks.pipeline.settings" by attribute lookup on the
# package, and importing `shared.tasks` alone does not bind the submodule.
import shared.tasks.pipeline  # noqa: F401


@pytest.fixture
def mock_settings():
    with patch("shared.tasks.pipeline.settings") as mock:
        mock.ES_HOST = "dummy-es"
        mock.ES_PORT = 9200
        mock.MINIO_ENDPOINT = "dummy-minio"
        mock.MINIO_ACCESS_KEY = "dummy"
        mock.MINIO_SECRET_KEY = "dummy"
        mock.ES_PASSWORD = None
        mock.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        yield mock


def test_process_potential_leak_degraded(mock_settings):
    """
    Test that the Celery task graceful degradation logic works
    when external services raise exceptions.
    """
    from shared.tasks.pipeline import process_potential_leak

    hit_data = {
        "source": "test_script",
        "content_snippet": "simulated_breach",
        "metadata": {"test": True},
        "tenant_id": "test-tenant",
        "id": "test-id",
    }

    # process_potential_leak builds its own loop with asyncio.new_event_loop()
    # and drives it with run_until_complete. This test used to patch
    # asyncio.run, which the task stopped calling, so the mock never applied
    # and the real pipeline ran against the configured Postgres host.
    def _swallow(coro):
        coro.close()  # the coroutine is never awaited; closing it avoids a RuntimeWarning
        return 50

    mock_loop = MagicMock()
    mock_loop.run_until_complete.side_effect = _swallow

    with patch("shared.tasks.pipeline.asyncio.new_event_loop", return_value=mock_loop) as mock_new_loop:
        result = process_potential_leak(hit_data, "raw_content_for_hash")

        assert result == 50
        mock_new_loop.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()
        mock_loop.close.assert_called_once()
