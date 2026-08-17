"""Tests for the Elasticsearch client factory.

Three call sites used to build the connection inline, all three hardcoding
``https://elastic:<password>@host:9200``. The development stack serves plaintext
HTTP — ``xpack.security.enabled=true`` alone leaves
``xpack.security.http.ssl.enabled`` at false and suppresses the image's
security auto-configuration — so every call failed, and
``AsyncElasticsearch.ping()`` reports transport failures by returning ``False``
rather than raising, which is why nothing ever logged a stack trace.

Both assertions below fail against that code:

  * ``test_scheme_follows_the_setting`` — the URL was never http.
  * ``test_password_is_not_in_the_url`` — the password was always in the netloc,
    which is the part that reaches logs and, with ``ElasticsearchInstrumentor``
    active, span attributes.
"""

import pytest
from shared.core import es_client


@pytest.fixture
def es_settings(monkeypatch):
    """Point the factory at a known host with a known credential."""
    monkeypatch.setattr(es_client.settings, "ES_HOST", "elasticsearch", raising=False)
    monkeypatch.setattr(es_client.settings, "ES_PORT", 9200, raising=False)
    monkeypatch.setattr(es_client.settings, "ES_USER", "elastic", raising=False)
    monkeypatch.setattr(es_client.settings, "ES_PASSWORD", "s3cret-pw", raising=False)
    monkeypatch.setattr(es_client.settings, "ES_USE_TLS", True, raising=False)
    monkeypatch.setattr(es_client.settings, "ES_VERIFY_CERTS", True, raising=False)
    return monkeypatch


def test_scheme_follows_the_setting(es_settings):
    assert es_client.es_url() == "https://elasticsearch:9200"
    es_settings.setattr(es_client.settings, "ES_USE_TLS", False)
    assert es_client.es_url() == "http://elasticsearch:9200"


def test_tls_is_the_default():
    # A deployment that configures nothing must not silently downgrade. This
    # reads the class default rather than the live settings object, which the
    # container's .env has already opted out of.
    from shared.config import Settings

    assert Settings.model_fields["ES_USE_TLS"].default is True
    assert Settings.model_fields["ES_VERIFY_CERTS"].default is True


def test_password_is_not_in_the_url(es_settings):
    assert "s3cret-pw" not in es_client.es_url()
    client = es_client.make_es_client()
    try:
        rendered = [str(node) for node in client.transport.node_pool.all()]
        assert rendered, "the client exposed no nodes to inspect"
        assert not any("s3cret-pw" in node for node in rendered)
    finally:
        # Constructed, never connected; closing releases the transport.
        del client


def test_verify_certs_is_only_passed_when_tls_is_on(es_settings):
    captured = {}

    class FakeClient:
        def __init__(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs

    import elasticsearch

    es_settings.setattr(elasticsearch, "AsyncElasticsearch", FakeClient)

    es_client.make_es_client()
    assert captured["kwargs"]["basic_auth"] == ("elastic", "s3cret-pw")
    assert captured["kwargs"]["verify_certs"] is True

    es_settings.setattr(es_client.settings, "ES_USE_TLS", False)
    captured.clear()
    es_client.make_es_client()
    assert captured["url"] == "http://elasticsearch:9200"
    # Meaningless over plain HTTP, and misleading to pass: it reads as though
    # the connection were encrypted.
    assert "verify_certs" not in captured["kwargs"]


def test_no_source_file_builds_an_elasticsearch_url_by_hand():
    """The one assertion here that fails against the pristine code.

    Everything else in this file tests a module that did not exist before, so it
    could only ever be green. This walks the tree instead and pins the property
    that was violated: a credential interpolated into a URL. It fails on
    ``c912256`` at three sites — the health probe, the indexing path and the
    tenant-deletion saga.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders = []
    for directory in ("shared", "backend", "cli"):
        for path in (root / directory).rglob("*.py"):
            if "__pycache__" in path.parts or path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "ES_PASSWORD}@" in text or "elastic:{" in text:
                offenders.append(str(path.relative_to(root)))
    assert not offenders, f"credential interpolated into an Elasticsearch URL: {offenders}"


def test_unconfigured_deployment_gets_no_client(es_settings):
    es_settings.setattr(es_client.settings, "ES_PASSWORD", None)
    assert es_client.make_es_client_if_configured() is None


def test_configured_deployment_gets_a_client(es_settings):
    assert es_client.make_es_client_if_configured() is not None
