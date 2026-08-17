"""One place that decides how to reach Elasticsearch.

Three call sites used to build the connection themselves — the health probe in
``backend/app/api/endpoints/system.py``, the indexing path in
``shared/tasks/pipeline.py`` and the tenant-deletion saga in
``shared/tasks/maintenance.py`` — and all three hardcoded the same two
mistakes.

**The scheme was a literal ``https://``.** The development stack sets
``xpack.security.enabled=true`` and nothing else, which leaves
``xpack.security.http.ssl.enabled`` at its default of ``false``: Elasticsearch
serves plaintext HTTP and authenticates with Basic. Setting the flag explicitly
also suppresses the image's security auto-configuration, so no certificate is
ever generated. The comments claiming a self-signed certificate described a
stack that does not exist. Measured against the running container:

    http  + basic_auth -> ping() True
    https + basic_auth -> ping() False

``AsyncElasticsearch.ping()`` reports transport failures by returning ``False``
rather than raising, so this never surfaced as an error anywhere — it surfaced
as ``/system/health`` reporting ``elasticsearch: degraded`` and as every
document silently failing to index.

**The password was in the URL.** ``https://elastic:<pw>@host:9200`` puts a live
credential in the netloc, which is the part that reaches logs, exception
messages and — with ``ElasticsearchInstrumentor`` active in
``shared/utils/worker_tracing.py`` — span attributes. ``basic_auth=`` carries it
in a header instead.

``ES_USE_TLS`` defaults to ``True`` so a deployment that says nothing gets the
safe behaviour; the development stack opts out in ``.env.example``, visibly.
"""

from typing import Optional

from shared.config import settings


def es_url() -> str:
    """The Elasticsearch base URL, scheme included."""
    scheme = "https" if settings.ES_USE_TLS else "http"
    return f"{scheme}://{settings.ES_HOST}:{settings.ES_PORT}"


def make_es_client():
    """An ``AsyncElasticsearch`` configured for this deployment.

    Imported lazily, as every existing call site did: the API image installs
    the client but a minimal install without Elasticsearch should not pay for
    the import at module scope.
    """
    from elasticsearch import AsyncElasticsearch

    kwargs = {"basic_auth": (settings.ES_USER or "elastic", settings.ES_PASSWORD)}
    if settings.ES_USE_TLS:
        # Only meaningful over TLS. Passing it on a plain-HTTP node is accepted
        # by elasticsearch-py 8.12 and ignored, but it reads as though the
        # connection were encrypted, which is the confusion this module exists
        # to remove.
        kwargs["verify_certs"] = settings.ES_VERIFY_CERTS
    return AsyncElasticsearch(es_url(), **kwargs)


def make_es_client_if_configured() -> Optional[object]:
    """The client, or ``None`` when this deployment has no Elasticsearch.

    Elasticsearch is optional. ``ES_PASSWORD`` is the marker the callers
    already used for "configured", and it stays the marker here so that a
    minimal install does not report a component it was never given.
    """
    if not settings.ES_PASSWORD:
        return None
    return make_es_client()
