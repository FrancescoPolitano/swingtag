"""Unit tests for handler.py."""
import json
import logging

from swingtag import handler
from swingtag.settings import Settings


class FakePublisher:
    def __init__(self, fail_on=()):
        self.settings = Settings(bucket="b", source_prefix="source/", public_prefix="public/",
                                 config_key="config/theme.json", public_base_url="https://d1",
                                 distribution_id="", queue_url="q", token_secret="s")
        self.published: list[str] = []
        self.fail_on = set(fail_on)
        self.error_page = 0

    def publish(self, prefix):
        self.published.append(prefix)
        if prefix in self.fail_on:
            raise RuntimeError("boom")

    def publish_error_page(self):
        self.error_page += 1

    def republish_all(self):
        return 7


def message(message_id, *keys):
    body = {"Records": [{"s3": {"object": {"key": k}}} for k in keys]}
    return {"messageId": message_id, "body": json.dumps(body)}


def test_decode_keys():
    fake = FakePublisher()
    handler.handle({"Records": [message("m1", "source/Vivaio/Olivo+%C2%B7+3xk9m2p7qhv4/10+A/x.pdf")]}, fake)
    assert fake.published == ["source/Vivaio/Olivo · 3xk9m2p7qhv4/"]


def test_dedup_prefixes():
    fake = FakePublisher()
    records = [message(f"m{i}", f"source/C/A+%C2%B7+abcdefghijkm/10+E/f{i}.pdf") for i in range(10)]
    handler.handle({"Records": records}, fake)
    assert fake.published == ["source/C/A · abcdefghijkm/"]


def test_test_event_skipped():
    fake = FakePublisher()
    result = handler.handle({"Records": [{"messageId": "m1", "body": json.dumps({"Event": "s3:TestEvent"})}]}, fake)
    assert fake.published == [] and result == {"batchItemFailures": []}


def test_garbage_skipped():
    fake = FakePublisher()
    result = handler.handle({"Records": [{"messageId": "m1", "body": "not json"}]}, fake)
    assert fake.published == [] and result == {"batchItemFailures": []}


def test_partial_failure():
    fake = FakePublisher(fail_on={"source/C/B · bcdefghijkmn/"})
    result = handler.handle({"Records": [
        message("ok1", "source/C/A+%C2%B7+abcdefghijkm/10+E/x.pdf"),
        message("bad1", "source/C/B+%C2%B7+bcdefghijkmn/10+E/x.pdf"),
        message("bad2", "source/C/B+%C2%B7+bcdefghijkmn/20+F/y.pdf"),
    ]}, fake)
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad1"}, {"itemIdentifier": "bad2"}]}


def test_direct_republish():
    fake = FakePublisher()
    assert handler.handle({"action": "republish_all"}, fake) == {"items": 7}
    assert fake.error_page == 1


def test_logging_level():
    root = logging.getLogger()
    extra = logging.StreamHandler()
    previous = root.level
    root.addHandler(extra)
    try:
        root.setLevel(logging.WARNING)
        handler.configure_logging("INFO")
        assert root.level == logging.INFO
    finally:
        root.removeHandler(extra)
        root.setLevel(previous)


def test_out_of_convention_key(caplog):
    fake = FakePublisher()
    with caplog.at_level(logging.WARNING):
        handler.handle({"Records": [message("m1", "source/readme.pdf")]}, fake)
    assert fake.published == []
    assert any("key outside convention" in r.getMessage() for r in caplog.records)


def test_encoded_plus_in_key():
    """a literal + in a name arrives as %2B and must not become a space."""
    fake = FakePublisher()
    handler.handle({"Records": [message("m1", "source/C/C%2B%2B+guide+%C2%B7+abcdefghijkm/10+E/x.pdf")]}, fake)
    assert fake.published == ["source/C/C++ guide · abcdefghijkm/"]
