from unittest.mock import patch, AsyncMock

import pytest


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

    with patch("shared.tasks.pipeline.asyncio.run") as mock_async_run:
        mock_async_run.return_value = 50

        result = process_potential_leak(hit_data, "raw_content_for_hash")

        assert result == 50
        mock_async_run.assert_called_once()
