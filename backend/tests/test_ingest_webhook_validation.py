"""Input validation on POST /leaks/ingest/webhook.

SECURITY.md names "the ingest webhook and the Celery task boundary" as in
scope. The route parsed its body with orjson and then reached into the result
with `.get()`, which answers "is this JSON" and nothing about the shape. Five
syntactically valid bodies each reached `metadata["tenant_id"] = ...` and
raised, for a 500:

    {"metadata": null}       TypeError: 'NoneType' object does not support ...
    {"metadata": "string"}   TypeError: 'str' object does not support ...
    {"metadata": 123}        TypeError: 'int' object does not support ...
    [1, 2, 3]                AttributeError: 'list' object has no attribute 'get'
    "a string"               AttributeError: 'str' object has no attribute 'get'

`{"metadata": null}` is the one worth dwelling on: the handler wrote
`payload.get("metadata", {})`, which looks defensive but is not — an explicit
null *finds* the key, so the `{}` fallback never applies and None goes
straight through. The model declared `dict | None`, so it would not have
caught it either.

These are 422 now. The bodies below are the ones that used to crash, so this
file fails against the unfixed handler rather than merely describing it.
"""

import uuid

import pytest
import pytest_asyncio

from shared.core.security import get_password_hash
from shared.models import Tenant, User


@pytest_asyncio.fixture
async def operator(db):
    tenant = Tenant(id=str(uuid.uuid4()), name=f"acme-{uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    user = User(
        id=str(uuid.uuid4()),
        email=f"op-{uuid.uuid4().hex[:6]}@naso.example.com",
        hashed_password=get_password_hash("Str0ng&Pass!"),
        tenant_id=tenant.id,
        role="analyst",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _auth(client, user):
    r = await client.post("/auth/login", data={"username": user.email, "password": "Str0ng&Pass!"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}


# Every one of these produced an unhandled exception before the fix.
CRASHED_BEFORE = [
    pytest.param('{"source":"s","content":"c","metadata":null}', id="metadata-is-null"),
    pytest.param('{"source":"s","content":"c","metadata":"nope"}', id="metadata-is-a-string"),
    pytest.param('{"source":"s","content":"c","metadata":123}', id="metadata-is-an-int"),
    pytest.param('{"source":"s","content":"c","metadata":[1,2]}', id="metadata-is-a-list"),
    pytest.param("[1,2,3]", id="body-is-a-list"),
    pytest.param('"a string"', id="body-is-a-string"),
    pytest.param("42", id="body-is-a-number"),
    pytest.param("null", id="body-is-null"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", CRASHED_BEFORE)
async def test_a_body_that_does_not_fit_is_rejected_not_crashed(client, operator, body):
    headers = await _auth(client, operator)
    r = await client.post("/leaks/ingest/webhook", content=body, headers=headers)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"
    # A 500 here would mean the handler ran and threw. Assert on the absence of
    # the generic crash body too, so a future global handler that answers 422
    # cannot make this pass while still crashing.
    assert "critical system error" not in r.text.lower()


@pytest.mark.asyncio
async def test_unparseable_bytes_still_answer_400(client, operator):
    """The pre-existing contract for malformed JSON does not move."""
    headers = await _auth(client, operator)
    r = await client.post("/leaks/ingest/webhook", content="{not json at all", headers=headers)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_the_route_is_still_closed_to_anonymous_callers(client, operator):
    client.cookies.clear()
    r = await client.post(
        "/leaks/ingest/webhook",
        content='{"source":"s","content":"c"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_omitting_source_and_content_still_works(client, operator, monkeypatch):
    """The previous handler defaulted both. Wiring the model must not break that.

    RabbitMQ is not reachable in the suite, so publishing is stubbed: what is
    under test is that validation lets the body through and the handler builds
    its envelope, not that aio_pika works.
    """
    published = {}

    class _FakeExchange:
        async def publish(self, message, routing_key):
            published["routing_key"] = routing_key
            published["body"] = message.body

    class _FakeChannel:
        async def get_exchange(self, name, ensure=False):
            return _FakeExchange()

        async def close(self):
            published["closed"] = True

    from app.api.endpoints import leaks as leaks_module

    async def _fake_get_channel():
        return _FakeChannel()

    monkeypatch.setattr(leaks_module.rabbitmq_pool, "get_channel", _fake_get_channel)

    headers = await _auth(client, operator)
    r = await client.post("/leaks/ingest/webhook", content="{}", headers=headers)
    assert r.status_code == 202, r.text
    assert published, "nothing was published"


@pytest.mark.asyncio
async def test_the_tenant_id_is_the_callers_and_not_the_bodys(client, operator, monkeypatch):
    """metadata is caller-supplied, and the tenant id is stamped over it.

    Worth pinning: the handler writes `metadata["tenant_id"]` into a dict that
    came from the request, so a body naming someone else's tenant must not
    survive into the Celery envelope.
    """
    import orjson

    published = {}

    class _FakeExchange:
        async def publish(self, message, routing_key):
            published["body"] = message.body

    class _FakeChannel:
        async def get_exchange(self, name, ensure=False):
            return _FakeExchange()

        async def close(self):
            published["closed"] = True

    from app.api.endpoints import leaks as leaks_module

    async def _fake_get_channel():
        return _FakeChannel()

    monkeypatch.setattr(leaks_module.rabbitmq_pool, "get_channel", _fake_get_channel)

    headers = await _auth(client, operator)
    r = await client.post(
        "/leaks/ingest/webhook",
        content='{"source":"s","content":"c","metadata":{"tenant_id":"00000000-dead-beef-0000-000000000000"}}',
        headers=headers,
    )
    assert r.status_code == 202, r.text

    envelope = orjson.loads(published["body"])
    hit_data = envelope[0][0]
    assert hit_data["metadata_json"]["tenant_id"] == operator.tenant_id
    assert hit_data["tenant_id"] == operator.tenant_id
